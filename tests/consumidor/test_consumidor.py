import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from conftest import carregar

c = carregar("consumidor_main", "consumidor/main.py")

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def limpa_ativos():
    c.ativos.clear()
    yield
    c.ativos.clear()


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def evento(tipo, dados, n=1, quality="VALIDO", ts=T0, entity="motor-1", motivo=None):
    return {"eventId": f"e-{tipo}-{n}", "eventType": tipo, "entityId": entity,
            "deviceId": "esp32-07", "eventTime": iso(ts), "quality": quality, "motivo": motivo, "data": dados}


def msg(ev, topico="swifties/esp32-07/medicao/vibracao"):
    return SimpleNamespace(topic=topico, payload=json.dumps(ev).encode())


def vib(rms=1.0, curtose=3.0):
    return {"rms_resultante": rms, "curtose": curtose}


def temp(delta=5.0):
    return {"delta_t": delta}


def ativo_com(vibs, temps, agora=T0, baseline=None, operacional="LIGADA"):
    """Ativo com amostras 1 s antes de `agora` e comunicação recente."""
    a = c.Ativo("motor-1")
    a.estado_operacional = operacional
    a.ultimo_evento = agora
    a.baseline = baseline
    a.vib = [(agora - timedelta(seconds=i + 1), d) for i, d in enumerate(vibs)]
    a.temp = [(agora - timedelta(seconds=i + 1), d) for i, d in enumerate(temps)]
    return a


# ---------------------------------------------------------------- ao_conectar
class TestConexao:
    def test_assina_ao_conectar(self):
        cli = MagicMock()
        c.ao_conectar(cli, None, None, 0)
        cli.subscribe.assert_called_once_with("swifties/#", qos=1)

    def test_nao_assina_se_recusado(self):
        cli = MagicMock()
        c.ao_conectar(cli, None, None, 5)
        cli.subscribe.assert_not_called()


# ----------------------------------------------------------------- ao_receber
class TestRecepcao:
    def test_status_nao_cria_ativo(self):
        c.ao_receber(None, None, SimpleNamespace(topic="swifties/esp32-07/status", payload=b"ONLINE"))
        assert c.ativos == {}

    def test_json_invalido_ignorado(self):
        c.ao_receber(None, None, SimpleNamespace(topic="swifties/x/medicao", payload=b"{nao json"))
        assert c.ativos == {}

    def test_registra_vibracao_e_temperatura(self):
        c.ao_receber(None, None, msg(evento("medicao.vibracao", vib())))
        c.ao_receber(None, None, msg(evento("medicao.temperatura", temp())))
        a = c.ativos["motor-1"]
        assert len(a.vib) == 1 and len(a.temp) == 1
        assert a.vib[0][0] == T0
        assert a.ultimo_evento is not None

    def test_duplicado_descartado(self):
        ev = evento("medicao.vibracao", vib())
        c.ao_receber(None, None, msg(ev))
        c.ao_receber(None, None, msg(ev))
        assert len(c.ativos["motor-1"].vib) == 1

    def test_qualidade_invalida_nao_entra_na_janela(self):
        c.ao_receber(None, None, msg(evento("medicao.vibracao", None, quality="INVALIDO", motivo="x")))
        a = c.ativos["motor-1"]
        assert a.vib == []
        assert a.ultimo_evento is not None  # ainda conta como comunicação

    def test_mudanca_de_operacao(self):
        c.ao_receber(None, None, msg(evento("maquina.mudanca_operacao", {"estado": "DESLIGADA"})))
        assert c.ativos["motor-1"].estado_operacional == "DESLIGADA"

    def test_ativos_separados_por_entidade(self):
        c.ao_receber(None, None, msg(evento("medicao.vibracao", vib(), entity="a")))
        c.ao_receber(None, None, msg(evento("medicao.vibracao", vib(), entity="b")))
        assert set(c.ativos) == {"a", "b"}


# --------------------------------------------------------------------- avaliar
class TestAvaliar:
    def test_sem_eventos_e_sem_comunicacao(self):
        assert c.avaliar(c.Ativo("x"), T0) == ("SEM_COMUNICACAO", {})

    def test_silencio_prolongado(self):
        a = ativo_com([vib()] * 3, [temp()] * 3)
        agora = T0 + timedelta(seconds=c.SILENCIO_S + 1)
        assert c.avaliar(a, agora)[0] == "SEM_COMUNICACAO"

    def test_dados_insuficientes(self):
        a = ativo_com([vib()] * 2, [temp()] * 3)
        assert c.avaliar(a, T0)[0] == "DADOS_INSUFICIENTES"
        a = ativo_com([vib()] * 3, [temp()] * 2)
        assert c.avaliar(a, T0)[0] == "DADOS_INSUFICIENTES"

    def test_amostras_fora_da_janela_sao_descartadas(self):
        a = ativo_com([vib()] * 3, [temp()] * 3)
        a.vib = [(T0 - timedelta(seconds=c.JANELA_S + 5), d) for _, d in a.vib]
        assert c.avaliar(a, T0)[0] == "DADOS_INSUFICIENTES"
        assert a.vib == []

    def test_desligada_nao_avaliavel(self):
        a = ativo_com([vib()] * 3, [temp()] * 3, operacional="DESLIGADA")
        assert c.avaliar(a, T0) == ("NAO_AVALIAVEL", {})

    def test_primeira_janela_vira_baseline(self):
        a = ativo_com([vib(1.0), vib(2.0), vib(3.0)], [temp(4.0)] * 3)
        assert c.avaliar(a, T0) == ("NORMAL", {})
        assert a.baseline == {"rms": 2.0, "delta_t": 4.0}

    def test_normal(self):
        a = ativo_com([vib(1.0)] * 5, [temp(5.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        decisao, m = c.avaliar(a, T0)
        assert decisao == "NORMAL"
        assert m == {"rmsNorm": 1.0, "curtoseMax": 3.0, "deltaT": 5.0}

    def test_atencao_por_rms_excedente(self):
        # 4 de 5 amostras (80%) acima de 1.5x a baseline
        vibs = [vib(1.6)] * 4 + [vib(1.0)]
        a = ativo_com(vibs, [temp(5.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        assert c.avaliar(a, T0)[0] == "ATENCAO"

    def test_atencao_por_delta_t(self):
        a = ativo_com([vib(1.0)] * 5, [temp(15.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        assert c.avaliar(a, T0)[0] == "ATENCAO"

    def test_critico_por_rms_e_curtose(self):
        a = ativo_com([vib(2.5, 7.0)] * 5, [temp(5.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        assert c.avaliar(a, T0)[0] == "CRITICO"

    def test_critico_por_rms_e_delta_t(self):
        a = ativo_com([vib(2.5, 3.0)] * 5, [temp(25.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        assert c.avaliar(a, T0)[0] == "CRITICO"

    def test_rms_alto_sozinho_nao_e_critico(self):
        a = ativo_com([vib(2.5, 3.0)] * 5, [temp(5.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        assert c.avaliar(a, T0)[0] == "ATENCAO"

    def test_delta_t_usa_ultimas_amostras(self):
        a = ativo_com([vib(1.0)] * 3, [temp(5.0)] * 3, baseline={"rms": 1.0, "delta_t": 5.0})
        # mais antigas (fim da lista) não entram: lista é ordenada por inserção
        a.temp = [(T0 - timedelta(seconds=10 - i), temp(d)) for i, d in enumerate([50, 50, 5, 5, 5])]
        assert c.avaliar(a, T0)[1]["deltaT"] == 5.0


# ----------------------------------------------------------------------- ciclo
class TestCiclo:
    def test_publica_decisao_retida_por_ativo(self):
        a = c.Ativo("motor-1")
        c.ativos["motor-1"] = a
        cli = MagicMock()
        c.ciclo(cli)
        topico, corpo = cli.publish.call_args[0]
        assert topico == "consumidor/motor-1/decisao"
        dados = json.loads(corpo)
        assert dados["entityId"] == "motor-1" and dados["decisao"] == "SEM_COMUNICACAO"
        assert cli.publish.call_args[1] == {"qos": 1, "retain": True}
        assert a.ultima_decisao == "SEM_COMUNICACAO"

    def test_publica_sempre_mesmo_sem_mudanca(self):
        c.ativos["motor-1"] = c.Ativo("motor-1")
        cli = MagicMock()
        c.ciclo(cli)
        c.ciclo(cli)
        assert cli.publish.call_count == 2

    def test_sem_ativos_nao_publica(self):
        cli = MagicMock()
        c.ciclo(cli)
        cli.publish.assert_not_called()


# ------------------------------------------------------------ integração local
def test_fluxo_completo_ate_critico():
    """Eventos brutos -> ao_receber -> avaliar: baseline, depois degradação."""
    agora = datetime.now(timezone.utc).replace(microsecond=0)
    n = [0]

    def envia(tipo, dados):
        n[0] += 1
        c.ao_receber(None, None, msg(evento(tipo, dados, n=n[0], ts=agora)))

    for _ in range(3):
        envia("medicao.vibracao", vib(1.0, 3.0))
        envia("medicao.temperatura", temp(5.0))
    a = c.ativos["motor-1"]
    assert c.avaliar(a, agora)[0] == "NORMAL" and a.baseline

    a.vib.clear()
    for _ in range(3):
        envia("medicao.vibracao", vib(3.0, 8.0))
    assert c.avaliar(a, agora)[0] == "CRITICO"


def test_main_conecta_e_encerra(monkeypatch):
    cli = MagicMock()
    monkeypatch.setattr(c.mqtt, "Client", MagicMock(return_value=cli))
    monkeypatch.setattr(c.time, "sleep", MagicMock(side_effect=KeyboardInterrupt))
    c.main()
    cli.username_pw_set.assert_called_once_with(c.MQTT_USUARIO, c.MQTT_SENHA)
    cli.connect.assert_called_once()
    cli.loop_start.assert_called_once()
    cli.loop_stop.assert_called_once()
    cli.disconnect.assert_called_once()
