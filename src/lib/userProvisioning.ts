/**
 * Выдача учётных записей — frontend-заготовка будущих `/api/users`.
 *
 * В демо ключ генерируется в браузере и сразу уходит в mock-email, а в
 * справочник сохраняется только соль и PBKDF2-хеш. Интерфейс администратора
 * открытый ключ не получает.
 *
 * После интеграции вся функция заменяется одним запросом к backend:
 * сервер сам генерирует ключ, сохраняет Argon2id-хеш и отправляет письмо.
 */

import { createAccessKeyRecord } from './accessKeys';
import {
  sendAccessKeyEmail,
  toInvitationState,
  type AccessKeyEmailResult,
} from './email';
import {
  findEmployeeById,
  toEmployeeAccount,
  type Employee,
  type EmployeeAccount,
  type EmployeeRole,
} from './employees';
import { API_CONFIG, createEmployee, reissueEmployee } from './api';
import { ROLE_LABELS } from './roles';

export interface NewEmployeeInput {
  fullName: string;
  email: string;
  role: EmployeeRole;
}

export interface ProvisionedEmployee {
  employee: EmployeeAccount;
  invitation: AccessKeyEmailResult;
  /** Локальный снимок нужен только mock-режиму для сохранения PBKDF2-данных. */
  localEmployee?: Employee;
}

function createEmployeeId(): string {
  const uuid = globalThis.crypto?.randomUUID?.();

  if (uuid) {
    return `emp-${uuid}`;
  }

  return `emp-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function normalizeName(value: string): string {
  return value.trim().replace(/\s+/g, ' ');
}

function normalizeEmail(value: string): string {
  return value.trim().toLowerCase();
}

function emptyInvitation(email: string): Employee['invitation'] {
  return {
    status: 'not_sent',
    email,
    provider: null,
    sentAt: null,
    error: null,
  };
}

async function deliverKey(
  employee: Employee,
  accessKey: string,
): Promise<AccessKeyEmailResult> {
  const result = await sendAccessKeyEmail({
    to: employee.email,
    fullName: employee.fullName,
    accessKey,
    role: ROLE_LABELS[employee.role],
  });

  employee.invitation = toInvitationState(employee.email, result);
  return result;
}

export async function provisionEmployee(
  input: NewEmployeeInput,
): Promise<ProvisionedEmployee> {
  if (!API_CONFIG.useMock) {
    return createEmployee(input);
  }

  const record = await createAccessKeyRecord();
  const email = normalizeEmail(input.email);
  const employee: Employee = {
    id: createEmployeeId(),
    fullName: normalizeName(input.fullName),
    email,
    role: input.role,
    keySalt: record.keySalt,
    keyHash: record.keyHash,
    keyCreatedAt: record.keyCreatedAt,
    invitation: emptyInvitation(email),
  };

  const invitation = await deliverKey(employee, record.accessKey);

  return {
    employee: toEmployeeAccount(employee),
    invitation,
    localEmployee: employee,
  };
}

export async function reissueEmployeeAccess(
  employee: EmployeeAccount,
): Promise<ProvisionedEmployee> {
  if (!API_CONFIG.useMock) {
    return reissueEmployee(employee.id);
  }

  const localEmployee = findEmployeeById(employee.id);
  if (!localEmployee) {
    throw new Error('Сотрудник не найден в демо-справочнике.');
  }

  const record = await createAccessKeyRecord();
  const nextEmployee: Employee = {
    ...localEmployee,
    keySalt: record.keySalt,
    keyHash: record.keyHash,
    keyCreatedAt: record.keyCreatedAt,
    invitation: emptyInvitation(employee.email),
  };

  const invitation = await deliverKey(nextEmployee, record.accessKey);

  return {
    employee: toEmployeeAccount(nextEmployee),
    invitation,
    localEmployee: nextEmployee,
  };
}
