import { Link } from 'react-router-dom';

export function BrandMark({ className = 'h-5 w-5' }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 28 28"
      fill="none"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M2 9V2h7M26 9V2h-7M2 19v7h7M26 19v7h-7"
        stroke="currentColor"
        strokeWidth="1.4"
      />
      <rect
        x="10"
        y="10"
        width="8"
        height="8"
        stroke="currentColor"
        strokeWidth="1.1"
      />
    </svg>
  );
}

interface BrandProps {
  to?: string;
  onClick?: () => void;
  className?: string;
}

export function Brand({ to = '/scanner', onClick, className = '' }: BrandProps) {
  return (
    <Link
      to={to}
      onClick={onClick}
      className={`group inline-flex items-center gap-3 rounded-sm transition-colors ${className}`}
      aria-label="ПромСкан — на главную"
    >
      <span className="grid h-9 w-9 shrink-0 place-items-center border border-line-strong text-accent transition-colors duration-150 group-hover:border-accent/60">
        <BrandMark />
      </span>
      <span className="min-w-0">
        <span className="block text-[15px] font-semibold leading-none tracking-[0.045em] text-ink">
          ПРОМСКАН
        </span>
        <span className="mt-1.5 block font-mono text-[9px] uppercase leading-none tracking-[0.22em] text-faint">
          industrial vision
        </span>
      </span>
    </Link>
  );
}
