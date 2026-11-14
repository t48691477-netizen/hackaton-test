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
  type EquipmentDetail,
  type EquipmentSummary,
  type InspectionResult,
  type Report,
  type ReportStatus,
} from './inspection';
import {
  findEmployeeById,
  loadEmployees,
  toEmployeeRef,
} from './employees';

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

  const response = await fetch(`${BASE_URL}${path}`, {
    ...init,
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
 * В real-режиме отправляет обязательный кадр
 * multipart/form-data и ждёт мгновенный InspectionResult.
 */
export async function inspectImage(
  image: Blob | null,
  equipmentId: string,
  tick = 0,
): Promise<InspectionResult> {
  if (API_CONFIG.useMock) {
    return copyJson(createMockInspection(tick, getMockEquipment(equipmentId)));
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
