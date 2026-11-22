const mqttStatusEl = document.getElementById('mqtt-status');
const gridEl = document.getElementById('assets-grid');

const ativos = {};

const client = mqtt.connect(CONFIG.MQTT_BROKER_URL, {
    username: CONFIG.MQTT_USER,
    password: CONFIG.MQTT_PASS,
    clientId: 'dashboard_' + Math.random().toString(16).substring(2, 8)
});

client.on('connect', () => {
    mqttStatusEl.textContent = 'Broker Online';
    mqttStatusEl.className = 'badge status-online';
    client.subscribe(CONFIG.MQTT_TOPIC);
});

client.on('close', () => {
    mqttStatusEl.textContent = 'Broker Offline';
    mqttStatusEl.className = 'badge status-offline';
});

client.on('error', (err) => {
    console.error('Erro MQTT:', err);
    mqttStatusEl.textContent = 'Erro de Conexão';
    mqttStatusEl.className = 'badge status-offline';
});

client.on('message', (topic, message) => {
    try {
        renderizar(JSON.parse(message.toString()));
    } catch (e) {
        console.error('Falha ao processar JSON:', e);
    }
});

function valorOuNulo(v) {
    return typeof v === 'number' ? v : null;
}

function formatar(v, sufixo = '') {
    return typeof v === 'number' ? `${v}${sufixo}` : '--';
}

function criarAtivo(entityId) {
    const card = document.createElement('div');
    card.className = 'asset-card';
    card.innerHTML = `
        <div class="asset-header">
            <h2 class="asset-title">${entityId}</h2>
            <span class="badge decisao-badge"></span>
        </div>
        <div class="metrics">
            <div class="metric-box">
                <div class="metric-label">RMS Norm</div>
                <div class="metric-value rms-val">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">ΔT (°C)</div>
                <div class="metric-value temp-val">--</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Curtose máx.</div>
                <div class="metric-value curtose-val">--</div>
            </div>
        </div>
        <div class="chart-box"><canvas></canvas></div>
        <h3 class="historico-titulo">Mudanças de estado</h3>
        <ul class="historico"></ul>
        <div class="timestamp"></div>
    `;
    gridEl.appendChild(card);

    const grafico = new Chart(card.querySelector('canvas'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                { label: 'RMS Norm (x)', data: [], yAxisID: 'yRms', borderColor: '#3b82f6',
                  pointBackgroundColor: [], pointRadius: 4, tension: 0.2 },
                { label: 'ΔT (°C)', data: [], yAxisID: 'yTemp', borderColor: '#f97316',
                  pointRadius: 2, tension: 0.2 }
            ]
        },
        options: {
            animation: false,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                yRms: { position: 'left', title: { display: true, text: 'RMS Norm' } },
                yTemp: { position: 'right', title: { display: true, text: 'ΔT (°C)' },
                         grid: { drawOnChartArea: false } },
                x: { ticks: { maxTicksLimit: 6 } }
            }
        }
    });

    const ativo = { card, grafico, ultimaDecisao: null, ultimaMsg: Date.now() };
    ativos[entityId] = ativo;
    return ativo;
}

function adicionarPonto(grafico, hora, rms, temp, cor) {
    const [dsRms, dsTemp] = grafico.data.datasets;
    grafico.data.labels.push(hora);
    dsRms.data.push(rms);
    dsRms.pointBackgroundColor.push(cor);
    dsTemp.data.push(temp);
    if (grafico.data.labels.length > CONFIG.MAX_PONTOS) {
        grafico.data.labels.shift();
        dsRms.data.shift();
        dsRms.pointBackgroundColor.shift();
        dsTemp.data.shift();
    }
    grafico.update();
}

function renderizar(dados) {
    const ativo = ativos[dados.entityId] || criarAtivo(dados.entityId);
    const { card, grafico } = ativo;
    const meta = CONFIG.DECISAO_META[dados.decisao] || CONFIG.DECISAO_META['DADOS_INSUFICIENTES'];
    const quando = new Date(dados.timestamp);
    const hora = quando.toLocaleTimeString();

    ativo.ultimaMsg = Date.now();
    card.classList.remove('desatualizado');

    card.querySelector('.decisao-badge').textContent = meta.label;
    card.querySelector('.rms-val').textContent = formatar(dados.rmsNorm, 'x');
    card.querySelector('.temp-val').textContent = formatar(dados.deltaT);
    card.querySelector('.curtose-val').textContent = formatar(dados.curtoseMax);
    card.querySelector('.timestamp').textContent = `Última att: ${hora}`;

    CONFIG.CLASSES.forEach(cls => card.classList.remove(cls));
    card.classList.add(meta.cssClass);

    adicionarPonto(grafico, hora, valorOuNulo(dados.rmsNorm), valorOuNulo(dados.deltaT), meta.cor);

    if (dados.decisao !== ativo.ultimaDecisao) {
        const item = document.createElement('li');
        item.textContent = `${hora} — ${meta.label}`;
        item.style.borderLeftColor = meta.cor;
        const lista = card.querySelector('.historico');
        lista.prepend(item);
        while (lista.children.length > CONFIG.MAX_HISTORICO) lista.lastChild.remove();
        ativo.ultimaDecisao = dados.decisao;
    }
}

setInterval(() => {
    Object.values(ativos).forEach(a => {
        a.card.classList.toggle('desatualizado', Date.now() - a.ultimaMsg > CONFIG.LIMITE_DESATUALIZADO_MS);
    });
}, 1000);
