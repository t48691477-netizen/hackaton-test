import { useEffect, useRef, useState, type FormEvent } from 'react';
import { Server } from 'lucide-react';
import { useFocusTrap } from '../lib/useFocusTrap';
import {
  SERVER_URL_CHANGED_EVENT,
  checkServer,
  getServerUrl,
  normalizeServerUrl,
  setServerUrl,
} from '../lib/serverConfig';

export function ServerAddressDialog() {
  const [configured, setConfigured] = useState(() => Boolean(getServerUrl()));
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const sync = () => setConfigured(Boolean(getServerUrl()));
    window.addEventListener(SERVER_URL_CHANGED_EVENT, sync);
    return () => window.removeEventListener(SERVER_URL_CHANGED_EVENT, sync);
  }, []);

  useFocusTrap(dialogRef, { initialFocus: 'input' });

  if (configured || import.meta.env.MODE === 'test') return null;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const url = normalizeServerUrl(value);

    if (!url) {
      setError('Введите адрес сервера, например 192.168.1.10:8000');
      return;
    }

    setChecking(true);
    setError(null);
    const ok = await checkServer(url);
    setChecking(false);

    if (!ok) {
      setError('Сервер не отвечает. Проверьте адрес и что контейнер запущен.');
      return;
    }

    setServerUrl(url);
  }

  return (
    <div className="fixed inset-0 z-[60] grid place-items-center bg-black/50 p-4">
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label="Адрес сервера"
        className="w-full max-w-md rounded-xl border border-line bg-panel p-6 shadow-sheet"
      >
        <div className="flex items-center gap-3">
          <span className="grid h-10 w-10 place-items-center rounded-lg bg-accent/10 text-accent">
            <Server className="h-5 w-5" aria-hidden="true" />
          </span>
          <h2 className="text-lg font-semibold text-ink">Адрес сервера</h2>
        </div>
        <p className="mt-3 text-sm text-muted">
          Вставьте адрес, где запущен сервер (Docker-контейнер), например
          192.168.1.10:8000.
        </p>
        <form onSubmit={handleSubmit} className="mt-4 space-y-3">
          <input
            value={value}
            onChange={(event) => setValue(event.target.value)}
            aria-label="Адрес сервера"
            placeholder="http://192.168.1.10:8000"
            inputMode="url"
            autoCapitalize="none"
            autoCorrect="off"
            className="w-full rounded-lg border border-line bg-deep px-3 py-2 text-sm text-ink"
          />
          {error ? (
            <p role="alert" className="text-sm text-red-500">
              {error}
            </p>
          ) : null}
          <button type="submit" disabled={checking} className="btn-primary w-full">
            {checking ? 'Проверка…' : 'Подключиться'}
          </button>
        </form>
      </div>
    </div>
  );
}
