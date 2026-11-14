import { Crosshair } from 'lucide-react';
import type { Defect } from '../lib/inspection';

const CONFIDENCE_FORMATTER = new Intl.NumberFormat('ru-RU', {
  maximumFractionDigits: 1,
});

const SEVERITY_STYLE: Record<Defect['severity'], string> = {
  high: 'text-danger',
  medium: 'text-warn',
  low: 'text-info',
};

interface RealtimeDefectsProps {
  defects: Defect[];
  isMock: boolean;
  isSnapshot: boolean;
  unavailable: boolean;
  analyzedAt: string;
}

/** A projection of the latest frame, never an accumulated detection history. */
export function RealtimeDefects({
  defects,
  isMock,
  isSnapshot,
  unavailable,
  analyzedAt,
}: RealtimeDefectsProps) {
  const visibleDefects = unavailable ? [] : defects;
  const time = new Date(analyzedAt);
  const formattedTime = Number.isNaN(time.getTime())
    ? null
    : time.toLocaleTimeString('ru-RU', { hour12: false });
  // Confidence changes every frame; announce membership changes, not every decimal.
  const announcement = unavailable
    ? 'Нет актуального результата. Ожидаем ответ распознавания.'
    : visibleDefects.length === 0
      ? 'Дефекты в кадре не обнаружены.'
      : `Зон в кадре: ${visibleDefects.length}. ${visibleDefects.map((defect) => defect.label).join('; ')}.`;

  return (
    <section
      className="mt-5 border-y border-line py-4"
      aria-labelledby="realtime-defects-heading"
      aria-describedby="realtime-defects-source"
      data-mock={isMock ? 'realtime-defects' : undefined}
      data-result-state={unavailable ? 'unavailable' : 'ready'}
    >
      <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-2">
        <h3 id="realtime-defects-heading" className="technical">Параметры realtime</h3>
        <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted">
          <span className={`h-1.5 w-1.5 rounded-full ${unavailable ? 'bg-warn' : 'bg-accent'}`} aria-hidden="true" />
          {unavailable ? 'Нет связи' : isSnapshot ? 'Снимок' : 'Текущий кадр'}
        </span>
      </div>
      <p id="realtime-defects-source" className="mt-1 text-xs leading-5 text-muted">
        {isMock ? 'Демо-детекции · ' : ''}Уверенность модели, %
      </p>

      <p className="sr-only" aria-live="polite" aria-atomic="true">{announcement}</p>

      {unavailable ? (
        <div className="mt-3 border-l-2 border-warn bg-warn/5 px-3 py-3">
          <p className="text-sm font-medium text-ink">Нет актуального результата</p>
          <p className="mt-1 text-xs leading-5 text-muted">
            Не удалось обновить кадр. Дефекты появятся после успешного ответа.
          </p>
        </div>
      ) : visibleDefects.length > 0 ? (
        <ul className="mt-3 divide-y divide-line" aria-label="Дефекты текущего кадра">
          {visibleDefects.map((defect) => {
            const validConfidence = Number.isFinite(defect.confidence)
              && defect.confidence >= 0 && defect.confidence <= 1;
            const percent = validConfidence ? defect.confidence * 100 : null;

            return (
              <li
                key={defect.id}
                className="realtime-defect-row py-3"
                data-defect-id={defect.id}
              >
                <div className="flex items-start justify-between gap-4">
                  <span className="flex min-w-0 items-start gap-2.5 text-sm font-medium leading-5 text-ink">
                    <span className={`mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full bg-current ${SEVERITY_STYLE[defect.severity] ?? 'text-accent'}`} aria-hidden="true" />
                    <span className="min-w-0 break-words [overflow-wrap:anywhere]">{defect.label}</span>
                  </span>
                  <span className="shrink-0 font-mono text-sm font-medium leading-5 tabular text-ink">
                    {percent === null ? 'Нет оценки' : `${CONFIDENCE_FORMATTER.format(percent)}%`}
                  </span>
                </div>
                {percent !== null ? (
                  <div className="mt-2 h-1 overflow-hidden rounded-full bg-line/60" aria-hidden="true">
                    <div
                      className="realtime-defect-confidence h-full rounded-full bg-accent transition-[width] duration-200 ease-out motion-reduce:transition-none"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="mt-3 flex items-start gap-3 bg-raised px-3 py-4">
          <Crosshair className="mt-0.5 h-4 w-4 shrink-0 text-muted" aria-hidden="true" />
          <div className="min-w-0">
            <p className="text-sm font-medium leading-5 text-ink">Дефекты в кадре не обнаружены</p>
            <p className="mt-1 text-xs leading-5 text-muted">
              {isSnapshot ? 'Можно загрузить другой снимок.' : 'Новые дефекты появятся здесь при обнаружении.'}
            </p>
          </div>
        </div>
      )}

      {!unavailable && formattedTime ? (
        <p className="mt-2 text-[11px] leading-5 text-muted">
          Последний результат · <time dateTime={analyzedAt} className="font-mono tabular">{formattedTime}</time>
        </p>
      ) : null}
    </section>
  );
}
