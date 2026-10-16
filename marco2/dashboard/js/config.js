const CONFIG = {
    MQTT_BROKER_URL: 'ws://localhost:9001',

    MQTT_USER: 'admin',
    MQTT_PASS: 'admin123',

    MQTT_TOPIC: 'consumidor/+/decisao',

    MAX_PONTOS: 90,
    MAX_HISTORICO: 8,
    LIMITE_DESATUALIZADO_MS: 8000,

    DECISAO_META: {
        'NORMAL': { cssClass: 'state-normal', label: '✅ Normal', cor: '#10b981' },
        'ATENCAO': { cssClass: 'state-atencao', label: '⚠️ Atenção', cor: '#f59e0b' },
        'CRITICO': { cssClass: 'state-critico', label: '🚨 Crítico', cor: '#ef4444' },
        'SEM_COMUNICACAO': { cssClass: 'state-desconectado', label: '📡 Sem Sinal', cor: '#f97316' },
        'DADOS_INSUFICIENTES': { cssClass: 'state-aguardando', label: '⏳ Coletando Baseline', cor: '#3b82f6' },
        'NAO_AVALIAVEL': { cssClass: 'state-desligado', label: '🛑 Máquina Desligada', cor: '#9ca3af' }
    }
};

CONFIG.CLASSES = Object.values(CONFIG.DECISAO_META).map(m => m.cssClass);
