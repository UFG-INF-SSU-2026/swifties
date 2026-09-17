import math, time, random

MPU_ADDR = 0x68
REG_PWR_MGMT_1 = 0x6B
REG_ACCEL_CFG = 0x1C
REG_ACCEL_XOUT_H = 0x3B
LSB_POR_G = 4096.0

RUIDO_G = 0.02
HISTERESE_CRUZAMENTO_G = 0.05

MAG_MIN_G, MAG_MAX_G = 0.05, 8.0
RMS_MAX_G = 50.0
CURTOSE_MIN, CURTOSE_MAX = 1.0, 50.0
TEMP_MIN_C, TEMP_MAX_C = -10.0, 150.0
TAXA_MAX_C_POR_MIN = 5.0

CONVERSAO_MS = 750


def _int16(alto, baixo):
    v = (alto << 8) | baixo
    if v > 32767:
        v = v - 65536
    return v


class MPU6050:
    def __init__(self, i2c):
        self.i2c = i2c
        self.ok = False

    def iniciar(self):
        try:
            self.i2c.writeto_mem(MPU_ADDR, REG_PWR_MGMT_1, b"\x00")
            self.i2c.writeto_mem(MPU_ADDR, REG_ACCEL_CFG, b"\x10")
            self.ok = True
        except OSError:
            self.ok = False
        return self.ok

    def ler_g(self):
        if not self.ok and not self.iniciar():
            return None
        try:
            b = self.i2c.readfrom_mem(MPU_ADDR, REG_ACCEL_XOUT_H, 6)
        except OSError:
            self.ok = False
            return None
        ax = _int16(b[0], b[1]) / LSB_POR_G
        ay = _int16(b[2], b[3]) / LSB_POR_G
        az = _int16(b[4], b[5]) / LSB_POR_G
        return (ax, ay, az)


def _ruido():
    return (random.getrandbits(10) / 1023 - 0.5) * 2 * RUIDO_G


def coletar_janela(mpu, amplitude_g, n, periodo_ms, freq_hz):
    amostras = []
    t0 = time.ticks_us()
    for i in range(n):
        espera = time.ticks_diff(time.ticks_add(t0, i * periodo_ms * 1000), time.ticks_us())
        if espera > 0:
            time.sleep_us(espera)

        leitura = mpu.ler_g()
        t = time.ticks_diff(time.ticks_us(), t0) / 1000000
        if leitura is None:
            return None, "mpu_sem_resposta"

        ax, ay, az = leitura
        mag = math.sqrt(ax * ax + ay * ay + az * az)
        if not (MAG_MIN_G < mag < MAG_MAX_G):
            return None, "mpu_fora_de_faixa"

        # senoide do desbalanceamento no eixo X + ruido nos tres eixos
        ax += amplitude_g * math.sin(2 * math.pi * freq_hz * t) + _ruido()
        ay += _ruido()
        az += _ruido()
        amostras.append((t, ax, ay, az))
    return amostras, None


def _curtose(sinal):
    n = len(sinal)
    m2 = sum(x * x for x in sinal) / n
    if m2 < 1e-12:
        return 0.0
    m4 = sum(x ** 4 for x in sinal) / n
    return m4 / (m2 * m2)


def _frequencia_cruzamentos(sinal, duracao_s):
    estado = 0
    cruzamentos = 0
    for x in sinal:
        if x > HISTERESE_CRUZAMENTO_G:
            novo = 1
        elif x < -HISTERESE_CRUZAMENTO_G:
            novo = -1
        else:
            continue
        if estado and novo != estado:
            cruzamentos += 1
        estado = novo
    if duracao_s <= 0:
        return 0.0
    return cruzamentos / (2 * duracao_s)


def calcular_indicadores(amostras):
    n = len(amostras)
    eixos = []
    for k in (1, 2, 3):
        media = sum(a[k] for a in amostras) / n
        eixos.append([a[k] - media for a in amostras])
    rms = [math.sqrt(sum(x * x for x in e) / n) for e in eixos]
    dx, dy, dz = eixos

    rms_resultante = math.sqrt(rms[0] ** 2 + rms[1] ** 2 + rms[2] ** 2)
    pico = max(math.sqrt(dx[i] ** 2 + dy[i] ** 2 + dz[i] ** 2) for i in range(n))
    dominante = eixos[rms.index(max(rms))]
    duracao = amostras[-1][0] - amostras[0][0]

    return {
        "rms_x": round(rms[0], 3),
        "rms_y": round(rms[1], 3),
        "rms_z": round(rms[2], 3),
        "rms_resultante": round(rms_resultante, 3),
        "pico": round(pico, 3),
        "curtose": round(_curtose(dominante), 2),
        "freq_dominante": round(_frequencia_cruzamentos(dominante, duracao), 1),
    }


def validar_vibracao(ind):
    if ind["pico"] < ind["rms_resultante"]:
        return "pico_menor_que_rms"
    if ind["rms_resultante"] > RMS_MAX_G:
        return "rms_fora_de_faixa"
    if not (CURTOSE_MIN <= ind["curtose"] <= CURTOSE_MAX):
        return "curtose_fora_de_faixa"
    return None


class Termometro:
    def __init__(self, pin):
        import onewire, ds18x20
        self.sensor = ds18x20.DS18X20(onewire.OneWire(pin))
        self.rom = None

    def iniciar_conversao(self):
        try:
            if self.rom is None:
                roms = self.sensor.scan()
                self.rom = roms[0] if roms else None
            if self.rom is not None:
                self.sensor.convert_temp()
        except Exception:
            self.rom = None

    def ler(self):
        if self.rom is None:
            return None
        try:
            t = self.sensor.read_temp(self.rom)
        except Exception:
            self.rom = None
            return None
        if t is None:
            return None
        return round(t, 2)


def validar_temperatura(carcaca, ambiente, anterior, dt_s):
    if carcaca is None:
        return "sensor_carcaca_ausente"
    if ambiente is None:
        return "sensor_ambiente_ausente"
    for t in (carcaca, ambiente):
        if not (TEMP_MIN_C <= t <= TEMP_MAX_C):
            return "temperatura_fora_de_faixa"
    if ambiente >= carcaca + 5:
        return "ambiente_maior_que_carcaca"
    if anterior is not None and dt_s > 0:
        limite = TAXA_MAX_C_POR_MIN * dt_s / 60
        if abs(carcaca - anterior[0]) > limite or abs(ambiente - anterior[1]) > limite:
            return "salto_de_temperatura"
    return None
