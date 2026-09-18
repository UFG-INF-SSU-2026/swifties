import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from statistics import mean, median

import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("consumidor")

MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORTA = int(os.getenv("MQTT_PORTA", "1883"))
PREFIXO_ENTRADA = "swifties"
PREFIXO_SAIDA = "consumidor"

# perfil de protótipo (atv02.md, questão 6)
JANELA_S = 120
PASSO_S = 10
MIN_VIB, MIN_TEMP = 12, 30
SILENCIO_S = 15   # sem nenhum evento por esse tempo -> SEM_COMUNICACAO

# regra de decisão (atv02.md, questão 9)
RMS_NORM_CRITICO, CURTOSE_CRITICO, DELTA_T_CRITICO = 2.0, 6.0, 20.0
EXCEDENTE_FRACAO, RMS_EXCEDENTE_MULT, DELTA_T_ATENCAO = 0.8, 1.5, 10.0

ativos = {}   # entityId -> Ativo


class Ativo:
    def __init__(self, entity_id):
        self.entity_id = entity_id
        self.estado_operacional = "DESCONHECIDO"
        self.baseline = None            # {"rms": .., "delta_t": ..}, aprendida na 1a janela
        self.vib, self.temp = [], []    # listas de (ts, data)
        self.ultimo_evento = None
        self.ultima_decisao = None
        self.vistos = set()             # eventId já processados (dedup por idempotência)


def ao_conectar(cliente, userdata, flags, rc, properties=None):
    cliente.subscribe(f"{PREFIXO_ENTRADA}/#", qos=1)
    log.info("conectado ao broker; assinado em %s/#", PREFIXO_ENTRADA)


def ao_receber(cliente, userdata, msg):
    if msg.topic.endswith("/status"):
        log.info("[STATUS] %s", msg.payload.decode())
        return

    try:
        ev = json.loads(msg.payload)
    except ValueError:
        log.warning("payload não é JSON válido em %s", msg.topic)
        return

    ativo = ativos.setdefault(ev["entityId"], Ativo(ev["entityId"]))

    if ev["eventId"] in ativo.vistos:
        return   # duplicado (reenvio QoS 1 do nó): descartado por idempotência
    ativo.vistos.add(ev["eventId"])
    ativo.ultimo_evento = datetime.now(timezone.utc)

    tipo = ev["eventType"]
    if tipo == "maquina.mudanca_operacao":
        ativo.estado_operacional = ev["data"]["estado"]
        log.info("[OPERACAO] %s -> %s", ativo.entity_id, ativo.estado_operacional)
        return

    if ev["quality"] != "VALIDO":
        log.info("[INVALIDO] %s %s: %s", ativo.entity_id, tipo, ev.get("motivo"))
        return

    ts = datetime.strptime(ev["eventTime"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    if tipo == "medicao.vibracao":
        ativo.vib.append((ts, ev["data"]))
    elif tipo == "medicao.temperatura":
        ativo.temp.append((ts, ev["data"]))


def avaliar(ativo, agora):
    """Regra de degradação sustentada (atv02.md, questão 9)."""
    limite = agora - timedelta(seconds=JANELA_S)
    ativo.vib = [x for x in ativo.vib if x[0] >= limite]
    ativo.temp = [x for x in ativo.temp if x[0] >= limite]

    if ativo.ultimo_evento is None or (agora - ativo.ultimo_evento).total_seconds() > SILENCIO_S:
        return "SEM_COMUNICACAO", {}

    if len(ativo.vib) < MIN_VIB or len(ativo.temp) < MIN_TEMP:
        return "DADOS_INSUFICIENTES", {}

    if ativo.estado_operacional == "DESLIGADA":
        return "NAO_AVALIAVEL", {}

    rms = [d["rms_resultante"] for _, d in ativo.vib]
    curtoses = [d["curtose"] for _, d in ativo.vib]
    delta_t = mean(d["delta_t"] for _, d in ativo.temp)

    if ativo.baseline is None:
        # primeira janela válida vira a linha de base do ativo (sem camada de
        # nuvem para reajustá-la nesta POC — ver README)
        ativo.baseline = {"rms": median(rms), "delta_t": delta_t}
        return "NORMAL", {}

    base = ativo.baseline
    rms_norm = median(rms) / base["rms"]
    curtose_max = max(curtoses)
    excedentes = sum(1 for r in rms if r > RMS_EXCEDENTE_MULT * base["rms"])
    metricas = {"rmsNorm": round(rms_norm, 3), "curtoseMax": curtose_max, "deltaT": round(delta_t, 2)}

    if rms_norm >= RMS_NORM_CRITICO and (curtose_max >= CURTOSE_CRITICO or delta_t >= base["delta_t"] + DELTA_T_CRITICO):
        return "CRITICO", metricas
    if excedentes >= EXCEDENTE_FRACAO * len(rms) or delta_t >= base["delta_t"] + DELTA_T_ATENCAO:
        return "ATENCAO", metricas
    return "NORMAL", metricas


def ciclo(cliente):
    agora = datetime.now(timezone.utc)
    for ativo in list(ativos.values()):
        decisao, metricas = avaliar(ativo, agora)
        if decisao == ativo.ultima_decisao:
            continue
        payload = {"entityId": ativo.entity_id, "decisao": decisao,
                   "timestamp": agora.strftime("%Y-%m-%dT%H:%M:%SZ"), **metricas}
        cliente.publish(f"{PREFIXO_SAIDA}/{ativo.entity_id}/decisao", json.dumps(payload), qos=1)
        log.info("[DECISAO] %s -> %s", ativo.entity_id, decisao)
        ativo.ultima_decisao = decisao


def main():
    cliente = mqtt.Client(client_id="consumidor-marco2",
                           callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    cliente.on_connect = ao_conectar
    cliente.on_message = ao_receber
    cliente.connect(MQTT_HOST, MQTT_PORTA, keepalive=60)
    cliente.loop_start()
    log.info("consumidor rodando, broker %s:%d", MQTT_HOST, MQTT_PORTA)
    try:
        while True:
            time.sleep(PASSO_S)
            ciclo(cliente)
    except KeyboardInterrupt:
        pass
    finally:
        cliente.loop_stop()
        cliente.disconnect()


if __name__ == "__main__":
    main()
