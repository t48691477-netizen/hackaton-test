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
      className="pointer-events-none absolute -bottom-24 -right-28 h-[440px] w-[440px]"
      aria-hidden="true"
    >
      <div className="absolute inset-0 rounded-full border border-white/10" />
      <div className="absolute inset-[12%] rounded-full border border-white/10" />
      <div className="absolute inset-[28%] rounded-full border border-white/15" />
      <div className="absolute inset-[44%] rounded-full border border-white/30" />
      <div className="absolute left-1/2 top-0 h-full w-px bg-white/10" />
      <div className="absolute left-0 top-1/2 h-px w-full bg-white/10" />
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
    <div className="grid min-h-dvh gap-5 bg-canvas p-4 lg:grid-cols-[1.08fr_0.92fr] lg:p-5">
      <aside className="relative hidden flex-col justify-end overflow-hidden rounded-xl bg-hero p-10 text-white lg:flex xl:p-14">
        <ScanTarget />

        <div className="relative z-10 max-w-xl py-10">
          <p className="text-sm font-medium text-white/70">
            Промышленное зрение
          </p>
          <p className="mt-5 text-balance text-[clamp(2.25rem,3.6vw,3.75rem)] font-semibold leading-[1.05] tracking-[-0.02em]">
            Контроль, который видит узел.
          </p>
          <p className="mt-6 max-w-md text-[15px] leading-7 text-white/75">
            Камера, отчёт ИИ и доступ к оборудованию — в одной панели. Снимок
            остаётся в браузере, результат появляется через две секунды.
          </p>
        </div>

        <div className="relative z-10 grid grid-cols-3 gap-6 border-t border-white/15 pt-5">
          <div>
            <p className="text-xs text-white/60">Модуль</p>
            <p className="mt-1 font-mono text-sm text-white">PSC-02</p>
          </div>
          <div>
            <p className="text-xs text-white/60">Режим</p>
            <p className="mt-1 text-sm text-white">Демо</p>
          </div>
          <div>
            <p className="text-xs text-white/60">Доступ</p>
            <p className="mt-1 text-sm text-white">По роли</p>
          </div>
        </div>
      </aside>

      <main className="flex min-h-[calc(100dvh-2rem)] flex-col px-2 py-3 sm:px-8 lg:min-h-[calc(100dvh-2.5rem)] lg:px-10 xl:px-16">
        <div>
          <Brand to="/" />
        </div>

        <div className="flex flex-1 items-center py-12">
          <div className="mx-auto w-full max-w-[420px] animate-page-in">
            <p className="eyebrow">Служебный доступ</p>
            <h1 className="mt-3 text-balance text-3xl font-semibold leading-tight tracking-[-0.01em] text-ink">
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
                    className="input pl-10 pr-12 font-mono uppercase tracking-[0.08em]"
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
                    className="mt-3 text-xs leading-5 text-muted"
                  >
                    Демо-ключ директора:{' '}
                    <code className="font-mono text-ink">PSCDRT2345</code>.
                    Ключи сотрудников
                    приходят на email после создания.
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

            <div className="mt-7 flex gap-3 rounded-xl border border-line bg-panel p-4">
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

            <p className="mt-6 text-xs leading-5 text-muted">
              Демо-режим: ключ проверяется в браузере по PBKDF2-хешу. В
              production проверка и сессия выполняются на сервере; ключ
              отправляется только по HTTPS.
            </p>
          </div>
        </div>

        <footer className="flex items-center justify-between gap-4 border-t border-line pt-4 text-xs text-muted">
          <span>ПромСкан · КСТ Энерго</span>
          <span>Демо-стенд</span>
        </footer>
      </main>
    </div>
  );
}
