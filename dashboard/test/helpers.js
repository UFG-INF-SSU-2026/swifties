const fs = require('node:fs');
const path = require('node:path');
const { JSDOM } = require('jsdom');

const RAIZ = path.join(__dirname, '..');
const ler = (p) => fs.readFileSync(path.join(RAIZ, p), 'utf8');

/** Carrega index.html + config.js + app.js num jsdom, com mqtt e Chart falsos. */
function carregarDashboard() {
  const dom = new JSDOM(
    ler('index.html').replace(/<script[^>]*><\/script>/g, ''),
    { runScripts: 'outside-only', pretendToBeVisual: true }
  );
  const w = dom.window;

  const handlers = {};
  const cliente = {
    on: (ev, fn) => { handlers[ev] = fn; },
    subscribe: (t) => { cliente.inscrito = t; },
  };
  w.mqtt = { connect: (url, opts) => { w.mqttArgs = { url, opts }; return cliente; } };

  w.intervalos = [];
  w.setInterval = (fn) => { w.intervalos.push(fn); return 0; };

  w.graficos = [];
  w.Chart = class {
    constructor(canvas, cfg) {
      this.canvas = canvas;
      this.data = cfg.data;
      this.atualizacoes = 0;
      w.graficos.push(this);
    }
    update() { this.atualizacoes++; }
  };

  // `const` de topo não vira propriedade de window: expomos via eval no mesmo escopo
  w.eval(ler('js/config.js') + '\n' + ler('js/app.js') +
         '\nwindow.__app = { ativos, renderizar, formatar, valorOuNulo, CONFIG };');

  return { w, doc: w.document, handlers, cliente, app: w.__app };
}

const decisao = (extra = {}) => ({
  entityId: 'motor-1', decisao: 'NORMAL', timestamp: '2026-01-01T12:00:00Z',
  rmsNorm: 1.0, deltaT: 5.0, curtoseMax: 3.0, ...extra,
});

module.exports = { carregarDashboard, decisao };
