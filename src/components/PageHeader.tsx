import type { ReactNode } from 'react';

interface PageHeaderProps {
  index: string;
  label: string;
  title: string;
  description: string;
  aside?: ReactNode;
  compact?: boolean;
}

export function PageHeader({
  index,
  label,
  title,
  description,
  aside,
  compact = false,
}: PageHeaderProps) {
  return (
    <header className={compact ? 'border-b border-line pb-5' : 'border-b border-line pb-8'}>
      <div className="flex items-center gap-3 font-mono text-[10px] uppercase tracking-[0.18em]">
        <span className="text-accent">{index}</span>
        <span className="h-px w-8 bg-accent/50" aria-hidden="true" />
        <span className="text-faint">{label}</span>
      </div>

      <div
        className={[
          'flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between',
          compact ? 'mt-3' : 'mt-5 gap-6',
        ].join(' ')}
      >
        <div className="min-w-0">
          <h1
            className={[
              'text-balance font-medium leading-[0.98] tracking-[-0.045em] text-ink',
              compact
                ? 'text-[clamp(2.1rem,3.4vw,3rem)]'
                : 'text-[clamp(2.4rem,4.6vw,4rem)]',
            ].join(' ')}
          >
            {title}
          </h1>
          <p
            className={[
              'text-muted',
              compact
                ? 'mt-2.5 max-w-3xl text-sm leading-6 line-clamp-2 sm:line-clamp-none'
                : 'mt-4 max-w-2xl text-[15px] leading-7 line-clamp-2 sm:line-clamp-none',
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
