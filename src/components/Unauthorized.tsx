import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  Eye,
  EyeOff,
  KeyRound,
  LogIn,
  Loader2,
  ShieldCheck,
} from 'lucide-react';
import { useRole } from '../context/RoleContext';
import {
  authenticateAccessKey,
  AuthError,
  normalizeAccessKey,
} from '../lib/auth';
import { Brand } from './Brand';

function ScanTarget() {
  return (
    <div
      className="pointer-events-none absolute -bottom-24 -right-28 h-[440px] w-[440px] opacity-60"
      aria-hidden="true"
    >
      <div className="absolute inset-0 border border-line" />
      <div className="absolute inset-[12%] border border-line" />
      <div className="absolute inset-[28%] border border-line-strong" />
      <div className="absolute inset-[44%] border border-accent/50" />
      <div className="absolute left-1/2 top-0 h-full w-px bg-line/70" />
      <div className="absolute left-0 top-1/2 h-px w-full bg-line/70" />
      <div className="absolute left-[44%] top-[44%] h-[12%] w-[12%] bg-accent/15" />
      <span className="absolute left-[44%] top-[28%] -translate-y-4 font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
        X 042.8
      </span>
      <span className="absolute left-[44%] top-[58%] mt-2 font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
        Y 118.2
      </span>
      <span className="absolute left-[28%] top-[44%] -translate-x-full pr-3 font-mono text-[9px] uppercase tracking-[0.18em] text-faint">
        PSC-02
      </span>
    </div>
  );
}

export function Unauthorized() {
  const { login } = useRole();
  const navigate = useNavigate();
  const [accessKey, setAccessKey] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');

    const normalized = normalizeAccessKey(accessKey);

    if (!normalized) {
      setError('Введите индивидуальный ключ доступа.');
      return;
    }

    setSubmitting(true);

    try {
      const session = await authenticateAccessKey(normalized);

      if (!session) {
        setError(
          'Ключ не подошёл. Проверьте 10 символов или обратитесь к директору.',
        );
        return;
      }

      // Сначала меняем маршрут, затем роль: после login дерево маршрутов
      // перестраивается, и navigate из уже размонтированного экрана входа
      // может потеряться.
      const target =
        session.role === 'director' || session.role === 'admin'
          ? '/users'
          : '/scanner';

      navigate(target, { replace: true });
      login(session);
    } catch (reason: unknown) {
      setError(
        reason instanceof AuthError
          ? reason.message
          : 'Не удалось проверить ключ. Повторите попытку.',
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid min-h-dvh bg-canvas lg:grid-cols-[1.08fr_0.92fr]">
      <aside className="relative hidden flex-col justify-between overflow-hidden border-r border-line bg-[linear-gradient(150deg,#f8f7f4_0%,#ebe8e1_55%,#ddd9d0_100%)] p-10 lg:flex xl:p-14">
        <div className="blueprint absolute inset-0" aria-hidden="true" />
        <div
          className="absolute inset-0 bg-[radial-gradient(circle_at_28%_22%,rgb(255_255_255/0.92)_0%,transparent_58%)]"
          aria-hidden="true"
        />
        <ScanTarget />

        <div className="relative z-10">
          <Brand to="/" />
        </div>

        <div className="relative z-10 max-w-xl py-10">
          <p className="eyebrow">Промышленное зрение / 2026</p>
          <p className="mt-6 text-balance text-[clamp(3rem,4.8vw,5.25rem)] font-medium leading-[0.9] tracking-[-0.055em] text-ink">
            Контроль, который видит узел.
          </p>
          <p className="mt-8 max-w-md text-[15px] leading-7 text-muted">
            Камера, отчёт ИИ и доступ к оборудованию — в одной панели. Снимок
            остаётся в браузере, результат появляется через две секунды.
          </p>
        </div>

        <div className="relative z-10 grid grid-cols-3 gap-6 border-t border-line pt-5">
          <div>
            <p className="technical">Модуль</p>
            <p className="mt-1.5 font-mono text-xs text-soft">PSC-02</p>
          </div>
          <div>
            <p className="technical">Режим</p>
            <p className="mt-1.5 font-mono text-xs text-soft">Демо</p>
          </div>
          <div>
            <p className="technical">Доступ</p>
            <p className="mt-1.5 font-mono text-xs text-soft">По роли</p>
          </div>
        </div>
      </aside>

      <main className="flex min-h-dvh flex-col bg-panel px-5 py-7 sm:px-10 lg:px-12 xl:px-20">
        <div className="lg:hidden">
          <Brand to="/" />
        </div>

        <div className="flex flex-1 items-center py-12">
          <div className="mx-auto w-full max-w-[420px] animate-page-in">
            <p className="eyebrow">Служебный доступ</p>
            <h1 className="mt-4 text-balance text-[clamp(2.35rem,3.5vw,3.4rem)] font-medium leading-[0.98] tracking-[-0.045em] text-ink">
              Вход в веб-панель
            </h1>
            <p className="mt-4 text-sm leading-6 text-muted">
              Введите индивидуальный 10-значный ключ. Директор создаёт ключи
              сотрудникам, а новая вкладка снова запросит вход.
            </p>

            <form
              onSubmit={handleSubmit}
              className="mt-8 space-y-5"
              noValidate
            >
              <div>
                <label htmlFor="access-key" className="label">
                  Индивидуальный ключ
                </label>
                <div className="relative">
                  <KeyRound
                    className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                    aria-hidden="true"
                  />
                  <input
                    id="access-key"
                    name="accessKey"
                    type={showKey ? 'text' : 'password'}
                    value={accessKey}
                    onChange={(event) => {
                      setAccessKey(event.target.value);
                      if (error) {
                        setError('');
                      }
                    }}
                    className="input pl-10 pr-12 font-mono uppercase tracking-[0.12em]"
                    placeholder="10 символов"
                    autoComplete="one-time-code"
                    inputMode="text"
                    maxLength={14}
                    spellCheck={false}
                    autoFocus
                    aria-invalid={Boolean(error)}
                    aria-describedby={error ? 'login-error' : 'login-hint'}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((value) => !value)}
                    className="absolute right-0 top-0 grid h-11 w-11 place-items-center text-faint transition-colors hover:text-ink"
                    aria-label={showKey ? 'Скрыть ключ' : 'Показать ключ'}
                  >
                    {showKey ? (
                      <EyeOff className="h-4 w-4" aria-hidden="true" />
                    ) : (
                      <Eye className="h-4 w-4" aria-hidden="true" />
                    )}
                  </button>
                </div>

                {error ? (
                  <p
                    id="login-error"
                    role="alert"
                    className="mt-3 flex items-start gap-2 text-xs leading-5 text-danger"
                  >
                    <AlertCircle
                      className="mt-0.5 h-3.5 w-3.5 shrink-0"
                      aria-hidden="true"
                    />
                    {error}
                  </p>
                ) : (
                  <p
                    id="login-hint"
                    className="mt-3 font-mono text-[10px] leading-5 tracking-[0.04em] text-faint"
                  >
                    Демо-ключ директора — в README, раздел «Быстрый старт».
                    Ключи сотрудников приходят на email после создания.
                  </p>
                )}
              </div>

              <button
                type="submit"
                className="btn-primary w-full"
                disabled={submitting}
                aria-busy={submitting}
              >
                {submitting ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <LogIn className="h-4 w-4" aria-hidden="true" />
                )}
                {submitting ? 'Проверяем ключ…' : 'Войти по ключу'}
              </button>
            </form>

            <div className="mt-7 flex gap-3 border border-line bg-raised p-4">
              <ShieldCheck
                className="mt-0.5 h-4 w-4 shrink-0 text-ok"
                aria-hidden="true"
              />
              <p className="text-xs leading-5 text-muted">
                Каждый ключ создаётся отдельно и определяет права: сканирование,
                диспетчерская, сотрудники. Ключ нельзя восстановить — только
                перевыпустить.
              </p>
            </div>

            <p className="mt-6 text-[11px] leading-5 text-faint">
              Демо-режим: ключ проверяется в браузере по PBKDF2-хешу. В
              production проверка и сессия выполняются на сервере; ключ
              отправляется только по HTTPS.
            </p>
          </div>
        </div>

        <footer className="flex items-center justify-between gap-4 border-t border-line pt-4 font-mono text-[9px] uppercase tracking-[0.16em] text-faint">
          <span>PSC-02 · демо</span>
          <span>Доступ по роли</span>
        </footer>
      </main>
    </div>
  );
}
