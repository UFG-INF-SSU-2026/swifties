import { render, screen } from '@testing-library/react-native';
import { AtivoCard } from '../src/AtivoCard';
import { Ativo, LIMITE_DESATUALIZADO_MS } from '../src/config';

const T = Date.parse('2026-01-01T12:00:00Z');
const ativo = (extra: Partial<Ativo['atual']> = {}, resto: Partial<Ativo> = {}): Ativo => ({
  entityId: 'motor-1',
  atual: { entityId: 'motor-1', decisao: 'NORMAL', timestamp: '2026-01-01T12:00:00Z', rmsNorm: 1.2, deltaT: 6.5, curtoseMax: 3.1, ...extra },
  recebidoEm: T,
  pontos: [],
  historico: [{ hora: '12:00:00', decisao: 'NORMAL' }],
  ...resto,
});

test('mostra id, estado e métricas formatadas', async () => {
  await render(<AtivoCard ativo={ativo()} agora={T} />);
  expect(screen.getByText('motor-1')).toBeTruthy();
  expect(screen.getAllByText('Normal').length).toBeGreaterThan(0);  // selo + linha do tempo
  expect(screen.getByText('1.2×')).toBeTruthy();
  expect(screen.getByText('6.5°')).toBeTruthy();
  expect(screen.getByText('3.1')).toBeTruthy();
  expect(screen.getByText(/Ao vivo/)).toBeTruthy();
});

test('métricas ausentes aparecem como traço', async () => {
  await render(<AtivoCard ativo={ativo({ rmsNorm: undefined, deltaT: undefined, curtoseMax: undefined })} agora={T} />);
  expect(screen.getAllByText('—')).toHaveLength(3);
});

test('dados antigos são sinalizados como desatualizados', async () => {
  await render(<AtivoCard ativo={ativo()} agora={T + LIMITE_DESATUALIZADO_MS + 1} />);
  expect(screen.getByText(/Dados desatualizados/)).toBeTruthy();
  expect(screen.queryByText(/Ao vivo/)).toBeNull();
});

test('decisão desconhecida usa o rótulo de baseline', async () => {
  await render(<AtivoCard ativo={ativo({ decisao: 'XYZ' })} agora={T} />);
  expect(screen.getByText('Baseline')).toBeTruthy();
});

test('linha do tempo exibe no máximo 4 entradas', async () => {
  const historico = Array.from({ length: 8 }, (_, i) => ({ hora: `12:00:0${i}`, decisao: 'CRITICO' }));
  await render(<AtivoCard ativo={ativo({}, { historico })} agora={T} />);
  expect(screen.getAllByText('Crítico')).toHaveLength(4);
  expect(screen.queryByText('12:00:05')).toBeNull();
});
