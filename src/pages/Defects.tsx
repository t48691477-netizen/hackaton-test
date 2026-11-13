import { useEffect, useMemo, useState } from 'react';
import { ExternalLink, RefreshCw } from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import {
  API_CONFIG,
  fetchEquipment,
  fetchReports,
  subscribeToReportChanges,
} from '../lib/api';
import {
  type EquipmentSummary,
  type Report,
  type ReportStatus,
  type Severity,
} from '../lib/inspection';
import { useMediaQuery } from '../lib/useMediaQuery';

const SEVERITY_META: Record<
  Severity,
  { label: string; dot: string; text: string }
> = {
  high: {
    label: 'Критический',
    dot: 'bg-danger',
    text: 'text-danger',
  },
  medium: {
    label: 'Внимание',
    dot: 'bg-warn',
    text: 'text-warn',
  },
  low: {
    label: 'Наблюдение',
    dot: 'bg-info',
    text: 'text-info',
  },
};

const STATUS_META: Record<
  ReportStatus,
  { label: string; dot: string; text: string }
> = {
  open: {
    label: 'Открыт',
    dot: 'bg-danger',
    text: 'text-danger',
  },
  in_progress: {
    label: 'В работе',
    dot: 'bg-warn',
    text: 'text-warn',
  },
  closed: {
    label: 'Выполнено',
    dot: 'bg-ok',
    text: 'text-ok',
  },
};

function formatCount(value: number): string {
  return String(value).padStart(2, '0');
}

function getErrorMessage(error: unknown): string {
  return error instanceof Error ? error.message : 'Проверьте подключение к API.';
}

function formatTime(value: string): string {
  const date = new Date(value);

  return Number.isNaN(date.getTime())
    ? '—'
    : date.toLocaleTimeString('ru-RU', {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'UTC',
      });
}

const SEVERITY_ORDER: Record<Severity, number> = { low: 0, medium: 1, high: 2 };

export function Defects() {
  const compact = useMediaQuery('(max-width: 1023px)');
  const [reports, setReports] = useState<Report[]>([]);
  const [equipment, setEquipment] = useState<EquipmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadAttempt, setLoadAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    Promise.all([fetchReports(), fetchEquipment()])
      .then(([nextReports, nextEquipment]) => {
        if (!active) return;

        setReports(nextReports);
        setEquipment(nextEquipment);
      })
      .catch((reason: unknown) => {
        if (active) setError(getErrorMessage(reason));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => { active = false; };
  }, [loadAttempt]);

  useEffect(() => {
    const refresh = () => setLoadAttempt((value) => value + 1);
    const unsubscribe = subscribeToReportChanges(refresh);

    window.addEventListener('focus', refresh);

    return () => {
      unsubscribe();
      window.removeEventListener('focus', refresh);
    };
  }, []);

  const defects = useMemo(() => {
    const equipmentById = new Map(equipment.map((item) => [item.id, item]));

    return [...reports]
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))
      .map((report) => {
        const item = equipmentById.get(report.equipment_id)
          ?? (report.result.equipment.id === report.equipment_id
            ? report.result.equipment
            : null);
        const primaryDefect = [...report.result.defects].sort(
          (a, b) => SEVERITY_ORDER[b.severity] - SEVERITY_ORDER[a.severity],
        )[0];

        return {
          id: report.id,
          title: primaryDefect?.label || report.result.summary || 'Дефекты не обнаружены',
          equipment: item?.name ?? report.equipment_id,
          area: item?.location ?? 'Локация не указана',
          severity: report.result.llm.criticality,
          status: report.status,
          assignee: report.assignee?.full_name ?? null,
          createdAt: report.created_at,
          time: formatTime(report.created_at),
        };
      });
  }, [reports, equipment]);

  const critical = defects.filter(
    (defect) => defect.severity === 'high',
  ).length;
  const inProgress = defects.filter(
    (defect) => defect.status === 'in_progress',
  ).length;
  const closed = defects.filter((defect) => defect.status === 'closed').length;
  const countLabel = (value: number) => loading || error ? '—' : formatCount(value);

  const summary = [
    { label: 'Всего заявок', value: defects.length, tone: 'text-ink' },
    { label: 'Критические', value: critical, tone: 'text-danger' },
    { label: 'В работе', value: inProgress, tone: 'text-warn' },
    { label: 'Выполнено', value: closed, tone: 'text-ok' },
  ];

  return (
    <div className="space-y-10" data-mock={API_CONFIG.useMock ? 'api' : undefined}>
      <PageHeader
        index="02"
        label="Оперативный контроль"
        title="Панель диспетчера"
        description="Открытые и закрытые дефекты с мобильных сканов. Сортировка по времени обнаружения."
        aside={
          <div className="flex items-end gap-6">
            <div>
              <p className="technical">Критические</p>
              <p className="mt-1 font-mono text-4xl leading-none tracking-[-0.04em] text-danger tabular">
                {countLabel(critical)}
              </p>
            </div>
            <span className="tag border-warn/30 bg-warn/5 text-warn">
              <span className="h-1.5 w-1.5 bg-warn" aria-hidden="true" />
              {API_CONFIG.useMock ? 'Демо-режим' : 'Данные API'}
            </span>
          </div>
        }
      />

      <section aria-label="Сводка по дефектам">
        <div className="grid grid-cols-2 gap-px border-y border-line bg-line sm:grid-cols-4">
          {summary.map((item) => (
            <div key={item.label} className="bg-panel px-5 py-6">
              <p className="technical">{item.label}</p>
              <p
                className={`mt-2 font-mono text-[2.25rem] leading-none tracking-[-0.04em] tabular ${item.tone}`}
              >
                {countLabel(item.value)}
              </p>
            </div>
          ))}
        </div>
      </section>

      <section aria-labelledby="defects-heading">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2
              id="defects-heading"
              className="text-2xl font-medium tracking-[-0.025em] text-ink"
            >
              Последние дефекты
            </h2>
            <p className="mt-1.5 text-sm text-muted">
              Сортировка по времени обнаружения. Время указано в UTC.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-secondary min-h-11 px-3 text-xs"
              onClick={() => setLoadAttempt((value) => value + 1)}
              disabled={loading}
              aria-busy={loading}
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`}
                aria-hidden="true"
              />
              Обновить
            </button>
            <span className="tag w-fit border-line text-muted">
              {countLabel(defects.length)} заявок
            </span>
          </div>
        </div>

        {compact ? (
          <div className="mt-6 space-y-3" aria-busy={loading}>
            {loading ? (
              <p
                role="status"
                className="border border-line bg-panel px-5 py-12 text-center text-muted"
              >
                Загрузка отчётов…
              </p>
            ) : error ? (
              <div
                role="alert"
                className="flex flex-col gap-4 border border-line bg-panel p-5"
              >
                <p className="text-danger">
                  Не удалось загрузить данные. {error}
                </p>
                <button
                  type="button"
                  className="btn-secondary w-full"
                  onClick={() => setLoadAttempt((value) => value + 1)}
                >
                  Повторить
                </button>
              </div>
            ) : defects.length === 0 ? (
              <p
                role="status"
                className="border border-line bg-panel px-5 py-12 text-center text-muted"
              >
                Отчётов пока нет. Они появятся после сохранения результатов
                сканирования.
              </p>
            ) : (
              defects.map((defect) => {
                const severity = SEVERITY_META[defect.severity];
                const status = STATUS_META[defect.status];

                return (
                  <article
                    key={defect.id}
                    className="border border-line bg-panel p-4"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-ink">{defect.title}</p>
                        <p className="mt-1 break-all font-mono text-[10px] tracking-[0.08em] text-faint">
                          {defect.id}
                        </p>
                      </div>
                      <span
                        className={`inline-flex shrink-0 items-center gap-2 font-mono text-[9px] uppercase tracking-[0.08em] ${severity.text}`}
                      >
                        <span
                          className={`h-1.5 w-1.5 shrink-0 ${severity.dot}`}
                          aria-hidden="true"
                        />
                        {severity.label}
                      </span>
                    </div>

                    <dl className="mt-3 divide-y divide-line border-y border-line">
                      <div className="flex items-center justify-between gap-4 py-2.5">
                        <dt className="technical">Оборудование</dt>
                        <dd className="min-w-0 text-right text-xs text-soft">
                          {defect.equipment}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-4 py-2.5">
                        <dt className="technical">Локация</dt>
                        <dd className="min-w-0 text-right text-xs text-faint">
                          {defect.area}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-4 py-2.5">
                        <dt className="technical">Статус</dt>
                        <dd
                          className={`inline-flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.08em] ${status.text}`}
                        >
                          <span
                            className={`h-1.5 w-1.5 shrink-0 ${status.dot}`}
                            aria-hidden="true"
                          />
                          {status.label}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-4 py-2.5">
                        <dt className="technical">Исполнитель</dt>
                        <dd className="text-right text-xs">
                          {defect.assignee ? (
                            <span className="text-soft">{defect.assignee}</span>
                          ) : (
                            <span className="text-faint" data-mock="assignee">
                              Не назначен
                            </span>
                          )}
                        </dd>
                      </div>
                      <div className="flex items-center justify-between gap-4 py-2.5">
                        <dt className="technical">Время</dt>
                        <dd className="font-mono text-xs text-faint tabular">
                          <time
                            dateTime={defect.createdAt}
                            title={defect.createdAt}
                          >
                            {defect.time}
                          </time>
                        </dd>
                      </div>
                    </dl>

                    <a
                      href={`/task/${defect.id}`}
                      target="_blank"
                      rel="noreferrer"
                      aria-label={`Открыть задачу ${defect.id}`}
                      className="btn-secondary mt-3 w-full"
                    >
                      Открыть задачу
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                    </a>
                  </article>
                );
              })
            )}
          </div>
        ) : (
        <div className="mt-6 overflow-x-auto border border-line bg-panel" aria-busy={loading}>
          <table className="w-full min-w-[860px] text-left text-sm" aria-labelledby="defects-heading">
            <thead className="table-head bg-raised">
              <tr>
                <th scope="col" className="px-5 py-3.5 font-medium">
                  Дефект
                </th>
                <th scope="col" className="px-5 py-3.5 font-medium">
                  Оборудование
                </th>
                <th scope="col" className="px-5 py-3.5 font-medium">
                  Приоритет
                </th>
                <th scope="col" className="px-5 py-3.5 font-medium">
                  Статус
                </th>
                <th scope="col" className="px-5 py-3.5 font-medium">
                  Исполнитель
                </th>
                <th scope="col" className="px-5 py-3.5 text-right font-medium">
                  Время
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {loading ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-muted">
                    <p role="status">Загрузка отчётов…</p>
                  </td>
                </tr>
              ) : error ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8">
                    <div role="alert" className="flex flex-wrap items-center justify-between gap-4">
                      <p className="text-danger">Не удалось загрузить данные. {error}</p>
                      <button type="button" className="btn-secondary" onClick={() => setLoadAttempt((value) => value + 1)}>
                        Повторить
                      </button>
                    </div>
                  </td>
                </tr>
              ) : defects.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-12 text-center text-muted">
                    <p role="status">Отчётов пока нет. Они появятся после сохранения результатов сканирования.</p>
                  </td>
                </tr>
              ) : defects.map((defect) => {
                const severity = SEVERITY_META[defect.severity];
                const status = STATUS_META[defect.status];

                return (
                  <tr
                    key={defect.id}
                    className="group transition-colors duration-150 hover:bg-ink/[0.025]"
                  >
                    <td className="px-5 py-4">
                      <p className="font-medium text-ink">{defect.title}</p>
                      <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <p className="font-mono text-[10px] tracking-[0.08em] text-faint">
                          {defect.id}
                        </p>
                        <a
                          href={`/task/${defect.id}`}
                          target="_blank"
                          rel="noreferrer"
                          aria-label={`Открыть задачу ${defect.id}`}
                          className="inline-flex min-h-11 items-center gap-1 py-2 pr-2 font-mono text-[11px] uppercase tracking-[0.06em] text-soft underline-offset-2 transition-colors hover:text-ink hover:underline"
                        >
                          Открыть
                          <ExternalLink className="h-3 w-3" aria-hidden="true" />
                        </a>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <p className="text-soft">{defect.equipment}</p>
                      <p className="mt-1 text-xs text-faint">{defect.area}</p>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] ${severity.text}`}
                      >
                        <span
                          className={`h-1.5 w-1.5 shrink-0 ${severity.dot}`}
                          aria-hidden="true"
                        />
                        {severity.label}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.1em] ${status.text}`}
                      >
                        <span
                          className={`h-1.5 w-1.5 shrink-0 ${status.dot}`}
                          aria-hidden="true"
                        />
                        {status.label}
                      </span>
                    </td>
                    <td className="px-5 py-4">
                      {defect.assignee ? (
                        <span className="text-soft">{defect.assignee}</span>
                      ) : (
                        <span className="text-faint" data-mock="assignee">
                          Не назначен
                        </span>
                      )}
                    </td>
                    <td className="px-5 py-4 text-right font-mono text-xs text-faint tabular">
                      <time dateTime={defect.createdAt} title={defect.createdAt}>{defect.time}</time>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        )}

        <p className="mt-3 text-[11px] text-faint" data-mock="assignee-note">
          {API_CONFIG.useMock ? 'Демо-данные API. ' : ''}
          Исполнитель приходит из задачи. «Не назначен» — только для задач без назначения.
        </p>
      </section>
    </div>
  );
}
