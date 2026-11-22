import json
import re

import pytest

from conftest import FakeMQTTClient, carregar

ev = carregar("publisher_evento", "publisher/evento.py")


def novo_emissor(transporte=None, max_buffer=3):
    enviados = []
    t = transporte or (lambda tipo, msg: enviados.append((tipo, msg)) or True)
    return ev.Emissor("esp32-07", "motor-1", 42, t, max_buffer=max_buffer), enviados


def test_agora_iso_formato():
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", ev.agora_iso())


class TestEmissor:
    def test_cria_evento_valido(self):
        e, _ = novo_emissor()
        r = e.criar("medicao.vibracao", {"rms": 1})
        assert r["eventId"] == "esp32-07-42-1"
        assert r["quality"] == "VALIDO" and r["motivo"] is None
        assert r["schemaVersion"] == ev.SCHEMA_VERSION
        assert r["entityId"] == "motor-1" and r["deviceId"] == "esp32-07"
        assert len(e.buffer) == 1

    def test_evento_invalido_conta(self):
        e, _ = novo_emissor()
        r = e.criar("medicao.vibracao", None, "mpu_sem_resposta")
        assert r["quality"] == "INVALIDO" and r["motivo"] == "mpu_sem_resposta"
        assert e.invalidos == 1

    def test_sequencia_e_ids_unicos(self):
        e, _ = novo_emissor(max_buffer=10)
        ids = [e.criar("t", {})["eventId"] for _ in range(5)]
        assert len(set(ids)) == 5 and e.seq == 5

    def test_buffer_cheio_descarta_o_mais_antigo(self):
        e, _ = novo_emissor(max_buffer=3)
        for _ in range(5):
            e.criar("t", {})
        assert len(e.buffer) == 3 and e.perdidos == 2
        # sobraram as sequências 3, 4 e 5
        assert [json.loads(m)["sequence"] for _, m in e.buffer] == [3, 4, 5]

    def test_offline_nao_envia(self):
        e, enviados = novo_emissor()
        e.criar("t", {})
        assert e.enviar_um(online=False) is False
        assert enviados == [] and len(e.buffer) == 1

    def test_envia_em_ordem_fifo(self):
        e, enviados = novo_emissor(max_buffer=10)
        for _ in range(3):
            e.criar("t", {})
        while e.enviar_um(online=True):
            pass
        assert [json.loads(m)["sequence"] for _, m in enviados] == [1, 2, 3]
        assert e.enviados == 3 and e.buffer == []

    def test_falha_de_transporte_mantem_no_buffer(self):
        e, _ = novo_emissor(transporte=lambda t, m: False)
        e.criar("t", {})
        assert e.enviar_um(online=True) is False
        assert len(e.buffer) == 1 and e.enviados == 0

    def test_buffer_vazio_online(self):
        e, _ = novo_emissor()
        assert e.enviar_um(online=True) is False

    def test_estado_link(self):
        e, _ = novo_emissor(max_buffer=2)
        e.enviar_um(online=False)
        assert e.estado_link() == "OFFLINE"
        e.enviar_um(online=True)
        assert e.estado_link() == "EM_DIA"
        e.criar("t", {})
        assert e.estado_link() == "PENDENTE"
        e.criar("t", {})
        assert e.estado_link() == "BUFFER_CHEIO"


class TestConexaoMQTT:
    @pytest.fixture
    def conexao(self):
        FakeMQTTClient.instancias.clear()
        c = ev.ConexaoMQTT("esp32-07", "h", 1883, "swifties/esp32-07", usuario="u", senha="s")
        return c, c.cliente

    def test_configura_last_will(self, conexao):
        c, cli = conexao
        assert cli.will == ("swifties/esp32-07/status", "OFFLINE", True, 1)
        assert (cli.user, cli.password) == ("u", "s")

    def test_conecta_e_publica_online(self, conexao):
        c, cli = conexao
        c.manter()
        assert c.conectado
        assert cli.publicados == [("swifties/esp32-07/status", "ONLINE", True, 1)]

    def test_falha_ao_conectar_nao_marca_conectado(self, conexao):
        c, cli = conexao
        cli.falha_connect = OSError("sem rota")
        c.manter()
        assert not c.conectado

    def test_respeita_intervalo_de_reconexao(self, conexao, monkeypatch):
        c, cli = conexao
        cli.falha_connect = OSError("x")
        c.manter()
        cli.falha_connect = None
        c.manter()                     # dentro dos 5 s: não tenta
        assert not c.conectado
        c.ultima_tentativa -= c.reconexao_ms + 1
        c.manter()
        assert c.conectado

    def test_enviar_traduz_topico(self, conexao):
        c, cli = conexao
        c.manter()
        assert c.enviar("medicao.vibracao", "{}") is True
        assert cli.publicados[-1][:2] == ("swifties/esp32-07/medicao/vibracao", "{}")
        assert cli.publicados[-1][3] == 1  # QoS 1

    def test_enviar_desconectado(self, conexao):
        c, _ = conexao
        assert c.enviar("t", "{}") is False

    def test_falha_no_envio_derruba_conexao(self, conexao):
        c, cli = conexao
        c.manter()
        cli.falha_publish = OSError("quebrou")
        assert c.enviar("t", "{}") is False
        assert not c.conectado

    def test_derrubar(self, conexao):
        c, _ = conexao
        c.manter()
        c.derrubar()
        assert not c.conectado
