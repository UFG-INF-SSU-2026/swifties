const test = require('node:test');
const assert = require('node:assert/strict');
const { carregarDashboard, decisao } = require('./helpers');

test('conecta ao broker com credenciais e client id do dashboard', () => {
  const { w, app } = carregarDashboard();
  assert.equal(w.mqttArgs.url, app.CONFIG.MQTT_BROKER_URL);
  assert.equal(w.mqttArgs.opts.username, app.CONFIG.MQTT_USER);
  assert.match(w.mqttArgs.opts.clientId, /^dashboard_[0-9a-f]+$/);
});

test('status do broker: connect, close e error', () => {
  const { doc, handlers, cliente } = carregarDashboard();
  const badge = doc.getElementById('mqtt-status');

  handlers.connect();
  assert.equal(badge.textContent, 'Broker Online');
  assert.ok(badge.classList.contains('status-online'));
  assert.equal(cliente.inscrito, 'consumidor/+/decisao');

  handlers.close();
  assert.equal(badge.textContent, 'Broker Offline');
  assert.ok(badge.classList.contains('status-offline'));

  const erro = console.error; console.error = () => {};
  handlers.error(new Error('x'));
  console.error = erro;
  assert.equal(badge.textContent, 'Erro de Conexão');
});

test('formatar e valorOuNulo', () => {
  const { app } = carregarDashboard();
  assert.equal(app.formatar(1.5, 'x'), '1.5x');
  assert.equal(app.formatar(0), '0');
  assert.equal(app.formatar(undefined), '--');
  assert.equal(app.formatar('abc'), '--');
  assert.equal(app.valorOuNulo(2), 2);
  assert.equal(app.valorOuNulo(null), null);
  assert.equal(app.valorOuNulo('2'), null);
});

test('mensagem cria card do ativo com métricas e classe de estado', () => {
  const { doc, handlers, app } = carregarDashboard();
  handlers.message('t', Buffer.from(JSON.stringify(decisao())));

  const card = doc.querySelector('.asset-card');
  assert.ok(card);
  assert.equal(card.querySelector('.asset-title').textContent, 'motor-1');
  assert.equal(card.querySelector('.rms-val').textContent, '1x');
  assert.equal(card.querySelector('.temp-val').textContent, '5');
  assert.equal(card.querySelector('.curtose-val').textContent, '3');
  assert.equal(card.querySelector('.decisao-badge').textContent, app.CONFIG.DECISAO_META.NORMAL.label);
  assert.ok(card.classList.contains('state-normal'));
});

test('um card por ativo, reaproveitado nas mensagens seguintes', () => {
  const { doc, handlers, w } = carregarDashboard();
  const envia = (d) => handlers.message('t', Buffer.from(JSON.stringify(d)));
  envia(decisao()); envia(decisao()); envia(decisao({ entityId: 'motor-2' }));
  assert.equal(doc.querySelectorAll('.asset-card').length, 2);
  assert.equal(w.graficos.length, 2);
  assert.equal(w.graficos[0].data.labels.length, 2);
});

test('troca de decisão atualiza classe e histórico só nas mudanças', () => {
  const { doc, handlers } = carregarDashboard();
  const envia = (d) => handlers.message('t', Buffer.from(JSON.stringify(d)));
  envia(decisao());
  envia(decisao());
  envia(decisao({ decisao: 'CRITICO' }));

  const card = doc.querySelector('.asset-card');
  assert.ok(card.classList.contains('state-critico'));
  assert.ok(!card.classList.contains('state-normal'));
  const itens = card.querySelectorAll('.historico li');
  assert.equal(itens.length, 2);
  assert.match(itens[0].textContent, /Crítico/);   // mais recente primeiro
});

test('histórico limitado a MAX_HISTORICO', () => {
  const { doc, handlers, app } = carregarDashboard();
  const ciclo = ['NORMAL', 'ATENCAO'];
  for (let i = 0; i < app.CONFIG.MAX_HISTORICO + 5; i++) {
    handlers.message('t', Buffer.from(JSON.stringify(decisao({ decisao: ciclo[i % 2] }))));
  }
  assert.equal(doc.querySelectorAll('.historico li').length, app.CONFIG.MAX_HISTORICO);
});

test('gráfico limitado a MAX_PONTOS', () => {
  const { handlers, w, app } = carregarDashboard();
  for (let i = 0; i < app.CONFIG.MAX_PONTOS + 10; i++) {
    handlers.message('t', Buffer.from(JSON.stringify(decisao())));
  }
  const g = w.graficos[0];
  assert.equal(g.data.labels.length, app.CONFIG.MAX_PONTOS);
  assert.equal(g.data.datasets[0].data.length, app.CONFIG.MAX_PONTOS);
  assert.equal(g.data.datasets[0].pointBackgroundColor.length, app.CONFIG.MAX_PONTOS);
  assert.equal(g.data.datasets[1].data.length, app.CONFIG.MAX_PONTOS);
});

test('métricas ausentes viram "--" e null no gráfico', () => {
  const { doc, handlers, w } = carregarDashboard();
  handlers.message('t', Buffer.from(JSON.stringify(
    { entityId: 'm', decisao: 'SEM_COMUNICACAO', timestamp: '2026-01-01T12:00:00Z' })));
  const card = doc.querySelector('.asset-card');
  assert.equal(card.querySelector('.rms-val').textContent, '--');
  assert.equal(card.querySelector('.temp-val').textContent, '--');
  assert.equal(w.graficos[0].data.datasets[0].data[0], null);
  assert.ok(card.classList.contains('state-desconectado'));
});

test('decisão desconhecida cai no meta de DADOS_INSUFICIENTES', () => {
  const { doc, handlers } = carregarDashboard();
  handlers.message('t', Buffer.from(JSON.stringify(decisao({ decisao: 'XYZ' }))));
  assert.ok(doc.querySelector('.asset-card').classList.contains('state-aguardando'));
});

test('JSON inválido não quebra nem cria card', () => {
  const { doc, handlers } = carregarDashboard();
  const erro = console.error; console.error = () => {};
  assert.doesNotThrow(() => handlers.message('t', Buffer.from('{ruim')));
  console.error = erro;
  assert.equal(doc.querySelectorAll('.asset-card').length, 0);
});

test('card fica "desatualizado" sem mensagens e volta ao receber', () => {
  const { doc, handlers, app, w } = carregarDashboard();
  handlers.message('t', Buffer.from(JSON.stringify(decisao())));
  const card = doc.querySelector('.asset-card');
  const tick = w.intervalos[0];

  tick();
  assert.ok(!card.classList.contains('desatualizado'));

  app.ativos['motor-1'].ultimaMsg = w.Date.now() - app.CONFIG.LIMITE_DESATUALIZADO_MS - 1000;
  tick();
  assert.ok(card.classList.contains('desatualizado'));

  handlers.message('t', Buffer.from(JSON.stringify(decisao())));
  assert.ok(!card.classList.contains('desatualizado'));
});
