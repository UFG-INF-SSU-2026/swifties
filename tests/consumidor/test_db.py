import queue
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from conftest import carregar

import db
c = carregar("consumidor_main_db", "consumidor/main.py")

TS = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def fila(monkeypatch):
    f = queue.Queue(maxsize=3)
    monkeypatch.setattr(db, "_fila", f)
    monkeypatch.setattr(db, "_habilitado", True)
    monkeypatch.setattr(db, "_descartados", 0)
    return f


def ev(tipo, data):
    return {"eventType": tipo, "entityId": "m1", "deviceId": "d1", "eventId": "e1", "sequence": 7, "data": data}


def test_desabilitado_nao_enfileira(fila, monkeypatch):
    monkeypatch.setattr(db, "_habilitado", False)
    db.gravar_decisao("m1", "NORMAL", TS, {})
    assert fila.empty()


def test_medicao_vibracao_mapeia_campos(fila):
    db.gravar_medicao(ev("medicao.vibracao", {"rms_x": 1, "rms_resultante": 2, "curtose": 3}), TS)
    tipo, linha = fila.get_nowait()
    assert tipo == "vib"
    assert linha["entity_id"] == "m1" and linha["sequence"] == 7 and linha["ts"] == TS
    assert linha["rms_resultante"] == 2 and linha["pico"] is None   # ausente vira None


def test_medicao_temperatura(fila):
    db.gravar_medicao(ev("medicao.temperatura", {"temp_carcaca": 60, "temp_ambiente": 25, "delta_t": 35}), TS)
    tipo, linha = fila.get_nowait()
    assert tipo == "temp" and linha["delta_t"] == 35


def test_tipo_desconhecido_ignorado(fila):
    db.gravar_medicao(ev("outro", {}), TS)
    assert fila.empty()


def test_decisao_mapeia_metricas(fila):
    db.gravar_decisao("m1", "CRITICO", TS, {"rmsNorm": 2.5, "curtoseMax": 7, "deltaT": 30})
    assert fila.get_nowait() == ("decisao", {"ts": TS, "entity_id": "m1", "decisao": "CRITICO",
                                             "rms_norm": 2.5, "curtose_max": 7, "delta_t": 30})


def test_fila_cheia_descarta_o_mais_antigo(fila):
    for i in range(5):
        db._enfileirar("decisao", {"i": i})
    assert fila.qsize() == 3
    assert [fila.get_nowait()[1]["i"] for _ in range(3)] == [2, 3, 4]
    assert db._descartados == 2


def test_gravar_lote_agrupa_por_tipo():
    cur = MagicMock()
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    db._gravar_lote(conn, [("vib", {"a": 1}), ("temp", {"b": 1}), ("vib", {"a": 2})])
    chamadas = {call.args[0]: call.args[1] for call in cur.executemany.call_args_list}
    assert chamadas[db.SQL["vib"]] == [{"a": 1}, {"a": 2}]
    assert chamadas[db.SQL["temp"]] == [{"b": 1}]
    assert db.SQL["decisao"] not in chamadas


def test_iniciar_desabilitado_nao_cria_thread(monkeypatch):
    monkeypatch.setattr(db, "_habilitado", False)
    t = MagicMock()
    monkeypatch.setattr(db.threading, "Thread", t)
    db.iniciar()
    t.assert_not_called()


def test_iniciar_habilitado_cria_thread_daemon(monkeypatch):
    monkeypatch.setattr(db, "_habilitado", True)
    t = MagicMock()
    monkeypatch.setattr(db.threading, "Thread", t)
    db.iniciar()
    assert t.call_args.kwargs["daemon"] is True
    t.return_value.start.assert_called_once()


# ---- integração consumidor -> db
def test_consumidor_grava_medicoes_e_decisao_so_na_mudanca(monkeypatch):
    import json
    from types import SimpleNamespace
    gm, gd = MagicMock(), MagicMock()
    monkeypatch.setattr(c.db, "gravar_medicao", gm)
    monkeypatch.setattr(c.db, "gravar_decisao", gd)
    c.ativos.clear()
    e = {"eventId": "x1", "eventType": "medicao.vibracao", "entityId": "m1", "deviceId": "d",
         "eventTime": "2026-01-01T12:00:00Z", "quality": "VALIDO", "data": {"rms_resultante": 1, "curtose": 3}}
    c.ao_receber(None, None, SimpleNamespace(topic="swifties/d/medicao/vibracao", payload=json.dumps(e).encode()))
    gm.assert_called_once()
    # evento inválido não é gravado
    e2 = {**e, "eventId": "x2", "quality": "INVALIDO"}
    c.ao_receber(None, None, SimpleNamespace(topic="t", payload=json.dumps(e2).encode()))
    gm.assert_called_once()

    cli = MagicMock()
    c.ciclo(cli); c.ciclo(cli)
    gd.assert_called_once()       # mesma decisão duas vezes: grava uma só
    c.ativos.clear()
