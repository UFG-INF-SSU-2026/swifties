# Broker — Mosquitto + ngrok

Broker MQTT local, sem autenticação (protótipo), exposto à internet por túnel TCP do ngrok para que o ESP32 no Wokwi o alcance.

```
Wokwi ESP32 ──internet──► ngrok (TCP) ──► mosquitto:1883 ◄── consumidor / mosquitto_sub (localhost:1883)
```

## Pré-requisitos
- Docker com Compose.
- Conta ngrok com cartão verificado (exigido para túneis TCP no plano gratuito; não há cobrança).

## Subir
```bash
cp .env.example .env          # colar o NGROK_AUTHTOKEN
docker compose up -d
```

## Endereço público
Muda a cada reinício do ngrok. Ver em http://localhost:4040 ou:
```bash
docker compose logs ngrok | grep -o 'tcp://[^ ]*'
# tcp://0.tcp.sa.ngrok.io:12345  →  MQTT_HOST e MQTT_PORTA em publisher/main.py
```

## Acompanhar as mensagens
```bash
docker compose exec mosquitto mosquitto_sub -t 'swifties/#' -v
```

## Derrubar o broker (falha real)
```bash
docker compose stop mosquitto    # o nó guarda eventos no buffer e tenta reconectar a cada 5 s
docker compose start mosquitto   # o nó reconecta e envia o que ficou pendente
```
