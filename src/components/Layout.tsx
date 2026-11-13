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
  ROLE_SHORT_LABELS,
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

const TODAY = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: 'short',
})
  .format(new Date())
  .replace('.', '')
  .toUpperCase();

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
            className="btn-icon border-0"
            aria-label="Закрыть меню"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-8">
          <p className="technical">Рабочее пространство</p>

          <nav aria-label="Мобильная навигация" className="mt-4">
            {visibleItems.map((item, index) => {
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
                          'grid h-10 w-10 shrink-0 place-items-center border transition-colors',
                          isActive
                            ? 'border-accent/40 bg-accent/10 text-accent'
                            : 'border-line text-faint group-hover:text-soft',
                        ].join(' ')}
                      >
                        <Icon className="h-4 w-4" aria-hidden="true" />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block font-mono text-[9px] tracking-[0.18em] text-faint">
                          0{index + 1}
                        </span>
                        <span className="mt-1 block text-[15px] font-medium leading-tight">
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
          <div className="flex items-start gap-3 border border-line bg-raised p-3">
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

      <div className="border-b border-line bg-deep">
        <div className="mx-auto flex h-8 w-full max-w-[1560px] items-center justify-between gap-4 px-4 font-mono text-[9px] uppercase tracking-[0.16em] text-faint sm:px-6 lg:px-10">
          <div className="flex items-center gap-2.5">
            <span
              className="h-1.5 w-1.5 animate-pulse-soft bg-ok"
              aria-hidden="true"
            />
            <span className="text-soft">Система в норме</span>
            <span className="hidden text-line-strong sm:inline" aria-hidden="true">
              /
            </span>
            <span className="hidden sm:inline">демо-стенд</span>
          </div>

          <div className="flex items-center gap-4">
            {session ? (
              <span className="hidden max-w-[220px] truncate md:inline">
                {session.fullName}
              </span>
            ) : null}
            <span className="hidden sm:inline">МСК · {TODAY}</span>
            <span>PSC-02 · v0.1</span>
          </div>
        </div>
      </div>

      <header className="sticky top-0 z-40 border-b border-line bg-canvas">
        <div className="mx-auto flex h-[72px] w-full max-w-[1560px] items-center gap-6 px-4 sm:px-6 lg:px-10">
          <Brand />

          <nav
            aria-label="Основная навигация"
            className="hidden h-full items-stretch border-l border-line lg:flex"
          >
            {visibleItems.map((item, index) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    'group relative flex min-w-[136px] flex-col justify-center gap-1.5 border-r border-line px-5 transition-colors duration-150',
                    isActive
                      ? 'bg-ink/[0.035] text-ink'
                      : 'text-muted hover:bg-ink/[0.025] hover:text-ink',
                  ].join(' ')
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={[
                        'font-mono text-[9px] tracking-[0.18em]',
                        isActive ? 'text-accent' : 'text-faint',
                      ].join(' ')}
                    >
                      0{index + 1}
                    </span>
                    <span className="text-[13px] font-medium leading-none">
                      {item.label}
                    </span>
                    <span
                      className={[
                        'absolute inset-x-0 bottom-0 h-px origin-left bg-accent transition-transform duration-200',
                        isActive
                          ? 'scale-x-100'
                          : 'scale-x-0 group-hover:scale-x-100',
                      ].join(' ')}
                      aria-hidden="true"
                    />
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2 sm:gap-3">
            <span
              className="tag hidden border-line bg-transparent text-soft sm:inline-flex"
              title={`Текущая роль: ${ROLE_LABELS[role]}${
                session ? ` · ${session.fullName}` : ''
              }`}
            >
              <span className="h-1.5 w-1.5 bg-accent" aria-hidden="true" />
              <span className="hidden 2xl:inline">
                {session?.fullName ?? ROLE_LABELS[role]}
              </span>
              <span className="2xl:hidden">{ROLE_SHORT_LABELS[role]}</span>
              <span className="sr-only">{ROLE_LABELS[role]}</span>
            </span>

            <div
              className="hidden h-9 w-9 place-items-center border border-line bg-panel font-mono text-[10px] font-medium tracking-[0.08em] text-soft md:grid"
              aria-hidden="true"
              title={ROLE_LABELS[role]}
            >
              {ROLE_INITIALS[role]}
            </div>

            <button
              ref={mobileTriggerRef}
              type="button"
              onClick={clearRole}
              className="btn-icon hidden border-0 sm:inline-flex"
              aria-label="Выйти"
              title="Выйти"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
            </button>

            <button
              type="button"
              onClick={() => setMobileOpen((value) => !value)}
              className="btn-icon border-0 lg:hidden"
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

      <footer className="border-t border-line">
        <div className="mx-auto flex w-full max-w-[1560px] flex-col gap-2 px-4 py-5 font-mono text-[9px] uppercase tracking-[0.16em] text-faint sm:flex-row sm:items-center sm:justify-between sm:px-6 lg:px-10">
          <p>ПромСкан · промышленное зрение</p>
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
