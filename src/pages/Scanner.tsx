import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from 'react';
import {
  Camera,
  CameraOff,
  Check,
  ChevronDown,
  Copy,
  Crosshair,
  ExternalLink,
  Gauge,
  Info,
  Loader2,
  MousePointer2,
  RefreshCw,
  RotateCcw,
  Send,
  Upload,
  Wrench,
} from 'lucide-react';
import { PageHeader } from '../components/PageHeader';
import { API_CONFIG, createReport, inspectImage } from '../lib/api';
import {
  EMPLOYEES_CHANGED_EVENT,
  getEngineers,
  loadEmployees,
  type Employee,
} from '../lib/employees';
import {
  getEquipmentNode,
  type Defect,
  type EquipmentNode,
  type InspectionResult,
  type Report,
  type Severity,
  type SpecItem,
} from '../lib/inspection';

type ScannerStatus = 'starting' | 'live' | 'ready' | 'error';

interface Snapshot {
  src: string;
  width: number;
  height: number;
}

const DETECTION_INTERVAL_MS = 1800;
const FIRST_DETECTION_MS = 500;

const STATUS_META: Record<
  ScannerStatus,
  { label: string; dot: string; tag: string }
> = {
  starting: {
    label: 'Подключение камеры',
    dot: 'bg-warn animate-pulse-soft',
    tag: 'border-warn/30 bg-warn/5 text-warn',
  },
  live: {
    label: 'Распознавание активно',
    dot: 'bg-ok animate-pulse-soft',
    tag: 'border-ok/30 bg-ok/5 text-ok',
  },
  ready: {
    label: 'Снимок распознан',
    dot: 'bg-info',
    tag: 'border-info/30 bg-info/5 text-info',
  },
  error: {
    label: 'Камера недоступна',
    dot: 'bg-danger',
    tag: 'border-danger/30 bg-danger/5 text-danger',
  },
};

const SEVERITY_META: Record<
  Severity,
  {
    label: string;
    text: string;
    border: string;
    bar: string;
    dot: string;
    stroke: string;
    fill: string;
  }
> = {
  high: {
    label: 'Критический',
    text: 'text-danger',
    border: 'border-danger',
    bar: 'bg-danger',
    dot: 'bg-danger',
    stroke: 'stroke-danger',
    fill: 'fill-danger/10',
  },
  medium: {
    label: 'Внимание',
    text: 'text-warn',
    border: 'border-warn',
    bar: 'bg-warn',
    dot: 'bg-warn',
    stroke: 'stroke-warn',
    fill: 'fill-warn/10',
  },
  low: {
    label: 'Наблюдение',
    text: 'text-info',
    border: 'border-info',
    bar: 'bg-info',
    dot: 'bg-info',
    stroke: 'stroke-info',
    fill: 'fill-info/10',
  },
};

const DATE_FORMATTER = new Intl.DateTimeFormat('ru-RU', {
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
});

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : DATE_FORMATTER.format(date);
}

function describeCameraError(error: unknown): string {
  const name = error instanceof Error ? error.name : '';

  switch (name) {
    case 'NotAllowedError':
    case 'PermissionDeniedError':
      return 'Доступ к камере запрещён. Разрешите использование камеры в настройках браузера и попробуйте снова.';
    case 'NotFoundError':
    case 'DevicesNotFoundError':
      return 'Камера не найдена. Подключите камеру или загрузите фотографию оборудования.';
    case 'NotReadableError':
    case 'TrackStartError':
      return 'Камера занята другим приложением. Закройте его и повторите попытку.';
    case 'OverconstrainedError':
      return 'Камера не поддерживает запрошенное разрешение. Попробуйте другую камеру.';
    default:
      return 'Не удалось включить камеру. Проверьте разрешения браузера или загрузите фотографию.';
  }
}

function SpecGrid({ specs }: { specs: SpecItem[] }) {
  return (
    <dl className="mt-2 grid grid-cols-1 gap-px border border-line bg-line min-[420px]:grid-cols-2">
      {specs.map((spec) => (
        <div key={spec.label} className="min-w-0 bg-panel px-3 py-2.5">
          <dt className="text-[9px] uppercase leading-4 tracking-[0.1em] text-faint">
            {spec.label}
          </dt>
          <dd className="mt-0.5 break-words font-mono text-xs leading-5 text-ink">
            {spec.value}
            {spec.unit ? (
              <span className="ml-1 text-[10px] text-muted">{spec.unit}</span>
            ) : null}
          </dd>
        </div>
      ))}
    </dl>
  );
}

interface DefectOverlayProps {
  analysis: InspectionResult;
  activeId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onFocus: (id: string | null) => void;
  onSelect: (id: string) => void;
}

function DefectOverlay({
  analysis,
  activeId,
  selectedId,
  onHover,
  onFocus,
  onSelect,
}: DefectOverlayProps) {
  return (
    <div className="absolute inset-0">
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true"
      >
        {analysis.defects.map((defect) => {
          if (!defect.polygon) {
            return null;
          }

          const meta = SEVERITY_META[defect.severity];
          const points = defect.polygon
            .map(([x, y]) => `${x * 100},${y * 100}`)
            .join(' ');

          return (
            <polygon
              key={defect.id}
              points={points}
              className={`${meta.fill} ${
                activeId === defect.id ? 'opacity-100' : 'opacity-60'
              } transition-opacity duration-150`}
            />
          );
        })}
      </svg>

      {analysis.defects.map((defect) => {
        const meta = SEVERITY_META[defect.severity];
        const [x1, y1, x2, y2] = defect.bbox;
        const active = activeId === defect.id;
        const selected = selectedId === defect.id;

        return (
          <button
            key={defect.id}
            type="button"
            className={`absolute cursor-crosshair border bg-transparent text-left transition-colors duration-150 focus-visible:outline-offset-2 ${
              meta.border
            } ${
              active
                ? 'bg-white/10 shadow-[0_0_0_1px_rgba(255,255,255,0.55)]'
                : 'hover:bg-white/[0.06]'
            }`}
            style={{
              left: `${x1 * 100}%`,
              top: `${y1 * 100}%`,
              width: `${(x2 - x1) * 100}%`,
              height: `${(y2 - y1) * 100}%`,
            }}
            onMouseEnter={() => onHover(defect.id)}
            onMouseLeave={() => onHover(null)}
            onFocus={() => onFocus(defect.id)}
            onBlur={() => onFocus(null)}
            onClick={() => onSelect(defect.id)}
            aria-pressed={selected}
            aria-controls="equipment-specs-panel"
            aria-label={`Рамка дефекта: ${defect.label}, уверенность ${Math.round(
              defect.confidence * 100,
            )} процентов`}
          >
            <span
              className={`absolute -top-6 left-0 whitespace-nowrap border bg-canvas/95 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.08em] ${meta.border} ${meta.text}`}
            >
              {defect.label} · {Math.round(defect.confidence * 100)}%
            </span>
          </button>
        );
      })}
    </div>
  );
}

function CameraGuide() {
  return (
    <div className="pointer-events-none absolute inset-0">
      <div className="absolute left-4 top-4 h-9 w-9 border-l border-t border-accent/70" />
      <div className="absolute right-4 top-4 h-9 w-9 border-r border-t border-accent/70" />
      <div className="absolute bottom-4 left-4 h-9 w-9 border-b border-l border-accent/70" />
      <div className="absolute bottom-4 right-4 h-9 w-9 border-b border-r border-accent/70" />

      <div className="absolute inset-0 grid place-items-center">
        <div className="flex items-center gap-3 border border-line bg-canvas/80 px-3 py-2">
          <Crosshair className="h-4 w-4 text-accent" aria-hidden="true" />
          <p className="font-mono text-[9px] font-medium uppercase tracking-[0.16em] text-soft">
            Наведите на оборудование
          </p>
        </div>
      </div>

      <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
        <span className="h-1.5 w-1.5 bg-accent" aria-hidden="true" />
        PSC-02 / демо
      </div>
    </div>
  );
}

function CameraError({
  message,
  onRetry,
  onUpload,
}: {
  message: string | null;
  onRetry: () => void;
  onUpload: () => void;
}) {
  return (
    <div className="flex h-full w-full flex-col items-center justify-center px-6 text-center">
      <div className="grid h-14 w-14 place-items-center border border-danger/30 bg-danger/10 text-danger">
        <CameraOff className="h-6 w-6" aria-hidden="true" />
      </div>
      <p className="mt-4 text-base font-medium text-ink">Камера недоступна</p>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted">
        {message ?? 'Не удалось получить доступ к камере.'}
      </p>
      <div className="mt-5 flex flex-wrap justify-center gap-2">
        <button type="button" onClick={onRetry} className="btn-secondary">
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
          Повторить
        </button>
        <button type="button" onClick={onUpload} className="btn-primary">
          <Upload className="h-4 w-4" aria-hidden="true" />
          Загрузить фото
        </button>
      </div>
      <p className="mt-4 font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
        Камера работает только на HTTPS или localhost
      </p>
    </div>
  );
}

function HowItWorksContent({ status }: { status: ScannerStatus }) {
  const steps = [
    {
      title: 'Наведите камеру',
      text: 'Держите узел в кадре — система распознаёт оборудование автоматически.',
    },
    {
      title: 'Смотрите распознавание',
      text: 'Рамки и маски дефектов обновляются в реальном времени, без отдельной кнопки.',
    },
    {
      title: 'Наведите на дефект',
      text: 'Справа появятся технические характеристики узла и рекомендации по устранению.',
    },
  ];

  return (
    <div>
      <div className="grid gap-8 pb-8 sm:grid-cols-3 sm:gap-10">
        {steps.map((step, index) => (
          <div key={step.title} className="border-t border-line pt-5">
            <p className="font-mono text-[10px] tracking-[0.16em] text-accent">
              0{index + 1}
            </p>
            <h3 className="mt-3 text-lg font-medium tracking-[-0.02em] text-ink">
              {step.title}
            </h3>
            <p className="mt-2 text-sm leading-6 text-muted">{step.text}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-4 border-t border-line pt-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex max-w-xl gap-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-hidden="true" />
          <p className="text-xs leading-5 text-muted">
            <span className="font-medium text-warn">Демо-режим.</span>{' '}
            Распознавание и характеристики симулируются на клиенте. При
            интеграции их заменит POST /api/inspect.
          </p>
        </div>
        <div className="flex items-center gap-3 font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
          Статус камеры
          <span className="text-soft">{STATUS_META[status].label}</span>
        </div>
      </div>
    </div>
  );
}

function ReportCreateForm({
  result,
  snapshotPhoto,
  onCancel,
  engineers,
}: {
  result: InspectionResult;
  snapshotPhoto: Blob | null;
  onCancel: () => void;
  engineers: ReturnType<typeof getEngineers>;
}) {
  const [assigneeId, setAssigneeId] = useState(
    () => engineers[0]?.id ?? '',
  );
  const [comment, setComment] = useState('');
  const [photo, setPhoto] = useState<Blob | null>(snapshotPhoto);
  const [saveState, setSaveState] = useState<
    'idle' | 'saving' | 'saved' | 'error'
  >('idle');
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedReport, setSavedReport] = useState<Report | null>(null);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>(
    'idle',
  );
  const savingRef = useRef(false);
  const saving = saveState === 'saving';
  const saved = saveState === 'saved' && savedReport !== null;
  const canAssign = engineers.length > 0 && Boolean(assigneeId);
  const canCopy =
    typeof navigator !== 'undefined' &&
    typeof navigator.clipboard?.writeText === 'function';
  const taskUrl = savedReport
    ? `${window.location.origin}/task/${savedReport.id}`
    : '';
  const assigneeName =
    savedReport?.assignee?.full_name ??
    engineers.find((employee) => employee.id === assigneeId)?.fullName ??
    'Не назначен';

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (savingRef.current || saved || !canAssign) {
      return;
    }

    savingRef.current = true;
    setSaveState('saving');
    setSaveError(null);

    try {
      const report = await createReport({
        equipmentId: result.equipment.id,
        inspectionId: result.inspection_id,
        status: 'open',
        comment,
        photo,
        result,
        assigneeId,
      });
      setSavedReport(report);
      setSaveState('saved');
    } catch {
      setSaveState('error');
      setSaveError(
        'Не удалось передать задачу. Проверьте подключение и повторите попытку.',
      );
    } finally {
      savingRef.current = false;
    }
  };

  const handleCopy = async () => {
    if (!canCopy || !taskUrl) {
      return;
    }

    try {
      await navigator.clipboard.writeText(taskUrl);
      setCopyState('copied');
    } catch {
      setCopyState('error');
    }
  };

  return (
    <section
      id="report-create-panel"
      aria-labelledby="report-create-heading"
      className="mt-3 border border-line bg-raised p-4"
      data-mock={API_CONFIG.useMock ? 'report-create' : undefined}
      data-api="POST /api/reports"
    >
      <div className="flex items-center justify-between gap-3">
        <h3 id="report-create-heading" className="technical">
          Передача задачи
        </h3>
        {API_CONFIG.useMock ? (
          <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
            mock
          </span>
        ) : null}
      </div>

      <p
        role="status"
        aria-live="polite"
        aria-atomic="true"
        className="mt-2 text-xs leading-5 text-soft"
      >
        {saved
          ? `Задача передана${API_CONFIG.useMock ? ' · mock' : ''}`
          : saving
            ? 'Передача задачи…'
            : 'Задача будет создана со статусом «Открыт» и назначена выбранному сотруднику.'}
      </p>

      {saved && savedReport ? (
        <div className="mt-3 space-y-3">
          <div className="border border-line bg-panel p-3">
            <p className="technical">Исполнитель</p>
            <p className="mt-1 text-sm font-medium text-ink">{assigneeName}</p>
          </div>

          <div className="flex flex-wrap gap-2">
            <a
              href={taskUrl}
              target="_blank"
              rel="noreferrer"
              data-task-link
              className="btn-secondary"
            >
              <ExternalLink className="h-4 w-4" aria-hidden="true" />
              Открыть задачу
            </a>
            {canCopy ? (
              <button
                type="button"
                onClick={() => void handleCopy()}
                className="btn-secondary"
              >
                {copyState === 'copied' ? (
                  <Check className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Copy className="h-4 w-4" aria-hidden="true" />
                )}
                {copyState === 'copied'
                  ? 'Ссылка скопирована'
                  : 'Скопировать ссылку'}
              </button>
            ) : null}
          </div>

          <p className="break-all font-mono text-[10px] leading-4 text-faint">
            {taskUrl}
          </p>

          {copyState === 'error' ? (
            <p role="status" className="text-xs leading-5 text-danger">
              Не удалось скопировать ссылку. Выделите адрес и скопируйте вручную.
            </p>
          ) : null}

          <button type="button" onClick={onCancel} className="btn-secondary">
            Закрыть
          </button>
        </div>
      ) : (
        <form
          onSubmit={(event) => void handleSubmit(event)}
          aria-labelledby="report-create-heading"
          aria-busy={saving}
          className="mt-3 space-y-4"
        >
          <fieldset disabled={saving} className="min-w-0 space-y-4">
            <div>
              <label htmlFor="report-assignee" className="text-xs text-soft">
                Исполнитель
              </label>
              <select
                id="report-assignee"
                value={assigneeId}
                onChange={(event) => setAssigneeId(event.target.value)}
                required
                disabled={!engineers.length}
                className="mt-1.5 min-h-10 w-full border border-line bg-panel px-3 py-2 text-xs text-ink"
                autoFocus
              >
                {engineers.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.fullName}
                  </option>
                ))}
              </select>
              {!engineers.length ? (
                <p className="mt-1.5 text-[10px] leading-4 text-danger">
                  Нет доступных исполнителей — передача задачи недоступна.
                </p>
              ) : null}
            </div>

            <div>
              <label htmlFor="report-comment" className="text-xs text-soft">
                Комментарий
                <span className="ml-1 text-faint">· необязательно</span>
              </label>
              <textarea
                id="report-comment"
                value={comment}
                onChange={(event) => setComment(event.target.value)}
                rows={4}
                className="mt-1.5 w-full resize-y border border-line bg-panel px-3 py-2 text-xs leading-5 text-ink"
              />
            </div>

            <div>
              <label htmlFor="report-photo" className="text-xs text-soft">
                Итоговое фото
                <span className="ml-1 text-faint">· необязательно</span>
              </label>
              <input
                id="report-photo"
                type="file"
                accept="image/*"
                onChange={(event) =>
                  setPhoto(event.target.files?.[0] ?? snapshotPhoto)
                }
                aria-describedby="report-photo-hint"
                className="mt-1.5 block w-full min-w-0 text-xs text-muted file:mr-2 file:border file:border-line file:bg-panel file:px-2 file:py-2 file:text-xs file:text-ink"
              />
              <p id="report-photo-hint" className="mt-1.5 text-[10px] leading-4 text-faint">
                {API_CONFIG.useMock
                  ? 'Демо: фото не отправляется; backend не подключён.'
                  : photo
                    ? 'Фото приложено. Можно выбрать другой снимок.'
                    : 'Можно передать задачу без фото.'}
              </p>
            </div>
          </fieldset>

          {saveError ? (
            <p role="alert" className="text-xs leading-5 text-danger">
              {saveError}
            </p>
          ) : null}

          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onCancel}
              disabled={saving}
              className="btn-secondary w-full sm:w-auto"
            >
              Отмена
            </button>
            <button
              type="submit"
              disabled={saving || !canAssign}
              className="btn-primary w-full sm:w-auto"
              aria-busy={saving}
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              ) : (
                <Send className="h-4 w-4" aria-hidden="true" />
              )}
              {saving
                ? 'Передача задачи…'
                : saveState === 'error'
                  ? 'Повторить сохранение'
                  : 'Передать задачу'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}

interface LiveReportProps {
  analysis: InspectionResult;
  activeDefect: Defect | null;
  activeNode: EquipmentNode | null;
  selectedId: string | null;
  snapshotPhoto: Blob | null;
  engineers: Employee[];
  onHover: (id: string | null) => void;
  onFocus: (id: string | null) => void;
  onSelect: (id: string) => void;
}

function LiveReport({
  analysis,
  activeDefect,
  activeNode,
  selectedId,
  snapshotPhoto,
  engineers,
  onHover,
  onFocus,
  onSelect,
}: LiveReportProps) {
  const [reportResult, setReportResult] = useState<InspectionResult | null>(null);
  const reportButtonRef = useRef<HTMLButtonElement>(null);
  const activeMeta = activeDefect
    ? SEVERITY_META[activeDefect.severity]
    : null;
  const mockSpecs = API_CONFIG.useMock || analysis.meta.vision_mode === 'mock';

  return (
    <div className="animate-fade-in border border-line bg-panel">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3 sm:px-5">
        <span className="eyebrow">Отчёт · live</span>
        <span className="inline-flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
          <span
            className="h-1.5 w-1.5 animate-pulse-soft bg-ok"
            aria-hidden="true"
          />
          vision: {analysis.meta.vision_mode}
        </span>
      </div>

      <div className="p-4 sm:p-5">
        <h2 className="text-lg font-medium leading-tight tracking-[-0.025em] text-ink sm:text-xl">
          {analysis.equipment.name}
        </h2>
        <p className="mt-2 font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
          Инв. № {analysis.equipment.inventory_number} · ресурс{' '}
          {analysis.equipment.service_life_years} лет · ТО{' '}
          {formatDate(analysis.equipment.last_maintenance_at)}
        </p>

        <div className="mt-4 border-l-2 border-accent pl-3 sm:mt-5 sm:pl-4">
          <p className="technical">Сводка</p>
          <p className="mt-2 text-sm leading-6 text-soft">{analysis.summary}</p>
        </div>

        <section
          id="equipment-specs-panel"
          className="mt-6"
          aria-labelledby="specs-heading"
          aria-describedby={mockSpecs ? 'equipment-specs-source' : undefined}
          data-mock={mockSpecs ? 'equipment-specs' : undefined}
          data-equipment-id={analysis.equipment.id}
          data-node-id={activeNode?.id}
        >
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line pb-2">
            <p
              id="specs-heading"
              className="inline-flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.14em] text-ink"
            >
              <Gauge className="h-3.5 w-3.5 text-accent" aria-hidden="true" />
              Технические характеристики
            </p>
            <span className="inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
              <MousePointer2 className="h-3 w-3" aria-hidden="true" />
              {mockSpecs ? 'демо · mock' : 'по наведению'}
            </span>
          </div>

          {mockSpecs ? (
            <p id="equipment-specs-source" className="mt-2 text-[10px] leading-4 text-faint">
              Демо-характеристики узла. После подключения backend здесь будут его
              характеристики, не замеры дефекта.
            </p>
          ) : null}

          {activeDefect && activeMeta ? (
            <div className="mt-3">
              <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
                <div className="min-w-0">
                  <p className="text-[10px] uppercase tracking-[0.12em] text-faint">
                    Активная зона
                  </p>
                  <p className="mt-1 text-sm font-medium leading-5 text-ink">
                    {activeDefect.label}
                  </p>
                  <p className="mt-1 font-mono text-[10px] text-faint">
                    {activeDefect.source_model === 'crack'
                      ? 'детекция трещин'
                      : 'сегментация коррозии'}{' '}
                    · уверенность{' '}
                    {Math.round(activeDefect.confidence * 100)}%
                  </p>
                </div>
                <span
                  className={`tag shrink-0 border-current ${activeMeta.text}`}
                >
                  {activeMeta.label}
                </span>
              </div>

              <div className="mt-3 flex items-center justify-between gap-3 border-t border-line pt-3">
                <p className="technical">Узел</p>
                <p className="text-right text-xs font-medium text-soft">
                  {activeNode?.name ?? 'не определён'}
                </p>
              </div>

              <SpecGrid
                specs={
                  activeNode?.specs.length
                    ? activeNode.specs
                    : analysis.equipment.specs
                }
              />

              <dl className="mt-3 divide-y divide-line border-y border-line">
                <div className="flex items-center justify-between gap-3 py-2">
                  <dt className="technical">Последнее ТО</dt>
                  <dd className="font-mono text-[10px] text-soft">
                    {formatDate(analysis.equipment.last_maintenance_at)}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3 py-2">
                  <dt className="technical">Следующее ТО</dt>
                  <dd className="font-mono text-[10px] text-soft">
                    {formatDate(analysis.equipment.next_maintenance_at)}
                  </dd>
                </div>
                <div className="flex items-center justify-between gap-3 py-2">
                  <dt className="technical">Ресурс</dt>
                  <dd className="font-mono text-[10px] text-soft">
                    {analysis.equipment.service_life_years} лет
                  </dd>
                </div>
              </dl>
            </div>
          ) : (
            <p className="mt-3 border-l border-line pl-3 text-xs leading-5 text-muted">
              Наведите курсор на рамку дефекта или строку ниже, чтобы открыть
              характеристики узла.
            </p>
          )}
        </section>

        <div className="mt-6">
          <div className="flex items-center justify-between border-b border-line pb-2">
            <p className="technical">Зоны риска</p>
            <span className="font-mono text-[10px] text-faint">
              0{analysis.defects.length}
            </span>
          </div>

          <div className="divide-y divide-line">
            {analysis.defects.map((defect) => {
              const meta = SEVERITY_META[defect.severity];
              const active =
                (activeDefect?.id ?? null) === defect.id;
              const selected = selectedId === defect.id;

              return (
                <button
                  key={defect.id}
                  type="button"
                  onMouseEnter={() => onHover(defect.id)}
                  onMouseLeave={() => onHover(null)}
                  onFocus={() => onFocus(defect.id)}
                  onBlur={() => onFocus(null)}
                  onClick={() => onSelect(defect.id)}
                  aria-pressed={selected}
                  aria-controls="equipment-specs-panel"
                  aria-label={`Дефект: ${defect.label}, уверенность ${Math.round(
                    defect.confidence * 100,
                  )} процентов`}
                  className={`w-full border-l-2 py-3 pl-3 pr-1 text-left transition-colors duration-150 ${
                    active
                      ? 'border-accent bg-ink/[0.025]'
                      : 'border-transparent hover:bg-ink/[0.02]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span
                      className={`inline-flex items-center gap-2 font-mono text-[9px] uppercase tracking-[0.1em] ${meta.text}`}
                    >
                      <span
                        className={`h-1.5 w-1.5 shrink-0 ${meta.dot}`}
                        aria-hidden="true"
                      />
                      {meta.label}
                    </span>
                    <span className="font-mono text-[10px] text-faint tabular">
                      {Math.round(defect.confidence * 100)}%
                    </span>
                  </div>

                  <p className="mt-1.5 text-sm font-medium text-ink">
                    {defect.label}
                  </p>

                  <div className="mt-2 h-px w-full bg-line">
                    <div
                      className={`h-px ${meta.bar}`}
                      style={{
                        width: `${Math.round(defect.confidence * 100)}%`,
                      }}
                    />
                  </div>

                  {active ? (
                    <div className="mt-2 flex gap-2 text-[11px] leading-5 text-muted">
                      <Wrench
                        className="mt-1 h-3 w-3 shrink-0 text-faint"
                        aria-hidden="true"
                      />
                      <span>{defect.recommendation}</span>
                    </div>
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>

        <section className="mt-5 border border-line bg-raised p-3.5 sm:p-4" aria-labelledby="llm-heading">
          <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
            <p id="llm-heading" className="technical">
              Рекомендация по восстановлению
            </p>
            <span className="font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
              llm: {analysis.meta.llm_mode}
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-soft">
            {analysis.llm.probable_cause}
          </p>
          <p className="mt-1.5 text-[10px] leading-4 text-faint">
            Рекомендация относится к повреждённому узлу и передаётся сотруднику
            вместе с задачей.
          </p>
          <ol className="mt-3 space-y-2">
            {analysis.llm.recommendation_steps.map((step, index) => (
              <li
                key={step}
                className="flex gap-2.5 text-[11px] leading-5 text-muted sm:text-xs sm:leading-6"
              >
                <span className="font-mono text-[9px] text-accent">
                  {String(index + 1).padStart(2, '0')}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </section>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 font-mono text-[9px] uppercase tracking-[0.1em] text-faint">
          <span>обработка {analysis.meta.processing_ms} мс</span>
          <span>обновление ~{DETECTION_INTERVAL_MS / 1000} с</span>
        </div>

        <p className="mt-3 text-[10px] leading-4 text-faint">
          {API_CONFIG.useMock
            ? 'Демо-результат. При интеграции заменится ответом POST /api/inspect.'
            : 'Результат получен от backend. Не использовать как основание для ремонта без проверки инженером.'}
        </p>

        <div className="mt-5 border-t border-line pt-4">
          <button
            ref={reportButtonRef}
            type="button"
            className="btn-secondary w-full"
            aria-expanded={Boolean(reportResult)}
            aria-controls={reportResult ? 'report-create-panel' : undefined}
            onClick={() => setReportResult((current) => current ?? analysis)}
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            Передать задачу
          </button>

          {reportResult ? (
            <ReportCreateForm
              result={reportResult}
              snapshotPhoto={snapshotPhoto}
              engineers={engineers}
              onCancel={() => {
                setReportResult(null);
                reportButtonRef.current?.focus();
              }}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function EmptyReport({ status }: { status: ScannerStatus }) {
  return (
    <div className="border border-line bg-panel" data-placeholder="equipment-specs">
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 border-b border-line px-4 py-3 sm:px-5">
        <span className="eyebrow">Отчёт · live</span>
        <span className="font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
          ожидание
        </span>
      </div>

      <div className="p-4 sm:p-5">
        <p
          className="font-mono text-[4rem] font-medium leading-none tracking-[-0.06em] text-line-strong"
          aria-hidden="true"
        >
          00
        </p>
        <h2 className="mt-4 text-xl font-medium tracking-[-0.025em] text-ink">
          Здесь появятся характеристики
        </h2>
        <p className="mt-2 text-sm leading-6 text-muted">
          Наведите камеру на оборудование. Распознавание начнётся автоматически,
          без отдельной кнопки. После распознавания наведите курсор на дефект,
          выберите его клавишей Tab или нажмите — здесь откроются технические
          характеристики узла.
        </p>

        <dl className="mt-6 divide-y divide-line border-y border-line">
          <div className="flex items-center justify-between gap-3 py-3">
            <dt className="technical">Статус камеры</dt>
            <dd className="font-mono text-[10px] uppercase tracking-[0.08em] text-soft">
              {status === 'ready'
                ? 'Распознавание снимка'
                : STATUS_META[status].label}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3 py-3">
            <dt className="technical">Режим</dt>
            <dd className="font-mono text-[10px] uppercase tracking-[0.08em] text-soft">
              live · {API_CONFIG.useMock ? 'mock' : 'real'}
            </dd>
          </div>
          <div className="flex items-center justify-between gap-3 py-3">
            <dt className="technical">Обработка</dt>
            <dd className="font-mono text-[10px] uppercase tracking-[0.08em] text-soft">
              на устройстве
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}

export function Scanner() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const requestIdRef = useRef(0);
  const tickRef = useRef(0);
  const imageBlobRef = useRef<Blob | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [status, setStatus] = useState<ScannerStatus>('starting');
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [analysis, setAnalysis] = useState<InspectionResult | null>(null);
  const [hoveredDefectId, setHoveredDefectId] = useState<string | null>(null);
  const [focusedDefectId, setFocusedDefectId] = useState<string | null>(null);
  const [selectedDefectId, setSelectedDefectId] = useState<string | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [howItWorksOpen, setHowItWorksOpen] = useState(false);
  const [engineers, setEngineers] = useState<Employee[]>(() =>
    getEngineers(loadEmployees()),
  );

  useEffect(() => {
    const refresh = () => setEngineers(getEngineers(loadEmployees()));
    window.addEventListener(EMPLOYEES_CHANGED_EVENT, refresh);
    window.addEventListener('storage', refresh);

    return () => {
      window.removeEventListener(EMPLOYEES_CHANGED_EVENT, refresh);
      window.removeEventListener('storage', refresh);
    };
  }, []);

  const stopStream = useCallback(() => {
    const stream = streamRef.current;
    streamRef.current = null;

    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  }, []);

  const startCamera = useCallback(async () => {
    const requestId = ++requestIdRef.current;

    stopStream();
    setError(null);
    setSnapshot(null);
    setAnalysis(null);
    setHoveredDefectId(null);
    setFocusedDefectId(null);
    setSelectedDefectId(null);
    setLiveError(null);
    imageBlobRef.current = null;
    setStatus('starting');
    tickRef.current = 0;

    if (!navigator.mediaDevices?.getUserMedia) {
      setStatus('error');
      setError(
        'Браузер не поддерживает доступ к камере. Откройте страницу в современном браузере или загрузите фотографию.',
      );
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
      });

      if (requestId !== requestIdRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      const video = videoRef.current;
      if (!video) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }

      streamRef.current = stream;
      video.srcObject = stream;
      await video.play();

      if (requestId === requestIdRef.current) {
        setStatus('live');
      }
    } catch (cameraError) {
      if (requestId !== requestIdRef.current) {
        return;
      }

      stopStream();
      setStatus('error');
      setError(describeCameraError(cameraError));
    }
  }, [stopStream]);

  useEffect(() => {
    void startCamera();

    return () => {
      requestIdRef.current += 1;
      stopStream();
    };
  }, [startCamera, stopStream]);

  // Live-распознавание: первый результат через 500 мс, далее обновление
  // каждые 1.8 с. API-клиент выбирает mock или POST /api/inspect.
  useEffect(() => {
    const active = status === 'live' || (status === 'ready' && Boolean(snapshot));

    if (!active) {
      return;
    }

    let cancelled = false;
    // Блокировка относится только к текущему источнику: старый запрос камеры
    // не должен пропускать единственный запуск для загруженного снимка.
    let inFlight = false;
    let interval: number | null = null;

    const captureFrame = async (): Promise<Blob | null> => {
      if (imageBlobRef.current) {
        return imageBlobRef.current;
      }

      const video = videoRef.current;

      if (!video || video.readyState < 2 || !video.videoWidth) {
        return null;
      }

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const context = canvas.getContext('2d');

      if (!context) {
        return null;
      }

      context.drawImage(video, 0, 0, canvas.width, canvas.height);

      return new Promise<Blob | null>((resolve) => {
        canvas.toBlob((blob) => resolve(blob), 'image/jpeg', 0.85);
      });
    };

    const runDetection = async () => {
      if (cancelled || inFlight) {
        return;
      }

      inFlight = true;
      tickRef.current += 1;
      const tick = tickRef.current;

      try {
        const frame = API_CONFIG.useMock ? null : await captureFrame();

        if (cancelled) {
          return;
        }

        if (!API_CONFIG.useMock && !frame) {
          // Камера ещё не отдала кадр — следующий тик попробует снова.
          return;
        }

        const result = await inspectImage(frame, 'pump-cns-38-220', tick);

        if (!cancelled) {
          setAnalysis(result);
          setLiveError(null);
        }
      } catch {
        if (!cancelled) {
          setLiveError(
            'Не удалось получить результат распознавания. Проверьте, что backend запущен и VITE_API_BASE_URL указан верно.',
          );
        }
      } finally {
        inFlight = false;
      }
    };

    const firstTimer = window.setTimeout(
      () => {
        void runDetection();
        // Считаем интервал от первого распознавания, не от запуска камеры.
        // Загруженное фото анализируется один раз, без отдельной кнопки.
        if (status === 'live') {
          interval = window.setInterval(
            () => void runDetection(),
            DETECTION_INTERVAL_MS,
          );
        }
      },
      FIRST_DETECTION_MS,
    );

    return () => {
      cancelled = true;
      window.clearTimeout(firstTimer);
      if (interval !== null) {
        window.clearInterval(interval);
      }
    };
  }, [snapshot, status]);

  const handleReset = useCallback(() => {
    setSnapshot(null);
    setAnalysis(null);
    setHoveredDefectId(null);
    setFocusedDefectId(null);
    setSelectedDefectId(null);
    setLiveError(null);
    imageBlobRef.current = null;
    setError(null);
    void startCamera();
  }, [startCamera]);

  const handleFileChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      event.target.value = '';

      if (!file) {
        return;
      }

      if (!file.type.startsWith('image/')) {
        setError('Выберите файл изображения: JPEG, PNG или WebP.');
        return;
      }

      if (file.size > 10 * 1024 * 1024) {
        setError('Файл больше 10 МБ. Выберите изображение меньшего размера.');
        return;
      }

      const reader = new FileReader();

      reader.onerror = () => {
        setError('Не удалось прочитать файл. Попробуйте другой снимок.');
      };

      reader.onload = () => {
        const src = typeof reader.result === 'string' ? reader.result : '';

        if (!src) {
          setError('Не удалось открыть изображение. Попробуйте другой файл.');
          return;
        }

        const image = new window.Image();
        image.onload = () => {
          requestIdRef.current += 1;
          stopStream();
          tickRef.current = 0;
          imageBlobRef.current = file;
          setSnapshot({
            src,
            width: image.naturalWidth || 1280,
            height: image.naturalHeight || 720,
          });
          setAnalysis(null);
          setHoveredDefectId(null);
          setFocusedDefectId(null);
          setSelectedDefectId(null);
          setError(null);
          setLiveError(null);
          setStatus('ready');
        };
        image.onerror = () => {
          setError('Не удалось декодировать изображение. Попробуйте другой файл.');
        };
        image.src = src;
      };

      reader.readAsDataURL(file);
    },
    [stopStream],
  );

  const statusMeta = STATUS_META[status];
  const statusLabel =
    status === 'ready' && !analysis
      ? 'Распознавание снимка'
      : statusMeta.label;
  const activeDefectId = hoveredDefectId ?? focusedDefectId ?? selectedDefectId;
  const activeDefect =
    analysis?.defects.find((defect) => defect.id === activeDefectId) ??
    null;
  const activeNode =
    analysis && activeDefect
      ? getEquipmentNode(analysis.equipment, activeDefect.node_id)
      : null;

  return (
    <div className="space-y-7">
      <PageHeader
        index="01"
        label="Компьютерное зрение"
        title="Веб-сканер"
        description="Наведите камеру на оборудование — дефекты и технические характеристики появляются автоматически. Наведите курсор на дефект, чтобы открыть характеристики узла."
        compact
        aside={
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-center">
            <span
              className={`tag ${statusMeta.tag}`}
              role="status"
              aria-live="polite"
              aria-atomic="true"
            >
              <span
                className={`h-1.5 w-1.5 shrink-0 ${statusMeta.dot}`}
                aria-hidden="true"
              />
              {statusLabel}
            </span>
            <span className="font-mono text-[9px] uppercase tracking-[0.16em] text-faint">
              CAM 01 · LIVE
            </span>
          </div>
        }
      />

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.5fr)_minmax(340px,0.9fr)] lg:gap-8 xl:grid-cols-[minmax(0,1.7fr)_minmax(400px,0.9fr)] 2xl:grid-cols-[minmax(0,1.8fr)_minmax(440px,0.8fr)] 2xl:gap-10">
        <section aria-label="Окно камеры" className="min-w-0">
          <div className="flex items-center justify-between gap-3 border border-line border-b-0 bg-panel px-4 py-2.5">
            <div className="flex min-w-0 items-center gap-3 font-mono text-[9px] uppercase tracking-[0.14em]">
              <span className="inline-flex items-center gap-1.5 text-accent">
                <Camera className="h-3.5 w-3.5" aria-hidden="true" />
                CAM 01
              </span>
              <span className="text-faint">
                / {snapshot ? 'снимок' : 'поток'}
              </span>
              <span className="hidden text-faint sm:inline">/ 1280 × 720</span>
            </div>

            <button
              type="button"
              onClick={handleReset}
              className="inline-flex h-8 shrink-0 items-center gap-1.5 font-mono text-[9px] uppercase tracking-[0.12em] text-faint transition-colors hover:text-ink"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Сбросить
            </button>
          </div>

          <div
            className="relative aspect-video max-h-[min(52vh,440px)] w-full overflow-hidden border border-line bg-black"
            style={
              snapshot
                ? { aspectRatio: `${snapshot.width} / ${snapshot.height}` }
                : undefined
            }
          >
            {snapshot ? (
              <img
                src={snapshot.src}
                alt="Снимок оборудования для анализа"
                className="h-full w-full object-cover"
              />
            ) : status === 'error' ? (
              <CameraError
                message={error}
                onRetry={() => void startCamera()}
                onUpload={() => fileInputRef.current?.click()}
              />
            ) : (
              <video
                ref={videoRef}
                autoPlay
                playsInline
                muted
                className="h-full w-full object-cover"
                aria-label="Видеопоток с камеры"
              />
            )}

            {status === 'starting' && !snapshot ? (
              <div className="absolute inset-0 grid place-items-center bg-canvas/80">
                <div className="text-center">
                  <Loader2
                    className="mx-auto h-7 w-7 animate-spin text-accent"
                    aria-hidden="true"
                  />
                  <p className="mt-3 text-sm font-medium text-ink">
                    Подключаем камеру...
                  </p>
                  <p className="mt-1 font-mono text-[9px] uppercase tracking-[0.14em] text-faint">
                    Разрешите доступ в браузере
                  </p>
                </div>
              </div>
            ) : null}

            {!analysis && status !== 'error' && status !== 'starting' ? (
              <CameraGuide />
            ) : null}

            {status === 'live' ? <div className="scanline" /> : null}

            {analysis && (status === 'live' || status === 'ready') ? (
              <DefectOverlay
                analysis={analysis}
                activeId={activeDefect?.id ?? null}
                selectedId={selectedDefectId}
                onHover={setHoveredDefectId}
                onFocus={setFocusedDefectId}
                onSelect={setSelectedDefectId}
              />
            ) : null}
          </div>

          <div className="flex flex-col gap-4 border border-line border-t-0 bg-panel p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2.5 text-xs leading-5 text-muted">
              <span
                className={`h-1.5 w-1.5 shrink-0 ${
                  liveError
                    ? 'bg-danger'
                    : status === 'live'
                      ? 'animate-pulse-soft bg-ok'
                      : 'bg-faint'
                }`}
                aria-hidden="true"
              />
              <p
                className={liveError ? 'text-danger' : undefined}
                aria-live="polite"
                aria-atomic="true"
              >
                {liveError
                  ? liveError
                  : status === 'live'
                  ? `Распознавание идёт автоматически · обновление ~${
                      DETECTION_INTERVAL_MS / 1000
                    } с`
                  : status === 'ready'
                    ? analysis
                      ? 'Снимок распознан автоматически. Выберите дефект, чтобы открыть характеристики.'
                      : 'Снимок распознаётся автоматически…'
                    : 'Распознавание запустится автоматически после доступа к камере.'}
              </p>
            </div>

            <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center">
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleFileChange}
                aria-label="Загрузить фотографию оборудования"
              />
              <button
                type="button"
                className="btn-secondary w-full sm:w-auto"
                onClick={() => fileInputRef.current?.click()}
              >
                <Upload className="h-4 w-4" aria-hidden="true" />
                Загрузить фото
              </button>
            </div>
          </div>
        </section>

        <aside className="min-w-0" aria-label="Результат распознавания">
          {analysis ? (
            <LiveReport
              analysis={analysis}
              activeDefect={activeDefect}
              activeNode={activeNode}
              selectedId={selectedDefectId}
              snapshotPhoto={snapshot ? imageBlobRef.current : null}
              engineers={engineers}
              onHover={setHoveredDefectId}
              onFocus={setFocusedDefectId}
              onSelect={setSelectedDefectId}
            />
          ) : (
            <EmptyReport status={status} />
          )}
        </aside>
      </div>

      <section className="border-t border-line" aria-label="Как это работает">
        <button
          type="button"
          onClick={() => setHowItWorksOpen((value) => !value)}
          aria-expanded={howItWorksOpen}
          aria-controls="how-it-works-panel"
          className="group flex w-full items-center justify-between gap-4 py-5 text-left"
        >
          <span className="flex items-start gap-4">
            <span className="mt-1 font-mono text-[10px] tracking-[0.16em] text-accent">
              04
            </span>
            <span>
              <span className="block text-lg font-medium tracking-[-0.02em] text-ink">
                Как это работает
              </span>
              <span className="mt-1 block text-xs leading-5 text-faint">
                Live-распознавание, характеристики по наведению и демо-режим
              </span>
            </span>
          </span>

          <span className="flex shrink-0 items-center gap-3 text-faint">
            <span className="hidden font-mono text-[9px] uppercase tracking-[0.14em] sm:inline">
              {howItWorksOpen ? 'Свернуть' : 'Открыть'}
            </span>
            <ChevronDown
              className={`h-4 w-4 transition-transform duration-200 ${
                howItWorksOpen ? 'rotate-180' : ''
              }`}
              aria-hidden="true"
            />
          </span>
        </button>

        {howItWorksOpen ? (
          <div
            id="how-it-works-panel"
            className="animate-fade-in border-t border-line pb-8 pt-6"
          >
            <HowItWorksContent status={status} />
          </div>
        ) : null}
      </section>
    </div>
  );
}
