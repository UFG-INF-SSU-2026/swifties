"""Fluxo ponta a ponta: produtores → broker → consumidor (decisão) → assinantes.

Os dois fluxos produtores (vibração e temperatura) entram no consumidor real,
que aprende a linha de base, detecta a degradação e publica a decisão no tópico
lido pelo dashboard e pelo app (``consumidor/+/decisao``).

Requisitos: RF-05, RF-07, RF-08, RF-09, RF-10, RNF-01, RNF-03.
"""
import time

import pytest

from integracao_apoio import esperar, temp, vib

pytestmark = pytest.mark.integracao

CAMPOS_CONTRATO = {"entityId", "decisao", "timestamp"}


def aprender_baseline(produtor, observador, entidade):
    produtor.operacao(entidade, "LIGADA")
    produtor.rajada(entidade, rms=1.0, curtose=2.0, delta_t=17.0, n=5)
    # 1º ciclo com dados suficientes vira a baseline; o seguinte já traz métricas
    return observador.esperar_decisao(entidade, "NORMAL", timeout=15) and esperar_metricas(observador, entidade)


def esperar_metricas(observador, entidade, timeout=10):
    return esperar(lambda: next((d for d in observador.decisoes(entidade)
                                 if d["decisao"] == "NORMAL" and "rmsNorm" in d), None),
                   timeout, msg="decisão NORMAL com métricas")


def test_baseline_e_degradacao_ate_critico(consumidor, produtor, observador, entidade):
    normal = aprender_baseline(produtor, observador, entidade)
    assert CAMPOS_CONTRATO <= normal.keys()
    assert normal["rmsNorm"] == pytest.approx(1.0)

    inicio = time.monotonic()
    produtor.rajada(entidade, rms=2.5, curtose=7.0, delta_t=17.0, n=15)
    critico = observador.esperar_decisao(entidade, "CRITICO", timeout=30, desde=inicio)

    assert time.monotonic() - inicio < 30, "RNF-01: degradação deve aparecer em até 30 s"
    assert critico["rmsNorm"] >= 2.0
    assert critico["curtoseMax"] >= 6.0


def test_atencao_por_aumento_de_temperatura(consumidor, produtor, observador, entidade):
    aprender_baseline(produtor, observador, entidade)
    inicio = time.monotonic()
    # ΔT médio das 3 últimas amostras sobe 12 °C acima da baseline (limiar: +10 °C)
    produtor.rajada(entidade, rms=1.0, curtose=2.0, delta_t=29.0, n=4)
    d = observador.esperar_decisao(entidade, "ATENCAO", timeout=20, desde=inicio)
    assert d["deltaT"] >= 27.0


def test_pico_isolado_nao_gera_alarme(consumidor, produtor, observador, entidade):
    """RNF-03: RMS alto sozinho, sem curtose nem ΔT, não é CRITICO."""
    aprender_baseline(produtor, observador, entidade)
    inicio = time.monotonic()
    produtor.rajada(entidade, rms=1.0, curtose=2.0, delta_t=17.0, n=3)
    produtor.rajada(entidade, rms=5.0, curtose=2.0, delta_t=17.0, n=1)
    time.sleep(6)   # três ciclos de avaliação
    decisoes = {d["decisao"] for d in observador.decisoes(entidade, desde=inicio)}
    assert "CRITICO" not in decisoes and decisoes, decisoes


def test_mudanca_de_contexto_maquina_desligada(consumidor, produtor, observador, entidade):
    """Contexto: com a máquina DESLIGADA o hub suspende o diagnóstico."""
    aprender_baseline(produtor, observador, entidade)
    inicio = time.monotonic()
    produtor.operacao(entidade, "DESLIGADA", anterior="LIGADA")
    produtor.rajada(entidade, rms=2.5, curtose=7.0, delta_t=17.0, n=5)   # seria CRITICO se ligada
    observador.esperar_decisao(entidade, "NAO_AVALIAVEL", timeout=15, desde=inicio)
    time.sleep(4)
    assert "CRITICO" not in {d["decisao"] for d in observador.decisoes(entidade, desde=inicio)}

    # volta a ligar: o diagnóstico é retomado e a degradação aparece
    retomada = time.monotonic()
    produtor.operacao(entidade, "LIGADA", anterior="DESLIGADA")
    produtor.rajada(entidade, rms=2.5, curtose=7.0, delta_t=17.0, n=5)
    observador.esperar_decisao(entidade, "CRITICO", timeout=15, desde=retomada)


def test_eventos_invalidos_e_duplicados_nao_entram_na_decisao(consumidor, produtor, observador, entidade):
    """RF-03/RF-07: inválidos são ignorados; duplicatas (reenvio QoS 1) são descartadas.

    Só 1 vibração válida chega (mais 4 cópias do mesmo eventId e 3 inválidas): se
    duplicatas ou inválidos contassem, a janela teria >= 3 vibrações e sairia de
    DADOS_INSUFICIENTES.
    """
    produtor.operacao(entidade, "LIGADA")
    ev = produtor.publicar(produtor.evento("medicao.vibracao", vib(), entidade))
    for _ in range(4):
        produtor.publicar(ev)
    for _ in range(3):
        produtor.publicar(produtor.evento("medicao.vibracao", None, entidade, motivo="mpu_fora_de_faixa"))
        produtor.publicar(produtor.evento("medicao.temperatura", temp(), entidade))

    observador.esperar_decisao(entidade, "DADOS_INSUFICIENTES", timeout=10)
    time.sleep(4)   # mais dois ciclos
    assert observador.ultima(entidade)["decisao"] == "DADOS_INSUFICIENTES"
