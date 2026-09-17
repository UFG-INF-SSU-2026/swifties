# Nó produtor — ESP32 (MicroPython, Wokwi)

Mede vibração e temperatura de um motor, valida as leituras, detecta máquina ligada/desligada e publica eventos (contrato v1) via MQTT. Guarda eventos em buffer quando o enlace cai e reenvia ao restabelecer.

## Executar
1. Subir o broker (`../broker/README.md`) e copiar o endereço público do ngrok.
2. Novo projeto no Wokwi: **ESP32 · MicroPython**.
3. Substituir `diagram.json` e `main.py`; criar `sensores.py` e `evento.py`.
4. Em `main.py`, ajustar `MQTT_HOST` e `MQTT_PORTA` com o endereço do ngrok.
5. Iniciar a simulação. Na máquina local: `docker compose exec mosquitto mosquitto_sub -t 'swifties/#' -v`.

## Arquivos
| Arquivo | Responsabilidade |
|---|---|
| `main.py` | configuração, laço principal, botão, LED, estado operacional |
| `sensores.py` | MPU6050, DS18B20, janela de vibração, indicadores, validação |
| `evento.py` | contrato v1, buffer store-and-forward, conexão MQTT |

## Montagem
| Componente | Pino | Papel |
|---|---|---|
| MPU6050 | 21 (SDA) / 22 (SCL) | vibração |
| DS18B20 carcaça | 18 | temperatura da carcaça |
| DS18B20 ambiente | 19 | temperatura ambiente |
| Potenciômetro | 34 | amplitude da vibração sintética |
| Botão | 4 | cortar / restabelecer enlace (simulado) |
| LED RGB + 3× 220 Ω | 25 / 26 / 27 | estado do nó |

Cada DS18B20 fica em um barramento próprio: evita depender da ordem de varredura do 1-Wire.

## Funcionamento
| A cada | O quê |
|---|---|
| 2 s | converte temperaturas; lê 750 ms depois (sem bloquear) → `medicao.temperatura` |
| 5 s | janela de 64 amostras a ~100 Hz → indicadores → `medicao.vibracao`; se o estado operacional mudar → `maquina.mudanca_operacao` |
| 50 ms | mantém a conexão MQTT, publica **um** evento do buffer (mais antigo primeiro), atualiza LED |

**Vibração.** Cada amostra = leitura real do MPU6050 + `A·sin(2π·29,6·t)` no eixo X + ruído, com `A = pot/4095 × 4 g`. Da janela: `rms_x/y/z`, `rms_resultante` (gravidade removida pela média), `pico`, `curtose` e `freq_dominante` (cruzamentos de zero com histerese).

**Estado operacional.** `LIGADA` se `rms_resultante ≥ 0,20 g`; `DESLIGADA` se `< 0,10 g`; entre os dois mantém o estado (histerese). A mudança só vale após **2 janelas** consecutivas. A classificação NORMAL/ATENÇÃO/CRÍTICO é do consumidor.

## Validação
| Fluxo | `INVALIDO` quando (`motivo`) |
|---|---|
| Vibração | MPU6050 não responde (`mpu_sem_resposta`) · magnitude real fora de 0,05–8 g (`mpu_fora_de_faixa`) · `pico < rms_resultante` · RMS > 50 g · curtose fora de 1–50 |
| Temperatura | sensor ausente · fora de −10–150 °C · ambiente ≥ carcaça + 5 °C · variação > 5 °C/min em relação à leitura anterior (`salto_de_temperatura`) |

Evento inválido **é publicado** com `quality: "INVALIDO"` e `motivo` — o consumidor conta a falha; nada some em silêncio.

## Contrato v1
```json
{
  "schemaVersion": 1,
  "eventId": "esp32-07-1789612330-3",
  "eventType": "medicao.vibracao",
  "deviceId": "esp32-07",
  "entityId": "motor-linha3-02",
  "sequence": 3,
  "eventTime": "2026-09-17T02:32:15Z",
  "quality": "VALIDO",
  "motivo": null,
  "data": { "rms_x": 1.379, "rms_y": 0.011, "rms_z": 0.012, "rms_resultante": 1.379,
            "pico": 1.97, "curtose": 1.5, "freq_dominante": 29.4 }
}
```
| `eventType` | `data` |
|---|---|
| `medicao.vibracao` | `rms_x`, `rms_y`, `rms_z`, `rms_resultante`, `pico` (g), `curtose`, `freq_dominante` (Hz) |
| `medicao.temperatura` | `temp_carcaca`, `temp_ambiente`, `delta_t` (°C) |
| `maquina.mudanca_operacao` | `estado`, `anterior`, `rms_resultante` |

- `eventId = deviceId-bootId-sequence`; `bootId` = horário NTP no boot → único mesmo após reinício (chave de deduplicação).
- `eventTime` em UTC (NTP). Se o evento for do buffer, `eventTime` é o da medição, não o do envio.
- Com medição inválida, `data` pode ser `null`.

## MQTT
| Tópico | Conteúdo | QoS | Retido |
|---|---|---|---|
| `swifties/esp32-07/medicao/vibracao` | evento `medicao.vibracao` | 1 | não |
| `swifties/esp32-07/medicao/temperatura` | evento `medicao.temperatura` | 1 | não |
| `swifties/esp32-07/maquina/mudanca_operacao` | evento `maquina.mudanca_operacao` | 1 | não |
| `swifties/esp32-07/status` | `ONLINE` ao conectar · `OFFLINE` (last will) | 1 | sim |

- Tópico = `swifties/<deviceId>/` + `eventType` com `.` trocado por `/`. O consumidor assina `swifties/#`.
- **QoS 1:** o nó espera o PUBACK do broker (timeout 5 s). Sem PUBACK, o evento continua no buffer e é reenviado — o consumidor pode receber repetição e deduplica por `eventId`.
- **Last will:** se a conexão cair sem DISCONNECT (queda real ou botão), o broker publica `OFFLINE` em nome do nó. O silêncio fica visível.
- **Reconexão:** nova tentativa a cada 5 s.
- Sem autenticação e sem TLS (protótipo).

## Buffer e enlace
Lista de até 100 eventos. Cheia → descarta o mais antigo e conta `perdidos`. Um evento só sai do buffer após o PUBACK.

| LED | Significado |
|---|---|
| azul | inicializando |
| verde | em dia |
| amarelo | drenando buffer |
| vermelho | desconectado ou buffer cheio |
| magenta | última leitura inválida |

## Roteiro de demonstração
1. **Máquina ligada:** pot em ~50% → após 2 janelas, `[OPERACAO] DESCONHECIDO -> LIGADA`.
2. **Desligar:** pot em 0 → após ~10 s, evento `maquina.mudanca_operacao` com `DESLIGADA`.
3. **Falha de enlace (simulada):** botão → socket fechado sem DISCONNECT → `OFFLINE` aparece no `mosquitto_sub`, LED vermelho, `[BUFFER]` a cada evento. Botão de novo → `ONLINE`, LED amarelo, eventos atrasados chegam em ordem de `sequence` com `eventTime` original.
4. **Falha real do broker:** `docker compose stop mosquitto` → `[MQTT] envio falhou`, tentativas a cada 5 s; `docker compose start mosquitto` → reconecta e drena o buffer.
5. **Sensor solto:** alterar bruscamente o DS18B20 da carcaça → um evento `INVALIDO / salto_de_temperatura`, LED magenta; a leitura seguinte já é válida.
6. **Acelerômetro com defeito:** zerar os três eixos do MPU6050 → `INVALIDO / mpu_fora_de_faixa`.

## Limitações declaradas
- A vibração é **sintetizada** sobre a leitura real: o Wokwi só oferece valores estáticos no MPU6050. O processamento é real; o fenômeno, não.
- A janela de vibração bloqueia o laço por ~0,64 s a cada 5 s (o botão usa interrupção e não é perdido).
- `freq_dominante` por cruzamentos de zero tem resolução de ~0,8 Hz; a curtose de uma senoide pura é 1,5, então a curtose só varia com ruído.
- Buffer em RAM: reiniciar o ESP32 perde os eventos pendentes.
- QoS 1 confirma só a entrega ao broker, não que o consumidor validou ou processou o evento.
- O publish QoS 1 bloqueia o laço até o PUBACK (pelo túnel, tipicamente centenas de ms).
- O endereço do ngrok gratuito muda a cada reinício: é preciso atualizar `main.py`.
