import { useEffect, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  ChevronRight,
  ClipboardList,
  LogOut,
  Menu,
  ScanLine,
  ShieldCheck,
  UsersRound,
  X,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useRole } from '../context/RoleContext';
import { useFocusTrap } from '../lib/useFocusTrap';
import {
  ROLE_LABELS,
  type Role,
} from '../lib/roles';
import { Brand } from './Brand';

interface NavItem {
  to: string;
  label: string;
  description: string;
  icon: LucideIcon;
  roles: readonly Role[];
}

const NAV_ITEMS: readonly NavItem[] = [
  {
    to: '/scanner',
    label: 'Веб-сканер',
    description: 'Сканирование оборудования',
    icon: ScanLine,
    roles: ['director', 'admin', 'dispatcher', 'engineer'],
  },
  {
    to: '/defects',
    label: 'Панель диспетчера',
    description: 'Дефекты и заявки',
    icon: ClipboardList,
    roles: ['director', 'admin', 'dispatcher'],
  },
  {
    to: '/users',
    label: 'Сотрудники',
    description: 'Управление доступом',
    icon: UsersRound,
    roles: ['director', 'admin'],
  },
];

const ROLE_INITIALS: Record<Role, string> = {
  director: 'ГД',
  admin: 'АД',
  dispatcher: 'ДС',
  engineer: 'РБ',
};

interface MobileNavProps {
  role: Role;
  accountName: string;
  triggerRef: { current: HTMLButtonElement | null };
  onClose: () => void;
  onLogout: () => void;
}

function MobileNav({
  role,
  accountName,
  triggerRef,
  onClose,
  onLogout,
}: MobileNavProps) {
  const visibleItems = NAV_ITEMS.filter((item) => item.roles.includes(role));
  const dialogRef = useRef<HTMLDivElement>(null);

  useFocusTrap(dialogRef, {
    initialFocus: 'nav a[href]',
    onEscape: onClose,
    restoreFocus: () => triggerRef.current?.focus(),
  });

  return (
    <div className="fixed inset-0 z-50 lg:hidden">
      <div
        onClick={onClose}
        className="absolute inset-0 bg-black/40"
        aria-hidden="true"
      />

      <div
        ref={dialogRef}
        id="mobile-navigation"
        role="dialog"
        aria-modal="true"
        aria-label="Меню навигации"
        className="absolute inset-y-0 right-0 flex w-[min(24rem,100vw)] animate-sheet-in flex-col border-l border-line bg-panel shadow-sheet"
      >
        <div className="flex h-[72px] shrink-0 items-center justify-between border-b border-line px-5">
          <Brand onClick={onClose} />
          <button
            type="button"
            onClick={onClose}
            className="btn-icon"
            aria-label="Закрыть меню"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-8">
          <p className="technical">Рабочее пространство</p>

          <nav aria-label="Мобильная навигация" className="mt-4">
            {visibleItems.map((item) => {
              const Icon = item.icon;

              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onClose}
                  className={({ isActive }) =>
                    [
                      'group flex items-center gap-4 border-b border-line py-5 transition-colors',
                      isActive ? 'text-ink' : 'text-muted hover:text-ink',
                    ].join(' ')
                  }
                >
                  {({ isActive }) => (
                    <>
                      <span
                        className={[
                          'grid h-10 w-10 shrink-0 place-items-center rounded-lg transition-colors',
                          isActive
                            ? 'bg-accent/10 text-accent'
                            : 'bg-deep text-faint group-hover:text-soft',
                        ].join(' ')}
                      >
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[15px] font-medium leading-tight">
                          {item.label}
                        </span>
                        <span className="mt-1 block text-xs leading-relaxed text-faint">
                          {item.description}
                        </span>
                      </span>
                      <ChevronRight
                        className={[
                          'h-4 w-4 shrink-0 transition-transform',
                          isActive
                            ? 'text-accent'
                            : 'text-faint group-hover:translate-x-0.5',
                        ].join(' ')}
                        aria-hidden="true"
                      />
                    </>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        <div className="shrink-0 border-t border-line p-5">
          <div className="flex items-start gap-3 rounded-xl bg-raised p-4">
            <ShieldCheck
              className="mt-0.5 h-4 w-4 shrink-0 text-ok"
              aria-hidden="true"
            />
            <div className="min-w-0">
              <p className="technical">Текущая роль</p>
              <p className="mt-1 text-sm font-medium text-ink">
                {ROLE_LABELS[role]}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-soft">
                {accountName}
              </p>
              <p className="mt-1 text-xs leading-relaxed text-faint">
                Разделы ограничены правами ключа.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="btn-secondary mt-3 w-full"
          >
            <LogOut className="h-4 w-4" aria-hidden="true" />
            Завершить сеанс
          </button>
        </div>
      </div>
    </div>
  );
}

export function Layout() {
  const { role, session, clearRole } = useRole();
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!mobileOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [mobileOpen]);

  // При расширении окна до desktop меню скрывается CSS-ом. Состояние и
  // блокировка прокрутки не должны оставаться включёнными.
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const query = window.matchMedia('(min-width: 1024px)');
    const handleChange = (event: MediaQueryListEvent) => {
      if (event.matches) {
        setMobileOpen(false);
      }
    };

    query.addEventListener?.('change', handleChange);
    return () => query.removeEventListener?.('change', handleChange);
  }, []);

  if (!role) {
    return null;
  }

  const visibleItems = NAV_ITEMS.filter((item) => item.roles.includes(role));

  return (
    <div className="flex min-h-dvh flex-col bg-canvas">
      <a href="#main" className="skip-link">
        Перейти к содержимому
      </a>

      <header className="sticky top-0 z-40 border-b border-line bg-panel">
        <div className="mx-auto flex h-[72px] w-full max-w-[1560px] items-center gap-6 px-4 sm:px-6 lg:px-10">
          <Brand />

          <nav
            aria-label="Основная навигация"
            className="ml-2 hidden items-center gap-1 lg:flex"
          >
            {visibleItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    'inline-flex h-10 items-center rounded-lg px-4 text-sm font-medium transition-colors duration-150',
                    isActive
                      ? 'bg-deep text-ink'
                      : 'text-muted hover:bg-deep hover:text-ink',
                  ].join(' ')
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <div
              className="hidden min-w-0 text-right leading-tight xl:block"
              title={`Текущая роль: ${ROLE_LABELS[role]}${
                session ? ` · ${session.fullName}` : ''
              }`}
            >
              <p className="max-w-[220px] truncate text-sm font-medium text-ink">
                {session?.fullName ?? ROLE_LABELS[role]}
              </p>
              <p className="mt-0.5 text-xs text-muted">{ROLE_LABELS[role]}</p>
            </div>

            <div
              className="hidden h-10 w-10 place-items-center rounded-full bg-deep text-xs font-semibold text-soft md:grid"
              title={ROLE_LABELS[role]}
            >
              <span aria-hidden="true">{ROLE_INITIALS[role]}</span>
              <span className="sr-only">
                {ROLE_LABELS[role]}
                {session ? `, ${session.fullName}` : ''}
              </span>
            </div>

            <button
              type="button"
              onClick={clearRole}
              className="btn-icon hidden sm:inline-flex"
              aria-label="Выйти"
              title="Выйти"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>

            <button
              ref={mobileTriggerRef}
              type="button"
              onClick={() => setMobileOpen((value) => !value)}
              className="btn-icon lg:hidden"
              aria-label={mobileOpen ? 'Закрыть меню' : 'Открыть меню'}
              aria-expanded={mobileOpen}
              aria-controls="mobile-navigation"
            >
              {mobileOpen ? (
                <X className="h-5 w-5" aria-hidden="true" />
              ) : (
                <Menu className="h-5 w-5" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </header>

      <main
        id="main"
        className="mx-auto w-full max-w-[1560px] flex-1 px-4 pb-16 pt-8 sm:px-6 lg:px-10 lg:pt-10"
      >
        <div key={location.pathname} className="animate-page-in">
          <Outlet />
        </div>
      </main>

      <footer className="border-t border-line bg-panel">
        <div className="mx-auto flex w-full max-w-[1560px] flex-col gap-1 px-4 py-5 text-xs text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-10">
          <p>ПромСкан · разработано для КСТ Энерго</p>
          <p>Демо-стенд · данные не покидают браузер</p>
        </div>
      </footer>

      {mobileOpen ? (
        <MobileNav
          role={role}
          accountName={session?.fullName ?? ROLE_LABELS[role]}
          triggerRef={mobileTriggerRef}
          onClose={() => setMobileOpen(false)}
          onLogout={clearRole}
        />
      ) : null}
    </div>
  );
}
