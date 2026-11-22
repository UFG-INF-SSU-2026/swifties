import AsyncStorage from '@react-native-async-storage/async-storage';
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react-native';
import { Vibration } from 'react-native';
import App from '../App';
import { DEFAULT_SETTINGS } from '../src/config';
import { clientes, connect, ultimo } from './mqttMock';

jest.mock('mqtt/dist/mqtt.esm', () => ({ __esModule: true, default: require('./mqttMock') }));
jest.mock('react-native-safe-area-context', () => {
  const real = jest.requireActual('react-native-safe-area-context');
  return { ...real, SafeAreaProvider: ({ children }: any) => children,
           useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});

const dec = (extra: object = {}) => ({
  entityId: 'motor-1', decisao: 'NORMAL', timestamp: '2026-01-01T12:00:00Z', rmsNorm: 1, deltaT: 5, curtoseMax: 3, ...extra,
});
const publica = async (d: object) =>
  act(async () => ultimo().emit('message', 't', Buffer.from(JSON.stringify(d))));

beforeEach(async () => {
  await AsyncStorage.clear();
  clientes.length = 0;
  connect.mockClear();
  jest.spyOn(Vibration, 'vibrate').mockImplementation(() => {});
});
afterEach(() => (Vibration.vibrate as jest.Mock).mockRestore());

async function abrir() {
  await render(<App />);
  await waitFor(() => expect(connect).toHaveBeenCalled());
}

test('conecta com as configurações padrão e mostra estado vazio', async () => {
  await abrir();
  expect(connect.mock.calls[0][0]).toBe(`ws://${DEFAULT_SETTINGS.host}:${DEFAULT_SETTINGS.porta}`);
  expect(screen.getByText('Sem conexão')).toBeTruthy();
  expect(screen.getByText('Conectando')).toBeTruthy();
});

test('usa configurações salvas no AsyncStorage', async () => {
  await AsyncStorage.setItem('swifties:settings', JSON.stringify({ host: '9.9.9.9' }));
  await abrir();
  expect(connect.mock.calls[0][0]).toBe(`ws://9.9.9.9:${DEFAULT_SETTINGS.porta}`);
});

test('online sem ativos: aguardando decisões', async () => {
  await abrir();
  await act(async () => ultimo().emit('connect'));
  expect(screen.getByText('Online')).toBeTruthy();
  expect(screen.getByText('Aguardando decisões')).toBeTruthy();
});

test('erro de conexão aparece na tela vazia', async () => {
  await abrir();
  await act(async () => ultimo().emit('error', new Error('ECONNREFUSED')));
  expect(screen.getByText('Erro')).toBeTruthy();
  expect(screen.getByText(/ECONNREFUSED/)).toBeTruthy();
});

test('cards e resumo refletem as decisões recebidas', async () => {
  await abrir();
  await act(async () => ultimo().emit('connect'));
  await publica(dec({ entityId: 'b' }));
  await publica(dec({ entityId: 'a', decisao: 'ATENCAO' }));
  await publica(dec({ entityId: 'c', decisao: 'CRITICO' }));
  expect(screen.getAllByText('Ativos').length).toBeGreaterThan(0);
  const titulos = screen.getAllByText(/^[abc]$/).map((n) => n.props.children);
  expect(titulos).toEqual(['a', 'b', 'c']);        // ordenados por id
  expect(screen.getByText('Críticos')).toBeTruthy();
});

test('ajustes: salvar persiste, reconecta e volta para ativos', async () => {
  await abrir();
  await fireEvent.press(screen.getByText('Ajustes'));
  await fireEvent.changeText(screen.getByDisplayValue(DEFAULT_SETTINGS.host), '7.7.7.7');
  await fireEvent.press(screen.getByText('Salvar e reconectar'));

  await waitFor(() => expect(connect).toHaveBeenCalledTimes(2));
  expect(connect.mock.calls[1][0]).toBe(`ws://7.7.7.7:${DEFAULT_SETTINGS.porta}`);
  expect(JSON.parse((await AsyncStorage.getItem('swifties:settings'))!).host).toBe('7.7.7.7');
  expect(screen.getByText('Sem conexão')).toBeTruthy();
});

test('desligar alertas nos ajustes impede a vibração', async () => {
  await abrir();
  await act(async () => ultimo().emit('connect'));
  await fireEvent.press(screen.getByText('Ajustes'));
  await fireEvent(screen.getByRole('switch'), 'valueChange', false);
  await fireEvent.press(screen.getByText('Ativos'));
  await publica(dec());
  await publica(dec({ decisao: 'CRITICO' }));
  expect(Vibration.vibrate).not.toHaveBeenCalled();
});
