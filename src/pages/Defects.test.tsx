import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import {
  fetchEquipment,
  fetchReports,
  subscribeToReportChanges,
} from '../lib/api';
import {
  MOCK_EQUIPMENT,
  MOCK_EQUIPMENT_LIST,
  MOCK_REPORTS,
  type Report,
} from '../lib/inspection';
import { Defects } from './Defects';

vi.mock('../lib/api', () => ({
  API_CONFIG: { useMock: true },
  fetchEquipment: vi.fn(),
  fetchReports: vi.fn(),
  subscribeToReportChanges: vi.fn(() => () => {}),
}));

const equipmentMock = vi.mocked(fetchEquipment);
const reportsMock = vi.mocked(fetchReports);
const subscribeMock = vi.mocked(subscribeToReportChanges);

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((complete) => { resolve = complete; });
  return { promise, resolve };
}

function getReportRow(reportId: string): HTMLElement {
  const row = screen.getByText(reportId).closest('tr');

  if (!row) {
    throw new Error(`Строка отчёта ${reportId} не найдена.`);
  }

  return row;
}

beforeEach(() => {
  vi.resetAllMocks();
  equipmentMock.mockResolvedValue(MOCK_EQUIPMENT_LIST);
  reportsMock.mockResolvedValue(MOCK_REPORTS);
  subscribeMock.mockReturnValue(() => {});
});

describe('панель диспетчера: API-данные', () => {
  it('показывает загрузку, затем маппит отчёты в существующие колонки', async () => {
    const pending = deferred<Report[]>();
    reportsMock.mockReturnValueOnce(pending.promise);
    render(<Defects />);

    expect(screen.getByRole('status')).toHaveTextContent('Загрузка отчётов');

    await act(async () => pending.resolve(MOCK_REPORTS));
    await screen.findByText(MOCK_REPORTS[0].id);

    const table = screen.getByRole('table', { name: 'Последние дефекты' });
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual([
      'Дефект', 'Оборудование', 'Приоритет', 'Статус', 'Исполнитель', 'Время',
    ]);
    expect(within(table).getAllByRole('row')).toHaveLength(MOCK_REPORTS.length + 1);
    const firstRow = within(table).getAllByRole('row')[1];
    expect(within(firstRow).getByText('Трещина корпуса')).toBeInTheDocument();
    expect(within(firstRow).getByText(MOCK_EQUIPMENT.name)).toBeInTheDocument();
    expect(within(firstRow).getByText('В работе')).toBeInTheDocument();
    expect(within(firstRow).getByText('14:12')).toBeInTheDocument();
    expect(within(firstRow).getByText('Алексей Смирнов')).not.toHaveAttribute('data-mock');
    expect(screen.queryByText('Паспорт оборудования')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Оборудование для паспорта')).not.toBeInTheDocument();
    expect(reportsMock).toHaveBeenCalledTimes(1);
    expect(equipmentMock).toHaveBeenCalledTimes(1);
  });

  it('показывает исполнителей из задач и заглушку только без назначения', async () => {
    render(<Defects />);
    await screen.findByText(MOCK_REPORTS[0].id);

    expect(within(getReportRow('report-1042')).getByText('Алексей Смирнов'))
      .toBeInTheDocument();
    expect(within(getReportRow('report-1041')).getByText('Анна Петрова'))
      .toBeInTheDocument();
    expect(within(getReportRow('report-1038')).getByText('Алексей Смирнов'))
      .toBeInTheDocument();

    const unassigned = within(getReportRow('report-1039')).getByText('Не назначен');
    expect(unassigned).toHaveAttribute('data-mock', 'assignee');
    expect(within(screen.getByRole('table')).getAllByText('Не назначен'))
      .toHaveLength(1);
  });

  it('показывает жизненный цикл задачи: «В работе» и «Выполнено»', async () => {
    render(<Defects />);
    await screen.findByText(MOCK_REPORTS[0].id);

    expect(within(getReportRow('report-1042')).getByText('В работе'))
      .toBeInTheDocument();
    expect(within(getReportRow('report-1036')).getByText('Выполнено'))
      .toBeInTheDocument();
    expect(screen.queryByText('Закрыт')).not.toBeInTheDocument();

    const summary = screen.getByLabelText('Сводка по дефектам');
    expect(within(summary).getByText('Выполнено')).toBeInTheDocument();
  });

  it('добавляет ссылку на мобильную задачу', async () => {
    render(<Defects />);
    await screen.findByText(MOCK_REPORTS[0].id);

    const link = within(getReportRow('report-1042')).getByRole('link', {
      name: 'Открыть задачу report-1042',
    });

    expect(link).toHaveAttribute('href', '/task/report-1042');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noreferrer');
  });

  it('обновляет данные по кнопке «Обновить»', async () => {
    const user = userEvent.setup();
    render(<Defects />);
    await screen.findByText(MOCK_REPORTS[0].id);

    const refreshButton = screen.getByRole('button', { name: 'Обновить' });
    await waitFor(() => expect(refreshButton).toBeEnabled());
    await user.click(refreshButton);

    await waitFor(() => expect(reportsMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(equipmentMock).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(MOCK_REPORTS[0].id)).toBeInTheDocument();
  });

  it('перезагружает данные по событию изменения задачи', async () => {
    render(<Defects />);
    await screen.findByText(MOCK_REPORTS[0].id);

    expect(subscribeMock).toHaveBeenCalledTimes(1);
    const listener = subscribeMock.mock.calls[0][0];

    await act(async () => listener());

    await waitFor(() => expect(reportsMock).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(equipmentMock).toHaveBeenCalledTimes(2));
  });

  it('перезагружает данные при возврате фокуса в окно', async () => {
    render(<Defects />);
    await screen.findByText(MOCK_REPORTS[0].id);

    await act(async () => {
      window.dispatchEvent(new Event('focus'));
    });

    await waitFor(() => expect(reportsMock).toHaveBeenCalledTimes(2));
  });

  it('отписывается от изменений при размонтировании', () => {
    const unsubscribe = vi.fn();
    subscribeMock.mockReturnValue(unsubscribe);
    const { unmount } = render(<Defects />);

    unmount();

    expect(unsubscribe).toHaveBeenCalledTimes(1);
  });

  it('показывает ошибку и повторяет загрузку списка', async () => {
    const user = userEvent.setup();
    reportsMock.mockRejectedValueOnce(new Error('Сервис недоступен'));
    render(<Defects />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис недоступен');
    await user.click(screen.getByRole('button', { name: 'Повторить' }));

    expect(await screen.findByText(MOCK_REPORTS[0].id)).toBeInTheDocument();
    expect(reportsMock).toHaveBeenCalledTimes(2);
    expect(equipmentMock).toHaveBeenCalledTimes(2);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('показывает ошибку GET оборудования, а не пустую успешную таблицу', async () => {
    equipmentMock.mockRejectedValueOnce(new Error('Каталог недоступен'));
    render(<Defects />);

    expect(await screen.findByRole('alert')).toHaveTextContent('Каталог недоступен');
    expect(screen.queryByText(MOCK_REPORTS[0].id)).not.toBeInTheDocument();
  });

  it('обрабатывает пустые списки оборудования и отчётов', async () => {
    equipmentMock.mockResolvedValue([]);
    reportsMock.mockResolvedValue([]);
    render(<Defects />);

    expect(await screen.findByText(/Отчётов пока нет/)).toBeInTheDocument();
    expect(screen.queryByText('Паспорт оборудования')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(equipmentMock).toHaveBeenCalledTimes(1);
    expect(reportsMock).toHaveBeenCalledTimes(1);
  });

  it('использует снимок оборудования из отчёта, если его нет в каталоге', async () => {
    equipmentMock.mockResolvedValue([]);
    reportsMock.mockResolvedValue([MOCK_REPORTS[0]]);
    render(<Defects />);

    await screen.findByText(MOCK_REPORTS[0].id);
    expect(within(screen.getByRole('table')).getByText(MOCK_EQUIPMENT.name)).toBeInTheDocument();
  });

  it('показывает безопасные заглушки для оборудования вне каталога и отчёта', async () => {
    equipmentMock.mockResolvedValue([]);
    reportsMock.mockResolvedValue([{
      ...MOCK_REPORTS[0],
      equipment_id: 'removed-equipment',
      result: { ...MOCK_REPORTS[0].result, defects: [] },
    }]);
    render(<Defects />);

    const table = await screen.findByRole('table');
    expect(within(table).getByText('removed-equipment')).toBeInTheDocument();
    expect(within(table).getByText('Локация не указана')).toBeInTheDocument();
    expect(within(table).getByText(MOCK_REPORTS[0].result.summary)).toBeInTheDocument();
  });
});
