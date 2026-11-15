import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  override state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('Unhandled UI error:', error, errorInfo);
  }

  private handleReload = (): void => {
    window.location.reload();
  };

  override render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-dvh flex-col items-center justify-center bg-canvas p-6 text-center">
          <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-8 shadow-sm">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-danger/10 text-danger">
              <AlertTriangle className="h-6 w-6" aria-hidden="true" />
            </div>
            <h2 className="mt-4 text-lg font-semibold text-ink">
              Непредвиденная ошибка интерфейса
            </h2>
            <p className="mt-2 text-xs leading-relaxed text-muted">
              {this.state.error?.message || 'Сбой при отрисовке компонента. Обновите страницу.'}
            </p>
            <button
              type="button"
              onClick={this.handleReload}
              className="btn-primary mt-6 w-full"
            >
              <RefreshCw className="h-4 w-4" aria-hidden="true" />
              Обновить страницу
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
