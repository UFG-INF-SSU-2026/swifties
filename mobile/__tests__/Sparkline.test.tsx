import { fireEvent, render, screen } from '@testing-library/react-native';
import { Sparkline } from '../src/Sparkline';

const layout = { nativeEvent: { layout: { width: 200, height: 64, x: 0, y: 0 } } };

async function montar(valores: (number | null)[]) {
  await render(<Sparkline id="x" valores={valores} cor="#fff" />);
  await fireEvent(screen.root!, 'layout', layout);
}

const paths = (_?: unknown): string[] => [...JSON.stringify(screen.toJSON()).matchAll(/"d":"([^"]*)"/g)].map((m) => m[1]);

test('não desenha nada antes do layout', async () => {
  await render(<Sparkline id="x" valores={[1, 2, 3]} cor="#fff" />);
  expect(paths()).toHaveLength(0);
});

test('menos de dois pontos não desenha linha', async () => {
  await montar([1]);
  expect(paths()).toHaveLength(0);
});

test('desenha área e linha com curvas para série válida', async () => {
  await montar([1, 3, 2, 5]);
  const [area, linha] = paths();
  expect(linha).toMatch(/^M [\d.]+ [\d.]+ C /);
  expect(area).toMatch(/Z $/);
});

test('valor nulo quebra a linha em segmentos', async () => {
  await montar([1, 2, null, 3, 4]);
  const [, linha] = paths();
  expect(linha.match(/M /g)).toHaveLength(2);
});

test('série constante não gera NaN', async () => {
  await montar([2, 2, 2]);
  expect(paths().join(' ')).not.toMatch(/NaN/);
});
