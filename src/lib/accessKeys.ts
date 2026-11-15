/**
 * Ключи доступа ПромСкан — демо-заготовка.
 *
 * В реальном продукте ключ генерирует и хеширует сервер, а клиент получает
 * его один раз после создания сотрудника. Здесь те же правила выполняются
 * в браузере, чтобы показать будущий контракт:
 *   - 10 символов из безопасного алфавита (без I/O/0/1);
 *   - в хранилище попадают только соль и PBKDF2-хеш, не сам ключ;
 *   - ключ отправляется сотруднику письмом и не показывается администратору.
 *
 * Это не заменяет серверную аутентификацию: frontend-проверка нужна только
 * для автономного демо. См. README, раздел про интеграцию.
 */

import type { Role } from './roles';

export const ACCESS_KEY_LENGTH = 10;

/**
 * 32 символа: латиница без I/O и цифры 2–9. Длина алфавита кратна степени
 * двух, поэтому randomInt не даёт смещения.
 */
export const ACCESS_KEY_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';

const ACCESS_KEY_PATTERN = /^[A-HJ-NP-Z2-9]{10}$/;
const PBKDF2_ITERATIONS = 120_000;
const PBKDF2_HASH_BYTES = 32;

export interface AccessKeyRecord {
  keySalt: string;
  keyHash: string;
  keyCreatedAt: string;
}

export interface AccessAccount extends AccessKeyRecord {
  id: string;
  fullName: string;
  email: string;
  role: Role;
}

export function normalizeAccessKey(value: string): string {
  return value
    .trim()
    .toUpperCase()
    .replace(/[\s-]+/g, '');
}

export function isValidAccessKeyFormat(value: string): boolean {
  return ACCESS_KEY_PATTERN.test(normalizeAccessKey(value));
}

function bytesToHex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join(
    '',
  );
}

function hexToBytes(value: string): Uint8Array {
  if (value.length % 2 !== 0 || !/^[0-9a-f]*$/i.test(value)) {
    throw new Error('Некорректная соль ключа.');
  }

  const bytes = new Uint8Array(value.length / 2);

  for (let index = 0; index < bytes.length; index += 1) {
    bytes[index] = Number.parseInt(value.slice(index * 2, index * 2 + 2), 16);
  }

  return bytes;
}

function randomHex(bytes: number): string {
  const values = new Uint8Array(bytes);
  globalThis.crypto.getRandomValues(values);
  return bytesToHex(values);
}

function getSubtleCrypto(): SubtleCrypto {
  const subtle = globalThis.crypto?.subtle;

  if (!subtle) {
    throw new Error(
      'WebCrypto недоступен. Откройте панель по HTTPS или на localhost.',
    );
  }

  return subtle;
}

export function isWebCryptoAvailable(): boolean {
  return (
    typeof globalThis.crypto?.subtle?.deriveBits === 'function' &&
    typeof globalThis.crypto.getRandomValues === 'function'
  );
}

/**
 * PBKDF2-SHA-256. На сервере для production лучше Argon2id; параметры
 * PBKDF2 зафиксированы в контракте, чтобы интегратор мог повторить проверку.
 */
export async function hashAccessKey(
  accessKey: string,
  salt: string,
): Promise<string> {
  const subtle = getSubtleCrypto();
  const material = await subtle.importKey(
    'raw',
    new TextEncoder().encode(normalizeAccessKey(accessKey)),
    'PBKDF2',
    false,
    ['deriveBits'],
  );
  const saltBytes = hexToBytes(salt);
  const bits = await subtle.deriveBits(
    {
      name: 'PBKDF2',
      salt: saltBytes.buffer.slice(
        saltBytes.byteOffset,
        saltBytes.byteOffset + saltBytes.byteLength,
      ) as ArrayBuffer,
      iterations: PBKDF2_ITERATIONS,
      hash: 'SHA-256',
    },
    material,
    PBKDF2_HASH_BYTES * 8,
  );

  return bytesToHex(new Uint8Array(bits));
}

export async function verifyAccessKey(
  accessKey: string,
  record: Pick<AccessKeyRecord, 'keySalt' | 'keyHash'>,
): Promise<boolean> {
  if (!isValidAccessKeyFormat(accessKey)) {
    return false;
  }

  const candidate = await hashAccessKey(accessKey, record.keySalt);
  const expected = record.keyHash.toLowerCase();

  if (candidate.length !== expected.length) {
    return false;
  }

  // Побайтовое сравнение без раннего выхода. Полноценный constant-time
  // гарантирует только сервер, но не ухудшаем ситуацию на клиенте.
  let difference = 0;

  for (let index = 0; index < candidate.length; index += 1) {
    difference |= candidate.charCodeAt(index) ^ expected.charCodeAt(index);
  }

  return difference === 0;
}

/**
 * Создаёт новый ключ и запись для хранения. Возвращённый `accessKey` нельзя
 * сохранять в справочнике: он передаётся только в mock-email (демо) или
 * серверному почтовому провайдеру.
 */
export async function createAccessKeyRecord(): Promise<
  AccessKeyRecord & { accessKey: string }
> {
  const values = new Uint8Array(ACCESS_KEY_LENGTH);
  globalThis.crypto.getRandomValues(values);
  const accessKey = Array.from(
    values,
    (value) => ACCESS_KEY_ALPHABET[value % ACCESS_KEY_ALPHABET.length],
  ).join('');
  const keySalt = randomHex(16);
  const keyHash = await hashAccessKey(accessKey, keySalt);

  return {
    accessKey,
    keySalt,
    keyHash,
    keyCreatedAt: new Date().toISOString(),
  };
}

export function maskAccessKey(): string {
  return '•••••-•••••';
}

/**
 * Демо-аккаунт генерального директора. Ключ `PSCDRT2345` указан в README;
 * в коде хранится только соль и хеш. Это единственный «корневой» ключ,
 * который нельзя перевыпустить из интерфейса.
 */
export const DIRECTOR_ACCOUNT: AccessAccount = {
  id: 'director',
  fullName: 'Генеральный директор',
  email: 'director@promscan.example',
  role: 'director',
  keySalt: '2d451780e6bdb082d21ec3715c5b8a4d',
  keyHash:
    'cce6f6a2c7d0085310fbd762066d7417bc44537779a606055122a74df6539e23',
  keyCreatedAt: '2026-11-13T09:00:00Z',
};
