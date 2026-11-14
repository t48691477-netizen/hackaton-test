import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';
import { RoleProvider } from '../context/RoleContext';
import { Layout } from './Layout';

function renderLayout() {
  return render(
    <RoleProvider initialRole="director">
      <MemoryRouter initialEntries={['/scanner']}>
        <Layout />
      </MemoryRouter>
    </RoleProvider>,
  );
}

describe('мобильная навигация', () => {
  it('удерживает Tab внутри меню и возвращает фокус при закрытии', () => {
    renderLayout();
    const trigger = screen.getByRole('button', { name: 'Открыть меню' });
    trigger.focus();
    fireEvent.click(trigger);

    const dialog = screen.getByRole('dialog', { name: 'Меню навигации' });
    const firstNavigationLink = within(dialog).getByRole('link', {
      name: /Веб-сканер/,
    });
    const menuLinks = within(dialog).getAllByRole('link');
    const brandLink = menuLinks[0];
    const lastButton = within(dialog).getAllByRole('button').at(-1)!;

    expect(firstNavigationLink).toHaveFocus();
    lastButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(brandLink).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Меню навигации' })).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });
});
