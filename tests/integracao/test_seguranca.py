"""Segurança no broker real: autenticação, autorização (ACL) e canal.

Usa exatamente ``broker/mosquitto.conf``, ``broker/acl`` e ``broker/passwd``.
Para que as negativas tenham valor, cada caso de bloqueio tem um controle
positivo: o mesmo cliente consegue fazer o que a ACL permite.

Requisitos: RF-06, RNF-05.
"""
import ssl
import time

import paho.mqtt.client as mqtt
import pytest

from integracao_apoio import (CRED, MQTT_HOST, Observador, Produtor, novo_cliente,
                              temp, tentar_conectar, vib)

pytestmark = pytest.mark.integracao

ESPERA_ENTREGA_S = 2


# ------------------------------------------------------------ autenticação
def test_credencial_valida_aceita(ambiente):
    assert tentar_conectar("esp32-07", CRED["esp32-07"]) == 0


@pytest.mark.parametrize("usuario,senha", [
    ("esp32-07", "senha-errada"),
    ("admin", ""),
    ("usuario-inexistente", "qualquer"),
], ids=["senha_errada", "senha_vazia", "usuario_inexistente"])
def test_identidade_invalida_rejeitada(ambiente, usuario, senha):
    rc = tentar_conectar(usuario, senha)
    assert rc is not None and rc.is_failure, f"broker aceitou {usuario!r}: {rc}"


def test_cliente_anonimo_rejeitado(ambiente):
    rc = tentar_conectar()   # sem usuário/senha (allow_anonymous false)
    assert rc is not None and rc.is_failure


# -------------------------------------------------------------- autorização
@pytest.fixture
def espiao(ambiente):
    """admin assina tudo em swifties/# para ver o que realmente chegou ao broker."""
    o = Observador(usuario="admin", topico="swifties/#")
    yield o
    o.fechar()


def chegou(espiao, marcador):
    return [t for t, p in espiao.recebidas(lambda t, p: isinstance(p, dict) and p.get("entityId") == marcador)]


def test_no_publica_apenas_no_proprio_topico(consumidor, espiao, observador, entidade):
    p = Produtor()
    try:
        # controle positivo
        p.publicar(p.evento("medicao.vibracao", vib(), entidade))
        # tentativa de se passar por outro nó
        intruso = entidade + "-forjado"
        for _ in range(3):
            p.publicar(p.evento("medicao.vibracao", vib(), intruso), topico="swifties/esp32-99/medicao/vibracao")
            p.publicar(p.evento("medicao.temperatura", temp(), intruso), topico="swifties/esp32-99/medicao/temperatura")
        time.sleep(ESPERA_ENTREGA_S + 2)
    finally:
        p.fechar()
    assert chegou(espiao, entidade) == ["swifties/esp32-07/medicao/vibracao"]
    assert chegou(espiao, intruso) == [], "ACL deveria barrar publicação fora de swifties/esp32-07/#"
    assert observador.decisoes(intruso) == [], "consumidor não pode ter recebido o evento forjado"


def test_consumidor_nao_publica_eventos_de_campo(ambiente, espiao, entidade):
    """Credencial do hub não serve para injetar medições como se fosse o nó."""
    p = Produtor(usuario="consumidor", device_id="esp32-07")
    try:
        p.publicar(p.evento("medicao.vibracao", vib(), entidade))
        time.sleep(ESPERA_ENTREGA_S)
    finally:
        p.fechar()
    assert chegou(espiao, entidade) == []


def test_no_nao_le_decisoes(consumidor, produtor, entidade):
    """esp32-07 só tem permissão de escrita: assinar consumidor/# não entrega nada."""
    o = Observador(usuario="esp32-07", topico="consumidor/#")
    controle = Observador(usuario="admin", topico="consumidor/#")
    try:
        produtor.operacao(entidade, "LIGADA")
        produtor.rajada(entidade, n=3)
        controle.esperar_decisao(entidade, "NORMAL", timeout=15)   # houve decisões publicadas
        time.sleep(1)
        assert o.recebidas() == []
    finally:
        o.fechar()
        controle.fechar()


def test_consumidor_nao_publica_fora_do_seu_prefixo(ambiente, espiao, entidade):
    c = novo_cliente("consumidor", CRED["consumidor"])
    c.connect(MQTT_HOST, 18830)
    c.loop_start()
    try:
        time.sleep(0.5)
        c.publish("swifties/esp32-07/status", f'{{"entityId": "{entidade}"}}', qos=1).wait_for_publish(5)
        time.sleep(ESPERA_ENTREGA_S)
    finally:
        c.loop_stop()
        c.disconnect()
    assert chegou(espiao, entidade) == []


# --------------------------------------------------------------------- canal
@pytest.mark.xfail(strict=True, reason="PENDENTE: broker ainda sem listener TLS (8883); "
                                        "ver limitações em docs/requisitos.md")
def test_canal_criptografado_tls(ambiente):
    c = mqtt.Client(client_id="it-tls", callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    c.username_pw_set("admin", CRED["admin"])
    c.tls_set(cert_reqs=ssl.CERT_REQUIRED)   # valida a identidade do servidor
    c.connect(MQTT_HOST, 18883, keepalive=10)
