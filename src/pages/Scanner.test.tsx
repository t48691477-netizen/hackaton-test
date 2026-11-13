import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from 'vitest';
import { AppRoutes } from '../App';
import { RoleProvider } from '../context/RoleContext';
import * as api from '../lib/api';
import { MOCK_ENGINEERS } from '../lib/employees';
import { createMockInspection, type Report } from '../lib/inspection';
import { SESSION_STORAGE_KEY } from '../lib/session';

const originalMediaDevices = navigator.mediaDevices;
const originalPlay = HTMLMediaElement.prototype.play;
const originalGetContext = HTMLCanvasElement.prototype.getContext;
const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
const originalImage = window.Image;
const originalFileReader = window.FileReader;
const originalClipboard = navigator.clipboard;
const originalUseMock = api.API_CONFIG.useMock;

const stopTrack = vi.fn();
let inspectImageSpy: MockInstance<typeof api.inspectImage>;
let createReportSpy: MockInstance<typeof api.createReport>;

function savedReport(input: api.CreateReportInput): Report {
  const assignee =
    MOCK_ENGINEERS.find((employee) => employee.id === input.assigneeId) ?? null;

  return {
    id: 'report-test',
    equipment_id: input.equipmentId,
    inspection_id: input.inspectionId,
    status: input.status,
    comment: input.comment ?? '',
    photo_url: null,
    result: input.result,
    assignee: assignee
      ? { id: assignee.id, full_name: assignee.fullName }
      : null,
    started_at: input.status === 'open' ? null : '2026-11-13T12:00:00Z',
    completed_at: input.status === 'closed' ? '2026-11-13T12:00:00Z' : null,
    repair_comment: null,
    created_at: '2026-11-13T12:00:00Z',
    updated_at: '2026-11-13T12:00:00Z',
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

async function advanceTime(milliseconds: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
}

async function startLiveWithTimers() {
  vi.useFakeTimers();
  const view = renderScanner();
  await act(async () => {});
  return view;
}

async function uploadPhoto() {
  class LoadedImage {
    naturalWidth = 1280;
    naturalHeight = 720;
    onload: (() => void) | null = null;

    set src(_value: string) {
      queueMicrotask(() => this.onload?.());
    }
  }

  class LoadedFileReader {
    result: string | null = null;
    onload: (() => void) | null = null;

    readAsDataURL(_file: Blob) {
      this.result = 'data:image/jpeg;base64,cGhvdG8=';
      queueMicrotask(() => this.onload?.());
    }
  }

  Object.defineProperty(window, 'Image', { configurable: true, value: LoadedImage });
  Object.defineProperty(window, 'FileReader', { configurable: true, value: LoadedFileReader });

  const file = new File(['image'], 'pump.jpg', { type: 'image/jpeg' });
  await act(async () => {
    fireEvent.change(screen.getByLabelText('Загрузить фотографию оборудования'), {
      target: { files: [file] },
    });
  });
  return file;
}

function renderScanner() {
  sessionStorage.setItem(
    SESSION_STORAGE_KEY,
    JSON.stringify({
      accountId: 'director',
      fullName: 'Генеральный директор',
      email: 'director@promscan.example',
      role: 'director',
      issuedAt: '2026-11-13T09:00:00Z',
    }),
  );

  return render(
    <MemoryRouter initialEntries={['/scanner']}>
      <RoleProvider initialRole="director">
        <AppRoutes />
      </RoleProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  stopTrack.mockClear();
  inspectImageSpy = vi.spyOn(api, 'inspectImage');
  createReportSpy = vi.spyOn(api, 'createReport');
  Object.defineProperty(api.API_CONFIG, 'useMock', { configurable: true, value: true });

  Object.defineProperty(navigator, 'mediaDevices', {
    configurable: true,
    value: {
      getUserMedia: vi.fn().mockResolvedValue({
        getTracks: () => [{ stop: stopTrack }],
      }),
    },
  });

  Object.defineProperty(HTMLMediaElement.prototype, 'play', {
    configurable: true,
    value: vi.fn().mockResolvedValue(undefined),
  });

  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    configurable: true,
    value: vi.fn(() => ({ drawImage: vi.fn() })),
  });

  Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {
    configurable: true,
    value: vi.fn(() => 'data:image/jpeg;base64,mock'),
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  Object.defineProperty(api.API_CONFIG, 'useMock', { configurable: true, value: originalUseMock });
  if (originalMediaDevices) {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: originalMediaDevices,
    });
  } else {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: undefined,
    });
  }

  Object.defineProperty(HTMLMediaElement.prototype, 'play', {
    configurable: true,
    value: originalPlay,
  });
  Object.defineProperty(HTMLCanvasElement.prototype, 'getContext', {
    configurable: true,
    value: originalGetContext,
  });
  Object.defineProperty(HTMLCanvasElement.prototype, 'toDataURL', {
    configurable: true,
    value: originalToDataURL,
  });
  Object.defineProperty(window, 'Image', {
    configurable: true,
    value: originalImage,
  });
  Object.defineProperty(window, 'FileReader', {
    configurable: true,
    value: originalFileReader,
  });
  Object.defineProperty(navigator, 'clipboard', {
    configurable: true,
    value: originalClipboard,
  });

  vi.useRealTimers();
});

describe('веб-сканер', () => {
  it('показывает объяснение в правой панели до первого результата', async () => {
    await startLiveWithTimers();

    const report = screen.getByRole('complementary', { name: 'Результат распознавания' });
    expect(within(report).getByText('Здесь появятся характеристики')).toBeInTheDocument();
    expect(within(report).getByText(/После распознавания наведите курсор на дефект/)).toBeInTheDocument();
    expect(report.querySelector('[data-placeholder="equipment-specs"]')).not.toBeNull();
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByRole('status')).toHaveTextContent('Распознавание активно');
    expect(screen.queryByRole('button', { name: 'Передать задачу' })).not.toBeInTheDocument();
    expect(inspectImageSpy).not.toHaveBeenCalled();
  });

  it('автоматически запускает камеру, распознаёт через 500 мс и обновляет через 1800 мс', async () => {
    await startLiveWithTimers();

    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({
      audio: false,
      video: {
        facingMode: { ideal: 'environment' },
        width: { ideal: 1280 },
        height: { ideal: 720 },
      },
    });
    expect(HTMLMediaElement.prototype.play).toHaveBeenCalledTimes(1);

    await advanceTime(499);
    expect(inspectImageSpy).not.toHaveBeenCalled();
    await advanceTime(1);
    expect(inspectImageSpy).toHaveBeenCalledTimes(1);
    expect(screen.getByText('Трещина корпуса')).toBeInTheDocument();

    await advanceTime(1799);
    expect(inspectImageSpy).toHaveBeenCalledTimes(1);
    await advanceTime(1);
    expect(inspectImageSpy).toHaveBeenCalledTimes(2);
    await advanceTime(1800);
    expect(inspectImageSpy).toHaveBeenCalledTimes(3);
    expect(screen.queryByRole('button', { name: /Анализировать/i })).not.toBeInTheDocument();
  });

  it('запускает live-распознавание без кнопки анализа', async () => {
    renderScanner();

    await screen.findAllByText('Распознавание активно');

    expect(
      screen.queryByRole('button', { name: /Анализировать/i }),
    ).not.toBeInTheDocument();

    expect(
      await screen.findByText('Трещина корпуса', {}, { timeout: 3000 }),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Технические характеристики'),
    ).toBeInTheDocument();
    expect(
      screen.getByText('Рекомендация по восстановлению'),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Рекомендация относится к повреждённому узлу/),
    ).toBeInTheDocument();
    expect(screen.queryByText('Заключение ИИ · ТОиР')).not.toBeInTheDocument();
    const specs = screen.getByRole('region', { name: 'Технические характеристики' });
    expect(within(specs).queryByText('Паспорт оборудования')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Подача')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Чугун СЧ20')).not.toBeInTheDocument();
    expect(within(specs).queryByText('ЦНС 38-220')).not.toBeInTheDocument();
    expect(
      screen.getByText(/Наведите курсор на рамку дефекта или строку ниже/i),
    ).toBeInTheDocument();
  });

  it('показывает характеристики узла при наведении на строку дефекта', async () => {
    renderScanner();

    await screen.findAllByText('Распознавание активно');

    const defectRow = await screen.findByRole(
      'button',
      { name: /^Дефект: Трещина корпуса, уверенность/i },
      { timeout: 3000 },
    );

    fireEvent.mouseEnter(defectRow);

    expect(screen.getByText('Активная зона')).toBeInTheDocument();
    expect(screen.getByText('Корпус насоса')).toBeInTheDocument();
    expect(screen.getByText('Толщина стенки')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
    expect(screen.getByText('мм')).toBeInTheDocument();
    const specs = screen.getByRole('region', { name: 'Технические характеристики' });
    expect(specs).toHaveAttribute('data-mock', 'equipment-specs');
    expect(specs).toHaveAttribute('data-node-id', 'node-housing');
    expect(within(specs).getByText('демо · mock')).toBeInTheDocument();
    expect(within(specs).getByText(/Демо-характеристики узла/)).toBeInTheDocument();
    expect(within(specs).queryByText(/Длина трещины|Глубина трещины|Площадь дефекта/i)).not.toBeInTheDocument();

    fireEvent.mouseLeave(defectRow);
    expect(screen.getByText(/Наведите курсор на рамку дефекта или строку ниже/i)).toBeInTheDocument();
    expect(within(specs).queryByText('Паспорт оборудования')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Подача')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Чугун СЧ20')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Толщина стенки')).not.toBeInTheDocument();
  });

  it('не меняет раскладку списка дефектов при выборе строки', async () => {
    await startLiveWithTimers();
    await advanceTime(500);

    const firstRow = screen.getByRole('button', {
      name: /^Дефект: Трещина корпуса, уверенность/i,
    });
    const secondRow = screen.getByRole('button', {
      name: /^Дефект: Износ крепления, уверенность/i,
    });
    const firstRecommendation = firstRow.querySelector('[data-defect-recommendation]');
    const secondRecommendation = secondRow.querySelector('[data-defect-recommendation]');

    expect(firstRecommendation).toHaveAttribute('aria-hidden', 'true');
    expect(secondRecommendation).toHaveAttribute('aria-hidden', 'true');

    fireEvent.mouseEnter(firstRow);
    expect(firstRecommendation).toHaveAttribute('aria-hidden', 'false');
    expect(secondRecommendation).toHaveAttribute('aria-hidden', 'true');

    fireEvent.mouseLeave(firstRow);
    expect(firstRecommendation).toHaveAttribute('aria-hidden', 'true');
    expect(secondRecommendation).toHaveAttribute('aria-hidden', 'true');
  });

  it('показывает характеристики соответствующего узла при наведении на рамку', async () => {
    await startLiveWithTimers();
    await advanceTime(500);

    const frame = screen.getByRole('button', { name: /^Рамка дефекта: Износ крепления, уверенность/i });
    expect(frame).toHaveAttribute('aria-controls', 'equipment-specs-panel');
    fireEvent.mouseEnter(frame);

    const specs = screen.getByRole('region', { name: 'Технические характеристики' });
    expect(specs).toHaveAttribute('data-node-id', 'node-mount');
    expect(within(specs).getByText('Крепление к раме')).toBeInTheDocument();
    expect(within(specs).getByText('Момент затяжки')).toBeInTheDocument();
    expect(within(specs).getByText('120')).toBeInTheDocument();

    fireEvent.mouseLeave(frame);
    expect(within(specs).getByText(/Наведите курсор на рамку дефекта или строку ниже/i)).toBeInTheDocument();
    expect(within(specs).queryByText('Паспорт оборудования')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Подача')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Чугун СЧ20')).not.toBeInTheDocument();
    expect(within(specs).queryByText('Момент затяжки')).not.toBeInTheDocument();
  });

  it.each(['Рамка дефекта', 'Дефект'])('открывает характеристики при фокусе: %s', async (prefix) => {
    await startLiveWithTimers();
    await advanceTime(500);

    const target = screen.getByRole('button', { name: new RegExp(`^${prefix}: Трещина корпуса, уверенность`) });
    fireEvent.focus(target);
    expect(screen.getByText('Корпус насоса')).toBeInTheDocument();

    fireEvent.mouseEnter(target);
    fireEvent.mouseLeave(target);
    expect(screen.getByText('Корпус насоса')).toBeInTheDocument();

    fireEvent.blur(target);
    expect(screen.getByText(/Наведите курсор на рамку дефекта или строку ниже/i)).toBeInTheDocument();
    expect(screen.queryByText('Паспорт оборудования')).not.toBeInTheDocument();
    expect(screen.queryByText('Подача')).not.toBeInTheDocument();
    expect(screen.queryByText('Чугун СЧ20')).not.toBeInTheDocument();
    expect(screen.queryByText('Корпус насоса')).not.toBeInTheDocument();
  });

  it('сохраняет выбранный нажатием дефект после ухода указателя', async () => {
    await startLiveWithTimers();
    await advanceTime(500);
    const row = screen.getByRole('button', { name: /^Дефект: Трещина корпуса, уверенность/i });
    fireEvent.click(row);
    fireEvent.mouseLeave(row);
    fireEvent.blur(row);

    expect(row).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText('Корпус насоса')).toBeInTheDocument();
  });

  it('распознаёт загруженное фото автоматически', async () => {
    await startLiveWithTimers();
    await uploadPhoto();

    expect(screen.getByRole('status')).toHaveTextContent('Распознавание снимка');
    expect(screen.queryByRole('button', { name: /Анализировать/i })).not.toBeInTheDocument();
    expect(stopTrack).toHaveBeenCalled();

    await advanceTime(500);
    expect(screen.getByRole('status')).toHaveTextContent('Снимок распознан');
    expect(screen.getByText('Трещина корпуса')).toBeInTheDocument();
    expect(inspectImageSpy).toHaveBeenCalledTimes(1);
    await advanceTime(5400);
    expect(inspectImageSpy).toHaveBeenCalledTimes(1);
  });

  it('не пропускает анализ фото, когда запрос предыдущего кадра ещё выполняется', async () => {
    const pending = deferred<ReturnType<typeof createMockInspection>>();
    inspectImageSpy.mockImplementationOnce(() => pending.promise);
    await startLiveWithTimers();
    await advanceTime(500);
    expect(inspectImageSpy).toHaveBeenCalledTimes(1);

    await uploadPhoto();
    await advanceTime(500);
    expect(inspectImageSpy).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Трещина корпуса')).toBeInTheDocument();

    const staleResult = createMockInspection(99);
    staleResult.equipment = { ...staleResult.equipment, name: 'Устаревший результат камеры' };
    await act(async () => pending.resolve(staleResult));
    expect(screen.queryByText('Устаревший результат камеры')).not.toBeInTheDocument();
  });

  it('не возвращается к камере, если доступ разрешён уже после загрузки фото', async () => {
    const pending = deferred<MediaStream>();
    vi.mocked(navigator.mediaDevices.getUserMedia).mockReturnValueOnce(pending.promise);
    await startLiveWithTimers();
    await uploadPhoto();

    await act(async () => pending.resolve({ getTracks: () => [{ stop: stopTrack }] } as unknown as MediaStream));
    expect(stopTrack).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('status')).toHaveTextContent('Распознавание снимка');
    await advanceTime(500);
    expect(screen.getByRole('status')).toHaveTextContent('Снимок распознан');
  });

  it('передаёт задачу выбранному исполнителю через mock API', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText },
    });
    createReportSpy.mockImplementation(async (input) => savedReport(input));
    await startLiveWithTimers();
    await advanceTime(500);
    const result = await inspectImageSpy.mock.results[0].value;
    fireEvent.click(screen.getByRole('button', { name: 'Передать задачу' }));

    const form = screen.getByRole('form', { name: 'Передача задачи' });
    expect(form.closest('[data-mock="report-create"]')).not.toBeNull();
    expect(form.closest('[data-api="POST /api/reports"]')).not.toBeNull();
    const assigneeSelect = within(form).getByLabelText('Исполнитель');
    expect(assigneeSelect).toHaveFocus();
    expect(within(form).getByRole('option', { name: 'Анна Петрова' })).toHaveValue('emp-002');
    expect(within(form).getByRole('option', { name: 'Алексей Смирнов' })).toHaveValue('emp-003');
    expect(assigneeSelect).toHaveValue('emp-002');
    expect(within(form).queryByLabelText('Статус ремонта')).not.toBeInTheDocument();

    fireEvent.change(assigneeSelect, { target: { value: 'emp-002' } });
    expect(assigneeSelect).toHaveValue('emp-002');
    fireEvent.change(assigneeSelect, { target: { value: 'emp-003' } });
    fireEvent.change(within(form).getByLabelText(/Комментарий/), { target: { value: 'Передано Алексею' } });

    await act(async () => fireEvent.click(within(form).getByRole('button', { name: 'Передать задачу' })));

    expect(createReportSpy).toHaveBeenCalledWith({
      equipmentId: result.equipment.id,
      inspectionId: result.inspection_id,
      status: 'open',
      comment: 'Передано Алексею',
      photo: null,
      result,
      assigneeId: 'emp-003',
    });
    expect(screen.getByText('Задача передана · mock')).toBeInTheDocument();
    expect(screen.getByText('Алексей Смирнов')).toBeInTheDocument();

    const link = screen.getByRole('link', { name: 'Открыть задачу' });
    expect(link).toHaveAttribute('data-task-link');
    expect(link).toHaveAttribute('href', `${window.location.origin}/task/report-test`);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noreferrer');
    expect(new URL(link.getAttribute('href') ?? '').origin).toBe(window.location.origin);

    fireEvent.click(screen.getByRole('button', { name: 'Скопировать ссылку' }));
    await act(async () => {});
    expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/task/report-test`);
    expect(screen.getByRole('button', { name: 'Ссылка скопирована' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Анализировать/i })).not.toBeInTheDocument();
  });

  it('отменяет передачу задачи и возвращает фокус к кнопке', async () => {
    await startLiveWithTimers();
    await advanceTime(500);
    const openButton = screen.getByRole('button', { name: 'Передать задачу' });
    fireEvent.click(openButton);
    fireEvent.click(screen.getByRole('button', { name: 'Отмена' }));

    expect(screen.queryByRole('form', { name: 'Передача задачи' })).not.toBeInTheDocument();
    expect(createReportSpy).not.toHaveBeenCalled();
    expect(openButton).toHaveFocus();
  });

  it('не останавливает live-цикл и не меняет результат задачи во время передачи', async () => {
    const pending = deferred<Report>();
    createReportSpy.mockImplementationOnce(() => pending.promise);
    await startLiveWithTimers();
    await advanceTime(500);
    const result = await inspectImageSpy.mock.results[0].value;
    fireEvent.click(screen.getByRole('button', { name: 'Передать задачу' }));

    await advanceTime(1800);
    expect(inspectImageSpy).toHaveBeenCalledTimes(2);
    const frame = screen.getByRole('button', { name: /^Рамка дефекта: Трещина корпуса, уверенность/i });
    fireEvent.mouseEnter(frame);
    expect(screen.getByText('Корпус насоса')).toBeInTheDocument();
    const form = screen.getByRole('form', { name: 'Передача задачи' });
    fireEvent.click(within(form).getByRole('button', { name: 'Передать задачу' }));

    const saving = within(form).getByRole('button', { name: 'Передача задачи…' });
    expect(saving).toBeDisabled();
    expect(within(form).getByLabelText('Исполнитель')).toBeDisabled();
    fireEvent.submit(form);
    expect(createReportSpy).toHaveBeenCalledTimes(1);
    expect(createReportSpy.mock.calls[0][0].result).toBe(result);
    expect(createReportSpy.mock.calls[0][0].status).toBe('open');
    expect(createReportSpy.mock.calls[0][0].assigneeId).toBe('emp-002');

    await advanceTime(1800);
    expect(inspectImageSpy).toHaveBeenCalledTimes(3);
    await act(async () => pending.resolve(savedReport(createReportSpy.mock.calls[0][0])));
    expect(screen.getByText('Задача передана · mock')).toBeInTheDocument();
    expect(screen.getByText('Анна Петрова')).toBeInTheDocument();
  });

  it('показывает ошибку передачи и позволяет повторить без потери полей', async () => {
    createReportSpy.mockImplementation(async (input) => savedReport(input));
    createReportSpy.mockRejectedValueOnce(new Error('Offline'));
    await startLiveWithTimers();
    await advanceTime(500);
    fireEvent.click(screen.getByRole('button', { name: 'Передать задачу' }));
    const form = screen.getByRole('form', { name: 'Передача задачи' });
    fireEvent.change(within(form).getByLabelText('Исполнитель'), { target: { value: 'emp-003' } });
    fireEvent.change(within(form).getByLabelText(/Комментарий/), { target: { value: 'Проверено' } });

    await act(async () => fireEvent.click(within(form).getByRole('button', { name: 'Передать задачу' })));
    expect(screen.getByRole('alert')).toHaveTextContent('Не удалось передать задачу');
    expect(within(form).getByLabelText('Исполнитель')).toHaveValue('emp-003');
    expect(within(form).getByLabelText(/Комментарий/)).toHaveValue('Проверено');

    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Повторить сохранение' })));
    expect(createReportSpy).toHaveBeenCalledTimes(2);
    expect(createReportSpy.mock.calls[1][0]).toEqual(createReportSpy.mock.calls[0][0]);
    expect(createReportSpy.mock.calls[1][0].assigneeId).toBe('emp-003');
    expect(screen.getByText('Задача передана · mock')).toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('использует текущий снимок как фото задачи в real-режиме', async () => {
    await startLiveWithTimers();
    const photo = await uploadPhoto();
    Object.defineProperty(api.API_CONFIG, 'useMock', { configurable: true, value: false });
    inspectImageSpy.mockImplementation(async (_image, _equipmentId, tick) => {
      const result = createMockInspection(tick);
      result.meta.vision_mode = 'real';
      return result;
    });
    createReportSpy.mockImplementation(async (input) => savedReport(input));
    await advanceTime(500);
    fireEvent.click(screen.getByRole('button', { name: 'Передать задачу' }));
    const panel = screen.getByRole('region', { name: 'Передача задачи' });
    expect(panel).not.toHaveAttribute('data-mock');
    expect(screen.getByRole('region', { name: 'Технические характеристики' })).not.toHaveAttribute('data-mock');

    await act(async () => fireEvent.click(within(panel).getByRole('button', { name: 'Передать задачу' })));
    expect(createReportSpy.mock.calls[0][0].photo).toBe(photo);
    expect(createReportSpy.mock.calls[0][0].assigneeId).toBe('emp-002');
    expect(screen.getByText('Задача передана', { exact: true })).toBeInTheDocument();
  });

  it('позволяет заменить итоговое фото перед передачей задачи', async () => {
    await startLiveWithTimers();
    await advanceTime(500);
    Object.defineProperty(api.API_CONFIG, 'useMock', { configurable: true, value: false });
    createReportSpy.mockImplementation(async (input) => savedReport(input));
    fireEvent.click(screen.getByRole('button', { name: 'Передать задачу' }));
    const form = screen.getByRole('form', { name: 'Передача задачи' });
    const photo = new File(['report image'], 'report.jpg', { type: 'image/jpeg' });
    fireEvent.change(within(form).getByLabelText(/Итоговое фото/), { target: { files: [photo] } });

    await act(async () => fireEvent.click(within(form).getByRole('button', { name: 'Передать задачу' })));
    expect(createReportSpy.mock.calls[0][0].photo).toBe(photo);
  });

  it('останавливает поток и таймеры при уходе со страницы', async () => {
    const { unmount } = await startLiveWithTimers();
    await advanceTime(500);
    unmount();
    expect(stopTrack).toHaveBeenCalledTimes(1);
    await advanceTime(5400);
    expect(inspectImageSpy).toHaveBeenCalledTimes(1);
  });

  it('показывает понятную ошибку, если доступ к камере запрещён', async () => {
    const denied = Object.assign(new Error('Permission denied'), {
      name: 'NotAllowedError',
    });

    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockRejectedValue(denied),
      },
    });

    renderScanner();

    expect(
      await screen.findByText(/Доступ к камере запрещён/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Повторить' }),
    ).toBeInTheDocument();
  });
});
