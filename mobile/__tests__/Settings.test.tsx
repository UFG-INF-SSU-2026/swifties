import { fireEvent, render, screen } from '@testing-library/react-native';
import { SettingsScreen } from '../src/Settings';
import { DEFAULT_SETTINGS } from '../src/config';
import { ThemeProvider } from '../src/theme';

const inicial = { host: '1.2.3.4', porta: '1883', usuario: 'ana', senha: 'x' };

async function montar(props: Partial<React.ComponentProps<typeof SettingsScreen>> = {}) {
  const onSave = jest.fn(), onAlertas = jest.fn();
  await render(
    <ThemeProvider>
      <SettingsScreen settings={inicial} alertas={true} onSave={onSave} onAlertas={onAlertas} {...props} />
    </ThemeProvider>,
  );
  return { onSave, onAlertas };
}

test('mostra as configurações atuais', async () => {
  await montar();
  expect(screen.getByDisplayValue('1.2.3.4')).toBeTruthy();
  expect(screen.getByDisplayValue('1883')).toBeTruthy();
  expect(screen.getByDisplayValue('ana')).toBeTruthy();
});

test('salvar envia valores editados (com trim)', async () => {
  const { onSave } = await montar();
  await fireEvent.changeText(screen.getByDisplayValue('1.2.3.4'), '  10.0.0.9 ');
  await fireEvent.press(screen.getByText('Salvar e reconectar'));
  expect(onSave).toHaveBeenCalledWith({ ...inicial, host: '10.0.0.9' });
});

test('restaurar padrão volta aos valores default', async () => {
  const { onSave } = await montar();
  await fireEvent.press(screen.getByText('Restaurar padrão'));
  await fireEvent.press(screen.getByText('Salvar e reconectar'));
  expect(onSave).toHaveBeenCalledWith(DEFAULT_SETTINGS);
});

test('alternar vibração chama onAlertas', async () => {
  const { onAlertas } = await montar();
  await fireEvent(screen.getByRole('switch'), 'valueChange', false);
  expect(onAlertas).toHaveBeenCalledWith(false);
});

test('seletor de aparência troca o modo e persiste', async () => {
  const AsyncStorage = require('@react-native-async-storage/async-storage');
  await montar();
  await fireEvent.press(screen.getByText('Escuro'));
  expect(AsyncStorage.setItem).toHaveBeenCalledWith('swifties:theme', 'dark');
});
