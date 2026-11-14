import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { createMockInspection, type Defect } from '../lib/inspection';
import { RealtimeDefects } from './RealtimeDefects';

afterEach(cleanup);

const defaults = {
  isMock: false,
  isSnapshot: false,
  unavailable: false,
  analyzedAt: '2026-11-14T12:00:00Z',
};

function region() {
  return screen.getByRole('region', { name: 'Параметры realtime' });
}

describe('дефекты текущего кадра', () => {
  it('рисует произвольные названия и уверенность из defects, без фиксированных классов', () => {
    const defect = { ...createMockInspection().defects[0], label: 'Повреждение защитного покрытия', confidence: 0.923 };
    render(<RealtimeDefects {...defaults} defects={[defect]} />);

    expect(within(region()).getByText(defect.label)).toBeInTheDocument();
    expect(within(region()).getByText('92,3%')).toBeInTheDocument();
    expect(within(region()).getAllByRole('listitem')).toHaveLength(1);
    expect(within(region()).queryByText('Утечка масла')).not.toBeInTheDocument();
    expect(within(region()).queryByText('Ржавчина')).not.toBeInTheDocument();
    expect(within(region()).queryByText('Плохой сварной шов')).not.toBeInTheDocument();
    expect(parseFloat((region().querySelector('.realtime-defect-confidence') as HTMLElement).style.width)).toBeCloseTo(92.3);
    expect(region()).not.toHaveAttribute('data-mock');
  });

  it('не накапливает исчезнувшие строки, обновляет процент без перемонтирования той же зоны', () => {
    const [first, second, third] = createMockInspection().defects;
    const view = render(<RealtimeDefects {...defaults} defects={[first, second]} />);
    const oldRow = region().querySelector(`[data-defect-id="${first.id}"]`);

    view.rerender(<RealtimeDefects {...defaults} defects={[{ ...first, confidence: 0.812 }, third]} />);

    expect(region().querySelector(`[data-defect-id="${first.id}"]`)).toBe(oldRow);
    expect(within(region()).getByText('81,2%')).toBeInTheDocument();
    expect(within(region()).queryByText(second.label)).not.toBeInTheDocument();
    expect(within(region()).getByText(third.label)).toBeInTheDocument();
    expect(within(region()).getAllByRole('listitem')).toHaveLength(2);

    view.rerender(<RealtimeDefects {...defaults} defects={[]} />);
    expect(within(region()).queryByRole('list')).not.toBeInTheDocument();
    expect(within(region()).getByText('Дефекты в кадре не обнаружены')).toBeInTheDocument();
    expect(within(region()).queryByText(first.label)).not.toBeInTheDocument();
  });

  it('сохраняет отдельные зоны одного класса и не ограничивает число строк', () => {
    const base = createMockInspection().defects[0];
    const defects = Array.from({ length: 6 }, (_, index) => ({ ...base, id: `zone-${index}` }));
    render(<RealtimeDefects {...defaults} defects={defects} />);

    expect(within(region()).getAllByRole('listitem')).toHaveLength(6);
    expect(within(region()).getAllByText(base.label)).toHaveLength(6);
  });

  it.each([
    [0, '0%'],
    [1, '100%'],
    [0.9, '90%'],
    [0.009, '0,9%'],
  ])('не вводит свой порог: confidence=%s отображается как %s', (confidence, expected) => {
    const defect = { ...createMockInspection().defects[0], confidence };
    render(<RealtimeDefects {...defaults} defects={[defect]} />);
    expect(within(region()).getByText(expected)).toBeInTheDocument();
  });

  it.each([NaN, Infinity, -0.1, 1.1, null, undefined, '0.9'])(
    'не показывает выдуманный процент для невалидной уверенности %s',
    (confidence) => {
      const defect = { ...createMockInspection().defects[0], confidence } as Defect;
      render(<RealtimeDefects {...defaults} defects={[defect]} />);
      expect(within(region()).getByText('Нет оценки')).toBeInTheDocument();
      expect(region().querySelector('.realtime-defect-confidence')).toBeNull();
    },
  );

  it('отличает ошибку от пустого кадра и скрывает устаревшие строки', () => {
    const defects = createMockInspection().defects;
    const view = render(<RealtimeDefects {...defaults} defects={defects} unavailable />);
    expect(within(region()).getByText('Нет актуального результата')).toBeInTheDocument();
    expect(within(region()).queryByRole('list')).not.toBeInTheDocument();
    expect(within(region()).queryByText('Дефекты в кадре не обнаружены')).not.toBeInTheDocument();
    expect(region().querySelector('time')).toBeNull();

    view.rerender(<RealtimeDefects {...defaults} defects={defects} />);
    expect(within(region()).getAllByRole('listitem')).toHaveLength(3);
    expect(within(region()).queryByText('Нет актуального результата')).not.toBeInTheDocument();
  });

  it('помечает демо, показывает время кадра и отдельное состояние снимка', () => {
    render(<RealtimeDefects {...defaults} defects={[]} isMock isSnapshot />);
    expect(region()).toHaveAttribute('data-mock', 'realtime-defects');
    expect(within(region()).getByText('Демо-детекции · Уверенность модели, %')).toBeInTheDocument();
    expect(within(region()).getByText('Снимок')).toBeInTheDocument();
    expect(within(region()).getByText('Можно загрузить другой снимок.')).toBeInTheDocument();
    expect(region().querySelector('time')).toHaveAttribute('dateTime', defaults.analyzedAt);
  });

  it('не объявляет каждое изменение процента в live-region', () => {
    const defect = createMockInspection().defects[0];
    const view = render(<RealtimeDefects {...defaults} defects={[defect]} />);
    const live = region().querySelector('[aria-live="polite"]');
    const announcement = live?.textContent;
    view.rerender(<RealtimeDefects {...defaults} defects={[{ ...defect, confidence: 0.6 }]} />);
    expect(live?.textContent).toBe(announcement);
    expect(within(region()).getByText('60%')).toBeInTheDocument();
  });
});
