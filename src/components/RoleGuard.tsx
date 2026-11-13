import type { ReactNode } from 'react';
import { AccessDenied } from './AccessDenied';
import { useRole } from '../context/RoleContext';
import type { Role } from '../lib/roles';

interface RoleGuardProps {
  allow: readonly Role[];
  children: ReactNode;
}

/**
 * Дополнительный рубеж поверх скрытия пунктов меню.
 * Прямой переход по URL не должен открывать чужой раздел.
 */
export function RoleGuard({ allow, children }: RoleGuardProps) {
  const { role } = useRole();

  if (!role || !allow.includes(role)) {
    return <AccessDenied />;
  }

  return <>{children}</>;
}
