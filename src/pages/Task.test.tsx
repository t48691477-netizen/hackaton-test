import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '../App';
import { RoleProvider } from '../context/RoleContext';
import { fetchReportById, updateReportStatus } from '../lib/api';
import { MOCK_REPORTS, type Report } from '../lib/inspection';
import type { Role } from '../lib/roles';

vi.mock('../lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../lib/api')>();

  return {
    ...actual,
    API_CONFIG: { ...actual.API_CONFIG, useMock: true },
    fetchReportById: vi.fn(),
    updateReportStatus: vi.fn(),
  };
});

const BASE_REPORT =
  MOCK_REPORTS.find((report) => report.id === 'report-1041') ??
  MOCK_REPORTS[0];

const fetchReportByIdMock = vi.mocked(fetchReportById);
const updateReportStatusMock = vi.mocked(updateReportStatus);

function createReport(overrides: Partial<Report> = {}): Report {
  return {
    ...(JSON.parse(JSON.stringify(BASE_REPORT)) as Report),
    ...overrides,
  };
}

function createClosedReport(): Report {
  return createReport({
    status: 'closed',
    started_at: '2026-11-13T14:20:00Z',
    completed_at: '2026-11-13T15:45:00Z',
    repair_comment: 'Уплотнение заменено.',
  });
}

function renderTask(role: Role | null, route = '/task/report-1041') {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <RoleProvider initialRole={role}>
        <AppRoutes />
      </RoleProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  vi.resetAllMocks();
});

describe('мобильный экран задания', () => {
  it('инженер видит рекомендацию, исполнителя и кнопку начала', async () => {
    fetchReportByIdMock.mockResolvedValue(createReport());

    renderTask('engineer');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Задание сотруднику' }),
    ).toBeInTheDocument();
    expect(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Анна Петрова')).toBeInTheDocument();
    expect(
      screen.getByText(BASE_REPORT.result.llm.recommendation_steps[0]),
    ).toBeInTheDocument();
    expect(fetchReportByIdMock).toHaveBeenCalledWith('report-1041');
    expect(
      screen.queryByRole('navigation', { name: 'Основная навигация' }),
    ).not.toBeInTheDocument();
  });

  it('переводит задачу в работу и меняет доступное действие', async () => {
    const user = userEvent.setup();
    const report = createReport();
    fetchReportByIdMock.mockResolvedValue(report);
    updateReportStatusMock.mockResolvedValue({
      ...report,
      status: 'in_progress',
      started_at: '2026-11-13T14:20:00Z',
      updated_at: '2026-11-13T14:20:00Z',
    });

    renderTask('engineer');

    await user.click(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    );

    await waitFor(() => {
      expect(updateReportStatusMock).toHaveBeenCalledWith(
        'report-1041',
        'in_progress',
      );
    });

    expect(
      await screen.findByRole('button', { name: 'Отметить выполненной' }),
    ).toBeInTheDocument();
    expect(screen.getByText('В работе')).toBeInTheDocument();
    expect(
      screen.getByLabelText('Комментарий к выполнению'),
    ).toBeInTheDocument();
  });

  it('закрывает задачу с комментарием и показывает завершение', async () => {
    const user = userEvent.setup();
    const report = createReport({
      status: 'in_progress',
      started_at: '2026-11-13T14:20:00Z',
    });
    fetchReportByIdMock.mockResolvedValue(report);
    updateReportStatusMock.mockResolvedValue({
      ...report,
      status: 'closed',
      completed_at: '2026-11-13T15:45:00Z',
      repair_comment: 'Заменил крепёжные болты.',
    });

    renderTask('engineer');

    await user.type(
      await screen.findByLabelText('Комментарий к выполнению'),
      'Заменил крепёжные болты.',
    );
    await user.click(
      screen.getByRole('button', { name: 'Отметить выполненной' }),
    );

    await waitFor(() => {
      expect(updateReportStatusMock).toHaveBeenCalledWith(
        'report-1041',
        'closed',
        'Заменил крепёжные болты.',
      );
    });

    expect(
      await screen.findByRole('heading', { name: 'Задача выполнена' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Заменил крепёжные болты.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Отметить выполненной' }),
    ).not.toBeInTheDocument();
  });

  it('сразу показывает закрытую задачу без кнопок действий', async () => {
    fetchReportByIdMock.mockResolvedValue(createClosedReport());

    renderTask('engineer');

    expect(
      await screen.findByRole('heading', { name: 'Задача выполнена' }),
    ).toBeInTheDocument();
    expect(screen.getByText('Уплотнение заменено.')).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Выполнить задачу' }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Отметить выполненной' }),
    ).not.toBeInTheDocument();
    expect(updateReportStatusMock).not.toHaveBeenCalled();
  });

  it('показывает отдельное состояние «задача не найдена»', async () => {
    fetchReportByIdMock.mockRejectedValue(
      Object.assign(new Error('Задача не найдена.'), { status: 404 }),
    );

    renderTask('engineer');

    expect(
      await screen.findByRole('heading', { name: 'Задача не найдена' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Повторить' }),
    ).toBeInTheDocument();
  });

  it('показывает ошибку загрузки и повторяет запрос', async () => {
    const user = userEvent.setup();
    fetchReportByIdMock
      .mockRejectedValueOnce(new Error('Сервер недоступен'))
      .mockResolvedValueOnce(createReport());

    renderTask('engineer');

    expect(
      await screen.findByRole('heading', {
        name: 'Не удалось загрузить задание',
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('Сервер недоступен')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    ).toBeInTheDocument();
    expect(fetchReportByIdMock).toHaveBeenCalledTimes(2);
  });

  it('не даёт начать задачу без назначенного исполнителя', async () => {
    fetchReportByIdMock.mockResolvedValue(createReport({ assignee: null }));

    renderTask('engineer');

    const button = await screen.findByRole('button', {
      name: 'Выполнить задачу',
    });

    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('title', 'Задачу назначает диспетчер');
    expect(screen.getByText('Не назначен')).toBeInTheDocument();
    expect(
      screen.getByText('Задачу назначает диспетчер'),
    ).toBeInTheDocument();
  });

  it('показывает ошибку действия и позволяет повторить переход', async () => {
    const user = userEvent.setup();
    const report = createReport();
    fetchReportByIdMock.mockResolvedValue(report);
    updateReportStatusMock
      .mockRejectedValueOnce(new Error('Сервер занят'))
      .mockResolvedValueOnce({
        ...report,
        status: 'in_progress',
        started_at: '2026-11-13T14:20:00Z',
      });

    renderTask('engineer');

    await user.click(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервер занят');

    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    await waitFor(() => {
      expect(updateReportStatusMock).toHaveBeenCalledTimes(2);
    });
    expect(
      await screen.findByRole('button', { name: 'Отметить выполненной' }),
    ).toBeInTheDocument();
  });

  it('диспетчер открывает задание вне Layout', async () => {
    fetchReportByIdMock.mockResolvedValue(createReport());

    renderTask('dispatcher');

    expect(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('navigation', { name: 'Основная навигация' }),
    ).not.toBeInTheDocument();
  });

  it('открывает мобильное задание без роли как демо-ссылку', async () => {
    fetchReportByIdMock.mockResolvedValue(createReport());

    renderTask(null);

    expect(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });
});

describe('доступ рабочего к маршрутам', () => {
  it('на /defects показывает 403, а не мобильную заглушку', () => {
    renderTask('engineer', '/defects');

    expect(
      screen.getByRole('heading', { level: 1, name: 'Доступ запрещён' }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Выполнить задачу' }),
    ).not.toBeInTheDocument();
  });

  it('на /task/:id открывает мобильный экран задания', async () => {
    fetchReportByIdMock.mockResolvedValue(createReport());

    renderTask('engineer', '/task/report-1041');

    expect(
      await screen.findByRole('button', { name: 'Выполнить задачу' }),
    ).toBeInTheDocument();
    expect(screen.getByText('report-1041')).toBeInTheDocument();
  });
});
