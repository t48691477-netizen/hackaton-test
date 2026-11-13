/**
 * Демо-сессия на одну вкладку.
 *
 * sessionStorage выбран намеренно: новая вкладка не наследует вход и снова
 * просит ключ. Это ближе к требованию «при открытии новой вкладки запрашивается
 * ключ», чем localStorage. В production сессию выдаёт сервер в HttpOnly
 * Secure SameSite-cookie; клиентский sessionStorage — только демо.
 */

import { isRole, type Role } from './roles';

export const SESSION_STORAGE_KEY = 'promscan:session:v1';
export const SESSION_CHANGED_EVENT = 'promscan:session-changed';

export interface Session {
  accountId: string;
  fullName: string;
  email: string;
  role: Role;
  issuedAt: string;
}

function storageOrNull(): Storage | null {
  return typeof window === 'undefined' ? null : window.sessionStorage;
}

export function getStoredSession(
  storage: Storage | null = storageOrNull(),
): Session | null {
  if (!storage) {
    return null;
  }

  try {
    const raw = storage.getItem(SESSION_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);

    if (!parsed || typeof parsed !== 'object') {
      return null;
    }

    const session = parsed as Partial<Session>;

    if (
      typeof session.accountId !== 'string' ||
      typeof session.fullName !== 'string' ||
      typeof session.email !== 'string' ||
      !isRole(session.role) ||
      typeof session.issuedAt !== 'string'
    ) {
      return null;
    }

    return {
      accountId: session.accountId,
      fullName: session.fullName,
      email: session.email,
      role: session.role,
      issuedAt: session.issuedAt,
    };
  } catch {
    return null;
  }
}

export function setStoredSession(session: Session): void {
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session));
    window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
  } catch {
    // Не роняем приложение из-за недоступного storage.
  }
}

export function clearStoredSession(): void {
  try {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
  } catch {
    // ignore
  }
}

export function getSessionRole(
  storage: Storage | null = storageOrNull(),
): Role | null {
  return getStoredSession(storage)?.role ?? null;
}
