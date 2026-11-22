"""Falhas reais e recuperação: banco fora, broker fora e silêncio do nó.

Os componentes são parados de verdade (``docker compose stop``) com o
consumidor em execução; cada teste verifica o comportamento durante a falha e
após o retorno.

Requisitos: RNF-07, RF-10, RNF-02 (lado do hub).
"""
import time

import pytest

from integracao_apoio import Observador, Produtor, consultar, contar, esperar

pytestmark = pytest.mark.integracao


def baseline(produtor, observador, entidade):
    produtor.operacao(entidade, "LIGADA")
    produtor.rajada(entidade, n=5)
    observador.esperar_decisao(entidade, "NORMAL", timeout=15)


def test_banco_fora_hub_segue_decidindo_e_grava_ao_voltar(ambiente, consumidor, produtor, observador, entidade):
    baseline(produtor, observador, entidade)
    esperar(lambda: contar("medicoes_vibracao", entidade) == 5, 20, msg="gravação inicial")

    ambiente.parar("timescaledb")
    try:
        # durante a falha: novas medições chegam e a decisão continua saindo
        inicio = time.monotonic()
        produtor.rajada(entidade, rms=2.5, curtose=7.0, n=15)
        observador.esperar_decisao(entidade, "CRITICO", timeout=30, desde=inicio)
        esperar(lambda: "falha no banco" in consumidor.log(), 30, msg="consumidor detectar o banco fora")
    finally:
        ambiente.iniciar("timescaledb")

    # após o retorno: o que ficou na fila em memória é gravado
    esperar(lambda: contar("medicoes_vibracao", entidade) == 20
            and contar("medicoes_temperatura", entidade) == 20, 60, msg="fila drenada no banco")
    esperar(lambda: consultar("SELECT 1 FROM decisoes WHERE entity_id = %s AND decisao = 'CRITICO'", entidade),
            20, msg="decisão CRITICO gravada")


def test_broker_fora_consumidor_reconecta_e_volta_a_decidir(ambiente, consumidor, entidade):
    ambiente.parar("mosquitto")
    try:
        time.sleep(5)
        assert consumidor.vivo(), "consumidor não pode morrer com o broker fora"
    finally:
        ambiente.iniciar("mosquitto")

    # o consumidor reconecta sozinho e reassina swifties/# (on_connect)
    esperar(lambda: consumidor.log().count("assinado em swifties/#") >= 2, 90, msg="consumidor reconectar")

    observador, produtor = Observador(), Produtor()
    try:
        produtor.operacao(entidade, "LIGADA")
        produtor.rajada(entidade, n=5)
        observador.esperar_decisao(entidade, "NORMAL", timeout=20)
    finally:
        produtor.fechar()
        observador.fechar()


def test_silencio_do_no_vira_sem_comunicacao_e_recupera(consumidor, produtor, observador, entidade):
    baseline(produtor, observador, entidade)

    silencio = time.monotonic()
    d = observador.esperar_decisao(entidade, "SEM_COMUNICACAO", timeout=30, desde=silencio)
    assert d   # SILENCIO_S = 15 s sem eventos

    retorno = time.monotonic()
    produtor.rajada(entidade, n=5)
    esperar(lambda: any(x["decisao"] != "SEM_COMUNICACAO" for x in observador.decisoes(entidade, retorno)),
            10, msg="sair de SEM_COMUNICACAO")
