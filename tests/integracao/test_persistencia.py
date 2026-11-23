"""Persistência no TimescaleDB: gravação, recuperação e preservação após reinício.

O consumidor real grava as medições válidas e as mudanças de decisão; os testes
recuperam os dados por SQL, reiniciam o banco e o próprio consumidor, e
verificam que nada se perde nem se duplica.

Requisitos: RF-14, RNF-08.
"""
import time
from datetime import timezone

import pytest

from integracao_apoio import consultar, contar, esperar

pytestmark = pytest.mark.integracao


def gravar_e_esperar(produtor, observador, entidade, n=5):
    produtor.operacao(entidade, "LIGADA")
    evs = produtor.rajada(entidade, n=n)
    observador.esperar_decisao(entidade, "NORMAL", timeout=15)
    esperar(lambda: contar("medicoes_vibracao", entidade) == n
            and contar("medicoes_temperatura", entidade) == n
            and consultar("SELECT 1 FROM decisoes WHERE entity_id = %s AND decisao = 'NORMAL'", entidade),
            timeout=20, msg="gravação no banco")
    return evs


def snapshot(entidade):
    return {
        "vib": consultar("SELECT event_id, ts, rms_resultante, curtose FROM medicoes_vibracao "
                         "WHERE entity_id = %s ORDER BY event_id", entidade),
        "temp": consultar("SELECT event_id, ts, delta_t FROM medicoes_temperatura "
                          "WHERE entity_id = %s ORDER BY event_id", entidade),
        "dec": consultar("SELECT ts, decisao FROM decisoes WHERE entity_id = %s ORDER BY ts", entidade),
    }


def test_esquema_temporal_criado(consumidor):
    """O consumidor aplica db/schema.sql: três hypertables com políticas de compressão/retenção."""
    tabelas = {r[0] for r in consultar("SELECT hypertable_name FROM timescaledb_information.hypertables")}
    assert {"medicoes_vibracao", "medicoes_temperatura", "decisoes"} <= tabelas
    jobs = {(r[0], r[1]) for r in consultar(
        "SELECT hypertable_name, proc_name FROM timescaledb_information.jobs WHERE hypertable_name IS NOT NULL")}
    assert ("medicoes_vibracao", "policy_retention") in jobs
    assert ("medicoes_vibracao", "policy_compression") in jobs
    assert not any(h == "decisoes" and p == "policy_retention" for h, p in jobs), \
        "RNF-08: decisões não têm retenção"


def test_medicoes_e_decisoes_gravadas_e_recuperadas(consumidor, produtor, observador, entidade):
    evs = gravar_e_esperar(produtor, observador, entidade)
    produtor.publicar(produtor.evento("medicao.vibracao", None, entidade, motivo="mpu_sem_resposta"))

    dados = snapshot(entidade)
    publicados = {e["eventId"]: e for e in evs if e["eventType"] == "medicao.vibracao"}
    assert {r[0] for r in dados["vib"]} == set(publicados)
    for event_id, ts, rms, curtose in dados["vib"]:
        assert rms == publicados[event_id]["data"]["rms_resultante"]
        assert ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") == publicados[event_id]["eventTime"], \
            "ts gravado é o eventTime (tempo do evento), não o de processamento"
    assert [r[2] for r in dados["temp"]] == [17.0] * 5
    assert "NORMAL" in {r[1] for r in dados["dec"]}

    # inválido não é gravado; decisões repetidas (publicadas a cada 2 s) só geram linha na mudança
    esperar(lambda: len(observador.decisoes(entidade)) >= 4, 15, msg="mais ciclos")
    assert contar("medicoes_vibracao", entidade) == 5
    decs = [r[0] for r in consultar("SELECT decisao FROM decisoes WHERE entity_id = %s ORDER BY ts", entidade)]
    assert all(a != b for a, b in zip(decs, decs[1:])), f"decisões repetidas gravadas: {decs}"


def test_dados_preservados_apos_reiniciar_o_banco(ambiente, consumidor, produtor, observador, entidade):
    gravar_e_esperar(produtor, observador, entidade)
    antes = snapshot(entidade)

    ambiente.compose("restart", "timescaledb")
    ambiente.esperar_banco()

    assert snapshot(entidade) == antes


def test_dados_preservados_apos_reiniciar_o_consumidor_sem_duplicar(consumidor, produtor, observador, entidade):
    evs = gravar_e_esperar(produtor, observador, entidade)
    antes = snapshot(entidade)

    consumidor.reiniciar()   # o conjunto de eventId vistos (em memória) recomeça vazio
    assert snapshot(entidade) == antes

    reenvio = time.monotonic()
    for ev in evs:           # reenvio dos mesmos eventos (ex.: buffer do nó após PUBACK perdido)
        produtor.publicar(ev)
    observador.esperar_decisao(entidade, "NORMAL", timeout=15, desde=reenvio)
    # dá tempo ao lote do banco (thread própria) e confere que a chave única barrou as cópias
    time.sleep(4)
    depois = snapshot(entidade)
    assert depois["vib"] == antes["vib"]
    assert depois["temp"] == antes["temp"]
