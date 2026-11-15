import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  vi.resetModules();
});

async function loadEmail(mock: 'true' | 'false') {
  vi.stubEnv('VITE_USE_MOCK_API', mock);
  vi.stubEnv('VITE_API_BASE_URL', 'https://api.test');
  vi.resetModules();
  return import('./email');
}

describe('sendAccessKeyEmail', () => {
  const input = {
    to: 'a@b.ru',
    fullName: 'Иван',
    accessKey: 'ABCDEF2345',
    role: 'Инженер',
  };

  it('в real-режиме отправляет письмо через backend, не пишет ключ в outbox', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'sent', message_id: '<1@x>' }), {
        status: 200,
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { sendAccessKeyEmail, readMockOutbox } = await loadEmail('false');

    const result = await sendAccessKeyEmail(input);

    expect(result).toMatchObject({ provider: 'smtp', status: 'sent', messageId: '<1@x>' });
    expect(fetchMock.mock.calls[0][0]).toBe('https://api.test/front/api/mail/access-key');
    expect(readMockOutbox()).toHaveLength(0);
  });

  it('возвращает failed с текстом ошибки сервера', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: 'SMTP не настроен' }), { status: 503 }),
      ),
    );
    const { sendAccessKeyEmail } = await loadEmail('false');

    const result = await sendAccessKeyEmail(input);

    expect(result).toMatchObject({ status: 'failed', error: 'SMTP не настроен' });
  });
});
