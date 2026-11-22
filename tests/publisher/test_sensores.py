import math

import pytest

from conftest import carregar

s = carregar("publisher_sensores", "publisher/sensores.py")


def senoide(amp=1.0, hz=10.0, n=200, fs=200.0, base=(0.0, 0.0, 1.0)):
    return [(i / fs, base[0] + amp * math.sin(2 * math.pi * hz * i / fs), base[1], base[2])
            for i in range(n)]


class FakeI2C:
    def __init__(self, bruto=None, falha=False):
        self.bruto, self.falha, self.escritas = bruto, falha, []

    def writeto_mem(self, addr, reg, dado):
        if self.falha:
            raise OSError
        self.escritas.append((addr, reg, dado))

    def readfrom_mem(self, addr, reg, n):
        if self.falha:
            raise OSError
        return self.bruto


def bruto_g(ax, ay, az):
    out = b""
    for g in (ax, ay, az):
        v = int(round(g * s.LSB_POR_G)) & 0xFFFF
        out += bytes([v >> 8, v & 0xFF])
    return out


class TestMPU:
    def test_int16_sinal(self):
        assert s._int16(0x00, 0x01) == 1
        assert s._int16(0xFF, 0xFF) == -1
        assert s._int16(0x80, 0x00) == -32768

    def test_iniciar(self):
        i2c = FakeI2C()
        m = s.MPU6050(i2c)
        assert m.iniciar() and m.ok
        assert (s.MPU_ADDR, s.REG_PWR_MGMT_1, b"\x00") in i2c.escritas

    def test_iniciar_falha(self):
        assert s.MPU6050(FakeI2C(falha=True)).iniciar() is False

    def test_ler_g(self):
        m = s.MPU6050(FakeI2C(bruto_g(0.5, -0.25, 1.0)))
        ax, ay, az = m.ler_g()
        assert (ax, ay, az) == pytest.approx((0.5, -0.25, 1.0), abs=1e-3)

    def test_ler_g_com_falha_marca_nao_ok(self):
        i2c = FakeI2C(bruto_g(0, 0, 1))
        m = s.MPU6050(i2c)
        m.iniciar()
        i2c.falha = True
        assert m.ler_g() is None and m.ok is False

    def test_ler_g_reinicia_se_nao_ok(self):
        assert s.MPU6050(FakeI2C(falha=True)).ler_g() is None


class TestIndicadores:
    def test_senoide_pura(self):
        ind = s.calcular_indicadores(senoide(amp=1.0))
        assert ind["rms_x"] == pytest.approx(1 / math.sqrt(2), abs=0.02)
        assert ind["rms_y"] == 0 and ind["rms_z"] == 0
        assert ind["rms_resultante"] == pytest.approx(ind["rms_x"], abs=1e-3)
        assert ind["pico"] == pytest.approx(1.0, abs=0.02)
        assert ind["curtose"] == pytest.approx(1.5, abs=0.1)   # curtose da senoide
        assert ind["freq_dominante"] == pytest.approx(10.0, abs=1.0)

    def test_remove_componente_dc(self):
        ind = s.calcular_indicadores(senoide(amp=0.5, base=(0, 0, 1.0)))
        assert ind["rms_z"] == 0     # a gravidade não conta como vibração

    def test_sinal_constante(self):
        a = [(i * 0.01, 0.0, 0.0, 1.0) for i in range(10)]
        ind = s.calcular_indicadores(a)
        assert ind["rms_resultante"] == 0 and ind["curtose"] == 0.0

    def test_curtose_constante_zero(self):
        assert s._curtose([0.0] * 5) == 0.0

    def test_frequencia_ignora_ruido_abaixo_da_histerese(self):
        sinal = [0.01, -0.01] * 50
        assert s._frequencia_cruzamentos(sinal, 1.0) == 0

    def test_frequencia_duracao_zero(self):
        assert s._frequencia_cruzamentos([1, -1, 1], 0) == 0.0


class TestValidacaoVibracao:
    base = {"rms_resultante": 1.0, "pico": 2.0, "curtose": 3.0}

    def test_valido(self):
        assert s.validar_vibracao(self.base) is None

    @pytest.mark.parametrize("mud,motivo", [
        ({"pico": 0.5}, "pico_menor_que_rms"),
        ({"rms_resultante": 60.0, "pico": 70.0}, "rms_fora_de_faixa"),
        ({"curtose": 0.5}, "curtose_fora_de_faixa"),
        ({"curtose": 80.0}, "curtose_fora_de_faixa"),
    ])
    def test_invalidos(self, mud, motivo):
        assert s.validar_vibracao({**self.base, **mud}) == motivo


class TestValidacaoTemperatura:
    def test_valida(self):
        assert s.validar_temperatura(60.0, 25.0, None, 2) is None

    def test_sensores_ausentes(self):
        assert s.validar_temperatura(None, 25, None, 2) == "sensor_carcaca_ausente"
        assert s.validar_temperatura(60, None, None, 2) == "sensor_ambiente_ausente"

    def test_fora_de_faixa(self):
        assert s.validar_temperatura(200, 25, None, 2) == "temperatura_fora_de_faixa"
        assert s.validar_temperatura(60, -50, None, 2) == "temperatura_fora_de_faixa"

    def test_ambiente_maior_que_carcaca(self):
        assert s.validar_temperatura(25, 40, None, 2) == "ambiente_maior_que_carcaca"

    def test_salto(self):
        # 5 °C/min * 2 s / 60 = ~0,17 °C permitidos
        assert s.validar_temperatura(61.0, 25.0, (60.0, 25.0), 2) == "salto_de_temperatura"
        assert s.validar_temperatura(60.1, 25.0, (60.0, 25.0), 2) is None

    def test_sem_dt_nao_valida_salto(self):
        assert s.validar_temperatura(90, 25, (60, 25), 0) is None


class TestJanela:
    def mpu(self, leituras):
        it = iter(leituras)

        class M:
            def ler_g(self_):
                return next(it, None)
        return M()

    def test_mpu_sem_resposta(self):
        amostras, motivo = s.coletar_janela(self.mpu([None]), 4, 10, 30)
        assert amostras is None and motivo == "mpu_sem_resposta"

    def test_fora_de_faixa(self):
        amostras, motivo = s.coletar_janela(self.mpu([(0, 0, 20.0)]), 4, 10, 30)
        assert motivo == "mpu_fora_de_faixa"

    def test_repouso_sem_vibracao_simulada(self):
        amostras, motivo = s.coletar_janela(self.mpu([(0.0, 0.0, 1.0)] * 20), 20, 10, 30)
        assert motivo is None and len(amostras) == 20
        # zona morta: só ruído (<= 0,02 g) sobre o repouso
        assert all(abs(a[1]) <= s.RUIDO_G + 1e-9 for a in amostras)

    def test_deslocamento_gera_oscilacao(self, monkeypatch):
        t = [0]
        monkeypatch.setattr(s.time, "ticks_us", lambda: t.__setitem__(0, t[0] + 10000) or t[0])
        amostras, _ = s.coletar_janela(self.mpu([(1.0, 0.0, 1.0)] * 64), 64, 10, 30)
        ax = [a[1] for a in amostras]
        assert max(ax) - min(ax) > 1.0

    def test_deslocamento_zona_morta_e_limite(self):
        assert s._deslocamento(0.0, 0.0, 1.0)[0] == 0.0
        amp, u = s._deslocamento(10.0, 0.0, 1.0)
        assert amp == s.AMPLITUDE_MAX_G and u[0] == pytest.approx(1.0, abs=0.01)


class FakeTermometro:
    """Injeta um DS18X20 falso no construtor."""
    def __init__(self, monkeypatch, roms=(b"r",), temp=25.123, erro=None):
        import sys, types
        self.convertidas = 0
        outer = self

        class DS:
            def __init__(self, ow): pass
            def scan(self): return list(roms)
            def convert_temp(self):
                outer.convertidas += 1
                if erro: raise erro
            def read_temp(self, rom):
                if erro: raise erro
                return temp
        monkeypatch.setitem(sys.modules, "onewire", types.SimpleNamespace(OneWire=lambda p: None))
        monkeypatch.setitem(sys.modules, "ds18x20", types.SimpleNamespace(DS18X20=DS))


class TestTermometro:
    def test_leitura_arredondada(self, monkeypatch):
        FakeTermometro(monkeypatch)
        t = s.Termometro(18)
        t.iniciar_conversao()
        assert t.ler() == 25.12

    def test_sem_sensor_no_barramento(self, monkeypatch):
        FakeTermometro(monkeypatch, roms=())
        t = s.Termometro(18)
        t.iniciar_conversao()
        assert t.rom is None and t.ler() is None

    def test_erro_na_leitura_zera_rom(self, monkeypatch):
        FakeTermometro(monkeypatch, erro=OSError())
        t = s.Termometro(18)
        t.rom = b"r"
        assert t.ler() is None and t.rom is None

    def test_erro_na_conversao(self, monkeypatch):
        FakeTermometro(monkeypatch, erro=OSError())
        t = s.Termometro(18)
        t.iniciar_conversao()
        assert t.rom is None
