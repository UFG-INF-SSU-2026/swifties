"""Infraestrutura dos testes de integração (plugin pytest carregado por pytest.ini).

Sobe um Mosquitto real (com a configuração, ACL e senhas de ``broker/``) e um
TimescaleDB local via Docker Compose, roda o consumidor como **processo real**
(``consumidor/main.py``) e oferece clientes MQTT de teste: um produtor no papel
do nó ``esp32-07`` e um observador ``admin`` que coleta as decisões.

Sem Docker disponível, todos os testes de integração são pulados (skip).

Variáveis úteis:
  INTEGRACAO_MANTER=1   não derruba o ambiente ao final (para inspeção)
"""
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
import psycopg
import pytest

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = Path(__file__).resolve().parent / "docker-compose.yml"
PROJETO = "swifties-it"

MQTT_HOST, MQTT_PORTA = "localhost", 18830
DB = dict(host="localhost", port=15432, user="swifties", password="swifties-teste", dbname="swifties")

# Credenciais de teste documentadas em broker/README.md
CRED = {
    "admin": "admin123",
    "esp32-07": "esp32123",
    "consumidor": "consumidor123",
}
TOPICO_DECISOES = "consumidor/+/decisao"


# ---------------------------------------------------------------- utilidades
def esperar(condicao, timeout, intervalo=0.25, msg="condição"):
    """Repete `condicao()` até retornar algo verdadeiro ou estourar `timeout`."""
    limite = time.monotonic() + timeout
    while True:
        r = condicao()
        if r:
            return r
        if time.monotonic() > limite:
            raise AssertionError(f"tempo esgotado ({timeout}s) esperando {msg}")
        time.sleep(intervalo)


def agora_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def novo_cliente(usuario=None, senha=None, prefixo="it"):
    c = mqtt.Client(client_id=f"{prefixo}-{uuid.uuid4().hex[:8]}",
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    if usuario is not None:
        c.username_pw_set(usuario, senha)
    return c


def tentar_conectar(usuario=None, senha=None, timeout=5):
    """Abre uma conexão e devolve o ReasonCode do CONNACK (None se não houver resposta)."""
    resultado, pronto = {}, threading.Event()
    c = novo_cliente(usuario, senha)
    c.reconnect_delay_set(60, 60)   # não insistir após a recusa

    def ao_conectar(cliente, userdata, flags, rc, properties=None):
        resultado["rc"] = rc
        pronto.set()

    c.on_connect = ao_conectar
    c.connect(MQTT_HOST, MQTT_PORTA, keepalive=10)
    c.loop_start()
    try:
        pronto.wait(timeout)
    finally:
        c.loop_stop()
        try:
            c.disconnect()
        except Exception:
            pass
    return resultado.get("rc")


def consultar(sql, *params):
    with psycopg.connect(**DB, connect_timeout=5) as conn:
        return conn.execute(sql, params).fetchall()


def contar(tabela, entidade):
    return consultar(f"SELECT count(*) FROM {tabela} WHERE entity_id = %s", entidade)[0][0]


# ------------------------------------------------------------ ambiente Docker
class Ambiente:
    def compose(self, *args, check=True):
        return subprocess.run(["docker", "compose", "-f", str(COMPOSE), "-p", PROJETO, *args],
                              check=check, capture_output=True, text=True)

    def parar(self, servico):
        self.compose("stop", servico)

    def iniciar(self, servico):
        self.compose("start", servico)
        {"mosquitto": self.esperar_broker, "timescaledb": self.esperar_banco}[servico]()

    def esperar_broker(self, timeout=60):
        def pronto():
            try:
                return tentar_conectar("admin", CRED["admin"], timeout=2) == 0
            except OSError:
                return False
        esperar(pronto, timeout, intervalo=0.5, msg="broker MQTT")

    def esperar_banco(self, timeout=90):
        def pronto():
            try:
                # a imagem reinicia o postgres uma vez durante a inicialização;
                # só considera pronto após a extensão estar disponível
                consultar("SELECT 1 FROM pg_available_extensions WHERE name = 'timescaledb'")
                return True
            except psycopg.Error:
                return False
        esperar(pronto, timeout, intervalo=1, msg="TimescaleDB")


def _docker_disponivel():
    if not shutil.which("docker"):
        return False
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


@pytest.fixture(scope="session")
def ambiente():
    if not _docker_disponivel():
        pytest.skip("Docker indisponível: testes de integração exigem `docker compose`")
    amb = Ambiente()
    amb.compose("down", "-v", check=False)
    amb.compose("up", "-d")
    try:
        amb.esperar_broker()
        amb.esperar_banco()
        # estabiliza: a imagem do TimescaleDB reinicia o servidor após o initdb
        time.sleep(2)
        amb.esperar_banco()
        yield amb
    finally:
        if os.getenv("INTEGRACAO_MANTER") != "1":
            amb.compose("down", "-v", check=False)


# -------------------------------------------------------------- consumidor
class Consumidor:
    """Executa consumidor/main.py como processo separado, apontado para o ambiente de teste."""

    def __init__(self, log_path):
        self.log_path = log_path
        self.proc = None
        self._log = None

    def env(self):
        e = dict(os.environ)
        e.update(PYTHONUNBUFFERED="1",
                 MQTT_HOST=MQTT_HOST, MQTT_PORTA=str(MQTT_PORTA),
                 MQTT_USUARIO="consumidor", MQTT_SENHA=CRED["consumidor"],
                 POSTGRES_HOST=DB["host"], POSTGRES_PORT=str(DB["port"]),
                 POSTGRES_USER=DB["user"], POSTGRES_PASSWORD=DB["password"],
                 POSTGRES_DB=DB["dbname"], DB_APLICAR_SCHEMA="1")
        return e

    def log(self):
        return self.log_path.read_text() if self.log_path.exists() else ""

    def iniciar(self):
        inicio = len(self.log())
        self._log = open(self.log_path, "a")
        self.proc = subprocess.Popen([sys.executable, "main.py"], cwd=RAIZ / "consumidor",
                                     env=self.env(), stdout=self._log, stderr=subprocess.STDOUT)
        esperar(lambda: "assinado em swifties/#" in self.log()[inicio:], 30,
                msg="consumidor conectar ao broker")
        esperar(lambda: "conectado ao TimescaleDB" in self.log()[inicio:], 60,
                msg="consumidor conectar ao banco")

    def parar(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self.proc.wait(10)
        if self._log:
            self._log.close()
            self._log = None

    def reiniciar(self):
        self.parar()
        self.iniciar()

    def vivo(self):
        return self.proc is not None and self.proc.poll() is None


@pytest.fixture(scope="session")
def _consumidor_sessao(ambiente, tmp_path_factory):
    c = Consumidor(tmp_path_factory.mktemp("consumidor") / "consumidor.log")
    c.iniciar()
    yield c
    c.parar()


@pytest.fixture
def consumidor(_consumidor_sessao, request):
    """Garante o consumidor rodando antes de cada teste; anexa o log em caso de falha."""
    if not _consumidor_sessao.vivo():
        _consumidor_sessao.iniciar()
    yield _consumidor_sessao
    rep = getattr(request.node, "rep_call", None)
    if rep is not None and rep.failed:
        print("\n--- log do consumidor (final) ---\n" + _consumidor_sessao.log()[-4000:])


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    resultado = yield
    rep = resultado.get_result()
    setattr(item, "rep_" + rep.when, rep)


# --------------------------------------------------------- clientes de teste
class Observador:
    """Cliente MQTT que assina tópicos e guarda as mensagens recebidas (JSON quando possível)."""

    def __init__(self, usuario="admin", topico=TOPICO_DECISOES):
        self.msgs, self._trava = [], threading.Lock()
        self._conectado = threading.Event()
        self.topico = topico
        self.c = novo_cliente(usuario, CRED.get(usuario), prefixo="it-obs")
        self.c.on_connect = self._ao_conectar
        self.c.on_message = self._ao_receber
        self.c.connect(MQTT_HOST, MQTT_PORTA, keepalive=30)
        self.c.loop_start()
        assert self._conectado.wait(10), "observador não conectou"
        time.sleep(0.3)   # SUBACK

    def _ao_conectar(self, cliente, userdata, flags, rc, properties=None):
        if rc == 0:
            cliente.subscribe(self.topico, qos=1)
            self._conectado.set()

    def _ao_receber(self, cliente, userdata, msg):
        try:
            payload = json.loads(msg.payload)
        except ValueError:
            payload = msg.payload.decode(errors="replace")
        with self._trava:
            self.msgs.append((msg.topic, payload, time.monotonic()))

    def decisoes(self, entidade, desde=0.0):
        with self._trava:
            return [p for t, p, ts in self.msgs
                    if ts >= desde and isinstance(p, dict) and p.get("entityId") == entidade]

    def esperar_decisao(self, entidade, decisao, timeout=30, desde=0.0):
        return esperar(lambda: next((d for d in self.decisoes(entidade, desde)
                                     if d["decisao"] == decisao), None),
                       timeout, msg=f"decisão {decisao} para {entidade}")

    def ultima(self, entidade):
        ds = self.decisoes(entidade)
        return ds[-1] if ds else None

    def recebidas(self, filtro=lambda t, p: True):
        with self._trava:
            return [(t, p) for t, p, _ in self.msgs if filtro(t, p)]

    def fechar(self):
        self.c.loop_stop()
        self.c.disconnect()


class Produtor:
    """Publica eventos do contrato v1 (publisher/README.md) no papel de um nó."""

    def __init__(self, usuario="esp32-07", device_id="esp32-07"):
        self.device_id = device_id
        self.boot = uuid.uuid4().hex[:8]
        self.seq = 0
        conectado = threading.Event()
        self.c = novo_cliente(usuario, CRED.get(usuario), prefixo=f"it-{usuario}")
        self.c.on_connect = lambda cl, ud, fl, rc, pr=None: rc == 0 and conectado.set()
        self.c.connect(MQTT_HOST, MQTT_PORTA, keepalive=30)
        self.c.loop_start()
        assert conectado.wait(10), f"produtor {usuario} não conectou"

    def evento(self, tipo, dados, entidade, motivo=None):
        self.seq += 1
        return {"schemaVersion": 1, "eventId": f"{self.device_id}-{self.boot}-{self.seq}",
                "eventType": tipo, "deviceId": self.device_id, "entityId": entidade,
                "sequence": self.seq, "eventTime": agora_iso(),
                "quality": "INVALIDO" if motivo else "VALIDO", "motivo": motivo, "data": dados}

    def publicar(self, ev, topico=None):
        topico = topico or f"swifties/{self.device_id}/" + ev["eventType"].replace(".", "/")
        self.c.publish(topico, json.dumps(ev), qos=1).wait_for_publish(5)
        return ev

    def operacao(self, entidade, estado, anterior="DESCONHECIDO"):
        return self.publicar(self.evento("maquina.mudanca_operacao",
                                         {"estado": estado, "anterior": anterior, "rms_resultante": 1.0},
                                         entidade))

    def rajada(self, entidade, rms=1.0, curtose=2.0, delta_t=17.0, n=5):
        """n medições de vibração + n de temperatura; devolve os eventos publicados."""
        evs = []
        for _ in range(n):
            evs.append(self.publicar(self.evento("medicao.vibracao", vib(rms, curtose), entidade)))
            evs.append(self.publicar(self.evento("medicao.temperatura", temp(delta_t), entidade)))
        return evs

    def fechar(self):
        self.c.loop_stop()
        self.c.disconnect()


def vib(rms=1.0, curtose=2.0):
    return {"rms_x": rms, "rms_y": 0.05, "rms_z": 0.05, "rms_resultante": rms,
            "pico": round(rms * 1.4, 3), "curtose": curtose, "freq_dominante": 29.6}


def temp(delta_t=17.0, ambiente=28.0):
    return {"temp_carcaca": ambiente + delta_t, "temp_ambiente": ambiente, "delta_t": delta_t}


@pytest.fixture
def observador(ambiente):
    o = Observador()
    yield o
    o.fechar()


@pytest.fixture
def produtor(ambiente):
    p = Produtor()
    yield p
    p.fechar()


@pytest.fixture
def entidade():
    """Ativo novo por teste: decisões retidas de outros testes não interferem."""
    return f"it-motor-{uuid.uuid4().hex[:6]}"
