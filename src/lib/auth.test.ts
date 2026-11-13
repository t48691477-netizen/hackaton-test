import { describe, expect, it } from 'vitest';
import {
  authenticateAccessKey,
  createAccessKeyRecord,
  isValidAccessKeyFormat,
  verifyAccessKey,
} from './auth';
import { DIRECTOR_ACCOUNT } from './accessKeys';

describe('вход по 10-значному ключу', () => {
  it('принимает ключ директора и отдаёт роль', async () => {
    const session = await authenticateAccessKey('PSCDRT2345');

    expect(session).toMatchObject({
      accountId: 'director',
      role: 'director',
    });
  });

  it('принимает ключ сотрудника и нормализует регистр/пробелы', async () => {
    const session = await authenticateAccessKey(' pscdsp4826 ');

    expect(session).toMatchObject({
      accountId: 'emp-001',
      role: 'dispatcher',
      fullName: 'Иван Иванов',
    });
  });

  it('отклоняет неверный ключ', async () => {
    await expect(authenticateAccessKey('PSCXXX2345')).resolves.toBeNull();
  });

  it('отклоняет ключ неверной длины', async () => {
    await expect(authenticateAccessKey('12345')).rejects.toMatchObject({
      code: 'invalid_format',
    });
    expect(isValidAccessKeyFormat('12345')).toBe(false);
    expect(isValidAccessKeyFormat('PSCDRT2345')).toBe(true);
  });

  it('создаёт уникальные ключи и проверяет их по хешу', async () => {
    const first = await createAccessKeyRecord();
    const second = await createAccessKeyRecord();

    expect(first.accessKey).toMatch(/^[A-HJ-NP-Z2-9]{10}$/);
    expect(second.accessKey).not.toBe(first.accessKey);
    await expect(
      verifyAccessKey(first.accessKey, {
        keySalt: first.keySalt,
        keyHash: first.keyHash,
      }),
    ).resolves.toBe(true);
    await expect(
      verifyAccessKey(second.accessKey, {
        keySalt: first.keySalt,
        keyHash: first.keyHash,
      }),
    ).resolves.toBe(false);
    expect(first.keyHash).not.toContain(first.accessKey);
  });

  it('хеш директора не совпадает с открытым ключом', () => {
    expect(DIRECTOR_ACCOUNT.keyHash).not.toBe('PSCDRT2345');
    expect(DIRECTOR_ACCOUNT.keyHash).toMatch(/^[0-9a-f]{64}$/);
  });
});
