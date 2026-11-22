import { DECISAO_META, DEFAULT_SETTINGS, TOPICO } from '../src/config';

test('toda decisão tem rótulo e cor hexadecimal', () => {
  for (const k of ['NORMAL', 'ATENCAO', 'CRITICO', 'SEM_COMUNICACAO', 'DADOS_INSUFICIENTES', 'NAO_AVALIAVEL']) {
    expect(DECISAO_META[k].label).toBeTruthy();
    expect(DECISAO_META[k].cor).toMatch(/^#[0-9a-f]{6}$/i);
  }
});

test('tópico e configurações padrão batem com o consumidor/broker', () => {
  expect(TOPICO).toBe('consumidor/+/decisao');
  expect(DEFAULT_SETTINGS.porta).toBe('9001');
});
