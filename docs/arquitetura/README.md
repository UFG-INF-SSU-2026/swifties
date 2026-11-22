# Arquitetura — Modelo de visões 4+1

Documentação arquitetural do sistema de manutenção preditiva segundo o modelo **4+1** de Kruchten: quatro visões complementares (lógica, processo, desenvolvimento e física), amarradas por um conjunto de cenários (+1) que mostra como elas colaboram.

```
              Visão lógica  ◄────────►  Visão de desenvolvimento
          (o que o sistema faz)         (como o código se organiza)
                        ▲     Cenários (+1)     ▲
                        │  (casos de uso que    │
                        │   validam as visões)  │
                        ▼                       ▼
            Visão de processo ◄────────►  Visão física
       (concorrência, tempo, falhas)      (onde cada parte roda)
```

| Visão | Pergunta que responde | Público principal | Diagramas |
|---|---|---|---|
| [**Cenários (+1)**](01-cenarios.md) | Para que serve e como se usa? | Todos | Casos de uso; 7 cenários |
| [**Lógica**](02-visao-logica.md) | Quais conceitos e estados existem? | Analistas, desenvolvedores | Classes; 2 máquinas de estado |
| [**Processo**](03-visao-processo.md) | Como as partes conversam no tempo e sob falha? | Integradores, testes | 2 sequências; 3 atividades |
| [**Desenvolvimento**](04-visao-desenvolvimento.md) | Como o repositório está organizado? | Desenvolvedores | Componentes |
| [**Física**](05-visao-fisica.md) | Onde cada parte executa? | Implantação, infraestrutura | Implantação do protótipo e da arquitetura-alvo |

## Escopo: protótipo × arquitetura-alvo

As visões descrevem o **protótipo como construído** neste repositório:

```
ESP32 (Wokwi) → ngrok → Mosquitto → consumidor Python → dashboard web
```

Onde a arquitetura-alvo de [`README.md`](../../README.md) e [`atv02.md`](../../atv02.md) difere, isso é dito explicitamente: TLS, nuvem, comando do LED pelo hub e marca d'água. A visão física tem um diagrama separado para a implantação-alvo.

## Decisões arquiteturais transversais

| Decisão | Motivo | Visões afetadas |
|---|---|---|
| **Decisão na névoa (hub local), não na nuvem** | O LED precisa refletir o estado em segundos, e o link de internet da planta é o elo menos confiável. | Física, Processo |
| **Indicadores calculados no nó** | 3,2 kHz × 3 eixos ≈ 1,4 MB/min por nó; enviar indicadores reduz o tráfego em ~3 ordens de grandeza e poupa o rádio. | Lógica, Física |
| **MQTT com QoS 1 + deduplicação por `eventId`** | Entrega "pelo menos uma vez" sem perder eventos; a idempotência no hub absorve as duplicatas. | Processo |
| **Store-and-forward no nó + last will** | Queda de enlace não perde dados e o silêncio fica visível. | Processo, Lógica |
| **Tempo do evento nas janelas** | Rajadas de eventos reenviados após uma queda não criam tendência falsa. | Processo |
| **Regra de degradação sustentada** | Uma leitura alta isolada (partida, impacto) não dispara alarme; exige-se persistência e confirmação. | Lógica |
| **Parâmetros, não constantes** | O mesmo código serve a bancada (USB, cadência alta) e o campo (bateria, cadência baixa). | Desenvolvimento |

## Requisitos

Os requisitos estão em [`../requisitos.md`](../requisitos.md). A §7 de lá rastreia cada requisito até a visão e o cenário correspondentes.

## Diagramas

As fontes PlantUML ficam em [`diagramas/`](diagramas/) e as imagens renderizadas em [`diagramas/svg/`](diagramas/svg/). Todas incluem [`diagramas/_estilo.iuml`](diagramas/_estilo.iuml), que define o estilo e usa o layout **Smetana** embutido no PlantUML, então não é preciso instalar o Graphviz.

Para regenerar as imagens depois de editar um `.puml` (requer Java 8+):

```bash
cd docs/arquitetura/diagramas
curl -sSLo /tmp/plantuml.jar \
  https://repo1.maven.org/maven2/net/sourceforge/plantuml/plantuml/1.2024.7/plantuml-1.2024.7.jar
java -jar /tmp/plantuml.jar -tsvg -o svg *.puml
```

Também funciona com a extensão PlantUML do VS Code ou com `docker run --rm -v "$PWD":/data plantuml/plantuml -tsvg -o svg /data/*.puml`.
