import { fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { AppRoutes } from '../App';
import { RoleProvider } from '../context/RoleContext';
import { verifyAccessKey } from '../lib/accessKeys';
import { readMockOutbox } from '../lib/email';
import {
  MOCK_EMPLOYEES,
  findEmployeeById,
  loadEmployees,
  saveEmployees,
  type Employee,
} from '../lib/employees';

function renderUsers(role: 'director' | 'admin' = 'director') {
  return render(
    <MemoryRouter initialEntries={['/users']}>
      <RoleProvider initialRole={role}>
        <AppRoutes />
      </RoleProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
});

describe('страница сотрудников', () => {
  it('показывает все колонки таблицы', () => {
    renderUsers();

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

  it('создаёт 10-значный ключ и добавляет сотрудника', async () => {
    const user = userEvent.setup();
    renderUsers();

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

  it('удаляет сотрудника после подтверждения', async () => {
    const user = userEvent.setup();
    renderUsers('admin');

    await user.click(
      screen.getAllByRole('button', { name: 'Удалить сотрудника: Иван Иванов' })[0],
    );
    const dialog = await screen.findByRole('alertdialog', {
      name: /Удалить Иван Иванов/,
    });
    await user.click(within(dialog).getByRole('button', { name: 'Отмена' }));
    expect(findEmployeeById('emp-001')).not.toBeNull();

    await user.click(
      screen.getAllByRole('button', { name: 'Удалить сотрудника: Иван Иванов' })[0],
    );
    const confirm = await screen.findByRole('alertdialog');
    await user.click(within(confirm).getByRole('button', { name: 'Удалить' }));

    expect(findEmployeeById('emp-001')).toBeNull();
    expect(screen.queryByText('Иван Иванов')).not.toBeInTheDocument();
    expect(loadEmployees()).toHaveLength(MOCK_EMPLOYEES.length - 1);
  });

  it('администратор не может удалить другого администратора', () => {
    const admin: Employee = {
      ...MOCK_EMPLOYEES[0],
      id: 'emp-admin',
      fullName: 'Пётр Админов',
      email: 'p.adminov@promscan.ru',
      role: 'admin',
    };
    saveEmployees([admin, ...MOCK_EMPLOYEES]);
    renderUsers('admin');

    expect(
      screen.getAllByRole('button', { name: 'Удалить сотрудника: Пётр Админов' })[0],
    ).toBeDisabled();
    expect(
      screen.getAllByRole('button', { name: 'Удалить сотрудника: Иван Иванов' })[0],
    ).toBeEnabled();
  });
});
