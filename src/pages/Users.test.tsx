import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '../App';
import { RoleProvider } from '../context/RoleContext';
import { verifyAccessKey } from '../lib/accessKeys';
import { readMockOutbox } from '../lib/email';
import {
  findEmployeeById,
  MOCK_EMPLOYEES,
  toEmployeeAccount,
} from '../lib/employees';
import * as api from '../lib/api';

function renderUsers() {
  return render(
    <MemoryRouter initialEntries={['/users']}>
      <RoleProvider initialRole="director">
        <AppRoutes />
      </RoleProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
});

async function waitForUsersReady() {
  await screen.findByRole('columnheader', { name: 'ФИО' });
  await waitFor(() => {
    expect(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    ).toBeEnabled();
  });
}

describe('страница сотрудников', () => {
  it('показывает все колонки таблицы', async () => {
    renderUsers();
    await waitForUsersReady();

    for (const column of ['ФИО', 'Email', 'Роль', 'Ключ доступа']) {
      expect(
        screen.getByRole('columnheader', { name: column }),
      ).toBeInTheDocument();
    }

    expect(
      screen.queryByRole('columnheader', { name: 'Статус' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText('Активен')).not.toBeInTheDocument();
    expect(screen.queryByText('Заблокирован')).not.toBeInTheDocument();
  });

  it('показывает ошибку загрузки и позволяет повторить запрос', async () => {
    const user = userEvent.setup();
    const fetchEmployees = vi
      .spyOn(api, 'fetchEmployees')
      .mockRejectedValueOnce(new Error('Сервис сотрудников временно недоступен'))
      .mockResolvedValueOnce([toEmployeeAccount(MOCK_EMPLOYEES[0])]);

    renderUsers();

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Не удалось загрузить список сотрудников');
    expect(alert).toHaveTextContent('Сервис сотрудников временно недоступен');

    await user.click(within(alert).getByRole('button', { name: 'Повторить' }));

    expect(await screen.findByText('Иван Иванов')).toBeInTheDocument();
    expect(fetchEmployees).toHaveBeenCalledTimes(2);
  });

  it('показывает пустое состояние, если API не вернул сотрудников', async () => {
    vi.spyOn(api, 'fetchEmployees').mockResolvedValue([]);

    renderUsers();

    expect(await screen.findByText('Сотрудников пока нет')).toBeInTheDocument();
    expect(screen.getByText('00 записей')).toBeInTheDocument();
    expect(
      screen.queryByRole('columnheader', { name: 'ФИО' }),
    ).not.toBeInTheDocument();
  });

  it('создаёт 10-значный ключ и добавляет сотрудника', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();

    await user.click(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    );

    const dialog = screen.getByRole('dialog', {
      name: 'Добавление сотрудника',
    });
    const nameInput = within(dialog).getByLabelText('ФИО');
    const emailInput = within(dialog).getByLabelText(
      'Email для письма с ключом',
    );

    await user.type(nameInput, 'Пётр Сидоров');
    await user.type(emailInput, 'p.sidorov@promscan.ru');

    await user.selectOptions(
      within(dialog).getByLabelText('Набор функций'),
      'dispatcher',
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Создать и отправить ключ' }),
    );

    const keyDialog = await screen.findByRole('dialog', {
      name: /Письмо с ключом/,
    });
    const [message] = readMockOutbox();
    expect(message.accessKey).toMatch(/^[A-HJ-NP-Z2-9]{10}$/);
    expect(keyDialog.querySelector('[data-access-key]')).toBeNull();
    expect(keyDialog).not.toHaveTextContent(message.accessKey);
    expect(document.body).not.toHaveTextContent(message.accessKey);

    await user.click(within(keyDialog).getByRole('button', { name: 'Готово' }));
    expect(screen.getByRole('button', { name: /Добавить сотрудника/ })).toHaveFocus();
    expect(screen.getByText('Пётр Сидоров')).toBeInTheDocument();
    expect(screen.getByText('p.sidorov@promscan.ru')).toBeInTheDocument();
    expect(screen.queryByText(message.accessKey)).not.toBeInTheDocument();
  });

  it('не создаёт сотрудника с некорректным email', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();

    await user.click(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    );

    const dialog = screen.getByRole('dialog', {
      name: 'Добавление сотрудника',
    });

    await user.type(within(dialog).getByLabelText('ФИО'), 'Иван Петров');
    await user.type(
      within(dialog).getByLabelText('Email для письма с ключом'),
      'not-an-email',
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Создать и отправить ключ' }),
    );

    expect(within(dialog).getByText('Некорректный email')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('блокирует дубликат email', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();

    await user.click(
      screen.getByRole('button', { name: /Добавить сотрудника/ }),
    );

    const dialog = screen.getByRole('dialog', {
      name: 'Добавление сотрудника',
    });

    await user.type(within(dialog).getByLabelText('ФИО'), 'Иван Петров');
    await user.type(
      within(dialog).getByLabelText('Email для письма с ключом'),
      'i.ivanov@promscan.ru',
    );
    await user.click(
      within(dialog).getByRole('button', { name: 'Создать и отправить ключ' }),
    );

    expect(
      within(dialog).getByText('Сотрудник с таким email уже существует'),
    ).toBeInTheDocument();
  });

  it('закрывается по Escape', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();

    const trigger = screen.getByRole('button', { name: /Добавить сотрудника/ });
    await user.click(trigger);
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it('удерживает фокус в форме создания сотрудника', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();

    await user.click(screen.getByRole('button', { name: /Добавить сотрудника/ }));
    const dialog = screen.getByRole('dialog', { name: 'Добавление сотрудника' });
    const closeButton = within(dialog).getByRole('button', { name: 'Закрыть окно' });
    const submitButton = within(dialog).getByRole('button', { name: 'Создать и отправить ключ' });

    expect(within(dialog).getByLabelText('ФИО')).toHaveFocus();
    submitButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(submitButton).toHaveFocus();
  });

  it('удерживает фокус и возвращает его на кнопку перевыпуска', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();
    const reissueButton = screen.getAllByRole('button', { name: /Перевыпустить/ })[0];
    await user.click(reissueButton);

    const dialog = await screen.findByRole('dialog');
    const closeButton = within(dialog).getByRole('button', { name: 'Закрыть окно' });
    const doneButton = within(dialog).getByRole('button', { name: 'Готово' });

    expect(closeButton).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(doneButton).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(reissueButton).toHaveFocus();
  });

  it('не показывает ключ в таблице и перевыпускает его', async () => {
    const user = userEvent.setup();
    renderUsers();
    await waitForUsersReady();

    expect(
      screen.queryByRole('dialog', { name: 'Добавление сотрудника' }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/iiva482/)).not.toBeInTheDocument();
    expect(screen.getAllByText('•••••-•••••').length).toBeGreaterThan(0);

    await user.click(
      screen.getAllByRole('button', { name: /Перевыпустить/ })[0],
    );

    const keyDialog = await screen.findByRole('dialog', {
      name: /Письмо с ключом/,
    });
    const [message] = readMockOutbox();
    expect(message.accessKey).toMatch(/^[A-HJ-NP-Z2-9]{10}$/);
    expect(keyDialog.querySelector('[data-access-key]')).toBeNull();
    expect(document.body).not.toHaveTextContent(message.accessKey);

    const employee = findEmployeeById('emp-001');
    expect(employee).not.toBeNull();
    expect(await verifyAccessKey('PSCDSP4826', employee!)).toBe(false);
  });

  it('удерживает фокус в диалоге удаления и удаляет сотрудника', async () => {
    const user = userEvent.setup();
    let resolveDelete: () => void = () => undefined;
    const deleteRequest = new Promise<void>((resolve) => {
      resolveDelete = resolve;
    });
    const deleteEmployee = vi
      .spyOn(api, 'deleteEmployee')
      .mockReturnValue(deleteRequest);

    renderUsers();
    await waitForUsersReady();

    const deleteButton = screen.getByRole('button', {
      name: 'Удалить сотрудника: Иван Иванов',
    });
    await user.click(deleteButton);

    const dialog = screen.getByRole('dialog', { name: 'Удалить сотрудника?' });
    const closeButton = within(dialog).getByRole('button', { name: 'Закрыть окно' });
    const cancelButton = within(dialog).getByRole('button', { name: 'Отмена' });
    const confirmButton = within(dialog).getByRole('button', { name: 'Удалить' });
    expect(cancelButton).toHaveFocus();
    confirmButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();
    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(confirmButton).toHaveFocus();

    await user.click(confirmButton);
    expect(deleteEmployee).toHaveBeenCalledWith('emp-001');
    expect(within(dialog).getByRole('button', { name: 'Удаляем…' })).toBeDisabled();
    expect(within(dialog).getByRole('button', { name: 'Отмена' })).toBeDisabled();

    resolveDelete();
    await waitFor(() => {
      expect(screen.queryByText('Иван Иванов')).not.toBeInTheDocument();
    });
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Штат и ключи доступа' })).toHaveFocus();
  });

  it('закрывает диалог удаления по Escape и восстанавливает фокус', async () => {
    const user = userEvent.setup();
    const deleteEmployee = vi.spyOn(api, 'deleteEmployee');

    renderUsers();
    await waitForUsersReady();

    const trigger = screen.getByRole('button', {
      name: 'Удалить сотрудника: Иван Иванов',
    });
    await user.click(trigger);
    expect(screen.getByRole('dialog', { name: 'Удалить сотрудника?' })).toBeInTheDocument();

    await user.keyboard('{Escape}');

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
    expect(deleteEmployee).not.toHaveBeenCalled();
    expect(screen.getByText('Иван Иванов')).toBeInTheDocument();
  });

  it('оставляет диалог открытым и показывает ошибку при сбое удаления', async () => {
    const user = userEvent.setup();
    vi.spyOn(api, 'deleteEmployee').mockRejectedValue(new Error('API отказал'));

    renderUsers();
    await waitForUsersReady();

    await user.click(
      screen.getByRole('button', {
        name: 'Удалить сотрудника: Иван Иванов',
      }),
    );
    const dialog = screen.getByRole('dialog', { name: 'Удалить сотрудника?' });
    await user.click(within(dialog).getByRole('button', { name: 'Удалить' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('API отказал');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('Иван Иванов')).toBeInTheDocument();
  });
});
