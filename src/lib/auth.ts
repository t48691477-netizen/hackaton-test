/**
 * Демо-аутентификация: вход только по 10-значному индивидуальному ключу.
 *
 * Ключ директора (демо-стенд): PSCDRT2345.
 * В коде хранится не ключ, а соль и PBKDF2-хеш; сам ключ перечислен в README,
 * потому что это публичный демо-стенд. В production проверка выполняется на
 * сервере, а ключ/пароль никогда не попадают в клиентский bundle.
 */

export {
  ACCESS_KEY_ALPHABET,
  ACCESS_KEY_LENGTH,
  DIRECTOR_ACCOUNT,
  createAccessKeyRecord,
  hashAccessKey,
  isValidAccessKeyFormat,
  maskAccessKey,
  normalizeAccessKey,
  verifyAccessKey,
} from './accessKeys';

export {
  AuthError,
  authenticateAccessKey,
  findAccountById,
  listAuthAccounts,
  type AuthAccount,
} from './access';

export { SESSION_STORAGE_KEY, type Session } from './session';
