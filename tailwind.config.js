/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        canvas: 'rgb(var(--bg) / <alpha-value>)',
        deep: 'rgb(var(--bg-deep) / <alpha-value>)',
        panel: 'rgb(var(--panel) / <alpha-value>)',
        raised: 'rgb(var(--raised) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
        'line-strong': 'rgb(var(--line-strong) / <alpha-value>)',
        ink: 'rgb(var(--ink) / <alpha-value>)',
        soft: 'rgb(var(--soft) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        faint: 'rgb(var(--faint) / <alpha-value>)',
        accent: 'rgb(var(--accent) / <alpha-value>)',
        'accent-hi': 'rgb(var(--accent-hi) / <alpha-value>)',
        'accent-ink': 'rgb(var(--accent-ink) / <alpha-value>)',
        ok: 'rgb(var(--ok) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        danger: 'rgb(var(--danger) / <alpha-value>)',
        info: 'rgb(var(--info) / <alpha-value>)',
      },
      fontFamily: {
        sans: [
          'Nunito Sans Variable',
          'Nunito Sans',
          'Segoe UI',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'sans-serif',
        ],
        mono: ['IBM Plex Mono', 'Cascadia Mono', 'Consolas', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        none: '0',
        sm: '4px',
        DEFAULT: '5px',
        md: '6px',
        lg: '8px',
        xl: '10px',
        full: '9999px',
      },
      boxShadow: {
        panel: '0 1px 2px rgb(27 26 24 / 0.04)',
        sheet: '-24px 0 64px rgb(27 26 24 / 0.14)',
      },
      keyframes: {
        'page-in': {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'sheet-in': {
          from: { opacity: '0', transform: 'translateX(28px)' },
          to: { opacity: '1', transform: 'translateX(0)' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        scan: {
          '0%': { top: '2%', opacity: '0' },
          '8%': { opacity: '0.5' },
          '92%': { opacity: '0.5' },
          '100%': { top: '98%', opacity: '0' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.35' },
        },
      },
      animation: {
        'page-in': 'page-in 420ms cubic-bezier(0.2, 0.7, 0.2, 1) both',
        'sheet-in': 'sheet-in 260ms cubic-bezier(0.2, 0.7, 0.2, 1) both',
        'fade-in': 'fade-in 200ms ease-out both',
        scan: 'scan 3.8s linear infinite',
        'pulse-soft': 'pulse-soft 2.6s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};
