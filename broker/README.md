# Broker — Mosquitto + ngrok

Broker MQTT local com autenticação (usuário/senha) e autorização (ACL), exposto à internet por túnel TCP do ngrok para que o ESP32 no Wokwi o alcance.

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

## Autenticação e autorização
`allow_anonymous false`: toda conexão precisa de usuário e senha (hashes em `passwd`; senhas fictícias de trabalho acadêmico). Permissões em `acl`:

| Usuário | Senha | Lê | Escreve |
|---|---|---|---|
| `esp32-07` | `esp32123` | — | `swifties/esp32-07/#` |
| `consumidor` | `consumidor123` | `swifties/#` | `consumidor/#` |
| `admin` | `admin123` | `#` | `#` |

Limitação: sem TLS, a senha cruza o túnel ngrok em texto claro (aceitável no protótipo; produção exigiria listener TLS na 8883).

## Endereço público
Muda a cada reinício do ngrok. Ver em http://localhost:4040 ou:
```bash
docker compose logs ngrok | grep -o 'tcp://[^ ]*'
# tcp://0.tcp.sa.ngrok.io:12345  →  MQTT_HOST e MQTT_PORTA em publisher/main.py
```

## Acompanhar as mensagens
```bash
docker compose exec mosquitto mosquitto_sub -u admin -P admin123 -t 'swifties/#' -v
```

## Derrubar o broker (falha real)
```bash
docker compose stop mosquitto    # o nó guarda eventos no buffer e tenta reconectar a cada 5 s
docker compose start mosquitto   # o nó reconecta e envia o que ficou pendente
```
