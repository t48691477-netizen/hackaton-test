/**
 * Демо-справочник сотрудников.
 *
 * Пока backend не отдаёт пользователей, этот модуль — единственный источник
 * сотрудников для страницы «Сотрудники», назначения задач и входа по ключу.
 * В нём НЕТ открытых ключей: только соль и PBKDF2-хеш. Ключ создаётся при
 * выдаче и отправляется сотруднику письмом; администратор его не видит.
 *
 * При интеграции заменяется будущими GET/POST /api/users; в отчётах хранится
 * только безопасный снимок `EmployeeRef`, без email и ключей.
 */

import type { Role } from './roles';

export type EmployeeRole = Exclude<Role, 'director'>;

export type InvitationStatus = 'not_sent' | 'queued' | 'sent' | 'failed';

export interface InvitationState {
  status: InvitationStatus;
  email: string;
  provider: 'mock' | 'smtp' | null;
  sentAt: string | null;
  error: string | null;
}

export interface Employee {
  id: string;
  fullName: string;
  email: string;
  role: EmployeeRole;
  keySalt: string;
  keyHash: string;
  keyCreatedAt: string;
  invitation: InvitationState;
}

/** Безопасный снимок сотрудника внутри Report. */
export interface EmployeeRef {
  id: string;
  full_name: string;
}

export const EMPLOYEES_STORAGE_KEY = 'promscan:employees:v2';
export const EMPLOYEES_CHANGED_EVENT = 'promscan:employees-changed';

function invitation(
  email: string,
  status: InvitationStatus = 'not_sent',
): InvitationState {
  return {
    status,
    email,
    provider: status === 'not_sent' ? null : 'mock',
    sentAt: status === 'sent' ? '2026-11-13T09:05:00Z' : null,
    error: null,
  };
}

/**
 * Сиды демо-стенда. Ключи перечислены в README, но в коде хранятся только
 * хеши; проверка выполняется через WebCrypto PBKDF2-SHA-256 (120 000 итераций).
 */
export const MOCK_EMPLOYEES: Employee[] = [
  {
    id: 'emp-001',
    fullName: 'Иван Иванов',
    email: 'i.ivanov@promscan.ru',
    role: 'dispatcher',
    keySalt: 'f78e9cd8dbbebf056337c7e427faf531',
    keyHash:
      '27bde3306f8872faf191d9f9b458a48c07ce23f944ec5e53dc53f4c98e50b900',
    keyCreatedAt: '2026-11-13T09:05:00Z',
    invitation: invitation('i.ivanov@promscan.ru'),
  },
  {
    id: 'emp-002',
    fullName: 'Анна Петрова',
    email: 'a.petrova@promscan.ru',
    role: 'engineer',
    keySalt: '9839689e19f859d3f52dbc179d8d5888',
    keyHash:
      '6a71115ad639c414db6fc86b831c5e8fc5d6c0e3752a58791a5ecaaae9a96cd9',
    keyCreatedAt: '2026-11-13T09:06:00Z',
    invitation: invitation('a.petrova@promscan.ru'),
  },
  {
    id: 'emp-003',
    fullName: 'Алексей Смирнов',
    email: 'a.smirnov@promscan.ru',
    role: 'engineer',
    keySalt: '8a23e0d8e16dc6cb624660bacd706994',
    keyHash:
      '80334076a08a34959cca19fad2a6f417aa45445fa41c32b684369eeb49aa3cfd',
    keyCreatedAt: '2026-11-13T09:07:00Z',
    invitation: invitation('a.smirnov@promscan.ru'),
  },
  {
    id: 'emp-004',
    fullName: 'Мария Кузнецова',
    email: 'm.kuznetsova@promscan.ru',
    role: 'dispatcher',
    keySalt: '84ce083d9dc97e0a3277d8e6b0ad7a37',
    keyHash:
      'ff56cfd86b17afdb038ac6556572ea80af45573a53cd09ba91a8be6931d48bcf',
    keyCreatedAt: '2026-11-13T09:08:00Z',
    invitation: invitation('m.kuznetsova@promscan.ru'),
  },
];

/** Исполнители ремонтных задач — только рабочие из сидов. */
export const MOCK_ENGINEERS: Employee[] = MOCK_EMPLOYEES.filter(
  (employee) => employee.role === 'engineer',
);

function copyJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

/**
 * Читает справочник из localStorage. Если данных нет, возвращает копию сидов.
 * Неизвестные/битые записи отбрасываются, чтобы нельзя было подсунуть роль.
 */
export function loadEmployees(
  storage: Storage | null = typeof window === 'undefined'
    ? null
    : window.localStorage,
): Employee[] {
  if (!storage) {
    return copyJson(MOCK_EMPLOYEES);
  }

  try {
    const raw = storage.getItem(EMPLOYEES_STORAGE_KEY);
    if (!raw) return copyJson(MOCK_EMPLOYEES);
    const parsed: unknown = JSON.parse(raw);

    if (!Array.isArray(parsed)) {
      return copyJson(MOCK_EMPLOYEES);
    }

    return parsed.filter(isEmployee).map((employee) => copyJson(employee));
  } catch {
    return copyJson(MOCK_EMPLOYEES);
  }
}

function isEmployee(value: unknown): value is Employee {
  if (!value || typeof value !== 'object') return false;
  const employee = value as Partial<Employee>;

  return (
    typeof employee.id === 'string' &&
    typeof employee.fullName === 'string' &&
    typeof employee.email === 'string' &&
    (employee.role === 'admin' ||
      employee.role === 'dispatcher' ||
      employee.role === 'engineer') &&
    typeof employee.keySalt === 'string' &&
    /^[0-9a-f]{32}$/i.test(employee.keySalt) &&
    typeof employee.keyHash === 'string' &&
    /^[0-9a-f]{64}$/i.test(employee.keyHash) &&
    typeof employee.keyCreatedAt === 'string' &&
    Boolean(employee.invitation)
  );
}

export function saveEmployees(
  employees: Employee[],
  storage: Storage | null = typeof window === 'undefined'
    ? null
    : window.localStorage,
): boolean {
  if (!storage) return false;

  try {
    storage.setItem(EMPLOYEES_STORAGE_KEY, JSON.stringify(employees));
  } catch {
    // Приватный режим или переполнение квоты: вызывающий код обязан
    // показать ошибку, а не делать вид, что запись сохранилась.
    return false;
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(EMPLOYEES_CHANGED_EVENT));
  }

  return true;
}

export function getEngineers(employees: Employee[] = loadEmployees()): Employee[] {
  return employees.filter((employee) => employee.role === 'engineer');
}

export function findEmployeeById(
  id: string,
  employees: Employee[] = loadEmployees(),
): Employee | null {
  return employees.find((employee) => employee.id === id) ?? null;
}

export function toEmployeeRef(employee: Employee): EmployeeRef {
  return { id: employee.id, full_name: employee.fullName };
}
