export const ROLES = ['director', 'admin', 'dispatcher', 'engineer'] as const;

export type Role = (typeof ROLES)[number];

/**
 * Права роли. Это только UI-модель: сервер обязан проверять те же права
 * независимо от того, что лежит в sessionStorage.
 */
export type Permission = 'scan' | 'dispatch' | 'users';

export const ROLE_PERMISSIONS: Record<Role, readonly Permission[]> = {
  director: ['scan', 'dispatch', 'users'],
  admin: ['scan', 'dispatch', 'users'],
  dispatcher: ['scan', 'dispatch'],
  engineer: ['scan'],
};

export const ROLE_LABELS: Record<Role, string> = {
  director: 'Генеральный директор',
  admin: 'Администратор',
  dispatcher: 'Диспетчер',
  engineer: 'Рабочий',
};

export const ROLE_SHORT_LABELS: Record<Role, string> = {
  director: 'Директор',
  admin: 'Админ',
  dispatcher: 'Диспетчер',
  engineer: 'Рабочий',
};

export const ROLE_DESCRIPTIONS: Record<Role, string> = {
  director: 'Сканер, диспетчерская, сотрудники и ключи',
  admin: 'Сканер, диспетчерская и сотрудники',
  dispatcher: 'Сканер и панель дефектов',
  engineer: 'Только веб-сканер',
};

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && (ROLES as readonly string[]).includes(value);
}

export function hasPermission(
  role: Role,
  permission: Permission,
): boolean {
  return ROLE_PERMISSIONS[role].includes(permission);
}
