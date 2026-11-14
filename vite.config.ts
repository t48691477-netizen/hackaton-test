import react from '@vitejs/plugin-react';
import basicSsl from '@vitejs/plugin-basic-ssl';
import { defineConfig } from 'vitest/config';

/**
 * Запуск в локальной сети (`npm run dev:lan` или `vite --host`) поднимает
 * HTTPS с самоподписанным сертификатом: WebCrypto (проверка ключа) и камера
 * работают только в защищённом контексте, поэтому по http://IP вход не работает.
 */
const globalProcess = (
  globalThis as {
    process?: { argv?: string[]; env?: Record<string, string | undefined> };
  }
).process;
const exposeToLan =
  Boolean(globalProcess?.argv?.includes('--host')) ||
  globalProcess?.env?.PROMSCAN_HTTPS === '1';

export default defineConfig({
  plugins: exposeToLan ? [react(), basicSsl()] : [react()],
  server: {
    host: exposeToLan ? true : '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: true,
    globals: true,
  },
});
