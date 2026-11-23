# Testes

Duas camadas de testes automatizados, mais verificações manuais do que não dá para automatizar (app no celular e nó no Wokwi).

| Camada | Onde | Ferramenta | Depende de |
|---|---|---|---|
| Unitários | `tests/consumidor`, `tests/publisher`, `dashboard/test`, `mobile/__tests__` | pytest, node:test + jsdom, jest-expo | nada (MQTT e banco simulados) |
| Integração | `tests/integracao` | pytest + Docker Compose | Docker: Mosquitto e TimescaleDB **reais**, consumidor como **processo real** |

## Como executar

```bash
# unitários (todos os componentes)
./scripts/test-all.sh

# só Python, unitários
pip install -r requirements-dev.txt
pytest

# integração (exige Docker; sobe e derruba o ambiente sozinho, ~3 min)
pytest -m integracao -v -rxs

# tudo
./scripts/test-all.sh --integracao
```

- O ambiente de integração está em [`tests/integracao/docker-compose.yml`](../tests/integracao/docker-compose.yml). Ele usa **os mesmos** `broker/mosquitto.conf`, `broker/acl` e `broker/passwd` da implantação, em portas deslocadas (MQTT `18830`, banco `15432`) para não colidir com o ambiente de desenvolvimento.
- Para inspecionar o ambiente depois da execução: `INTEGRACAO_MANTER=1 pytest -m integracao`, e depois `docker compose -p swifties-it down -v`.
- Sem Docker, os testes de integração são **pulados** (skip) com o motivo, e os unitários rodam normalmente.
- No CI ([`.github/workflows/tests.yml`](../.github/workflows/tests.yml)), cada push roda as quatro suítes. O job `integracao` publica o log e o relatório JUnit como artefato `evidencias-integracao`.
- Os testes de integração usam os tempos reais do consumidor (ciclo de 2 s, janela de 30 s, silêncio de 15 s), sem relógio simulado. Por isso levam alguns minutos.

## Verificações exigidas → testes de integração

| Verificação (Marco 4) | Teste | O que comprova |
|---|---|---|
| **Fluxo e contexto** | `test_fluxo.py::test_baseline_e_degradacao_ate_critico` | Dois fluxos produtores (vibração + temperatura) → consumidor aprende a baseline → degradação sustentada vira `CRITICO` em menos de 30 s, publicada no tópico do dashboard/app |
| | `test_fluxo.py::test_atencao_por_aumento_de_temperatura` | A combinação de informações (ΔT acima da baseline) gera `ATENCAO` |
| | `test_fluxo.py::test_mudanca_de_contexto_maquina_desligada` | **Mudança de contexto:** máquina `DESLIGADA` suspende o diagnóstico (`NAO_AVALIAVEL`) mesmo com vibração anômala; ao religar, a degradação volta a ser detectada |
| | `test_fluxo.py::test_pico_isolado_nao_gera_alarme` | Um pico isolado não gera `CRITICO` (RNF-03) |
| | `test_fluxo.py::test_eventos_invalidos_e_duplicados_nao_entram_na_decisao` | Eventos `INVALIDO` e duplicatas (mesmo `eventId`) não contam na janela |
| **Persistência** | `test_persistencia.py::test_esquema_temporal_criado` | Três hypertables, compressão e retenção nas medições, decisões sem retenção |
| | `test_persistencia.py::test_medicoes_e_decisoes_gravadas_e_recuperadas` | Medições válidas e decisões são gravadas e **recuperadas por SQL** com os valores e o `eventTime` publicados. Inválidos não são gravados e decisões só entram quando mudam |
| | `test_persistencia.py::test_dados_preservados_apos_reiniciar_o_banco` | Os dados continuam idênticos após `docker compose restart timescaledb` |
| | `test_persistencia.py::test_dados_preservados_apos_reiniciar_o_consumidor_sem_duplicar` | O consumidor reinicia e os mesmos eventos são reenviados: a chave única do banco impede duplicatas |
| **Segurança** | `test_seguranca.py::test_identidade_invalida_rejeitada[*]`, `test_cliente_anonimo_rejeitado` | **Rejeição de identidade inválida:** senha errada, senha vazia, usuário inexistente e cliente anônimo são recusados no CONNACK |
| | `test_seguranca.py::test_no_publica_apenas_no_proprio_topico` | **Operação fora da permissão:** `esp32-07` autenticado não consegue publicar como `esp32-99`. O evento forjado não chega ao broker nem ao consumidor, e há controle positivo no próprio tópico |
| | `test_seguranca.py::test_consumidor_nao_publica_eventos_de_campo`, `test_consumidor_nao_publica_fora_do_seu_prefixo` | A credencial do hub não injeta medições nem status de campo |
| | `test_seguranca.py::test_no_nao_le_decisoes` | O nó só escreve: assinar `consumidor/#` não entrega nada (com controle positivo via `admin`) |
| | `test_seguranca.py::test_canal_criptografado_tls` | **PENDENTE (xfail estrito):** o broker ainda não tem listener TLS. Quando o TLS for implementado, este teste passa a falhar como XPASS e deve virar teste normal |
| **Falha e recuperação** | `test_falha.py::test_banco_fora_hub_segue_decidindo_e_grava_ao_voltar` | Com o TimescaleDB parado, o hub continua decidindo (`CRITICO` publicado). Quando o banco volta, a fila em memória é gravada sem perda |
| | `test_falha.py::test_broker_fora_consumidor_reconecta_e_volta_a_decidir` | Com o Mosquitto parado, o consumidor não cai. Quando o broker volta, ele reconecta, reassina e decide sobre um ativo novo |
| | `test_falha.py::test_silencio_do_no_vira_sem_comunicacao_e_recupera` | 15 s sem eventos → `SEM_COMUNICACAO`. Quando os eventos voltam, o estado sai de `SEM_COMUNICACAO` |

## Rastreabilidade: requisitos → testes

Requisitos de [`requisitos.md`](requisitos.md). "U" = unitário, "I" = integração.

| Requisito | Testes |
|---|---|
| RF-01 Indicadores de vibração | U `tests/publisher/test_sensores.py` (RMS, curtose, frequência, remoção do DC) |
| RF-02 Temperatura e ΔT | U `tests/publisher/test_sensores.py` (DS18B20, leitura, conversão) |
| RF-03 Validação por faixa | U `test_sensores.py` (`test_invalidos`, `test_fora_de_faixa`, `test_salto`, …) · I `test_fluxo.py::test_eventos_invalidos_e_duplicados_…` |
| RF-04 Ligada/desligada | U `tests/publisher/test_estado_operacao.py` (histerese, persistência) |
| RF-05 Publicação e buffer | U `tests/publisher/test_evento.py` (FIFO, buffer cheio, falha mantém no buffer, last will) · I `test_fluxo.py` |
| RF-06 Autenticação e ACL | I `test_seguranca.py` |
| RF-07 Deduplicação | U `tests/consumidor/test_consumidor.py::…test_duplicado_descartado` · I `test_fluxo.py::test_eventos_invalidos_e_duplicados_…`, `test_persistencia.py::…sem_duplicar` |
| RF-08 Linha de base | U `test_consumidor.py::…test_primeira_janela_vira_baseline` · I `test_fluxo.py::test_baseline_e_degradacao_ate_critico` |
| RF-09 Classificação | U `test_consumidor.py` (`test_normal`, `test_atencao_*`, `test_critico_*`) · I `test_fluxo.py` |
| RF-10 Sem comunicação e desligada | U `test_consumidor.py` (`test_silencio_prolongado`, `test_desligada_nao_avaliavel`) · I `test_falha.py::test_silencio_…`, `test_fluxo.py::test_mudanca_de_contexto_…` |
| RF-11 Cards, gráfico e histórico | U `dashboard/test/dashboard.test.js` · `mobile/__tests__/AtivoCard.test.tsx`, `Sparkline.test.tsx`, `App.test.tsx` |
| RF-12 Vibração no celular | U `mobile/__tests__/useMqtt.test.tsx`, `App.test.tsx` (desligar alertas impede a vibração) |
| RF-13 Configuração no app | U `mobile/__tests__/Settings.test.tsx`, `App.test.tsx` (salvar persiste e reconecta) |
| RF-14 Gravação no TimescaleDB | U `tests/consumidor/test_db.py` · I `test_persistencia.py` |
| RNF-01 Latência ≤ 30 s | I `test_fluxo.py::test_baseline_e_degradacao_ate_critico` (mede o tempo) |
| RNF-02 Sem perda no enlace | U `tests/publisher/test_evento.py` (buffer/reenvio) · manual M2 |
| RNF-03 Pico isolado não alarma | U `test_consumidor.py::…test_rms_alto_sozinho_nao_e_critico`, `test_estado_operacao.py::test_pico_isolado_…` · I `test_fluxo.py::test_pico_isolado_…` |
| RNF-04 Só indicadores | Inspeção do contrato v1 (`publisher/README.md`): nenhum campo de sinal bruto |
| RNF-05 Segurança | I `test_seguranca.py` (TLS pendente, xfail) |
| RNF-06 Implantação por Compose | I o ambiente de integração sobe com `docker compose` · manual M4 |
| RNF-07 Banco fora não para a decisão | U `test_db.py::test_fila_cheia_descarta_o_mais_antigo` · I `test_falha.py::test_banco_fora_…` |
| RNF-08 Retenção e compressão | I `test_persistencia.py::test_esquema_temporal_criado` |

## Verificações manuais

Complementam o que depende de celular ou do simulador. Preencher "Observado" e "Evidência" (print, trecho de log ou minuto do vídeo) a cada versão demonstrada.

| # | Verificação | Passos / entradas | Esperado | Observado | Evidência |
|---|---|---|---|---|---|
| M1 | App no celular recebe a decisão | Subir broker e consumidor. `python consumidor/ferramentas/mock_publisher.py --cenario critico`. App aberto, com o IP do broker configurado | O card do ativo fica Crítico e o celular vibra | | |
| M2 | Store-and-forward do nó (Wokwi) | Pressionar o botão do ESP32 (corta o enlace), aguardar 20 s e pressionar de novo | `OFFLINE` no broker, LED vermelho, depois `ONLINE` e os eventos atrasados chegam em ordem de `sequence` com o `eventTime` original | | |
| M3 | App trata falha de comunicação | Com o app aberto, `docker compose stop mosquitto` em `broker/`, depois `start` | O app mostra o estado offline/erro e se reconecta sozinho | | |
| M4 | Implantação do zero | Seguir os READMEs de `broker/`, `consumidor/` e `mobile/` numa máquina limpa | Todos os componentes sobem e o fluxo M1 funciona | | |

## Evidências

- Unitários (execução local): [`evidencias/testes/unitarios.log`](evidencias/testes/unitarios.log) e [`unitarios.xml`](evidencias/testes/unitarios.xml).
- Integração: gerar com o comando abaixo e versionar em `docs/evidencias/testes/` a cada versão demonstrada. Cada execução do CI também publica o log e o JUnit como artefato `evidencias-integracao` (aba Actions → execução → Artifacts).

  ```bash
  pytest -m integracao -v -rxs --junitxml=docs/evidencias/testes/integracao.xml | tee docs/evidencias/testes/integracao.log
  ```
