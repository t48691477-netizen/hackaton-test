import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
} from 'react';
import { createPortal } from 'react-dom';
import {
  AlertCircle,
  ChevronDown,
  KeyRound,
  Mail,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserPlus,
  X,
} from 'lucide-react';
import { AccessDenied } from '../components/AccessDenied';
import { PageHeader } from '../components/PageHeader';
import { useRole } from '../context/RoleContext';
import { DIRECTOR_ACCOUNT, maskAccessKey } from '../lib/accessKeys';
import { API_CONFIG, deleteEmployee, fetchEmployees } from '../lib/api';
import type { AccessKeyEmailResult } from '../lib/email';
import {
  EMPLOYEES_CHANGED_EVENT,
  EMPLOYEES_STORAGE_KEY,
  loadEmployees,
  saveEmployees,
  toEmployeeAccount,
  type Employee,
  type EmployeeAccount,
  type EmployeeRole,
} from '../lib/employees';
import { ROLE_LABELS } from '../lib/roles';
import { useMediaQuery } from '../lib/useMediaQuery';
import { useFocusTrap } from '../lib/useFocusTrap';
import {
  provisionEmployee,
  reissueEmployeeAccess,
  type ProvisionedEmployee,
} from '../lib/userProvisioning';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

const EMPLOYEE_ROLE_META: Record<
  EmployeeRole,
  { label: string; dot: string; text: string; note: string }
> = {
  admin: {
    label: 'Администратор',
    dot: 'bg-accent',
    text: 'text-accent',
    note: 'Сканер, диспетчерская и сотрудники',
  },
  dispatcher: {
    label: 'Диспетчер',
    dot: 'bg-info',
    text: 'text-info',
    note: 'Сканер и панель дефектов',
  },
  engineer: {
    label: 'Рабочий',
    dot: 'bg-warn',
    text: 'text-warn',
    note: 'Только веб-сканер',
  },
};

function getInitials(fullName: string): string {
  const [firstName, lastName] = fullName.trim().split(/\s+/);
  return `${firstName?.[0] ?? ''}${lastName?.[0] ?? ''}`.toUpperCase();
}

function FieldError({ id, message }: { id: string; message: string }) {
  return (
    <p
      id={id}
      role="alert"
      className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-danger"
    >
      <AlertCircle
        className="mt-1 h-3.5 w-3.5 shrink-0"
        aria-hidden="true"
      />
      {message}
    </p>
  );
}

function InvitationLine({ employee }: { employee: EmployeeAccount }) {
  const { invitation } = employee;

  if (invitation.status === 'sent') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-ok">
        <Mail className="h-3 w-3" aria-hidden="true" />
        Письмо отправлено
      </span>
    );
  }

  if (invitation.status === 'queued') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-warn">
        <Mail className="h-3 w-3" aria-hidden="true" />
        Письмо в очереди
      </span>
    );
  }

  if (invitation.status === 'failed') {
    return (
      <span className="inline-flex items-center gap-1 text-[10px] text-danger">
        <AlertCircle className="h-3 w-3" aria-hidden="true" />
        Письмо не отправлено
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 text-[10px] text-faint">
      <Mail className="h-3 w-3" aria-hidden="true" />
      Письмо не отправлялось
    </span>
  );
}

interface KeyDeliveryDialogProps {
  employee: EmployeeAccount;
  invitation: AccessKeyEmailResult;
  restoreFocus: () => void;
  onClose: () => void;
}

/**
 * Подтверждение выдачи. Ключ здесь не показывается: в production его
 * отправляет сервер на email сотрудника, в демо он лежит в mock-outbox.
 */
function KeyDeliveryDialog({
  employee,
  invitation,
  restoreFocus,
  onClose,
}: KeyDeliveryDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useFocusTrap(dialogRef, {
    initialFocus: 'button[aria-label="Закрыть окно"]',
    onEscape: onClose,
    restoreFocus,
  });

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const failed = invitation.status === 'failed';
  const sent = invitation.status === 'sent';
  const title = failed
    ? 'Письмо не отправлено'
    : sent
      ? 'Ключ отправлен на email'
      : 'Письмо с ключом в очереди';

  return createPortal(
    <div className="fixed inset-0 z-[60] grid place-items-center px-4 py-6">
      <div
        onClick={onClose}
        className="absolute inset-0 bg-black/45"
        aria-hidden="true"
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="key-delivery-title"
        className="relative w-full max-w-[520px] border border-line bg-panel shadow-sheet"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-5 sm:px-7">
          <div>
            <p className="eyebrow">Ключ доступа</p>
            <h2
              id="key-delivery-title"
              className="mt-2 text-2xl font-medium tracking-[-0.035em] text-ink"
            >
              {title}
            </h2>
            <p className="mt-2 text-xs leading-5 text-muted">
              {employee.fullName} · {ROLE_LABELS[employee.role]}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="btn-icon border-0"
            aria-label="Закрыть окно"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-5 px-5 py-6 sm:px-7">
          <div
            className={`border p-4 ${
              failed
                ? 'border-danger/30 bg-danger/[0.04]'
                : 'border-line bg-raised'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <p className="technical">Доставка ключа</p>
              {failed ? (
                <AlertCircle className="h-4 w-4 text-danger" aria-hidden="true" />
              ) : (
                <Mail className="h-4 w-4 text-accent" aria-hidden="true" />
              )}
            </div>
            <p className="mt-3 text-sm leading-6 text-soft">
              {failed ? (
                <>
                  Письмо для {employee.email} не удалось поставить в очередь.
                  Перевыпустите ключ или обратитесь к администратору почты.
                </>
              ) : sent ? (
                <>Ключ отправлен на {employee.email}.</>
              ) : (
                <>
                  Письмо для <strong className="text-ink">{employee.email}</strong>{' '}
                  поставлено в очередь. Backend отправит его после подключения
                  почтового провайдера.
                </>
              )}
            </p>
            <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
              provider: {invitation.provider ?? '—'} · status: {invitation.status}
            </p>
          </div>

          <div className="flex gap-3 border border-warn/25 bg-warn/[0.04] p-4">
            <ShieldCheck
              className="mt-0.5 h-4 w-4 shrink-0 text-warn"
              aria-hidden="true"
            />
            <div>
              <p className="text-[11px] leading-5 text-muted">
                Ключ не показывается в веб-панели: администратор его не видит
                и не может скопировать. Сотрудник получает ключ только на свой
                email; старый ключ при перевыпуске перестаёт работать.
              </p>
              {!failed ? (
                <p className="mt-2 text-[11px] leading-5 text-faint">
                  Демо-режим: письмо сохранено в mock-outbox браузера. Как его
                  открыть — в README, раздел «Ключи и приглашения».
                </p>
              ) : null}
            </div>
          </div>

          <button type="button" onClick={onClose} className="btn-primary w-full">
            Готово
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

interface DeleteEmployeeDialogProps {
  employee: EmployeeAccount;
  deleting: boolean;
  error: string;
  restoreFocus: () => void;
  onClose: () => void;
  onConfirm: () => void;
}

function DeleteEmployeeDialog({
  employee,
  deleting,
  error,
  restoreFocus,
  onClose,
  onConfirm,
}: DeleteEmployeeDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);

  useFocusTrap(dialogRef, {
    initialFocus: 'button[data-delete-cancel]',
    onEscape: deleting ? undefined : onClose,
    restoreFocus,
  });

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  return createPortal(
    <div className="fixed inset-0 z-[60] grid place-items-center px-4 py-6">
      <div
        onClick={() => {
          if (!deleting) onClose();
        }}
        className="absolute inset-0 bg-black/45"
        aria-hidden="true"
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="delete-employee-title"
        className="relative w-full max-w-[520px] border border-line bg-panel shadow-sheet"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-5 sm:px-7">
          <div>
            <p className="eyebrow">Отзыв доступа</p>
            <h2
              id="delete-employee-title"
              className="mt-2 text-2xl font-medium tracking-[-0.035em] text-ink"
            >
              Удалить сотрудника?
            </h2>
            <p className="mt-2 text-xs leading-5 text-muted">
              {employee.fullName} · {employee.email}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={deleting}
            className="btn-icon border-0"
            aria-label="Закрыть окно"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <div className="space-y-5 px-5 py-6 sm:px-7">
          <div className="border border-danger/30 bg-danger/[0.04] p-4">
            <p className="text-sm leading-6 text-soft">
              Доступ сотрудника будет отозван, а запись исчезнет из списка.
              Это действие нельзя отменить.
            </p>
          </div>

          {error ? (
            <p className="border border-danger/30 bg-danger/[0.04] px-4 py-3 text-sm text-danger" role="alert">
              {error}
            </p>
          ) : null}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              data-delete-cancel
              onClick={onClose}
              disabled={deleting}
              className="btn-secondary w-full sm:w-auto"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={onConfirm}
              disabled={deleting}
              aria-busy={deleting}
              className="inline-flex min-h-11 items-center justify-center gap-2 border border-danger bg-danger px-4 font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {deleting ? (
                <RefreshCw className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Trash2 className="h-4 w-4" aria-hidden="true" />
              )}
              {deleting ? 'Удаляем…' : 'Удалить'}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function keyDateLabel(keyCreatedAt: string | null): string {
  return keyCreatedAt ? `создан ${keyCreatedAt.slice(0, 10)}` : 'ключ ещё не создан';
}

interface AddEmployeeModalProps {
  existingEmails: ReadonlySet<string>;
  canCreateAdmin: boolean;
  restoreFocus: () => void;
  onClose: () => void;
  onCreated: (result: ProvisionedEmployee) => void;
}

function AddEmployeeModal({
  existingEmails,
  canCreateAdmin,
  restoreFocus,
  onClose,
  onCreated,
}: AddEmployeeModalProps) {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [role, setRole] = useState<EmployeeRole>('dispatcher');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const submittingRef = useRef(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  const normalizedEmail = email.trim().toLowerCase();
  const nameParts = fullName.trim().split(/\s+/).filter(Boolean);
  const errors = {
    fullName: !fullName.trim()
      ? 'Введите ФИО'
      : nameParts.length < 2
        ? 'Укажите имя и фамилию через пробел'
        : '',
    email: !email.trim()
      ? 'Введите email'
      : !EMAIL_PATTERN.test(normalizedEmail)
        ? 'Некорректный email'
        : existingEmails.has(normalizedEmail)
          ? 'Сотрудник с таким email уже существует'
          : '',
  };

  useFocusTrap(dialogRef, {
    initialFocus: 'input',
    onEscape: () => {
      if (!submittingRef.current) onClose();
    },
    restoreFocus,
  });

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    setSubmitError('');

    if (errors.fullName || errors.email || submitting) {
      return;
    }

    setSubmitting(true);
    submittingRef.current = true;

    try {
      const result = await provisionEmployee({
        fullName,
        email: normalizedEmail,
        role,
      });

      onCreated(result);
    } catch (reason: unknown) {
      setSubmitError(
        reason instanceof Error
          ? reason.message
          : 'Не удалось создать ключ. Повторите попытку.',
      );
    } finally {
      setSubmitting(false);
      submittingRef.current = false;
    }
  };

  return createPortal(
    <div
      className="fixed inset-0 z-50"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !submittingRef.current) {
          onClose();
        }
      }}
    >
      <div
        className="fixed inset-0 animate-fade-in bg-black/40"
        aria-hidden="true"
        onMouseDown={() => {
          if (!submittingRef.current) onClose();
        }}
      />

      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-employee-title"
        className="relative ml-auto flex h-dvh w-full max-w-[560px] animate-sheet-in flex-col overflow-hidden border-l border-line bg-panel shadow-sheet"
      >
        <div className="flex shrink-0 items-start justify-between gap-4 border-b border-line bg-panel px-5 py-5 sm:px-7">
          <div>
            <p className="eyebrow">Новый сотрудник</p>
            <h2
              id="add-employee-title"
              className="mt-2 text-2xl font-medium tracking-[-0.035em] text-ink"
            >
              Добавление сотрудника
            </h2>
            <p className="mt-2 text-xs leading-5 text-muted">
              Ключ создаётся автоматически и отправляется на email сотрудника.
              Администратор его не видит; в справочнике остаётся только хеш.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="btn-icon border-0"
            aria-label="Закрыть окно"
          >
            <X className="h-5 w-5" aria-hidden="true" />
          </button>
        </div>

        <form
          onSubmit={(event) => void handleSubmit(event)}
          className="flex min-h-0 flex-1 flex-col"
          noValidate
        >
          <div className="min-h-0 flex-1 space-y-9 overflow-y-auto px-5 py-7 sm:px-7">
            <fieldset>
              <legend className="flex w-full items-center gap-3 border-b border-line pb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
                <span className="text-accent">01</span>
                Идентификация
              </legend>

              <div className="mt-5 space-y-5">
                <div>
                  <label htmlFor="employee-full-name" className="label">
                    ФИО
                  </label>
                  <input
                    id="employee-full-name"
                    name="fullName"
                    value={fullName}
                    onChange={(event) => setFullName(event.target.value)}
                    className="input"
                    placeholder="Иван Иванов"
                    autoComplete="off"
                    aria-invalid={submitted && Boolean(errors.fullName)}
                    aria-describedby={
                      submitted && errors.fullName ? 'full-name-error' : undefined
                    }
                  />
                  {submitted && errors.fullName ? (
                    <FieldError id="full-name-error" message={errors.fullName} />
                  ) : null}
                </div>

                <div>
                  <label htmlFor="employee-email" className="label">
                    Email для письма с ключом
                  </label>
                  <input
                    id="employee-email"
                    name="email"
                    type="email"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    className="input"
                    placeholder="i.ivanov@promscan.ru"
                    autoComplete="off"
                    aria-invalid={submitted && Boolean(errors.email)}
                    aria-describedby={
                      submitted && errors.email ? 'email-error' : undefined
                    }
                  />
                  {submitted && errors.email ? (
                    <FieldError id="email-error" message={errors.email} />
                  ) : null}
                </div>
              </div>
            </fieldset>

            <fieldset>
              <legend className="flex w-full items-center gap-3 border-b border-line pb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
                <span className="text-accent">02</span>
                Доступ
              </legend>

              <div className="mt-5">
                <label htmlFor="employee-role" className="label">
                  Набор функций
                </label>
                <div className="relative">
                  <select
                    id="employee-role"
                    name="role"
                    value={role}
                    onChange={(event) =>
                      setRole(event.target.value as EmployeeRole)
                    }
                    className="input appearance-none pr-10"
                  >
                    {canCreateAdmin ? (
                      <option value="admin">
                        Администратор · сканер, дефекты, сотрудники
                      </option>
                    ) : null}
                    <option value="dispatcher">
                      Диспетчер · сканер и дефекты
                    </option>
                    <option value="engineer">
                      Рабочий · веб-сканер
                    </option>
                  </select>
                  <ChevronDown
                    className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                    aria-hidden="true"
                  />
                </div>
                <p className="mt-2 text-xs leading-5 text-faint">
                  {EMPLOYEE_ROLE_META[role].note}. Ключ получает только этот
                  набор функций.
                </p>
              </div>
            </fieldset>

            <fieldset>
              <legend className="flex w-full items-center gap-3 border-b border-line pb-2 font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
                <span className="text-accent">03</span>
                Ключ и письмо
              </legend>

              <div className="mt-5">
                <div className="flex items-center justify-between gap-3 border border-line bg-raised px-4 py-3">
                  <div>
                    <p className="text-sm font-medium text-ink">
                      Ключ уйдёт только на email
                    </p>
                    <p className="mt-1 text-[11px] leading-5 text-faint">
                      10 символов, криптографический генератор. В веб-панели
                      ключ не отображается и не копируется.
                    </p>
                  </div>
                  <KeyRound
                    className="h-5 w-5 shrink-0 text-accent"
                    aria-hidden="true"
                  />
                </div>

                <div className="mt-4 flex items-start gap-3 border border-line p-4">
                  <Mail
                    className="mt-0.5 h-4 w-4 shrink-0 text-ok"
                    aria-hidden="true"
                  />
                  <span>
                    <span className="block text-sm font-medium text-ink">
                      Письмо с ключом и кодом подтверждения
                    </span>
                    <span className="mt-1 block text-[11px] leading-5 text-faint">
                      В демо письмо складывается в mock-outbox браузера, реальную
                      отправку выполнит backend после подключения SMTP/Gmail.
                    </span>
                  </span>
                </div>
              </div>
            </fieldset>

            <div className="flex gap-3 border border-warn/25 bg-warn/[0.04] p-4">
              <ShieldCheck
                className="mt-0.5 h-4 w-4 shrink-0 text-warn"
                aria-hidden="true"
              />
              <p className="text-[11px] leading-5 text-muted">
                Ключ не попадает в интерфейс администратора. В production его
                генерирует сервер, хранит только Argon2id-хеш и отправляет
                письмо через защищённый провайдер.
              </p>
            </div>
          </div>

          {submitError ? (
            <p role="alert" className="px-5 pt-3 text-xs text-danger sm:px-7">
              {submitError}
            </p>
          ) : null}

          <div className="flex shrink-0 gap-3 border-t border-line bg-panel px-5 py-4 sm:px-7">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="btn-secondary flex-1"
            >
              Отмена
            </button>
            <button
              type="submit"
              className="btn-primary flex-1"
              disabled={submitting}
              aria-busy={submitting}
            >
              {submitting ? (
                <RefreshCw
                  className="h-4 w-4 animate-spin"
                  aria-hidden="true"
                />
              ) : (
                <UserPlus className="h-4 w-4" aria-hidden="true" />
              )}
              {submitting ? 'Создаём ключ…' : 'Создать и отправить ключ'}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body,
  );
}

export function Users() {
  const { role } = useRole();
  const compact = useMediaQuery('(max-width: 1023px)');
  const [employees, setEmployees] = useState<EmployeeAccount[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [delivery, setDelivery] = useState<ProvisionedEmployee | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<EmployeeAccount | null>(null);
  const [deleteError, setDeleteError] = useState('');
  const [actionError, setActionError] = useState('');
  const addEmployeeButtonRef = useRef<HTMLButtonElement>(null);
  const deleteTriggerRef = useRef<HTMLButtonElement>(null);
  const staffHeadingRef = useRef<HTMLHeadingElement>(null);
  const mountedRef = useRef(true);

  const loadEmployeeList = useCallback(async () => {
    setLoading(true);
    setLoadError('');

    try {
      const next = await fetchEmployees();
      if (!mountedRef.current) return;
      setEmployees(next);
    } catch (reason: unknown) {
      if (!mountedRef.current) return;
      setLoadError(
        reason instanceof Error
          ? reason.message
          : 'Не удалось загрузить список сотрудников.',
      );
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    void loadEmployeeList();

    if (!API_CONFIG.useMock) {
      return () => {
        mountedRef.current = false;
      };
    }

    const refresh = () => {
      void loadEmployeeList();
    };
    window.addEventListener(EMPLOYEES_CHANGED_EVENT, refresh);
    const handleStorage = (event: StorageEvent) => {
      if (event.key === null || event.key === EMPLOYEES_STORAGE_KEY) {
        refresh();
      }
    };
    window.addEventListener('storage', handleStorage);

    return () => {
      window.removeEventListener(EMPLOYEES_CHANGED_EVENT, refresh);
      window.removeEventListener('storage', handleStorage);
      mountedRef.current = false;
    };
  }, [loadEmployeeList]);

  const existingEmails = useMemo(
    () =>
      new Set([
        DIRECTOR_ACCOUNT.email.toLowerCase(),
        ...employees.map((employee) => employee.email.toLowerCase()),
      ]),
    [employees],
  );

  const closeModal = useCallback(() => setModalOpen(false), []);
  const closeDelivery = useCallback(() => setDelivery(null), []);

  const handleCreated = useCallback(
    (result: ProvisionedEmployee) => {
      setModalOpen(false);

      if (API_CONFIG.useMock) {
        const localEmployee = result.localEmployee;
        if (!localEmployee) {
          setActionError('Демо-режим не вернул локальные данные сотрудника.');
          return;
        }

        const next: Employee[] = [
          localEmployee,
          ...loadEmployees().filter((item) => item.id !== localEmployee.id),
        ];
        if (!saveEmployees(next)) {
          setActionError(
            'Не удалось сохранить сотрудника: хранилище браузера недоступно. Ключ уже отправлен в демо-письмо, но учётная запись не создана.',
          );
          return;
        }
        setEmployees(next.map(toEmployeeAccount));
      } else {
        setEmployees((current) => [
          result.employee,
          ...current.filter((item) => item.id !== result.employee.id),
        ]);
      }

      setActionError('');
      setDelivery(result);
    },
    [],
  );

  const handleReissue = useCallback(
    async (employee: EmployeeAccount) => {
      if (busyId || deletingId) return;
      if (role === 'admin' && employee.role === 'admin') {
        setActionError('Перевыпускать ключи администраторов может только директор.');
        return;
      }

      setBusyId(employee.id);
      setActionError('');

      try {
        const result = await reissueEmployeeAccess(employee);
        if (API_CONFIG.useMock) {
          const localEmployee = result.localEmployee;
          if (!localEmployee) {
            setActionError('Демо-режим не вернул локальные данные сотрудника.');
            return;
          }

          const next = loadEmployees().map((item) =>
            item.id === localEmployee.id ? localEmployee : item,
          );
          if (!saveEmployees(next)) {
            setActionError(
              'Не удалось сохранить новый ключ: хранилище браузера недоступно. Старый ключ продолжает действовать.',
            );
            return;
          }
          setEmployees(next.map(toEmployeeAccount));
        } else {
          setEmployees((current) =>
            current.map((item) =>
              item.id === result.employee.id ? result.employee : item,
            ),
          );
        }

        setDelivery(result);
      } catch (reason: unknown) {
        setActionError(
          reason instanceof Error
            ? reason.message
            : 'Не удалось перевыпустить ключ.',
        );
      } finally {
        setBusyId(null);
      }
    },
    [busyId, deletingId, role],
  );

  const handleDelete = useCallback(
    (employee: EmployeeAccount, trigger: HTMLButtonElement) => {
      if (busyId || deletingId) return;

      deleteTriggerRef.current = trigger;
      setDeleteError('');
      setDeleteTarget(employee);
    },
    [busyId, deletingId],
  );

  const closeDeleteDialog = useCallback(() => {
    if (deletingId) return;
    setDeleteTarget(null);
    setDeleteError('');
  }, [deletingId]);

  const confirmDelete = useCallback(async () => {
    if (!deleteTarget || busyId || deletingId) return;

    const employee = deleteTarget;
    setDeletingId(employee.id);
    setDeleteError('');
    setActionError('');

    try {
      await deleteEmployee(employee.id);
      setEmployees((current) =>
        current.filter((item) => item.id !== employee.id),
      );
      setDeletingId(null);
      setDeleteTarget(null);
    } catch (reason: unknown) {
      setDeleteError(
        reason instanceof Error
          ? reason.message
          : 'Не удалось удалить сотрудника.',
      );
      setDeletingId(null);
    }
  }, [busyId, deleteTarget, deletingId]);

  // Дополнительная проверка поверх RoleGuard: прямой вызов компонента
  // не должен раскрывать таблицу сотрудников.
  if (role !== 'director' && role !== 'admin') {
    return <AccessDenied />;
  }

  const admins = employees.filter((employee) => employee.role === 'admin').length;
  const dispatchers = employees.filter(
    (employee) => employee.role === 'dispatcher',
  ).length;
  const engineers = employees.filter(
    (employee) => employee.role === 'engineer',
  ).length;

  const summary = [
    {
      index: '01',
      label: 'Всего сотрудников',
      value: employees.length,
      note: 'Веб-панель и мобильные задания',
    },
    {
      index: '02',
      label: 'Администраторы',
      value: admins,
      note: 'Сканер, диспетчерская и сотрудники',
    },
    {
      index: '03',
      label: 'Диспетчеры',
      value: dispatchers,
      note: 'Сканер и панель дефектов',
    },
    {
      index: '04',
      label: 'Рабочие',
      value: engineers,
      note: 'Только веб-сканер',
    },
  ];

  return (
    <div className="space-y-10">
      <PageHeader
        index="03"
        label="Управление доступом"
        title="Сотрудники"
        description="Каждый сотрудник входит по индивидуальному 10-значному ключу. Ключ создаётся автоматически, отправляется на email сотрудника и не показывается администратору."
        aside={
          <button
            ref={addEmployeeButtonRef}
            type="button"
            onClick={() => setModalOpen(true)}
            disabled={loading || busyId !== null || deletingId !== null}
            className="btn-primary"
          >
            <UserPlus className="h-4 w-4" aria-hidden="true" />
            Добавить сотрудника
          </button>
        }
      />

      <section aria-label="Сводка по сотрудникам">
        <div className="grid grid-cols-2 gap-px border-y border-line bg-line lg:grid-cols-4">
          {summary.map((item) => (
            <div key={item.label} className="min-w-0 bg-panel px-4 py-5 sm:px-5 sm:py-6">
              <div className="flex items-baseline justify-between gap-2">
                <p className="technical">{item.label}</p>
                <span className="font-mono text-[9px] tracking-[0.16em] text-faint">
                  {item.index}
                </span>
              </div>
              <p className="mt-3 font-mono text-[2.5rem] leading-none tracking-[-0.05em] text-ink tabular sm:text-[3rem]">
                {String(item.value).padStart(2, '0')}
              </p>
              <p className="mt-2 text-[11px] leading-4 text-faint sm:text-xs sm:leading-5">
                {item.note}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="staff-heading">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2
              ref={staffHeadingRef}
              id="staff-heading"
              tabIndex={-1}
              className="text-2xl font-medium tracking-[-0.025em] text-ink"
            >
              Штат и ключи доступа
            </h2>
            <p className="mt-1.5 max-w-2xl text-sm leading-6 text-muted">
              Ключи не отображаются в таблице. Если сотрудник потерял ключ,
              перевыпустите его: новый уйдёт на email, старый перестанет
              действовать для новых входов.
            </p>
          </div>
          <span className="tag w-fit border-line text-muted">
            {loading
              ? 'Загрузка…'
              : `${String(employees.length).padStart(2, '0')} записей`}
          </span>
        </div>

        {actionError ? (
          <p role="alert" className="mt-4 border border-danger/30 bg-danger/[0.04] px-4 py-3 text-sm text-danger">
            {actionError}
          </p>
        ) : null}

        {loading ? (
          <div
            role="status"
            aria-live="polite"
            className="mt-6 flex min-h-40 items-center justify-center border border-line bg-panel px-5 py-10 text-center"
          >
            <div>
              <RefreshCw
                className="mx-auto h-5 w-5 animate-spin text-accent"
                aria-hidden="true"
              />
              <p className="mt-3 text-sm text-muted">Загружаем сотрудников…</p>
            </div>
          </div>
        ) : loadError ? (
          <div
            role="alert"
            className="mt-6 flex flex-col gap-4 border border-danger/30 bg-danger/[0.04] px-5 py-5 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex items-start gap-3">
              <AlertCircle
                className="mt-0.5 h-4 w-4 shrink-0 text-danger"
                aria-hidden="true"
              />
              <div>
                <p className="text-sm font-medium text-ink">
                  Не удалось загрузить список сотрудников
                </p>
                <p className="mt-1 text-xs leading-5 text-muted">{loadError}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => void loadEmployeeList()}
              className="btn-secondary shrink-0"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Повторить
            </button>
          </div>
        ) : employees.length === 0 ? (
          <div className="mt-6 flex min-h-40 flex-col items-center justify-center border border-dashed border-line-strong bg-panel px-5 py-10 text-center">
            <UserPlus className="h-5 w-5 text-accent" aria-hidden="true" />
            <p className="mt-3 text-sm font-medium text-ink">
              Сотрудников пока нет
            </p>
            <p className="mt-1 max-w-sm text-xs leading-5 text-muted">
              Добавьте первую учётную запись, чтобы выдать сотруднику ключ доступа.
            </p>
            <button
              type="button"
              onClick={() => setModalOpen(true)}
              className="btn-secondary mt-4"
            >
              <UserPlus className="h-4 w-4" aria-hidden="true" />
              Добавить сотрудника
            </button>
          </div>
        ) : compact ? (
          <div className="mt-6 space-y-3">
            {employees.map((employee) => {
              const roleMeta = EMPLOYEE_ROLE_META[employee.role];
              const canReissue =
                role === 'director' || employee.role !== 'admin';
              const isDeleting = deletingId === employee.id;

              return (
                <article
                  key={employee.id}
                  className="border border-line bg-panel p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex min-w-0 items-center gap-3">
                      <span
                        className="grid h-10 w-10 shrink-0 place-items-center border border-line bg-canvas font-mono text-[10px] font-medium tracking-[0.08em] text-soft"
                        aria-hidden="true"
                      >
                        {getInitials(employee.fullName)}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-ink">
                          {employee.fullName}
                        </p>
                        <p className="mt-1 break-all text-xs text-muted">
                          {employee.email}
                        </p>
                      </div>
                    </div>
                    <span
                      className={`inline-flex shrink-0 items-center gap-2 font-mono text-[9px] uppercase tracking-[0.08em] ${roleMeta.text}`}
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 ${roleMeta.dot}`}
                        aria-hidden="true"
                      />
                      {roleMeta.label}
                    </span>
                  </div>

                  <div className="mt-3">
                    <InvitationLine employee={employee} />
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                    <code
                      className="border border-line bg-deep px-2 py-1 font-mono text-xs tracking-[0.12em] text-faint"
                      title="Ключ хранится только в виде хеша"
                    >
                      {maskAccessKey()}
                    </code>
                    <button
                      type="button"
                      onClick={() => void handleReissue(employee)}
                      disabled={busyId !== null || deletingId !== null || !canReissue}
                      aria-label={`Перевыпустить ключ: ${employee.fullName}`}
                      title={
                        canReissue
                          ? undefined
                          : 'Ключи администраторов перевыпускает только директор'
                      }
                      className="inline-flex h-11 items-center gap-1.5 border border-line px-3 font-mono text-[9px] uppercase tracking-[0.08em] text-muted transition-colors hover:border-line-strong hover:text-ink disabled:opacity-50"
                    >
                      <RefreshCw
                        className={`h-3 w-3 ${
                          busyId === employee.id ? 'animate-spin' : ''
                        }`}
                        aria-hidden="true"
                      />
                      Перевыпустить
                    </button>
                    <button
                      type="button"
                      onClick={(event) => handleDelete(employee, event.currentTarget)}
                      disabled={busyId !== null || deletingId !== null}
                      aria-label={`Удалить сотрудника: ${employee.fullName}`}
                      aria-busy={isDeleting}
                      className="inline-flex h-11 items-center gap-1.5 border border-danger/25 px-3 font-mono text-[9px] uppercase tracking-[0.08em] text-danger transition-colors hover:border-danger/50 disabled:opacity-50"
                    >
                      {isDeleting ? (
                        <RefreshCw className="h-3 w-3 animate-spin" aria-hidden="true" />
                      ) : (
                        <Trash2 className="h-3 w-3" aria-hidden="true" />
                      )}
                      {isDeleting ? 'Удаляем…' : 'Удалить'}
                    </button>
                  </div>
                  <p className="mt-1.5 font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
                    {keyDateLabel(employee.keyCreatedAt)}
                  </p>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="mt-6 overflow-x-auto border border-line bg-panel">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="table-head bg-raised">
                <tr>
                  <th scope="col" className="px-5 py-3.5 font-medium">
                    ФИО
                  </th>
                  <th scope="col" className="px-5 py-3.5 font-medium">
                    Email
                  </th>
                  <th scope="col" className="px-5 py-3.5 font-medium">
                    Роль
                  </th>
                  <th scope="col" className="px-5 py-3.5 font-medium">
                    Ключ доступа
                  </th>
                  <th scope="col" className="px-5 py-3.5 font-medium">
                    Действия
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {employees.map((employee) => {
                  const roleMeta = EMPLOYEE_ROLE_META[employee.role];
                  const canReissue =
                    role === 'director' || employee.role !== 'admin';
                  const isDeleting = deletingId === employee.id;

                  return (
                    <tr
                      key={employee.id}
                      className="transition-colors duration-150 hover:bg-ink/[0.025]"
                    >
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <span
                            className="grid h-10 w-10 shrink-0 place-items-center border border-line bg-canvas font-mono text-[10px] font-medium tracking-[0.08em] text-soft"
                            aria-hidden="true"
                          >
                            {getInitials(employee.fullName)}
                          </span>
                          <div className="min-w-0">
                            <p className="font-medium text-ink">
                              {employee.fullName}
                            </p>
                            <p className="mt-1 font-mono text-[9px] tracking-[0.1em] text-faint">
                              {employee.id}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <p className="text-muted">{employee.email}</p>
                        <div className="mt-1.5">
                          <InvitationLine employee={employee} />
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <span
                          className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] ${roleMeta.text}`}
                        >
                          <span
                            className={`h-1.5 w-1.5 shrink-0 ${roleMeta.dot}`}
                            aria-hidden="true"
                          />
                          {roleMeta.label}
                        </span>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <code
                            className="border border-line bg-deep px-2 py-1 font-mono text-xs tracking-[0.12em] text-faint"
                            title="Ключ хранится только в виде хеша"
                          >
                            {maskAccessKey()}
                          </code>
                          <p className="font-mono text-[9px] uppercase tracking-[0.08em] text-faint">
                            {keyDateLabel(employee.keyCreatedAt)}
                          </p>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void handleReissue(employee)}
                            disabled={busyId !== null || deletingId !== null || !canReissue}
                            aria-label={`Перевыпустить ключ: ${employee.fullName}`}
                            title={
                              canReissue
                                ? undefined
                                : 'Ключи администраторов перевыпускает только директор'
                            }
                            className="inline-flex h-11 items-center gap-1.5 border border-line px-3 font-mono text-[9px] uppercase tracking-[0.08em] text-muted transition-colors hover:border-line-strong hover:text-ink disabled:opacity-50"
                          >
                            <RefreshCw
                              className={`h-3 w-3 ${
                                busyId === employee.id ? 'animate-spin' : ''
                              }`}
                              aria-hidden="true"
                            />
                            Перевыпустить
                          </button>
                          <button
                            type="button"
                            onClick={(event) => handleDelete(employee, event.currentTarget)}
                            disabled={busyId !== null || deletingId !== null}
                            aria-label={`Удалить сотрудника: ${employee.fullName}`}
                            aria-busy={isDeleting}
                            className="inline-flex h-11 items-center gap-1.5 border border-danger/25 px-3 font-mono text-[9px] uppercase tracking-[0.08em] text-danger transition-colors hover:border-danger/50 disabled:opacity-50"
                          >
                            {isDeleting ? (
                              <RefreshCw className="h-3 w-3 animate-spin" aria-hidden="true" />
                            ) : (
                              <Trash2 className="h-3 w-3" aria-hidden="true" />
                            )}
                            {isDeleting ? 'Удаляем…' : 'Удалить'}
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="mt-3 flex flex-col gap-2 text-[11px] text-faint sm:flex-row sm:items-center sm:justify-between">
          <p>Показано {employees.length} сотрудников</p>
          <p>
            {API_CONFIG.useMock
              ? 'Демо-справочник · в localStorage только PBKDF2-хеши, письма — в mock-outbox'
              : 'Данные загружены из employee API · ключи и их хеши не возвращаются в интерфейс'}
          </p>
        </div>
      </section>

      {modalOpen ? (
        <AddEmployeeModal
          existingEmails={existingEmails}
          canCreateAdmin={role === 'director'}
          restoreFocus={() => addEmployeeButtonRef.current?.focus()}
          onClose={closeModal}
          onCreated={handleCreated}
        />
      ) : null}

      {delivery ? (
        <KeyDeliveryDialog
          employee={delivery.employee}
          invitation={delivery.invitation}
          restoreFocus={() => addEmployeeButtonRef.current?.focus()}
          onClose={closeDelivery}
        />
      ) : null}

      {deleteTarget ? (
        <DeleteEmployeeDialog
          employee={deleteTarget}
          deleting={deletingId === deleteTarget.id}
          error={deleteError}
          restoreFocus={() => {
            const trigger = deleteTriggerRef.current;
            if (trigger?.isConnected) {
              trigger.focus();
            } else {
              staffHeadingRef.current?.focus();
            }
          }}
          onClose={closeDeleteDialog}
          onConfirm={() => void confirmDelete()}
        />
      ) : null}
    </div>
  );
}
