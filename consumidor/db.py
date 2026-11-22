"""Gravação assíncrona no TimescaleDB.
"""
import logging
import os
import queue
import threading
import time
from pathlib import Path

import psycopg

log = logging.getLogger("db")

HOST = os.getenv("POSTGRES_HOST")
PORTA = os.getenv("POSTGRES_PORT", "5432")
USUARIO = os.getenv("POSTGRES_USER")
SENHA = os.getenv("POSTGRES_PASSWORD")
BANCO = os.getenv("POSTGRES_DB")
APLICAR_SCHEMA = os.getenv("DB_APLICAR_SCHEMA", "1") == "1"

TAM_FILA = 5000
TAM_LOTE = 200
ESPERA_RECONEXAO_S = 5

SQL = {
    "vib": """INSERT INTO medicoes_vibracao
        (ts, entity_id, device_id, event_id, sequence, rms_x, rms_y, rms_z,
         rms_resultante, pico, curtose, freq_dominante)
        VALUES (%(ts)s, %(entity_id)s, %(device_id)s, %(event_id)s, %(sequence)s,
                %(rms_x)s, %(rms_y)s, %(rms_z)s, %(rms_resultante)s, %(pico)s,
                %(curtose)s, %(freq_dominante)s)
        ON CONFLICT DO NOTHING""",
    "temp": """INSERT INTO medicoes_temperatura
        (ts, entity_id, device_id, event_id, sequence, temp_carcaca, temp_ambiente, delta_t)
        VALUES (%(ts)s, %(entity_id)s, %(device_id)s, %(event_id)s, %(sequence)s,
                %(temp_carcaca)s, %(temp_ambiente)s, %(delta_t)s)
        ON CONFLICT DO NOTHING""",
    "decisao": """INSERT INTO decisoes (ts, entity_id, decisao, rms_norm, curtose_max, delta_t)
        VALUES (%(ts)s, %(entity_id)s, %(decisao)s, %(rms_norm)s, %(curtose_max)s, %(delta_t)s)
        ON CONFLICT DO NOTHING""",
}

_fila = queue.Queue(maxsize=TAM_FILA)
_descartados = 0
_habilitado = all([HOST, USUARIO, SENHA, BANCO])


def _enfileirar(tipo, linha):
    global _descartados
    if not _habilitado:
        return
    try:
        _fila.put_nowait((tipo, linha))
    except queue.Full:
        try:
            _fila.get_nowait()
        except queue.Empty:
            pass
        _fila.put_nowait((tipo, linha))
        _descartados += 1
        if _descartados % 100 == 1:
            log.warning("fila do banco cheia: %d itens descartados até agora", _descartados)


def gravar_medicao(ev, ts):
    d = ev["data"]
    base = {"ts": ts, "entity_id": ev["entityId"], "device_id": ev["deviceId"],
            "event_id": ev["eventId"], "sequence": ev.get("sequence")}
    if ev["eventType"] == "medicao.vibracao":
        campos = ("rms_x", "rms_y", "rms_z", "rms_resultante", "pico", "curtose", "freq_dominante")
        _enfileirar("vib", {**base, **{c: d.get(c) for c in campos}})
    elif ev["eventType"] == "medicao.temperatura":
        campos = ("temp_carcaca", "temp_ambiente", "delta_t")
        _enfileirar("temp", {**base, **{c: d.get(c) for c in campos}})


def gravar_decisao(entity_id, decisao, ts, metricas):
    _enfileirar("decisao", {"ts": ts, "entity_id": entity_id, "decisao": decisao,
                            "rms_norm": metricas.get("rmsNorm"),
                            "curtose_max": metricas.get("curtoseMax"),
                            "delta_t": metricas.get("deltaT")})


def _conectar():
    conn = psycopg.connect(host=HOST, port=PORTA, user=USUARIO, password=SENHA,
                           dbname=BANCO, connect_timeout=5, autocommit=True)
    if APLICAR_SCHEMA:
        conn.execute((Path(__file__).parent / "db" / "schema.sql").read_text())
    return conn


def _gravar_lote(conn, lote):
    with conn.transaction():
        with conn.cursor() as cur:
            for tipo in SQL:
                linhas = [l for t, l in lote if t == tipo]
                if linhas:
                    cur.executemany(SQL[tipo], linhas)


def _trabalhador():
    conn, pendente = None, []
    while True:
        try:
            if conn is None:
                conn = _conectar()
                log.info("conectado ao TimescaleDB em %s:%s/%s", HOST, PORTA, BANCO)
            if not pendente:
                pendente = [_fila.get()]
                while len(pendente) < TAM_LOTE:
                    try:
                        pendente.append(_fila.get_nowait())
                    except queue.Empty:
                        break
            _gravar_lote(conn, pendente)
            pendente = []
        except Exception as e:   # banco fora, rede, erro SQL...
            log.error("falha no banco (%s); nova tentativa em %ds, %d itens pendentes",
                      e, ESPERA_RECONEXAO_S, len(pendente) + _fila.qsize())
            try:
                conn and conn.close()
            except Exception:
                pass
            conn = None
            time.sleep(ESPERA_RECONEXAO_S)


def iniciar():
    if not _habilitado:
        log.warning("POSTGRES_HOST/USER/PASSWORD/DB ausentes: gravação no banco desabilitada")
        return
    threading.Thread(target=_trabalhador, daemon=True, name="db-writer").start()
