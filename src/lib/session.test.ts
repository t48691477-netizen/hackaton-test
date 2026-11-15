import { beforeEach, describe, expect, it } from 'vitest';
import {
  SESSION_STORAGE_KEY,
  clearStoredSession,
  getSessionRole,
  getStoredSession,
  setStoredSession,
  type Session,
} from './session';

const SESSION: Session = {
  accountId: 'emp-003',
  fullName: 'Алексей Смирнов',
  email: 'a.smirnov@promscan.ru',
  role: 'engineer',
  issuedAt: '2026-11-14T09:00:00Z',
};

function emptyStorage(): Storage {
  return {
    getItem: () => null,
    setItem: () => undefined,
    removeItem: () => undefined,
    clear: () => undefined,
    key: () => null,
    length: 0,
  } as Storage;
}

beforeEach(() => {
  sessionStorage.clear();
});

describe('сессия вкладки', () => {
  it('сохраняет и читает сессию', () => {
    setStoredSession(SESSION);

    expect(getStoredSession()).toEqual(SESSION);
    expect(getSessionRole()).toBe('engineer');
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toContain('emp-003');
  });

  it('не переносит сессию в пустое хранилище новой вкладки', () => {
    setStoredSession(SESSION);

    expect(getStoredSession(emptyStorage())).toBeNull();
    expect(getSessionRole(emptyStorage())).toBeNull();
  });

  it('отбрасывает битый JSON и неизвестную роль', () => {
    sessionStorage.setItem(SESSION_STORAGE_KEY, '{not-json');
    expect(getStoredSession()).toBeNull();

    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ ...SESSION, role: 'superuser' }),
    );
    expect(getStoredSession()).toBeNull();
  });

  it('не отдаёт сессию с неполными полями', () => {
    sessionStorage.setItem(
      SESSION_STORAGE_KEY,
      JSON.stringify({ role: 'director' }),
    );

    expect(getStoredSession()).toBeNull();
  });

  it('очищает сессию', () => {
    setStoredSession(SESSION);
    clearStoredSession();

    expect(getStoredSession()).toBeNull();
    expect(sessionStorage.getItem(SESSION_STORAGE_KEY)).toBeNull();
  });
});
