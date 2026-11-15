import type { ReactNode } from 'react';

interface PageHeaderProps {
  label: string;
  title: string;
  description: string;
  aside?: ReactNode;
  compact?: boolean;
}

export function PageHeader({
  label,
  title,
  description,
  aside,
  compact = false,
}: PageHeaderProps) {
  return (
    <header className={compact ? 'pb-2' : 'pb-4'}>
      <p className="eyebrow">{label}</p>

      <div
        className={[
          'flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between',
          compact ? 'mt-2' : 'mt-2 gap-6',
        ].join(' ')}
      >
        <div className="min-w-0">
          <h1
            className={[
              'text-balance font-semibold leading-tight tracking-[-0.01em] text-ink',
              compact ? 'text-2xl' : 'text-[1.75rem] sm:text-[2rem]',
            ].join(' ')}
          >
            {title}
          </h1>
          <p
            className={[
              'text-muted',
              compact
                ? 'mt-2 max-w-3xl text-sm leading-6 line-clamp-2 sm:line-clamp-none'
                : 'mt-3 max-w-2xl text-[15px] leading-7 line-clamp-2 sm:line-clamp-none',
            ].join(' ')}
          >
            {description}
          </p>
        </div>

        {aside ? <div className="shrink-0 lg:pb-1">{aside}</div> : null}
      </div>
    </header>
  );
}
