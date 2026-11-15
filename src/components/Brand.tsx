import { Link } from 'react-router-dom';

export function BrandLockup({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-3 ${className}`}>
      <img
        src="/kst-energo-logo.svg"
        alt="КСТ Энерго"
        className="h-7 w-auto shrink-0"
        width={118}
        height={28}
      />
      <span className="h-6 w-px shrink-0 bg-line-strong" aria-hidden="true" />
      <span className="text-[17px] font-semibold leading-none text-ink">
        ПромСкан
      </span>
    </span>
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
      className={`inline-flex min-h-11 items-center rounded-lg ${className}`}
      aria-label="ПромСкан, КСТ Энерго — на главную"
    >
      <BrandLockup />
    </Link>
  );
}
