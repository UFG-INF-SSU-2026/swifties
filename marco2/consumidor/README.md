# Consumidor — hub local (névoa)

POC do consumidor MQTT: assina os eventos do nó (`../publisher`) via broker
(`../broker`), junta vibração e temperatura numa janela deslizante por
ativo e aplica a regra de degradação sustentada de `atv02.md` (questão 9),
publicando a decisão de volta em MQTT.

```
mosquitto (../broker) ──swifties/#──► consumidor ──consumidor/<entityId>/decisao──► mosquitto_sub
```

## Rodar

### Com Docker Compose
```bash
cd marco2/consumidor
cp .env.example .env          
docker compose up --build
```
Por padrão `MQTT_HOST=host.docker.internal`, que alcança o broker publicado
por `docker compose up` em `../broker` (porta `1883` exposta ao host).

### Sem Docker
```bash
cd marco2/consumidor
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
MQTT_HOST=localhost python main.py
```

## Acompanhar
```bash
mosquitto_sub -h localhost -t 'consumidor/#' -v
```

## Testar sem o Wokwi/ngrok

`ferramentas/mock_publisher.py` publica eventos sintéticos do contrato v1
direto no broker local:

```bash
python3 ferramentas/mock_publisher.py --cenario normal
python3 ferramentas/mock_publisher.py --cenario atencao
python3 ferramentas/mock_publisher.py --cenario critico
python3 ferramentas/mock_publisher.py --cenario desligada
python3 ferramentas/mock_publisher.py --cenario invalido
python3 ferramentas/mock_publisher.py --cenario duplicata
python3 ferramentas/mock_publisher.py --cenario sem_comunicacao
```

Rode `python main.py` numa aba e o cenário desejado em outra. Os cenários `atencao`/`critico` esperam ~12s entre a rajada que define a baseline e a rajada anômala, de propósito: o consumidor só reavalia a cada 10s (`PASSO_S`), então as duas rajadas precisam cair em ciclos diferentes — senão a primeira avaliação mistura as duas e aprende uma baseline errada (e sempre volta `NORMAL` na primeira janela).
