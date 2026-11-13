import { Link } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useRole } from '../context/RoleContext';
import { ROLE_LABELS } from '../lib/roles';

export function AccessDenied() {
  const { role } = useRole();

  return (
    <div className="animate-page-in">
      <div className="grid gap-8 border-b border-line pb-12 lg:grid-cols-[0.34fr_0.66fr] lg:gap-16">
        <p
          className="font-mono text-[clamp(4rem,9vw,8rem)] font-medium leading-[0.8] tracking-[-0.06em] text-line-strong"
          aria-hidden="true"
        >
          403
        </p>

        <div className="max-w-2xl">
          <p className="eyebrow">Ограничение доступа</p>
          <h1 className="mt-4 text-[clamp(2.4rem,4vw,3.6rem)] font-medium leading-[0.98] tracking-[-0.045em] text-ink">
            Доступ запрещён
          </h1>
            <p className="mt-5 text-[15px] leading-7 text-muted">
              У роли{role ? ` «${ROLE_LABELS[role]}»` : ''} нет прав на этот
              раздел. Если вам нужен доступ, обратитесь к директору или
              администратору.
            </p>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Link to="/scanner" className="btn-primary">
              <ArrowLeft className="h-4 w-4" aria-hidden="true" />
              Вернуться к сканеру
            </Link>
            <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-faint">
              Код · role / forbidden
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
