# Requisitos

**Escopo:** monitorar a vibração e a temperatura de máquinas rotativas, decidir o estado de saúde de cada ativo num hub local e exibir esse estado em tempo real. Esta é a versão protótipo: ESP32 simulado no Wokwi, broker Mosquitto, consumidor Python, dashboard web, app mobile e TimescaleDB na nuvem.

## Requisitos funcionais

| ID | Requisito | Componente |
|---|---|---|
| RF-01 | Medir vibração triaxial a cada 5 s e calcular RMS, pico, curtose e frequência dominante. | Nó |
| RF-02 | Medir temperatura da carcaça e ambiente a cada 2 s e calcular ΔT. | Nó |
| RF-03 | Validar as leituras por faixa física e marcar as inválidas (`quality: INVALIDO`). | Nó |
| RF-04 | Detectar se a máquina está ligada ou desligada pelo nível de vibração. | Nó |
| RF-05 | Publicar os eventos por MQTT, guardando-os em buffer enquanto o enlace estiver fora. | Nó |
| RF-06 | Autenticar clientes e restringir os tópicos de cada um (ACL). | Broker |
| RF-07 | Descartar eventos duplicados. | Consumidor |
| RF-08 | Aprender a linha de base de cada ativo na primeira janela válida. | Consumidor |
| RF-09 | A cada 2 s, classificar o ativo em `NORMAL`, `ATENCAO` ou `CRITICO` com base numa janela de 30 s. | Consumidor |
| RF-10 | Sinalizar `SEM_COMUNICACAO` após 15 s sem eventos e não avaliar máquina desligada. | Consumidor |
| RF-11 | Exibir um card por ativo com estado (cor), métricas, gráfico e histórico de mudanças. | Dashboard, App |
| RF-12 | Vibrar o celular quando um ativo entrar em `CRITICO`, com opção de desativar. | App |
| RF-13 | Permitir configurar o endereço e as credenciais do broker no app, salvos no aparelho. | App |
| RF-14 | Gravar no TimescaleDB as medições válidas e cada mudança de decisão, sem duplicar registros. | Consumidor |

## Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | **Latência:** uma degradação sustentada deve aparecer no dashboard e no app em até 30 s. |
| RNF-02 | **Confiabilidade:** quedas de enlace não podem perder eventos (dentro da capacidade do buffer, 100 eventos). |
| RNF-03 | **Robustez:** um pico isolado não pode gerar alarme; o estado crítico exige confirmação por um segundo indicador. |
| RNF-04 | **Eficiência:** o nó envia só indicadores calculados, nunca o sinal bruto. |
| RNF-05 | **Segurança:** todo cliente se autentica e só acessa os tópicos de que precisa. |
| RNF-06 | **Implantação:** cada componente sobe com `docker compose up`. |
| RNF-07 | **Disponibilidade:** a falha do banco não pode interromper a decisão; as gravações ficam numa fila (até 5000 itens) e são retentadas a cada 5 s. |
| RNF-08 | **Armazenamento:** medições guardadas por 1 ano e comprimidas após 7 dias; decisões guardadas sem limite. |

## Limitações do protótipo

- A vibração é sintetizada no Wokwi a partir da posição do acelerômetro.
- Não há TLS: as senhas trafegam em texto claro.
- O dashboard e o app leem as decisões direto do broker e ainda não consultam o histórico do banco.
- Se o consumidor reiniciar com o banco fora do ar, a fila em memória se perde.
- O app só funciona com o celular na mesma rede local do broker.
