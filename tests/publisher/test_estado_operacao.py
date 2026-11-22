"""EstadoOperacao vive em publisher/main.py, que executa o hardware ao ser importado.
Extraímos só a classe (e as constantes que ela usa) via AST, sem alterar o firmware."""
import ast

import pytest

from conftest import RAIZ


def carregar_estado():
    arvore = ast.parse((RAIZ / "publisher/main.py").read_text())
    consts = {"LIGA_RMS_G", "DESLIGA_RMS_G", "PERSISTENCIA"}
    nos = [n for n in arvore.body
           if (isinstance(n, ast.Assign) and any(getattr(t, "id", None) in consts for t in n.targets))
           or (isinstance(n, ast.ClassDef) and n.name == "EstadoOperacao")]
    ns = {}
    exec(compile(ast.Module(nos, []), "main.py", "exec"), ns)
    return ns


NS = carregar_estado()


@pytest.fixture
def op():
    return NS["EstadoOperacao"]()


def test_constantes_coerentes():
    assert NS["DESLIGA_RMS_G"] < NS["LIGA_RMS_G"]


def test_exige_persistencia_para_mudar(op):
    assert op.atualizar(1.0) is False and op.estado == "DESCONHECIDO"
    assert op.atualizar(1.0) is True
    assert (op.estado, op.anterior) == ("LIGADA", "DESCONHECIDO")


def test_pico_isolado_nao_muda_estado(op):
    op.atualizar(1.0); op.atualizar(1.0)
    op.atualizar(0.0)           # um desligado só
    op.atualizar(1.0)           # volta a ligado: candidato é descartado
    op.atualizar(0.0)
    assert op.estado == "LIGADA"


def test_desliga_apos_persistencia(op):
    op.atualizar(1.0); op.atualizar(1.0)
    assert op.atualizar(0.0) is False
    assert op.atualizar(0.0) is True
    assert (op.estado, op.anterior) == ("DESLIGADA", "LIGADA")


def test_histerese_faixa_intermediaria_mantem(op):
    op.atualizar(1.0); op.atualizar(1.0)
    meio = (NS["LIGA_RMS_G"] + NS["DESLIGA_RMS_G"]) / 2
    for _ in range(5):
        assert op.atualizar(meio) is False
    assert op.estado == "LIGADA"
