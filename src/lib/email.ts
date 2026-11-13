/**
 * Заготовка отправки письма с ключом доступа.
 *
 * В production письмо отправляет только сервер: он генерирует ключ, хранит
 * его хеш и вызывает SMTP/Gmail API. Браузер не должен ни генерировать ключ,
 * ни отправлять письма, ни получать открытый ключ.
 *
 * В автономном демо письмо складывается в mock-outbox в localStorage, чтобы
 * можно было проверить вход новым сотрудником. Интерфейс администратора
 * outbox не читает и ключ не показывает. Инструкция — в README.
 *
 * Целевой контракт: `POST /api/users` и `POST /api/users/{id}/reissue-key`
 * (см. docs/API_CONTRACT.md). Сервер отвечает только статусом приглашения,
 * без `access_key`.
 */

import type { InvitationState } from './employees';

export const MOCK_OUTBOX_STORAGE_KEY = 'promscan:mail-outbox:v1';

const MAX_OUTBOX_MESSAGES = 20;

export interface AccessKeyEmailInput {
  to: string;
  fullName: string;
  accessKey: string;
  role: string;
  confirmationCode?: string;
}

export interface AccessKeyEmailResult {
  provider: 'mock' | 'smtp';
  status: 'queued' | 'sent' | 'failed';
  messageId: string | null;
  error: string | null;
}

export interface MockEmailMessage {
  id: string;
  to: string;
  fullName: string;
  role: string;
  subject: string;
  body: string;
  accessKey: string;
  confirmationCode: string;
  createdAt: string;
}

function createMessageId(): string {
  const uuid = globalThis.crypto?.randomUUID?.();
  if (uuid) return `mock-mail-${uuid}`;

  return `mock-mail-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function createConfirmationCode(): string {
  const values = new Uint32Array(1);
  globalThis.crypto.getRandomValues(values);
  return String(values[0] % 1_000_000).padStart(6, '0');
}

function getDefaultStorage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage;
  } catch {
    return null;
  }
}

/**
 * Читает демо-письма. Используется тестами и инструкцией в README,
 * но никогда — интерфейсом администратора.
 */
export function readMockOutbox(
  storage: Storage | null = getDefaultStorage(),
): MockEmailMessage[] {
  if (!storage) return [];

  try {
    const raw = storage.getItem(MOCK_OUTBOX_STORAGE_KEY);
    if (!raw) return [];
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed.filter(isMockEmailMessage);
  } catch {
    return [];
  }
}

function isMockEmailMessage(value: unknown): value is MockEmailMessage {
  if (!value || typeof value !== 'object') return false;
  const message = value as Partial<MockEmailMessage>;

  return (
    typeof message.id === 'string' &&
    typeof message.to === 'string' &&
    typeof message.fullName === 'string' &&
    typeof message.role === 'string' &&
    typeof message.subject === 'string' &&
    typeof message.body === 'string' &&
    typeof message.accessKey === 'string' &&
    typeof message.confirmationCode === 'string' &&
    typeof message.createdAt === 'string'
  );
}

function saveMockMessage(
  message: MockEmailMessage,
  storage: Storage | null = getDefaultStorage(),
): boolean {
  if (!storage) return false;

  try {
    const next = [message, ...readMockOutbox(storage)].slice(
      0,
      MAX_OUTBOX_MESSAGES,
    );
    storage.setItem(MOCK_OUTBOX_STORAGE_KEY, JSON.stringify(next));
    return true;
  } catch {
    return false;
  }
}

/**
 * Никогда не логирует `accessKey`. В демо письмо попадает в mock-outbox;
 * в production этот модуль должен вызывать backend, а не SMTP напрямую.
 */
export async function sendAccessKeyEmail(
  input: AccessKeyEmailInput,
): Promise<AccessKeyEmailResult> {
  const confirmationCode = input.confirmationCode ?? createConfirmationCode();
  const message: MockEmailMessage = {
    id: createMessageId(),
    to: input.to,
    fullName: input.fullName,
    role: input.role,
    subject: 'ПромСкан · ключ доступа к веб-панели',
    body: [
      `Здравствуйте, ${input.fullName}!`,
      '',
      `Ваш ключ доступа к веб-панели «ПромСкан»: ${input.accessKey}`,
      `Роль: ${input.role}.`,
      `Код подтверждения email: ${confirmationCode}.`,
      '',
      'Ключ действует только для вашей учётной записи. Не пересылайте его.',
    ].join('\n'),
    accessKey: input.accessKey,
    confirmationCode,
    createdAt: new Date().toISOString(),
  };

  if (!saveMockMessage(message)) {
    return {
      provider: 'mock',
      status: 'failed',
      messageId: null,
      error: 'Демо-хранилище писем недоступно в этом браузере.',
    };
  }

  return {
    provider: 'mock',
    status: 'queued',
    messageId: message.id,
    error: null,
  };
}

export function toInvitationState(
  email: string,
  result: AccessKeyEmailResult,
): InvitationState {
  return {
    status: result.status === 'failed' ? 'failed' : result.status,
    email,
    provider: result.provider,
    sentAt: result.status === 'sent' ? new Date().toISOString() : null,
    error: result.error,
  };
}
