/**
 * API-клиент ПромСкан.
 *
 * Пока VITE_USE_MOCK_API !== 'false', все методы возвращают данные из
 * src/lib/inspection.ts. Для интеграции достаточно поднять backend по
 * docs/API_CONTRACT.md и выставить:
 *
 *   VITE_API_BASE_URL=http://127.0.0.1:8000
 *   VITE_USE_MOCK_API=false
 *
 * Ни один компонент не должен ходить в fetch напрямую — только через этот файл.
 */

import {
  MOCK_EQUIPMENT_LIST,
  MOCK_REPORTS,
  createMockInspection,
  createMockLiveInspection,
  type EquipmentDetail,
  type EquipmentSummary,
  type InspectionResult,
  type Report,
  type ReportStatus,
} from './inspection';
import { createAccessKeyRecord } from './accessKeys';
import {
  sendAccessKeyEmail,
  toInvitationState,
  type AccessKeyEmailResult,
} from './email';
import {
  findEmployeeById,
  isLocalEmployee,
  loadEmployees,
  saveEmployees,
  toEmployeeAccount,
  toEmployeeRef,
  type Employee,
  type EmployeeAccount,
  type EmployeeRole,
  type InvitationState,
  type InvitationStatus,
} from './employees';
import { ROLE_LABELS, type Permission, type Role } from './roles';
import { getStoredSession, type Session } from './session';

const BASE_URL = (
  import.meta.env?.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
).replace(/\/+$/, '');

export const API_CONFIG = {
  baseUrl: BASE_URL,
  useMock: (import.meta.env?.VITE_USE_MOCK_API ?? 'true') !== 'false',
} as const;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function formatApiErrorDetail(detail: unknown, status: number): string {
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => {
      if (!item || typeof item !== 'object') return [];

      const error = item as { loc?: unknown; msg?: unknown };
      if (typeof error.msg !== 'string' || !error.msg.trim()) return [];

      const location = Array.isArray(error.loc)
        ? error.loc.slice(1).filter((part) => typeof part === 'string' || typeof part === 'number').join('.')
        : '';

      return [location ? `${location}: ${error.msg}` : error.msg];
    });

    if (messages.length > 0) return messages.join('; ');
  }

  return `HTTP ${status}`;
}

// Все mock-ответы — JSON-снимки, как при настоящем HTTP-запросе.
// Изменения живут в памяти до перезагрузки страницы и не меняют исходные fixtures.
function copyJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

const mockEquipment = new Map(
  MOCK_EQUIPMENT_LIST.map((equipment) => [equipment.id, copyJson(equipment)]),
);

/**
 * Задачи/отчёты в mock-режиме переживают переход между вкладками и страницами:
 * они лежат в localStorage. Это только демо-хранилище, а не замена backend.
 * Событие нужно, чтобы открытая панель диспетчера обновлялась после действия
 * сотрудника в соседней вкладке.
 */
const MOCK_REPORTS_STORAGE_KEY = 'promscan:mock-reports:v2';
const MOCK_REPORTS_EVENT = 'promscan:mock-reports-changed';

function loadMockReports(): Report[] {
  if (typeof window === 'undefined') {
    return copyJson(MOCK_REPORTS);
  }

  try {
    const raw = window.localStorage.getItem(MOCK_REPORTS_STORAGE_KEY);
    if (!raw) return copyJson(MOCK_REPORTS);
    const parsed: unknown = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as Report[]) : copyJson(MOCK_REPORTS);
  } catch {
    return copyJson(MOCK_REPORTS);
  }
}

const mockReports = loadMockReports();
let mockSequence = 0;

function refreshMockReports(): Report[] {
  const stored = loadMockReports();
  mockReports.splice(0, mockReports.length, ...stored);
  return mockReports;
}

function persistMockReports(): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.setItem(
      MOCK_REPORTS_STORAGE_KEY,
      JSON.stringify(mockReports),
    );
  } catch {
    // Приватный режим/запрет storage: демо продолжит работать в памяти вкладки.
  }

  window.dispatchEvent(new Event(MOCK_REPORTS_EVENT));
}

/**
 * Подписка на изменения mock-задач в этой и соседних вкладках.
 * В real-режиме подписка не нужна: панель перечитывает данные по API.
 */
export function subscribeToReportChanges(listener: () => void): () => void {
  if (!API_CONFIG.useMock || typeof window === 'undefined') {
    return () => {};
  }

  const handleChange = () => listener();
  const handleStorage = (event: StorageEvent) => {
    if (event.key === null || event.key === MOCK_REPORTS_STORAGE_KEY) {
      listener();
    }
  };

  window.addEventListener(MOCK_REPORTS_EVENT, handleChange);
  window.addEventListener('storage', handleStorage);

  return () => {
    window.removeEventListener(MOCK_REPORTS_EVENT, handleChange);
    window.removeEventListener('storage', handleStorage);
  };
}

function getMockReport(reportId: string): Report {
  refreshMockReports();
  const report = mockReports.find((item) => item.id === reportId);

  if (!report) {
    throw new ApiError(404, 'Задача не найдена.');
  }

  return report;
}

function createMockId(prefix: string): string {
  mockSequence += 1;
  return `${prefix}-${Date.now()}-${mockSequence}`;
}

function getMockEquipment(equipmentId: string): EquipmentDetail {
  const equipment = mockEquipment.get(equipmentId);

  if (!equipment) {
    throw new ApiError(404, 'Оборудование не найдено.');
  }

  return equipment;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');
  const sessionToken = getStoredSession()?.sessionToken;
  if (sessionToken) {
    headers.set('Authorization', `Bearer ${sessionToken}`);
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;

    try {
      const payload = (await response.json()) as { detail?: unknown };
      detail = formatApiErrorDetail(payload.detail, response.status);
    } catch {
      // Тело ошибки может быть пустым или не JSON.
    }

    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function fetchEquipment(): Promise<EquipmentSummary[]> {
  if (API_CONFIG.useMock) {
    return Array.from(mockEquipment.values(), (equipment) => ({
      id: equipment.id,
      name: equipment.name,
      inventory_number: equipment.inventory_number,
      category: equipment.category,
      location: equipment.location,
      state: equipment.state,
    }));
  }

  return request<EquipmentSummary[]>('/api/equipment');
}

export async function fetchEquipmentById(
  equipmentId: string,
): Promise<EquipmentDetail> {
  if (API_CONFIG.useMock) {
    return copyJson(getMockEquipment(equipmentId));
  }

  return request<EquipmentDetail>(
    `/api/equipment/${encodeURIComponent(equipmentId)}`,
  );
}

export type EquipmentUpsert = Omit<
  EquipmentDetail,
  'id' | 'created_at' | 'updated_at'
> & { id?: string };

export async function saveEquipment(
  equipment: EquipmentUpsert,
): Promise<EquipmentDetail> {
  // EquipmentDetail тоже может прийти из формы: служебные даты не входят в upsert.
  const payload = { ...equipment };
  delete (payload as Partial<EquipmentDetail>).created_at;
  delete (payload as Partial<EquipmentDetail>).updated_at;

  if (API_CONFIG.useMock) {
    const existing = payload.id === undefined
      ? undefined
      : getMockEquipment(payload.id);
    const now = new Date().toISOString();
    const saved: EquipmentDetail = {
      ...payload,
      id: existing?.id ?? createMockId('equipment'),
      created_at: existing?.created_at ?? now,
      updated_at: now,
    };

    mockEquipment.set(saved.id, copyJson(saved));
    return copyJson(saved);
  }

  return request<EquipmentDetail>('/api/equipment', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
}

/**
 * POST /api/inspect.
 *
 * В mock-режиме возвращает демо-результат для выбранного оборудования;
 * null-кадр разрешён для демонстрационного live-цикла без камеры.
 * options.live включает сценарий исчезновения/появления зон только в mock.
 * В real-режиме отправляет обязательный кадр
 * multipart/form-data и ждёт мгновенный InspectionResult.
 */
export async function inspectImage(
  image: Blob | null,
  equipmentId: string,
  tick = 0,
  options: { live?: boolean } = {},
): Promise<InspectionResult> {
  if (API_CONFIG.useMock) {
    const createInspection = options.live ? createMockLiveInspection : createMockInspection;
    return copyJson(createInspection(tick, getMockEquipment(equipmentId)));
  }

  if (!image) {
    throw new ApiError(400, 'Не удалось получить кадр для анализа.');
  }

  const form = new FormData();
  form.append('file', image, 'frame.jpg');
  form.append('equipment_id', equipmentId);

  return request<InspectionResult>('/api/inspect', {
    method: 'POST',
    body: form,
  });
}

interface AuthLoginResponse {
  session_token: string;
  expires_at: string;
  account: {
    id: string;
    full_name: string;
    email: string;
    role: Role;
  };
}

export async function loginWithAccessKey(accessKey: string): Promise<Session | null> {
  try {
    const response = await request<AuthLoginResponse>('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_key: accessKey }),
    });

    return {
      accountId: response.account.id,
      fullName: response.account.full_name,
      email: response.account.email,
      role: response.account.role,
      issuedAt: new Date().toISOString(),
      sessionToken: response.session_token,
      expiresAt: response.expires_at,
    };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export async function logout(): Promise<void> {
  if (API_CONFIG.useMock || !getStoredSession()?.sessionToken) return;
  try {
    await request<void>('/api/auth/logout', { method: 'POST' });
  } catch {
    // The client still clears local state when the server cannot be reached.
  }
}

export type ApiInvitationProvider = 'mock' | 'resend' | 'smtp' | 'gmail' | null;

export interface ApiInvitation {
  status: InvitationStatus;
  email?: string;
  provider?: ApiInvitationProvider;
  sent_at?: string | null;
  error?: string | null;
}

/** Безопасная запись пользователя из GET/POST /api/users. */
export interface AuthAccount {
  id: string;
  full_name: string;
  email: string;
  role: Role;
  permissions?: readonly Permission[];
  invitation?: ApiInvitation | null;
  key_created_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CreateUserInput {
  fullName: string;
  email: string;
  role: EmployeeRole;
}

export interface UserMutationResponse {
  account: AuthAccount;
  invitation: ApiInvitation;
}

function employeeHeaders(init?: HeadersInit): Headers {
  const headers = new Headers(init);
  const sessionToken = getStoredSession()?.sessionToken;

  if (sessionToken) {
    headers.set('Authorization', `Bearer ${sessionToken}`);
  }

  return headers;
}

async function employeeRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  return request<T>(path, {
    ...init,
    headers: employeeHeaders(init?.headers),
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function requireRecord(value: unknown, label: string): Record<string, unknown> {
  if (!isRecord(value)) {
    throw new ApiError(502, `Ответ API содержит некорректные данные: ${label}.`);
  }
  return value;
}

function isRole(value: unknown): value is Role {
  return value === 'director' || value === 'admin' || value === 'dispatcher' || value === 'engineer';
}

function normalizeInvitation(
  accountEmail: string,
  value?: unknown,
): InvitationState {
  if (value === undefined || value === null) {
    return {
      status: 'not_sent',
      email: accountEmail,
      provider: null,
      sentAt: null,
      error: null,
    };
  }

  const invitation = requireRecord(value, 'invitation');
  const status = invitation.status ?? 'not_sent';
  if (status !== 'not_sent' && status !== 'queued' && status !== 'sent' && status !== 'failed') {
    throw new ApiError(502, 'Ответ API содержит неизвестный статус приглашения.');
  }

  const provider = invitation.provider ?? null;
  if (provider !== null && provider !== 'mock' && provider !== 'resend' && provider !== 'smtp' && provider !== 'gmail') {
    throw new ApiError(502, 'Ответ API содержит неизвестного почтового провайдера.');
  }

  const email = invitation.email;
  const sentAt = invitation.sent_at;
  const error = invitation.error;
  if (email !== undefined && email !== null && typeof email !== 'string') {
    throw new ApiError(502, 'Ответ API содержит некорректный email приглашения.');
  }
  if (sentAt !== undefined && sentAt !== null && typeof sentAt !== 'string') {
    throw new ApiError(502, 'Ответ API содержит некорректную дату приглашения.');
  }
  if (error !== undefined && error !== null && typeof error !== 'string') {
    throw new ApiError(502, 'Ответ API содержит некорректную ошибку приглашения.');
  }

  return {
    status,
    email: (typeof email === 'string' ? email.trim().toLowerCase() : '') || accountEmail,
    provider,
    sentAt: typeof sentAt === 'string' ? sentAt : null,
    error: typeof error === 'string' ? error : null,
  };
}

function isEmployeeRole(role: Role): role is EmployeeRole {
  return role !== 'director';
}

function normalizeEmployeeAccount(value: unknown): EmployeeAccount | null {
  const account = requireRecord(value, 'account');
  if (!isRole(account.role)) {
    throw new ApiError(502, 'Ответ API содержит неизвестную роль сотрудника.');
  }
  if (!isEmployeeRole(account.role)) {
    return null;
  }

  const id = account.id;
  const fullName = account.full_name;
  const email = account.email;
  const keyCreatedAt = account.key_created_at;
  if (typeof id !== 'string' || !id.trim()) {
    throw new ApiError(502, 'Ответ API содержит некорректный ID сотрудника.');
  }
  if (typeof fullName !== 'string' || !fullName.trim()) {
    throw new ApiError(502, 'Ответ API содержит некорректное имя сотрудника.');
  }
  if (typeof email !== 'string' || !email.trim()) {
    throw new ApiError(502, 'Ответ API содержит некорректный email сотрудника.');
  }
  if (keyCreatedAt !== undefined && keyCreatedAt !== null && typeof keyCreatedAt !== 'string') {
    throw new ApiError(502, 'Ответ API содержит некорректную дату ключа сотрудника.');
  }

  return {
    id,
    fullName: fullName.trim().replace(/\s+/g, ' '),
    email: email.trim().toLowerCase(),
    role: account.role,
    keyCreatedAt: typeof keyCreatedAt === 'string' && keyCreatedAt.trim()
      ? keyCreatedAt
      : null,
    invitation: normalizeInvitation(email.trim().toLowerCase(), account.invitation),
  };
}

function normalizeMutationInvitation(value: unknown): AccessKeyEmailResult {
  const invitation = requireRecord(value, 'invitation');
  const normalized = normalizeInvitation('', invitation);
  return {
    provider: normalized.provider ?? 'smtp',
    status:
      normalized.status === 'failed'
        ? 'failed'
        : normalized.status === 'sent'
          ? 'sent'
          : 'queued',
    messageId: null,
    error: normalized.error,
  };
}

function requireEmployeeAccount(account: unknown): EmployeeAccount {
  const employee = normalizeEmployeeAccount(account);
  if (!employee) {
    throw new ApiError(502, 'Ответ API вернул учётную запись директора вместо сотрудника.');
  }
  return employee;
}

export async function fetchEmployees(): Promise<EmployeeAccount[]> {
  if (API_CONFIG.useMock) {
    return loadEmployees().map((employee) => copyJson(toEmployeeAccount(employee)));
  }

  const accounts = await employeeRequest<unknown>('/api/users');
  if (!Array.isArray(accounts)) {
    throw new ApiError(502, 'Ответ API содержит некорректный список сотрудников.');
  }
  return accounts.flatMap((account) => {
    const employee = normalizeEmployeeAccount(account);
    return employee ? [employee] : [];
  });
}

export async function createEmployee(
  input: CreateUserInput,
): Promise<{ employee: EmployeeAccount; invitation: AccessKeyEmailResult }> {
  if (API_CONFIG.useMock) {
    const record = await createAccessKeyRecord();
    const email = input.email.trim().toLowerCase();
    const employee: Employee = {
      id: `emp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      fullName: input.fullName.trim().replace(/\s+/g, ' '),
      email,
      role: input.role,
      keySalt: record.keySalt,
      keyHash: record.keyHash,
      keyCreatedAt: record.keyCreatedAt,
      invitation: {
        status: 'not_sent',
        email,
        provider: null,
        sentAt: null,
        error: null,
      },
    };
    const accessKey = record.accessKey;
    const invitation = await sendAccessKeyEmail({
      to: employee.email,
      fullName: employee.fullName,
      accessKey,
      role: ROLE_LABELS[employee.role],
    });
    employee.invitation = toInvitationState(employee.email, invitation);

    if (!saveEmployees([employee, ...loadEmployees()])) {
      throw new ApiError(500, 'Не удалось сохранить нового сотрудника.');
    }

    return { employee, invitation };
  }

  const response = requireRecord(await employeeRequest<unknown>('/api/users', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      full_name: input.fullName.trim().replace(/\s+/g, ' '),
      email: input.email.trim().toLowerCase(),
      role: input.role,
    }),
  }), 'результат создания сотрудника');

  return {
    employee: requireEmployeeAccount(response.account),
    invitation: normalizeMutationInvitation(response.invitation),
  };
}

export async function reissueEmployee(
  employeeId: string,
): Promise<{ employee: EmployeeAccount; invitation: AccessKeyEmailResult }> {
  if (API_CONFIG.useMock) {
    const employee = findEmployeeById(employeeId);
    if (!employee) throw new ApiError(404, 'Сотрудник не найден.');
    if (!isLocalEmployee(employee)) {
      throw new ApiError(409, 'Для локального сотрудника недоступен перевыпуск ключа.');
    }

    const record = await createAccessKeyRecord();
    const nextEmployee: Employee = {
      ...employee,
      keySalt: record.keySalt,
      keyHash: record.keyHash,
      keyCreatedAt: record.keyCreatedAt,
      invitation: {
        status: 'not_sent',
        email: employee.email,
        provider: null,
        sentAt: null,
        error: null,
      },
    };
    const invitation = await sendAccessKeyEmail({
      to: nextEmployee.email,
      fullName: nextEmployee.fullName,
      accessKey: record.accessKey,
      role: ROLE_LABELS[nextEmployee.role],
    });
    nextEmployee.invitation = toInvitationState(nextEmployee.email, invitation);

    if (!saveEmployees(loadEmployees().map((item) =>
      item.id === nextEmployee.id ? nextEmployee : item,
    ))) {
      throw new ApiError(500, 'Не удалось сохранить новый ключ сотрудника.');
    }

    return { employee: nextEmployee, invitation };
  }

  const response = requireRecord(await employeeRequest<unknown>(
    `/api/users/${encodeURIComponent(employeeId)}/access`,
    { method: 'POST' },
  ), 'результат перевыпуска ключа');

  return {
    employee: requireEmployeeAccount(response.account),
    invitation: normalizeMutationInvitation(response.invitation),
  };
}

export async function deleteEmployee(employeeId: string): Promise<void> {
  if (API_CONFIG.useMock) {
    const employees = loadEmployees();
    if (!employees.some((employee) => employee.id === employeeId)) {
      throw new ApiError(404, 'Сотрудник не найден.');
    }

    if (!saveEmployees(employees.filter((employee) => employee.id !== employeeId))) {
      throw new ApiError(500, 'Не удалось сохранить изменения в справочнике сотрудников.');
    }
    return;
  }

  await employeeRequest<void>(`/api/users/${encodeURIComponent(employeeId)}`, {
    method: 'DELETE',
  });
}

export async function fetchReports(
  status?: ReportStatus,
): Promise<Report[]> {
  if (API_CONFIG.useMock) {
    refreshMockReports();
    return copyJson(status
      ? mockReports.filter((report) => report.status === status)
      : mockReports);
  }

  const query = status ? `?status=${encodeURIComponent(status)}` : '';
  return request<Report[]>(`/api/reports${query}`);
}

/** Карточка задачи для мобильного экрана сотрудника. */
export async function fetchReportById(reportId: string): Promise<Report> {
  if (API_CONFIG.useMock) {
    return copyJson(getMockReport(reportId));
  }

  return request<Report>(`/api/reports/${encodeURIComponent(reportId)}`);
}

export interface CreateReportInput {
  equipmentId: string;
  inspectionId: string;
  status: ReportStatus;
  comment?: string;
  photo?: Blob | null;
  result: InspectionResult;
  /** Кому передаётся задача. В real-режиме backend проверяет сотрудника. */
  assigneeId?: string | null;
}

export async function createReport({
  equipmentId,
  inspectionId,
  status,
  comment = '',
  photo,
  result,
  assigneeId = null,
}: CreateReportInput): Promise<Report> {
  if (API_CONFIG.useMock) {
    getMockEquipment(equipmentId);
    refreshMockReports();
    const employee = assigneeId
      ? findEmployeeById(assigneeId, loadEmployees())
      : null;

    if (assigneeId && !employee) {
      throw new ApiError(404, 'Сотрудник не найден.');
    }

    const now = new Date().toISOString();

    const report: Report = {
      id: createMockId('report'),
      equipment_id: equipmentId,
      inspection_id: inspectionId,
      status,
      comment,
      photo_url: null, // В mock-режиме файл не загружается и URL не выдумывается.
      result,
      assignee: employee ? toEmployeeRef(employee) : null,
      started_at: status === 'open' ? null : now,
      completed_at: status === 'closed' ? now : null,
      repair_comment: null,
      created_at: now,
      updated_at: now,
    };

    mockReports.unshift(copyJson(report));
    persistMockReports();
    return copyJson(report);
  }

  const form = new FormData();
  form.append('equipment_id', equipmentId);
  form.append('inspection_id', inspectionId);
  form.append('status', status);
  form.append('comment', comment);
  form.append('payload', JSON.stringify(result));

  if (assigneeId) {
    form.append('assignee_id', assigneeId);
  }

  if (photo) {
    form.append('photo', photo, 'report.jpg');
  }

  return request<Report>('/api/reports', {
    method: 'POST',
    body: form,
  });
}

/**
 * Переход задачи: open → in_progress → closed.
 * В real-режиме сотрудник определяется серверной сессией, а не телом запроса.
 */
export async function updateReportStatus(
  reportId: string,
  status: Exclude<ReportStatus, 'open'>,
  comment?: string,
): Promise<Report> {
  if (API_CONFIG.useMock) {
    const report = getMockReport(reportId);

    if (status === report.status) {
      return copyJson(report);
    }

    if (status === 'in_progress' && report.status !== 'open') {
      throw new ApiError(409, 'Начать можно только назначенную задачу.');
    }

    if (status === 'closed' && report.status !== 'in_progress') {
      throw new ApiError(409, 'Завершить можно только задачу в работе.');
    }

    if (!report.assignee) {
      throw new ApiError(409, 'Сначала назначьте задачу сотруднику.');
    }

    const now = new Date().toISOString();
    report.status = status;
    report.updated_at = now;

    if (status === 'in_progress') {
      report.started_at = report.started_at ?? now;
    }

    if (status === 'closed') {
      report.started_at = report.started_at ?? now;
      report.completed_at = now;
    }

    if (comment !== undefined) {
      report.repair_comment = comment;
    }

    persistMockReports();
    return copyJson(report);
  }

  return request<Report>(
    `/api/reports/${encodeURIComponent(reportId)}/status`,
    {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, ...(comment ? { comment } : {}) }),
    },
  );
}
