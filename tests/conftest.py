"""Utilitários compartilhados: carrega módulos por caminho (main.py existe em dois
componentes) e simula as APIs de MicroPython usadas pelo publisher."""
import importlib.util
import sys
import time
import types
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
# consumidor/main.py faz `import db` (módulo vizinho)
sys.path.insert(0, str(RAIZ / "consumidor"))


def carregar(nome, caminho):
    spec = importlib.util.spec_from_file_location(nome, RAIZ / caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- shims MicroPython (rodam no CPython dos testes) ------------------------
if not hasattr(time, "ticks_ms"):
    time.ticks_ms = lambda: int(time.monotonic() * 1000)
    time.ticks_us = lambda: int(time.monotonic() * 1_000_000)
    time.ticks_diff = lambda a, b: a - b
    time.ticks_add = lambda a, b: a + b
    time.sleep_us = lambda us: None
    time.sleep_ms = lambda ms: None


class FakeMQTTClient:
    """Substitui umqtt.simple.MQTTClient."""
    instancias = []

    def __init__(self, client_id, host, port, user=None, password=None, keepalive=0):
        self.client_id, self.host, self.port = client_id, host, port
        self.user, self.password, self.keepalive = user, password, keepalive
        self.will = None
        self.publicados = []
        self.falha_connect = None
        self.falha_publish = None
        self.sock = types.SimpleNamespace(settimeout=lambda t: None, close=lambda: None)
        FakeMQTTClient.instancias.append(self)

    def set_last_will(self, topico, msg, retain=False, qos=0):
        self.will = (topico, msg, retain, qos)

    def connect(self, timeout=None):
        if self.falha_connect:
            raise self.falha_connect

    def publish(self, topico, msg, retain=False, qos=0):
        if self.falha_publish:
            raise self.falha_publish
        self.publicados.append((topico, msg, retain, qos))


umqtt = types.ModuleType("umqtt")
simple = types.ModuleType("umqtt.simple")
simple.MQTTClient = FakeMQTTClient
umqtt.simple = simple
sys.modules.setdefault("umqtt", umqtt)
sys.modules.setdefault("umqtt.simple", simple)
