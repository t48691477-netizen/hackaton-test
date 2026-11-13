import { useEffect, useState } from 'react';

/**
 * CSS media query в React. Нужен, чтобы на телефоне/планшете рендерить
 * карточки вместо широких таблиц, а не прятать таблицу через overflow.
 *
 * `fallback` используется в jsdom/SSR, где matchMedia может отсутствовать.
 * Для тестов таблиц по умолчанию оставляем desktop-ветку.
 */
export function useMediaQuery(query: string, fallback = false): boolean {
  const [matches, setMatches] = useState(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return fallback;
    }

    return window.matchMedia(query).matches;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) {
      return;
    }

    const media = window.matchMedia(query);
    const update = () => setMatches(media.matches);

    update();
    media.addEventListener?.('change', update);

    return () => media.removeEventListener?.('change', update);
  }, [query]);

  return matches;
}
