import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  Crosshair,
  Loader2,
  MapPin,
  Play,
  RefreshCw,
  UserRound,
  Wrench,
} from 'lucide-react';
import { BrandMark } from '../components/Brand';
import {
  API_CONFIG,
  fetchReportById,
  updateReportStatus,
} from '../lib/api';
import {
  getEquipmentNode,
  type Defect,
  type Report,
  type ReportStatus,
  type Severity,
} from '../lib/inspection';

const STATUS_META: Record<
  ReportStatus,
  { label: string; tag: string; dot: string }
> = {
  open: {
    label: 'Открыта',
    tag: 'border-accent/30 bg-accent/[0.06] text-accent',
    dot: 'bg-accent',
  },
  in_progress: {
    label: 'В работе',
    tag: 'border-warn/30 bg-warn/5 text-warn',
    dot: 'bg-warn',
  },
  closed: {
    label: 'Выполнена',
    tag: 'border-ok/30 bg-ok/5 text-ok',
    dot: 'bg-ok',
  },
};

const SEVERITY_META: Record<
  Severity,
  { label: string; text: string; dot: string }
> = {
  high: { label: 'Критический', text: 'text-danger', dot: 'bg-danger' },
  medium: { label: 'Внимание', text: 'text-warn', dot: 'bg-warn' },
  low: { label: 'Наблюдение', text: 'text-info', dot: 'bg-info' },
};

const SEVERITY_ORDER: Record<Severity, number> = {
  low: 0,
  medium: 1,
  high: 2,
};

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  timeZone: 'UTC',
});

function formatDateTime(value: string | null): string {
  if (!value) {
    return '—';
  }

  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? '—'
    : DATE_TIME_FORMATTER.format(date);
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim()
    ? error.message
    : 'Проверьте подключение к API и повторите попытку.';
}

function isNotFoundError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'status' in error &&
    error.status === 404
  );
}

function getInitials(fullName: string): string {
  const [firstName, lastName] = fullName.trim().split(/\s+/);
  return `${firstName?.[0] ?? ''}${lastName?.[0] ?? ''}`.toUpperCase();
}

function getPrimaryDefect(defects: Defect[]): Defect | null {
  return (
    [...defects].sort(
      (a, b) =>
        SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity] ||
        b.confidence - a.confidence,
    )[0] ?? null
  );
}

function getRecommendations(
  report: Report,
  primaryDefect: Defect | null,
): string[] {
  const steps = [...report.result.llm.recommendation_steps];

  if (primaryDefect?.recommendation) {
    steps.push(primaryDefect.recommendation);
  }

  const seen = new Set<string>();

  return steps
    .map((step) => step.trim())
    .filter((step) => {
      if (!step || seen.has(step)) {
        return false;
      }

      seen.add(step);
      return true;
    });
}

function StatusTag({ status }: { status: ReportStatus }) {
  const meta = STATUS_META[status];

  return (
    <span className={`tag ${meta.tag}`} data-status={status}>
      <span className={`h-1.5 w-1.5 ${meta.dot}`} aria-hidden="true" />
      {meta.label}
    </span>
  );
}

export function Task() {
  const { id } = useParams<{ id: string }>();
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<{
    message: string;
    notFound: boolean;
  } | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const [action, setAction] = useState<'idle' | 'starting' | 'closing'>('idle');
  const [actionError, setActionError] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [announcement, setAnnouncement] = useState('');

  useEffect(() => {
    let active = true;

    setLoading(true);
    setLoadError(null);
    setReport(null);
    setActionError(null);
    setComment('');
    setAnnouncement('');

    if (!id) {
      setLoadError({
        message: 'В адресе нет идентификатора задачи.',
        notFound: true,
      });
      setLoading(false);

      return () => {
        active = false;
      };
    }

    fetchReportById(id)
      .then((nextReport) => {
        if (active) {
          setReport(nextReport);
        }
      })
      .catch((reason: unknown) => {
        if (!active) {
          return;
        }

        setLoadError({
          message: getErrorMessage(reason),
          notFound: isNotFoundError(reason),
        });
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [id, loadAttempt]);

  const handleStart = async () => {
    if (!id || action !== 'idle') {
      return;
    }

    setAction('starting');
    setActionError(null);

    try {
      const nextReport = await updateReportStatus(id, 'in_progress');
      setReport(nextReport);
      setAnnouncement('Статус задачи: в работе.');
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason));
    } finally {
      setAction('idle');
    }
  };

  const handleComplete = async () => {
    if (!id || action !== 'idle') {
      return;
    }

    setAction('closing');
    setActionError(null);
    const trimmedComment = comment.trim();

    try {
      const nextReport = await updateReportStatus(
        id,
        'closed',
        trimmedComment || undefined,
      );
      setReport(nextReport);
      setAnnouncement('Статус задачи: выполнена.');
    } catch (reason: unknown) {
      setActionError(getErrorMessage(reason));
    } finally {
      setAction('idle');
    }
  };

  const retryAction = () => {
    if (!report || action !== 'idle') {
      return;
    }

    if (report.status === 'open') {
      void handleStart();
    } else if (report.status === 'in_progress') {
      void handleComplete();
    }
  };

  const primaryDefect = report
    ? getPrimaryDefect(report.result.defects)
    : null;
  const node =
    report && primaryDefect
      ? getEquipmentNode(report.result.equipment, primaryDefect.node_id)
      : null;
  const recommendations = report
    ? getRecommendations(report, primaryDefect)
    : [];

  return (
    <div
      className="min-h-dvh bg-canvas sm:px-5 sm:py-8"
      data-mock={API_CONFIG.useMock ? 'task' : undefined}
      data-api="GET /api/reports/{id}"
    >
      <div className="mx-auto flex min-h-dvh w-full max-w-[560px] flex-col border-line bg-panel sm:min-h-[calc(100dvh-4rem)] sm:border">
        <div className="h-0.5 w-full bg-accent" aria-hidden="true" />

        <header className="border-b border-line px-5 pb-6 pt-5 sm:px-7">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-center gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center border border-line-strong text-accent">
                <BrandMark />
              </span>
              <span className="min-w-0">
                <span className="block text-[13px] font-semibold leading-none tracking-[0.055em] text-ink">
                  ПРОМСКАН
                </span>
                <span className="mt-1.5 block font-mono text-[8px] uppercase leading-none tracking-[0.2em] text-faint">
                  mobile task
                </span>
              </span>
            </div>

            {report ? (
              <StatusTag status={report.status} />
            ) : (
              <span className="tag border-line text-faint">
                {loading ? 'Загрузка' : 'Нет данных'}
              </span>
            )}
          </div>

          <div className="mt-8 border-t border-line pt-5">
            <p className="eyebrow">Мобильное рабочее место</p>
            <h1 className="mt-2 text-[1.9rem] font-medium leading-[1.05] tracking-[-0.045em] text-ink">
              Задание сотруднику
            </h1>
          </div>
        </header>

        <main className="flex-1 px-5 py-6 sm:px-7">
          {loading ? (
            <div
              role="status"
              aria-live="polite"
              className="flex min-h-[320px] flex-col items-center justify-center gap-4 px-6 py-16 text-center"
            >
              <Loader2
                className="h-6 w-6 animate-spin text-accent"
                aria-hidden="true"
              />
              <div>
                <p className="technical">Загрузка</p>
                <p className="mt-2 text-sm text-muted">Получаем задание…</p>
              </div>
            </div>
          ) : loadError ? (
            <div
              role="alert"
              className="border border-danger/30 bg-danger/[0.04] p-5"
            >
              <div className="flex items-start gap-3">
                <AlertCircle
                  className="mt-0.5 h-5 w-5 shrink-0 text-danger"
                  aria-hidden="true"
                />
                <div>
                  <h2 className="text-lg font-medium tracking-[-0.02em] text-ink">
                    {loadError.notFound
                      ? 'Задача не найдена'
                      : 'Не удалось загрузить задание'}
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-muted">
                    {loadError.message}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setLoadAttempt((value) => value + 1)}
                className="btn-primary mt-5 w-full"
              >
                <RefreshCw className="h-4 w-4" aria-hidden="true" />
                Повторить
              </button>
            </div>
          ) : report ? (
            <>
              <p className="sr-only" role="status" aria-live="polite">
                {announcement}
              </p>

              <div className="flex items-center justify-between gap-4 border-b border-line pb-4">
                <span className="technical">ID задачи</span>
                <code className="font-mono text-xs text-soft">{report.id}</code>
              </div>

              <div className="mt-6 space-y-7">
                <section
                  aria-labelledby="task-equipment-heading"
                  className="border-b border-line pb-6"
                >
                  <h2 id="task-equipment-heading" className="technical">
                    Оборудование
                  </h2>
                  <p className="mt-3 text-xl font-medium leading-tight tracking-[-0.025em] text-ink">
                    {report.result.equipment.name}
                  </p>
                  <div className="mt-3 space-y-2 text-sm text-muted">
                    <p className="font-mono text-xs text-soft">
                      Инв. № {report.result.equipment.inventory_number}
                    </p>
                    <p className="flex items-start gap-2">
                      <MapPin
                        className="mt-0.5 h-4 w-4 shrink-0 text-faint"
                        aria-hidden="true"
                      />
                      <span>{report.result.equipment.location}</span>
                    </p>
                  </div>
                </section>

                <section aria-labelledby="task-defect-heading">
                  <div className="flex items-center justify-between gap-3">
                    <h2 id="task-defect-heading" className="technical">
                      Дефект
                    </h2>
                    {primaryDefect ? (
                      <span
                        className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] ${SEVERITY_META[primaryDefect.severity].text}`}
                      >
                        <span
                          className={`h-1.5 w-1.5 shrink-0 ${SEVERITY_META[primaryDefect.severity].dot}`}
                          aria-hidden="true"
                        />
                        {SEVERITY_META[primaryDefect.severity].label}
                      </span>
                    ) : null}
                  </div>

                  {primaryDefect ? (
                    <div className="mt-3 border border-line bg-raised px-4 py-4">
                      <p className="text-base font-medium text-ink">
                        {primaryDefect.label}
                      </p>
                      <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
                        Уверенность ·{' '}
                        {Math.round(primaryDefect.confidence * 100)}%
                      </p>
                    </div>
                  ) : (
                    <p className="mt-3 text-sm leading-6 text-muted">
                      Дефект не указан в результате осмотра.
                    </p>
                  )}

                  <div className="mt-3 flex items-start gap-3 border border-line px-4 py-3">
                    <Crosshair
                      className="mt-1 h-4 w-4 shrink-0 text-faint"
                      aria-hidden="true"
                    />
                    <div className="min-w-0">
                      <p className="technical">Узел</p>
                      <p className="mt-1 text-sm text-soft">
                        {node?.name ?? 'Не указан'}
                      </p>
                    </div>
                  </div>
                </section>

                <section aria-labelledby="task-recommendation-heading">
                  <h2
                    id="task-recommendation-heading"
                    className="technical flex items-center gap-2"
                  >
                    <Wrench
                      className="h-3.5 w-3.5 text-accent"
                      aria-hidden="true"
                    />
                    Рекомендация по восстановлению
                  </h2>

                  {recommendations.length > 0 ? (
                    <ol className="mt-3 divide-y divide-line border-y border-line">
                      {recommendations.map((step, index) => (
                        <li
                          key={`${index}-${step}`}
                          className="flex gap-4 py-3"
                        >
                          <span className="shrink-0 font-mono text-[10px] leading-6 tracking-[0.1em] text-accent tabular">
                            {String(index + 1).padStart(2, '0')}
                          </span>
                          <p className="text-sm leading-6 text-soft">{step}</p>
                        </li>
                      ))}
                    </ol>
                  ) : (
                    <p className="mt-3 text-sm leading-6 text-muted">
                      Рекомендации не указаны.
                    </p>
                  )}
                </section>

                <section aria-labelledby="task-assignee-heading">
                  <h2 id="task-assignee-heading" className="technical">
                    Исполнитель
                  </h2>

                  {report.assignee ? (
                    <div className="mt-3 flex items-center gap-3">
                      <span
                        className="grid h-10 w-10 shrink-0 place-items-center border border-line bg-canvas font-mono text-[10px] font-medium tracking-[0.08em] text-soft"
                        aria-hidden="true"
                      >
                        {getInitials(report.assignee.full_name)}
                      </span>
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink">
                          {report.assignee.full_name}
                        </p>
                        <p className="mt-1 font-mono text-[9px] tracking-[0.1em] text-faint">
                          {report.assignee.id}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="mt-3 flex items-start gap-3 border border-warn/25 bg-warn/[0.04] px-4 py-3">
                      <UserRound
                        className="mt-0.5 h-4 w-4 shrink-0 text-warn"
                        aria-hidden="true"
                      />
                      <p className="text-sm font-medium text-ink">
                        Не назначен
                      </p>
                    </div>
                  )}
                </section>

                <section aria-labelledby="task-timeline-heading">
                  <div className="flex items-baseline justify-between gap-3">
                    <h2 id="task-timeline-heading" className="technical">
                      Хронология
                    </h2>
                    <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
                      UTC
                    </span>
                  </div>

                  <dl className="mt-3 divide-y divide-line border-y border-line">
                    {[
                      { label: 'Создана', value: report.created_at },
                      { label: 'Начата', value: report.started_at },
                      { label: 'Завершена', value: report.completed_at },
                    ].map((item) => (
                      <div
                        key={item.label}
                        className="flex items-center justify-between gap-4 py-3"
                      >
                        <dt className="text-sm text-muted">{item.label}</dt>
                        <dd className="font-mono text-xs text-soft tabular">
                          {item.value ? (
                            <time
                              dateTime={item.value}
                              title={item.value}
                            >
                              {formatDateTime(item.value)}
                            </time>
                          ) : (
                            '—'
                          )}
                        </dd>
                      </div>
                    ))}
                  </dl>
                </section>

                {report.status === 'closed' ? (
                  <section
                    aria-labelledby="task-completed-heading"
                    className="border border-ok/30 bg-ok/[0.05] p-5"
                  >
                    <div className="flex items-start gap-3">
                      <CheckCircle2
                        className="mt-0.5 h-5 w-5 shrink-0 text-ok"
                        aria-hidden="true"
                      />
                      <div>
                        <h2
                          id="task-completed-heading"
                          className="text-lg font-medium tracking-[-0.02em] text-ink"
                        >
                          Задача выполнена
                        </h2>
                        <p className="mt-1.5 text-sm leading-6 text-muted">
                          {report.completed_at
                            ? `Завершена ${formatDateTime(report.completed_at)}`
                            : 'Завершена'}
                        </p>
                      </div>
                    </div>

                    {report.repair_comment ? (
                      <div className="mt-4 border-t border-ok/20 pt-4">
                        <p className="technical">Комментарий к выполнению</p>
                        <p className="mt-2 text-sm leading-6 text-soft">
                          {report.repair_comment}
                        </p>
                      </div>
                    ) : null}
                  </section>
                ) : (
                  <section
                    aria-labelledby="task-actions-heading"
                    aria-busy={action !== 'idle'}
                    className="border-t border-line pt-6"
                  >
                    <h2 id="task-actions-heading" className="technical">
                      Действия
                    </h2>

                    {actionError ? (
                      <div
                        role="alert"
                        className="mt-3 border border-danger/30 bg-danger/[0.04] p-4"
                      >
                        <div className="flex items-start gap-2.5">
                          <AlertCircle
                            className="mt-0.5 h-4 w-4 shrink-0 text-danger"
                            aria-hidden="true"
                          />
                          <p className="text-sm leading-5 text-danger">
                            Не удалось изменить статус. {actionError}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={retryAction}
                          disabled={action !== 'idle'}
                          className="btn-secondary mt-3 h-9 w-full px-3 text-xs"
                        >
                          Повторить
                        </button>
                      </div>
                    ) : null}

                    {report.status === 'open' ? (
                      <>
                        <p className="mt-3 text-sm leading-6 text-muted">
                          Когда будете на месте, начните выполнение — время
                          старта сохранится в задаче.
                        </p>
                        <button
                          type="button"
                          onClick={() => void handleStart()}
                          disabled={action !== 'idle' || !report.assignee}
                          title={
                            report.assignee
                              ? undefined
                              : 'Задачу назначает диспетчер'
                          }
                          aria-describedby={
                            report.assignee ? undefined : 'task-assignee-hint'
                          }
                          aria-busy={action === 'starting'}
                          data-api="PATCH /api/reports/{id}/status"
                          className="btn-primary mt-4 h-12 w-full"
                        >
                          {action === 'starting' ? (
                            <Loader2
                              className="h-4 w-4 animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <Play
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          )}
                          Выполнить задачу
                        </button>
                      </>
                    ) : (
                      <>
                        <label
                          htmlFor="task-comment"
                          className="label mt-4"
                        >
                          Комментарий к выполнению
                        </label>
                        <textarea
                          id="task-comment"
                          name="comment"
                          rows={4}
                          value={comment}
                          onChange={(event) =>
                            setComment(event.target.value)
                          }
                          disabled={action !== 'idle'}
                          aria-describedby="task-comment-hint"
                          placeholder="Что сделано, какие детали заменены"
                          className="input h-auto min-h-[112px] resize-y py-3 leading-6"
                        />
                        <p
                          id="task-comment-hint"
                          className="mt-2 text-[11px] leading-5 text-faint"
                        >
                          Необязательно. Комментарий увидят диспетчер и
                          директор.
                        </p>
                        <button
                          type="button"
                          onClick={() => void handleComplete()}
                          disabled={action !== 'idle' || !report.assignee}
                          title={
                            report.assignee
                              ? undefined
                              : 'Задачу назначает диспетчер'
                          }
                          aria-describedby={
                            report.assignee ? undefined : 'task-assignee-hint'
                          }
                          aria-busy={action === 'closing'}
                          data-api="PATCH /api/reports/{id}/status"
                          className="btn-primary mt-4 h-12 w-full"
                        >
                          {action === 'closing' ? (
                            <Loader2
                              className="h-4 w-4 animate-spin"
                              aria-hidden="true"
                            />
                          ) : (
                            <CheckCircle2
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          )}
                          Отметить выполненной
                        </button>
                      </>
                    )}

                    {!report.assignee ? (
                      <div
                        id="task-assignee-hint"
                        className="mt-3 flex items-start gap-2 border border-warn/25 bg-warn/[0.04] px-3 py-2.5"
                      >
                        <AlertTriangle
                          className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn"
                          aria-hidden="true"
                        />
                        <p className="text-xs leading-5 text-warn">
                          Задачу назначает диспетчер
                        </p>
                      </div>
                    ) : null}
                  </section>
                )}
              </div>
            </>
          ) : null}
        </main>

        <footer className="border-t border-line px-5 py-4 sm:px-7">
          <div className="flex items-center justify-between gap-4 font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
            <span>PSC-02 · мобильное приложение</span>
            <span>{API_CONFIG.useMock ? 'Демо' : 'API'}</span>
          </div>
        </footer>
      </div>
    </div>
  );
}
