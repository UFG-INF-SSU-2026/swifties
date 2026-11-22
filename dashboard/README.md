# ⚙️ Dashboard - Monitoramento Preditivo Industrial

Interface Web de alta performance desenvolvida em JavaScript puro (Vanilla JS) para monitoramento em tempo real do estado operacional e saúde mecânica de ativos industriais. O dashboard consome decisões processadas pelo motor de inferência Python através do protocolo MQTT sobre WebSockets.

---

## 🚀 Tecnologias Utilizadas

- **HTML5 & CSS3:** Layout responsivo baseado em CSS Grid, CSS Variables (`:root`) e animações para estados críticos.
- **Vanilla JavaScript (ES6+):** Manipulação dinâmica de DOM sem dependência de frameworks pesados.
- **MQTT.js:** Cliente JavaScript para comunicação Pub/Sub bidirecional via WebSockets (`ws://`).
- **Nginx & Docker:** Servidor web leve e de alta disponibilidade para containerização da aplicação estática.

---

## 🏗️ Arquitetura e Fluxo de Dados

```text
[ Sensor ESP32 / Wokwi ] ──(MQTT: 1883)──► [ Mosquitto Broker ] ◄──(MQTT: 1883)── [ Consumidor Python ]
                                                   │
                                            (WebSockets: 9001)
                                                   │
                                                   ▼
                                     [ Dashboard Web (Frontend) ]
```

1. O **Consumidor Python** processa os dados de telemetria brutos (vibração e temperatura) e publica a inferência no tópico `consumidor/<entityId>/decisao`.
2. O **Dashboard Frontend** assina o padrão de tópicos wildcard `consumidor/+/decisao` via WebSockets.
3. À medida que novos payloads chegam, a aplicação renderediza dinamicamente os cartões dos ativos (`cards`) ou atualiza os métricas e classes de estado em tempo real.

---

## 📊 Matriz de Estados e Mapeamento Visual

O dashboard reage às decisões do motor através da injeção limpa de classes CSS baseadas em `Set` para prevenir acúmulo ou conflitos de estilização:

| Estado (`decisao`) | Representação Visual | Classe CSS | Cor | Animação / Comportamento |
|---|---|---|---|---|
| **`NORMAL`** | ✅ Normal | `.state-normal` | Verde (`#10b981`) | Borda e badge verdes |
| **`ATENCAO`** | ⚠️ Atenção | `.state-atencao` | Amarelo (`#f59e0b`) | Borda e badge amarelos |
| **`CRITICO`** | 🚨 Crítico | `.state-critico` | Vermelho (`#ef4444`) | Borda vermelha com animação *pulse/glow* |
| **`SEM_COMUNICACAO`** | 📡 Sem Sinal | `.state-desconectado` | Laranja (`#f97316`) | Indicador de perda de link de telemetria |
| **`DADOS_INSUFICIENTES`**| ⏳ Coletando Baseline | `.state-aguardando` | Azul (`#3b82f6`) | Fase de acumulação de amostras da janela |
| **`NAO_AVALIAVEL`** | 🛑 Máquina Desligada | `.state-desligado` | Cinza (`#9ca3af`) | Cartão com opacidade reduzida |

---

## 📑 Contrato da Mensagem (Payload JSON)

A aplicação espera receber pacotes com a seguinte estrutura no tópico `consumidor/+/decisao`:

```json
{
  "entityId": "motor-linha3-02",
  "decisao": "CRITICO",
  "timestamp": "2026-10-16T12:54:55Z",
  "rmsNorm": 2.15,
  "curtoseMax": 6.2,
  "deltaT": 15.0
}
```

*Nota: Atributos como `rmsNorm`, `curtoseMax` e `deltaT` são opcionais dependendo do estado (ex: omitidos em `SEM_COMUNICACAO` ou `NAO_AVALIAVEL`). O frontend trata valores ausentes exibindo `--`.*

---

## ⚙️ Configuração (`js/config.js`)

As variáveis de conexão e mapeamentos estão centralizadas em `js/config.js`:

```javascript
const CONFIG = {
    MQTT_BROKER_URL: 'ws://localhost:9001', // Endereço WebSocket do Mosquitto
    MQTT_TOPIC: 'consumidor/+/decisao',     // Escuta todos os ativos
    DECISAO_META: { ... }                    // De/Para de classes CSS e labels
};
```

---

## 🛠️ Como Executar

### Pré-requisitos
O broker MQTT Mosquitto deve estar rodando com o suporte a WebSockets habilitado na porta `9001` (`listener 9001` / `protocol websockets`).

### Opção 1: Via Docker Compose (Recomendado)

```bash
# Entrar no diretório do dashboard
cd marco2/dashboard

# Subir o servidor Nginx
docker compose up -d
```

Acesse a aplicação via navegador em: `http://localhost:8080`

### Opção 2: Servidor Estático Local (Python / Node / Live Server)

```bash
# Navegar até a pasta do dashboard
cd marco2/dashboard

# Subir servidor estático via Python
python3 -m http.server 8080
```

Acesse a aplicação em: `http://localhost:8080`

---

## 📂 Estrutura do Código Frontend

```text
dashboard/
├── css/
│   └── styles.css      # Regras de estilização, CSS Variables e animações de estado
├── js/
│   ├── config.js       # Parâmetros de rede, tópicos e metadados de decisão
│   └── app.js          # Conexão MQTT WebSocket, parsing de JSON e re-renderização de DOM
├── index.html          # Layout SPA base da aplicação
├── docker-compose.yml  # Orquestração do serviço do frontend
└── README.md           # Documentação técnica do componente