import { act, renderHook } from '@testing-library/react-native';
import { Vibration } from 'react-native';
import { clientes, connect, ultimo } from './mqttMock';
import { useMqtt } from '../src/useMqtt';
import { MAX_HISTORICO, MAX_PONTOS, Settings } from '../src/config';

jest.mock('mqtt/dist/mqtt.esm', () => ({ __esModule: true, default: require('./mqttMock') }));

const settings: Settings = { host: '10.0.0.5', porta: '9001', usuario: 'u', senha: 's' };
const dec = (extra: object = {}) => ({
  entityId: 'motor-1', decisao: 'NORMAL', timestamp: '2026-01-01T12:00:00Z',
  rmsNorm: 1, deltaT: 5, curtoseMax: 3, ...extra,
});
const envia = async (d: object | string) =>
  await act(() => ultimo().emit('message', 't', Buffer.from(typeof d === 'string' ? d : JSON.stringify(d))));

beforeEach(() => {
  clientes.length = 0;
  connect.mockClear();
  jest.spyOn(Vibration, 'vibrate').mockImplementation(() => {});
});
// restoreAllMocks apagaria a implementação do jest.fn de connect
afterEach(() => (Vibration.vibrate as jest.Mock).mockRestore());

test('sem configurações não conecta', async () => {
  const { result } = await renderHook(() => useMqtt(null, true));
  expect(connect).not.toHaveBeenCalled();
  expect(result.current.status).toBe('offline');
});

test('conecta no ws://host:porta com credenciais e assina o tópico', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  expect(result.current.status).toBe('conectando');
  expect(connect.mock.calls[0][0]).toBe('ws://10.0.0.5:9001');
  expect(connect.mock.calls[0][1]).toMatchObject({ username: 'u', password: 's' });
  expect(connect.mock.calls[0][1].clientId).toMatch(/^mobile_/);

  await act(async () => ultimo().emit('connect'));
  expect(result.current.status).toBe('online');
  expect(ultimo().subscribe).toHaveBeenCalledWith('consumidor/+/decisao', { qos: 1 });
});

test('transições de status: reconnect, close e error', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  await act(async () => ultimo().emit('connect'));
  await act(async () => ultimo().emit('close'));
  expect(result.current.status).toBe('offline');
  await act(async () => ultimo().emit('reconnect'));
  expect(result.current.status).toBe('conectando');
  await act(async () => ultimo().emit('error', new Error('boom')));
  expect(result.current.status).toBe('erro');
  expect(result.current.erro).toBe('boom');
  await act(async () => ultimo().emit('close'));
  expect(result.current.status).toBe('erro');   // close não mascara o erro
  await act(async () => ultimo().emit('connect'));
  expect(result.current.status).toBe('online');
  expect(result.current.erro).toBe('');
});

test('mensagem cria o ativo com ponto e histórico', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  await envia(dec());
  const a = result.current.ativos['motor-1'];
  expect(a.atual.decisao).toBe('NORMAL');
  expect(a.pontos).toHaveLength(1);
  expect(a.pontos[0]).toMatchObject({ rms: 1, temp: 5 });
  expect(a.historico).toHaveLength(1);
});

test('histórico só cresce quando a decisão muda', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  await envia(dec()); await envia(dec()); await envia(dec({ decisao: 'ATENCAO' }));
  const a = result.current.ativos['motor-1'];
  expect(a.pontos).toHaveLength(3);
  expect(a.historico.map((h) => h.decisao)).toEqual(['ATENCAO', 'NORMAL']);
});

test('limites de pontos e histórico', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  for (let i = 0; i < MAX_PONTOS + 10; i++) await envia(dec({ decisao: i % 2 ? 'NORMAL' : 'ATENCAO' }));
  const a = result.current.ativos['motor-1'];
  expect(a.pontos).toHaveLength(MAX_PONTOS);
  expect(a.historico).toHaveLength(MAX_HISTORICO);
});

test('métricas não numéricas viram null', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  await envia({ entityId: 'm', decisao: 'SEM_COMUNICACAO', timestamp: '2026-01-01T12:00:00Z' });
  expect(result.current.ativos.m.pontos[0]).toMatchObject({ rms: null, temp: null });
});

test('payload inválido ou sem entityId é ignorado', async () => {
  const { result } = await renderHook(() => useMqtt(settings, true));
  await envia('{ruim');
  await envia({ decisao: 'NORMAL' });
  expect(result.current.ativos).toEqual({});
});

describe('vibração em estado crítico', () => {
  test('vibra ao mudar para CRITICO', async () => {
    await renderHook(() => useMqtt(settings, true));
    await envia(dec());
    await envia(dec({ decisao: 'CRITICO' }));
    expect(Vibration.vibrate).toHaveBeenCalledTimes(1);
  });

  test('não vibra se alertas desligados', async () => {
    await renderHook(() => useMqtt(settings, false));
    await envia(dec());
    await envia(dec({ decisao: 'CRITICO' }));
    expect(Vibration.vibrate).not.toHaveBeenCalled();
  });

  test('não vibra na primeira mensagem nem repetindo CRITICO', async () => {
    await renderHook(() => useMqtt(settings, true));
    await envia(dec({ decisao: 'CRITICO' }));
    await envia(dec({ decisao: 'CRITICO' }));
    expect(Vibration.vibrate).not.toHaveBeenCalled();
  });
});

test('encerra o cliente ao desmontar e reconecta se as configurações mudam', async () => {
  const { rerender, unmount } = await renderHook(({ s }) => useMqtt(s, true), { initialProps: { s: settings } });
  const primeiro = ultimo();
  await rerender({ s: { ...settings, host: '10.0.0.9' } });
  expect(primeiro.end).toHaveBeenCalledWith(true);
  expect(connect).toHaveBeenCalledTimes(2);
  expect(ultimo().url).toBe('ws://10.0.0.9:9001');
  await unmount();
  expect(ultimo().end).toHaveBeenCalled();
});
