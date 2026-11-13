/**
 * Демо-аутентификация по 10-значному ключу.
 *
 * Ключ проверяется локально по PBKDF2-хешу из справочника. Это заготовка
 * будущего `POST /api/auth/login`: после интеграции браузер должен отправлять
 * ключ на сервер, получать HttpOnly-сессию и больше не хранить ключ.
 */

import {
  DIRECTOR_ACCOUNT,
  isValidAccessKeyFormat,
  normalizeAccessKey,
  verifyAccessKey,
  isWebCryptoAvailable,
} from './accessKeys';
import {
  findEmployeeById,
  loadEmployees,
  type Employee,
} from './employees';
import type { Role } from './roles';
import type { Session } from './session';

export interface AuthAccount {
  accountId: string;
  fullName: string;
  email: string;
  role: Role;
  keySalt: string;
  keyHash: string;
}

export class AuthError extends Error {
  readonly code:
    | 'invalid_format'
    | 'invalid_key'
    | 'account_not_found'
    | 'crypto_unavailable';

  constructor(
    code: 'invalid_format' | 'invalid_key' | 'account_not_found' | 'crypto_unavailable',
    message: string,
  ) {
    super(message);
    this.name = 'AuthError';
    this.code = code;
  }
}

function employeeToAccount(employee: Employee): AuthAccount {
  return {
    accountId: employee.id,
    fullName: employee.fullName,
    email: employee.email,
    role: employee.role,
    keySalt: employee.keySalt,
    keyHash: employee.keyHash,
  };
}

export function listAuthAccounts(
  employees: Employee[] = loadEmployees(),
): AuthAccount[] {
  return [
    {
      accountId: DIRECTOR_ACCOUNT.id,
      fullName: DIRECTOR_ACCOUNT.fullName,
      email: DIRECTOR_ACCOUNT.email,
      role: DIRECTOR_ACCOUNT.role,
      keySalt: DIRECTOR_ACCOUNT.keySalt,
      keyHash: DIRECTOR_ACCOUNT.keyHash,
    },
    ...employees.map(employeeToAccount),
  ];
}

/**
 * Ищет аккаунт по ключу. Перебирает все записи, чтобы не раскрывать, какая
 * именно запись совпала, и возвращает null при любой ошибке.
 */
export async function authenticateAccessKey(
  rawKey: string,
  employees: Employee[] = loadEmployees(),
): Promise<Session | null> {
  const accessKey = normalizeAccessKey(rawKey);

  if (!isValidAccessKeyFormat(accessKey)) {
    throw new AuthError(
      'invalid_format',
      'Ключ должен состоять из 10 символов: латинские буквы и цифры.',
    );
  }

  // WebCrypto есть только в защищённом контексте (HTTPS или localhost).
  // Без него проверка PBKDF2 невозможна, и молча показывать «ключ не подошёл»
  // было бы неправильно — объясняем, что нужен другой адрес.
  if (!isWebCryptoAvailable()) {
    throw new AuthError(
      'crypto_unavailable',
      'Браузер отключил WebCrypto на этом адресе. Откройте панель по HTTPS или на localhost.',
    );
  }

  const accounts = listAuthAccounts(employees);
  let matched: AuthAccount | null = null;
  let matchCount = 0;

  // Не прерываемся на первом совпадении: так время проверки меньше зависит
  // от позиции аккаунта. Коллизии исключены генератором, но проверяем.
  for (const account of accounts) {
    let isMatch = false;

    try {
      isMatch = await verifyAccessKey(accessKey, account);
    } catch {
      // Одна повреждённая запись ( например, битая соль) не должна
      // блокировать вход по остальным ключам, включая директора.
      continue;
    }

    if (isMatch) {
      matchCount += 1;
      matched = account;
    }
  }

  if (matchCount !== 1 || !matched) {
    return null;
  }

  const account = matched;

  return {
    accountId: account.accountId,
    fullName: account.fullName,
    email: account.email,
    role: account.role,
    issuedAt: new Date().toISOString(),
  };
}

/**
 * Заготовка перевыпуска удалена: ключ теперь выдаёт `userProvisioning.ts`
 * и отправляет его письмом, не возвращая в интерфейс администратора.
 */

export function findAccountById(
  id: string,
  employees: Employee[] = loadEmployees(),
): AuthAccount | null {
  if (id === DIRECTOR_ACCOUNT.id) {
    return listAuthAccounts(employees)[0];
  }

  const employee = findEmployeeById(id, employees);
  return employee ? employeeToAccount(employee) : null;
}
