from machine import Pin, ADC, I2C
import network, ntptime, time
import sensores, evento

DEVICE_ID = "esp32-07"
ENTITY_ID = "motor-linha3-02"

CADENCIA_VIB_MS = 5000
CADENCIA_TEMP_MS = 2000
LOOP_MS = 50

AMOSTRAS = 64
PERIODO_AMOSTRA_MS = 10
FREQ_ROTACAO_HZ = 29.6
AMPLITUDE_MAX_G = 4.0

LIGA_RMS_G = 0.20
DESLIGA_RMS_G = 0.10
PERSISTENCIA = 2

# o endereco do ngrok muda toda vez que o tunel reinicia
MQTT_HOST = "0.tcp.sa.ngrok.io"
MQTT_PORTA = 24143
MQTT_PREFIXO = "swifties/" + DEVICE_ID

BUFFER_MAX = 100
DEBOUNCE_MS = 300

led_r, led_g, led_b = Pin(25, Pin.OUT), Pin(26, Pin.OUT), Pin(27, Pin.OUT)
pot = ADC(Pin(34))
pot.atten(ADC.ATTN_11DB)
btn = Pin(4, Pin.IN, Pin.PULL_UP)

AZUL, VERDE, AMARELO, VERMELHO, MAGENTA = (0, 0, 1), (0, 1, 0), (1, 1, 0), (1, 0, 0), (1, 0, 1)


def cor(rgb):
    led_r.value(rgb[0])
    led_g.value(rgb[1])
    led_b.value(rgb[2])


falha_simulada = False
_t_botao = 0


def _ao_botao(pin):
    global falha_simulada, _t_botao
    agora = time.ticks_ms()
    if time.ticks_diff(agora, _t_botao) > DEBOUNCE_MS:
        _t_botao = agora
        falha_simulada = not falha_simulada


btn.irq(trigger=Pin.IRQ_FALLING, handler=_ao_botao)


class EstadoOperacao:
    def __init__(self):
        self.estado = "DESCONHECIDO"
        self.anterior = None
        self.candidato = None
        self.contagem = 0

    def atualizar(self, rms):
        if rms >= LIGA_RMS_G:
            alvo = "LIGADA"
        elif rms < DESLIGA_RMS_G:
            alvo = "DESLIGADA"
        else:
            alvo = self.estado

        if alvo == self.estado:
            self.candidato, self.contagem = None, 0
            return False

        if alvo == self.candidato:
            self.contagem += 1
        else:
            self.candidato, self.contagem = alvo, 1

        if self.contagem >= PERSISTENCIA:
            self.anterior, self.estado = self.estado, alvo
            self.candidato, self.contagem = None, 0
            return True
        return False


def conectar_wifi(timeout_ms=15000):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect("Wokwi-GUEST", "")
        inicio = time.ticks_ms()
        while not wlan.isconnected():
            if time.ticks_diff(time.ticks_ms(), inicio) > timeout_ms:
                print("[WIFI] falhou")
                return False
            time.sleep_ms(200)
    print("[WIFI] ok", wlan.ifconfig()[0])
    return True


def sincronizar_relogio(tentativas=5):
    for _ in range(tentativas):
        try:
            ntptime.settime()
            print("[NTP] ok", evento.agora_iso())
            return True
        except Exception:
            time.sleep_ms(1000)
    print("[NTP] falhou: eventTime ficara sem referencia real")
    return False


cor(AZUL)
if conectar_wifi():
    sincronizar_relogio()

mqtt = evento.ConexaoMQTT(DEVICE_ID, MQTT_HOST, MQTT_PORTA, MQTT_PREFIXO)
emissor = evento.Emissor(DEVICE_ID, ENTITY_ID, boot_id=time.time(),
                         transporte=mqtt.enviar, max_buffer=BUFFER_MAX)
mpu = sensores.MPU6050(I2C(0, scl=Pin(22), sda=Pin(21), freq=400000))
if not mpu.iniciar():
    print("[MPU6050] sem resposta")
term_carcaca = sensores.Termometro(Pin(18))
term_ambiente = sensores.Termometro(Pin(19))
operacao = EstadoOperacao()

temp_anterior = None
t_temp_anterior = 0
conversao_desde = None
invalido_vib = invalido_temp = False
falha_anterior = False
link_anterior = None
drenando = False

t_vib = t_temp = time.ticks_ms()
print("[BOOT] %s / %s  boot_id=%d" % (DEVICE_ID, ENTITY_ID, emissor.boot_id))


def tratar_temperatura():
    global temp_anterior, t_temp_anterior, invalido_temp
    carcaca, ambiente = term_carcaca.ler(), term_ambiente.ler()
    agora = time.ticks_ms()
    dt_s = time.ticks_diff(agora, t_temp_anterior) / 1000

    motivo = sensores.validar_temperatura(carcaca, ambiente, temp_anterior, dt_s)
    if carcaca is not None and ambiente is not None:
        delta = round(carcaca - ambiente, 2)
    else:
        delta = None
    emissor.criar("medicao.temperatura",
                  {"temp_carcaca": carcaca, "temp_ambiente": ambiente, "delta_t": delta},
                  motivo)
    invalido_temp = motivo is not None

    if delta is not None:
        temp_anterior, t_temp_anterior = (carcaca, ambiente), agora


def tratar_vibracao():
    global invalido_vib
    amplitude = pot.read() / 4095 * AMPLITUDE_MAX_G
    amostras, motivo = sensores.coletar_janela(mpu, amplitude, AMOSTRAS,
                                               PERIODO_AMOSTRA_MS, FREQ_ROTACAO_HZ)
    ind = sensores.calcular_indicadores(amostras) if amostras else None
    if ind is not None:
        motivo = sensores.validar_vibracao(ind)

    emissor.criar("medicao.vibracao", ind, motivo)
    invalido_vib = motivo is not None

    if motivo is None and operacao.atualizar(ind["rms_resultante"]):
        print("[OPERACAO] %s -> %s" % (operacao.anterior, operacao.estado))
        emissor.criar("maquina.mudanca_operacao",
                      {"estado": operacao.estado, "anterior": operacao.anterior,
                       "rms_resultante": ind["rms_resultante"]})


def atualizar_led(link):
    if link in ("OFFLINE", "BUFFER_CHEIO"):
        cor(VERMELHO)
    elif invalido_vib or invalido_temp:
        cor(MAGENTA)
    elif link == "PENDENTE":
        cor(AMARELO)
    else:
        cor(VERDE)


while True:
    agora = time.ticks_ms()

    if falha_simulada != falha_anterior:
        falha_anterior = falha_simulada
        print("[FALHA SIMULADA] %s" % ("enlace cortado" if falha_simulada else "enlace restabelecido"))

    if time.ticks_diff(agora, t_temp) >= CADENCIA_TEMP_MS:
        t_temp = agora
        term_carcaca.iniciar_conversao()
        term_ambiente.iniciar_conversao()
        conversao_desde = agora

    if conversao_desde is not None and time.ticks_diff(agora, conversao_desde) >= sensores.CONVERSAO_MS:
        conversao_desde = None
        tratar_temperatura()

    if time.ticks_diff(agora, t_vib) >= CADENCIA_VIB_MS:
        t_vib = agora
        tratar_vibracao()

    if falha_simulada:
        mqtt.derrubar()
    else:
        mqtt.manter()
    emissor.enviar_um(online=mqtt.conectado)

    link = emissor.estado_link()
    # em operacao normal EM_DIA <-> PENDENTE dura um ciclo so, nao vale log
    oscilacao = {link, link_anterior} == {"EM_DIA", "PENDENTE"} and not drenando
    if link != link_anterior and not oscilacao:
        print("[ENLACE] %s (pendentes=%d enviados=%d perdidos=%d invalidos=%d)"
              % (link, len(emissor.buffer), emissor.enviados, emissor.perdidos, emissor.invalidos))
    if link in ("OFFLINE", "BUFFER_CHEIO"):
        drenando = True
    elif link == "EM_DIA":
        drenando = False
    link_anterior = link
    atualizar_led(link)

    time.sleep_ms(LOOP_MS)
