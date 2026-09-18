#!/usr/bin/env python3
"""Publicador simulado, para testar o consumidor sem depender do Wokwi/ngrok.

Publica eventos no contrato v1 (marco2/publisher/README.md) direto no broker
local, cobrindo os cenários do roteiro de demonstração do publisher.

Uso:
    pip install -r ../requirements.txt
    python mock_publisher.py --cenario normal
    python mock_publisher.py --cenario atencao
    python mock_publisher.py --cenario critico
    python mock_publisher.py --cenario desligada
    python mock_publisher.py --cenario invalido
    python mock_publisher.py --cenario duplicata
    python mock_publisher.py --cenario sem_comunicacao

Acompanhe os logs do consumidor (ou `mosquitto_sub -t 'consumidor/#' -v`)
enquanto cada cenário roda.
"""
import argparse
import json
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

DEVICE_ID = "esp32-07"
ENTITY_ID = "motor-linha3-02"
PREFIXO = f"swifties/{DEVICE_ID}"

seq = 0
boot_id = int(time.time())


def evento(tipo, dados, motivo=None):
    global seq
    seq += 1
    return {
        "schemaVersion": 1,
        "eventId": f"{DEVICE_ID}-{boot_id}-{seq}",
        "eventType": tipo,
        "deviceId": DEVICE_ID,
        "entityId": ENTITY_ID,
        "sequence": seq,
        "eventTime": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "quality": "INVALIDO" if motivo else "VALIDO",
        "motivo": motivo,
        "data": dados,
    }


def vib(rms=1.0, curtose=2.0, freq=29.6):
    return {"rms_x": rms, "rms_y": 0.05, "rms_z": 0.05, "rms_resultante": rms,
            "pico": rms * 1.4, "curtose": curtose, "freq_dominante": freq}


def temp(carcaca=45.0, ambiente=28.0):
    return {"temp_carcaca": carcaca, "temp_ambiente": ambiente, "delta_t": round(carcaca - ambiente, 2)}


def publicar(cliente, ev):
    topico = PREFIXO + "/" + ev["eventType"].replace(".", "/")
    cliente.publish(topico, json.dumps(ev), qos=1)
    print("[PUB]", ev["eventType"], ev["eventId"], ev.get("data") or f"motivo={ev.get('motivo')}")


def rajada(cliente, rms, curtose, delta_carcaca, n=15, intervalo=0.05):
    """Publica amostras suficientes para passar de MIN_VIB/MIN_TEMP numa única janela."""
    for _ in range(n):
        publicar(cliente, evento("medicao.vibracao", vib(rms=rms, curtose=curtose)))
        publicar(cliente, evento("medicao.temperatura", temp(carcaca=28 + delta_carcaca)))
        time.sleep(intervalo)


CENARIOS = {}


def cenario(nome):
    def decorador(fn):
        CENARIOS[nome] = fn
        return fn
    return decorador


ESPERA_CICLO_S = 12


@cenario("normal")
def _(c):
    publicar(c, evento("maquina.mudanca_operacao", {"estado": "LIGADA", "anterior": "DESCONHECIDO", "rms_resultante": 1.0}))
    rajada(c, rms=1.0, curtose=2.0, delta_carcaca=17)   # aprende a baseline (-> NORMAL)
    print(f"Aguardando {ESPERA_CICLO_S}s o consumidor fechar o ciclo de avaliação...")
    time.sleep(ESPERA_CICLO_S)
    rajada(c, rms=1.0, curtose=2.0, delta_carcaca=17)   # deve permanecer NORMAL


@cenario("atencao")
def _(c):
    rajada(c, rms=1.0, curtose=2.0, delta_carcaca=17)   # aprende a baseline
    print(f"Aguardando {ESPERA_CICLO_S}s o consumidor aprender a baseline antes da rajada anômala...")
    time.sleep(ESPERA_CICLO_S)
    rajada(c, rms=1.8, curtose=3.0, delta_carcaca=17)   # excedentes >= 80% -> ATENCAO


@cenario("critico")
def _(c):
    rajada(c, rms=1.0, curtose=2.0, delta_carcaca=17)   # aprende a baseline
    print(f"Aguardando {ESPERA_CICLO_S}s o consumidor aprender a baseline antes da rajada anômala...")
    time.sleep(ESPERA_CICLO_S)
    rajada(c, rms=2.5, curtose=7.0, delta_carcaca=17)   # rms_norm>=2 e curtose>=6 -> CRITICO


@cenario("desligada")
def _(c):
    publicar(c, evento("maquina.mudanca_operacao", {"estado": "DESLIGADA", "anterior": "LIGADA", "rms_resultante": 0.05}))
    rajada(c, rms=0.05, curtose=1.6, delta_carcaca=2)   # deve ficar NAO_AVALIAVEL


@cenario("invalido")
def _(c):
    publicar(c, evento("medicao.vibracao", None, motivo="mpu_fora_de_faixa"))
    publicar(c, evento("medicao.temperatura", None, motivo="temperatura_fora_de_faixa"))


@cenario("duplicata")
def _(c):
    ev = evento("medicao.vibracao", vib())
    publicar(c, ev)
    time.sleep(0.2)
    publicar(c, ev)   # mesmo eventId: o consumidor deve descartar por idempotência


@cenario("sem_comunicacao")
def _(c):
    rajada(c, rms=1.0, curtose=2.0, delta_carcaca=17)
    print("Pronto. Não publique mais nada e aguarde ~20s: "
          "o consumidor deve marcar SEM_COMUNICACAO.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cenario", choices=sorted(CENARIOS), default="normal")
    p.add_argument("--host", default="localhost")
    p.add_argument("--porta", type=int, default=1883)
    args = p.parse_args()

    c = mqtt.Client(client_id=f"mock-publisher-{uuid.uuid4().hex[:6]}",
                     callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    c.connect(args.host, args.porta, keepalive=30)
    c.loop_start()
    try:
        CENARIOS[args.cenario](c)
        time.sleep(0.5)
    finally:
        c.loop_stop()
        c.disconnect()


if __name__ == "__main__":
    main()
