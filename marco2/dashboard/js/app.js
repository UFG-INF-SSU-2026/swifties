const mqttStatusEl = document.getElementById('mqtt-status');
const gridEl = document.getElementById('assets-grid');

// Conecta no broker
const client = mqtt.connect(CONFIG.MQTT_BROKER_URL);

client.on('connect', () => {
    console.log('Conectado ao broker MQTT via WebSocket');
    mqttStatusEl.textContent = 'Broker Online';
    mqttStatusEl.className = 'badge status-online';
    
    client.subscribe(CONFIG.MQTT_TOPIC, (err) => {
        if (!err) console.log(`Assinado no tópico: ${CONFIG.MQTT_TOPIC}`);
    });
});

client.on('error', (err) => {
    console.error('Erro MQTT:', err);
    mqttStatusEl.textContent = 'Erro de Conexão';
    mqttStatusEl.className = 'badge status-offline';
});

// Ao receber mensagem do consumidor Python
client.on('message', (topic, message) => {
    try {
        const payload = JSON.parse(message.toString());
        console.log("Recebido:", payload);
        renderizarCard(payload);
    } catch (e) {
        console.error("Falha ao processar JSON:", e);
    }
});

// Função que cria ou atualiza o Card do motor na tela
function renderizarCard(dados) {
    let card = document.getElementById(`card-${dados.entityId}`);
    
    // Se o card não existe, cria o HTML base dele
    if (!card) {
        card = document.createElement('div');
        card.id = `card-${dados.entityId}`;
        card.className = 'asset-card';
        card.innerHTML = `
            <div class="asset-header">
                <h2 class="asset-title">${dados.entityId}</h2>
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
            </div>
            <div class="timestamp"></div>
        `;
        gridEl.appendChild(card);
    }

    // 1. Atualizar Textos e Métricas
    const meta = CONFIG.DECISAO_META[dados.decisao] || CONFIG.DECISAO_META['DADOS_INSUFICIENTES'];
    
    card.querySelector('.decisao-badge').textContent = meta.label;
    card.querySelector('.timestamp').textContent = `Última att: ${new Date(dados.timestamp).toLocaleTimeString()}`;
    
    // Algumas decisões não enviam métricas (ex: SEM_COMUNICACAO)
    card.querySelector('.rms-val').textContent = dados.rmsNorm ? `${dados.rmsNorm}x` : '--';
    card.querySelector('.temp-val').textContent = dados.deltaT ? dados.deltaT : '--';

    // 2. A CORREÇÃO DO BUG (Aplicar a cor correta)
    // Extraímos todos os nomes de classes CSS possíveis usando Set para evitar qualquer duplicata
    const todasAsClasses = [...new Set(Object.values(CONFIG.DECISAO_META).map(m => m.cssClass))];
    
    // Removemos qualquer estado anterior de forma limpa e segura
    todasAsClasses.forEach(cls => card.classList.remove(cls));
    
    // Adicionamos a nova classe do estado atual (isso muda a cor da borda e do badge)
    card.classList.add(meta.cssClass);
}