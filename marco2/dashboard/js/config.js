const CONFIG = {
    // Usando protocolo WebSocket (ws://) na porta 9001 configurada no Mosquitto
    MQTT_BROKER_URL: 'ws://localhost:9001',
    
    // Assinamos todas as decisões de todos os consumidores
    MQTT_TOPIC: 'consumidor/+/decisao',
    
    // Mapeamento De/Para: Decisão que vem do Python -> Classe CSS visual
    DECISAO_META: {
        'NORMAL': { cssClass: 'state-normal', label: '✅ Normal' },
        'ATENCAO': { cssClass: 'state-atencao', label: '⚠️ Atenção' },
        'CRITICO': { cssClass: 'state-critico', label: '🚨 Crítico' },
        'SEM_COMUNICACAO': { cssClass: 'state-desconectado', label: '📡 Sem Sinal' },
        'DADOS_INSUFICIENTES': { cssClass: 'state-aguardando', label: '⏳ Coletando Baseline' },
        'NAO_AVALIAVEL': { cssClass: 'state-desligado', label: '🛑 Máquina Desligada' }
    }
};