import json, time
from umqtt.simple import MQTTClient

SCHEMA_VERSION = 1


def agora_iso():
    t = time.gmtime(time.time())
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (t[0], t[1], t[2], t[3], t[4], t[5])


class ConexaoMQTT:
    def __init__(self, client_id, host, porta, prefixo,
                 keepalive_s=60, reconexao_ms=5000, timeout_s=5):
        self.host, self.porta, self.prefixo = host, porta, prefixo
        self.reconexao_ms, self.timeout_s = reconexao_ms, timeout_s
        self.topico_status = prefixo + "/status"
        self.cliente = MQTTClient(client_id, host, porta, keepalive=keepalive_s)
        self.cliente.set_last_will(self.topico_status, "OFFLINE", retain=True, qos=1)
        self.conectado = False
        self.ultima_tentativa = None

    def manter(self):
        if self.conectado:
            return
        agora = time.ticks_ms()
        if self.ultima_tentativa is not None and \
                time.ticks_diff(agora, self.ultima_tentativa) < self.reconexao_ms:
            return
        self.ultima_tentativa = agora
        try:
            try:
                self.cliente.connect(timeout=self.timeout_s)
            except TypeError:
                self.cliente.connect()
            self.conectado = True
            self._publicar(self.topico_status, "ONLINE", retain=True)
            print("[MQTT] conectado a %s:%d" % (self.host, self.porta))
        except Exception as e:
            self._fechar()
            print("[MQTT] falha ao conectar (%r); nova tentativa em %d s" % (e, self.reconexao_ms // 1000))

    def derrubar(self):
        if self.conectado:
            self._fechar()
            print("[MQTT] conexao derrubada (o broker publicara OFFLINE)")

    def enviar(self, tipo, mensagem):
        if not self.conectado:
            return False
        topico = self.prefixo + "/" + tipo.replace(".", "/")
        try:
            self._publicar(topico, mensagem)
        except Exception as e:
            print("[MQTT] envio falhou (%r): evento continua no buffer" % e)
            self._fechar()
            return False
        print("[PUB]", topico, mensagem)
        return True

    def _publicar(self, topico, mensagem, retain=False):
        # o umqtt deixa o socket bloqueante, entao reaplico o timeout a cada envio
        self.cliente.sock.settimeout(self.timeout_s)
        self.cliente.publish(topico, mensagem, retain, 1)

    def _fechar(self):
        self.conectado = False
        try:
            self.cliente.sock.close()
        except Exception:
            pass


class Emissor:
    def __init__(self, device_id, entity_id, boot_id, transporte, max_buffer=100):
        self.device_id = device_id
        self.entity_id = entity_id
        self.boot_id = boot_id
        self.max_buffer = max_buffer
        self.transporte = transporte

        self.buffer = []
        self.seq = 0
        self.online = False
        self.enviados = 0
        self.perdidos = 0
        self.invalidos = 0

    def criar(self, tipo, dados, motivo=None):
        self.seq += 1
        ev = {
            "schemaVersion": SCHEMA_VERSION,
            "eventId": "%s-%d-%d" % (self.device_id, self.boot_id, self.seq),
            "eventType": tipo,
            "deviceId": self.device_id,
            "entityId": self.entity_id,
            "sequence": self.seq,
            "eventTime": agora_iso(),
            "quality": "INVALIDO" if motivo else "VALIDO",
            "motivo": motivo,
            "data": dados,
        }
        if motivo:
            self.invalidos += 1
            print("[INVALIDO] seq=%d %s: %s" % (self.seq, tipo, motivo))

        if len(self.buffer) >= self.max_buffer:
            self.buffer.pop(0)
            self.perdidos += 1
            print("[PERDA] buffer cheio: evento mais antigo descartado (perdidos=%d)" % self.perdidos)

        self.buffer.append((tipo, json.dumps(ev)))
        if not self.online:
            print("[BUFFER] seq=%d %s guardado (pendentes=%d)" % (self.seq, tipo, len(self.buffer)))
        return ev

    def enviar_um(self, online):
        self.online = online
        if not online or not self.buffer:
            return False
        tipo, mensagem = self.buffer[0]
        if self.transporte(tipo, mensagem):
            self.buffer.pop(0)
            self.enviados += 1
            return True
        return False

    def estado_link(self):
        if len(self.buffer) >= self.max_buffer:
            return "BUFFER_CHEIO"
        if not self.online:
            return "OFFLINE"
        if self.buffer:
            return "PENDENTE"
        return "EM_DIA"
