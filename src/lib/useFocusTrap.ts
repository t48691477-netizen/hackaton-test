import { useEffect, useRef } from 'react';

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

interface FocusTrapOptions {
  initialFocus?: string;
  onEscape?: () => void;
  restoreFocus?: () => void;
}

export function useFocusTrap<T extends HTMLElement>(
  containerRef: { current: T | null },
  { initialFocus, onEscape, restoreFocus }: FocusTrapOptions = {},
) {
  const onEscapeRef = useRef(onEscape);
  const restoreFocusRef = useRef(restoreFocus);
  onEscapeRef.current = onEscape;
  restoreFocusRef.current = restoreFocus;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const previousFocus =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    const getFocusable = () =>
      Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR));
    const focusTarget = initialFocus
      ? container.querySelector<HTMLElement>(initialFocus)
      : null;

    (focusTarget ?? getFocusable()[0] ?? container).focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onEscapeRef.current?.();
        return;
      }

      if (event.key !== 'Tab') return;

      const focusable = getFocusable();
      if (focusable.length === 0) {
        event.preventDefault();
        container.focus();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const focusIsOutside = !container.contains(document.activeElement);

      if (event.shiftKey && (document.activeElement === first || focusIsOutside)) {
        event.preventDefault();
        last.focus();
      } else if (
        !event.shiftKey &&
        (document.activeElement === last || focusIsOutside)
      ) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (previousFocus?.isConnected && !previousFocus.hasAttribute('disabled')) {
        previousFocus.focus();
      } else {
        restoreFocusRef.current?.();
      }
    };
  }, [containerRef, initialFocus]);
}
