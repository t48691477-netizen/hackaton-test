export const SERVER_URL_STORAGE_KEY = 'promscan:server-url';
export const SERVER_URL_CHANGED_EVENT = 'promscan:server-url-changed';

export function normalizeServerUrl(input: string): string | null {
  const trimmed = input.trim();
  if (!trimmed) return null;

  const withScheme = /^https?:\/\//i.test(trimmed) ? trimmed : `http://${trimmed}`;

  try {
    const url = new URL(withScheme);
    if (!url.hostname) return null;
    return `${url.protocol}//${url.host}`;
  } catch {
    return null;
  }
}

export function resolveRequestBase(url: string): string {
  if (
    typeof window !== 'undefined' &&
    window.location.protocol === 'https:' &&
    url.startsWith('http:')
  ) {
    return '';
  }

  return url;
}

export function getServerUrl(): string | null {
  if (typeof window === 'undefined') return null;

  try {
    return window.localStorage.getItem(SERVER_URL_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setServerUrl(url: string): boolean {
  if (typeof window === 'undefined') return false;

  try {
    window.localStorage.setItem(SERVER_URL_STORAGE_KEY, url);
  } catch {
    return false;
  }

  window.dispatchEvent(new Event(SERVER_URL_CHANGED_EVENT));
  return true;
}

export function clearServerUrl(): void {
  if (typeof window === 'undefined') return;

  try {
    window.localStorage.removeItem(SERVER_URL_STORAGE_KEY);
  } catch {
    return;
  }

  window.dispatchEvent(new Event(SERVER_URL_CHANGED_EVENT));
}

export async function checkServer(url: string, timeoutMs = 6000): Promise<boolean> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${resolveRequestBase(url)}/health`, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    window.clearTimeout(timer);
  }
}
