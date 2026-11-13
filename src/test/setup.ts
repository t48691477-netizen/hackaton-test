import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

// jsdom не даёт WebCrypto.subtle, а проверка ключей использует PBKDF2.
// В браузере это нативный API; в тестах подставляем реализацию Node.
if (!globalThis.crypto?.subtle) {
  // setup выполняется только в Vitest; используем Node-реализацию WebCrypto
  // без статического импорта, чтобы браузерная сборка не тянула node:crypto.
  const nodeCrypto = (
    globalThis as typeof globalThis & {
      process?: { getBuiltinModule?: (name: string) => unknown };
    }
  ).process?.getBuiltinModule?.('node:crypto') as
    | { webcrypto: Crypto }
    | undefined;

  if (!nodeCrypto) {
    throw new Error('Не удалось загрузить WebCrypto для тестов.');
  }

  Object.defineProperty(globalThis, 'crypto', {
    configurable: true,
    value: nodeCrypto.webcrypto,
  });
}

afterEach(() => {
  cleanup();
  localStorage.clear();
  sessionStorage.clear();
  vi.useRealTimers();
});
