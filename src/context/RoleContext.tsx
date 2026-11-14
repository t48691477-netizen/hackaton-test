import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  clearStoredSession,
  getStoredSession,
  SESSION_CHANGED_EVENT,
  SESSION_STORAGE_KEY,
  setStoredSession,
  type Session,
} from '../lib/session';
import type { Role } from '../lib/roles';

interface RoleContextValue {
  role: Role | null;
  session: Session | null;
  login: (session: Session) => void;
  clearRole: () => void;
  refreshRole: () => void;
}

const RoleContext = createContext<RoleContextValue | undefined>(undefined);

interface RoleProviderProps {
  children: ReactNode;
  /**
   * Удобно для тестов и SSR: если передан, сессия не читается из storage.
   * В реальном приложении sessionStorage очищается при закрытии вкладки,
   * поэтому новая вкладка снова просит ключ.
   */
  initialRole?: Role | null;
}

function testSession(role: Role): Session {
  return {
    accountId: `test-${role}`,
    fullName: role === 'director' ? 'Генеральный директор' : 'Тестовый сотрудник',
    email: `${role}@promscan.example`,
    role,
    issuedAt: '2026-11-13T09:00:00Z',
  };
}

export function RoleProvider({ children, initialRole }: RoleProviderProps) {
  const [session, setSession] = useState<Session | null>(() => {
    if (initialRole !== undefined) {
      return initialRole ? testSession(initialRole) : null;
    }

    return getStoredSession();
  });

  const refreshRole = useCallback(() => {
    setSession(getStoredSession());
  }, []);

  useEffect(() => {
    const handleStorage = (event: StorageEvent) => {
      if (event.key === SESSION_STORAGE_KEY || event.key === null) {
        refreshRole();
      }
    };

    const handleFocus = () => refreshRole();
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        refreshRole();
      }
    };

    window.addEventListener('storage', handleStorage);
    window.addEventListener(SESSION_CHANGED_EVENT, refreshRole);
    window.addEventListener('focus', handleFocus);
    document.addEventListener('visibilitychange', handleVisibility);

    return () => {
      window.removeEventListener('storage', handleStorage);
      window.removeEventListener(SESSION_CHANGED_EVENT, refreshRole);
      window.removeEventListener('focus', handleFocus);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [refreshRole]);

  const login = useCallback((nextSession: Session) => {
    setStoredSession(nextSession);
    setSession(nextSession);
  }, []);

  const clearRole = useCallback(() => {
    clearStoredSession();
    setSession(null);
  }, []);

  const value = useMemo(
    () => ({
      role: session?.role ?? null,
      session,
      login,
      clearRole,
      refreshRole,
    }),
    [session, login, clearRole, refreshRole],
  );

  return <RoleContext.Provider value={value}>{children}</RoleContext.Provider>;
}

export function useRole(): RoleContextValue {
  const context = useContext(RoleContext);

  if (!context) {
    throw new Error('useRole должен использоваться внутри RoleProvider');
  }

  return context;
}
