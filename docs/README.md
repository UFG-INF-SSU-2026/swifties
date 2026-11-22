# Documentação

Documentação de requisitos e de arquitetura do sistema de **manutenção preditiva de ativos industriais** (Sistemas Ubíquos).

| Documento | Conteúdo |
|---|---|
| [`requisitos.md`](requisitos.md) | Requisitos funcionais, não funcionais e de interface, requisitos planejados da arquitetura-alvo, matriz de rastreabilidade e limitações conhecidas. |
| [`arquitetura/`](arquitetura/README.md) | Modelo de visões **4+1**: |
| ↳ [Cenários (+1)](arquitetura/01-cenarios.md) | casos de uso e 7 cenários que atravessam as visões |
| ↳ [Visão lógica](arquitetura/02-visao-logica.md) | modelo de domínio, estado de saúde do ativo, estados do nó |
| ↳ [Visão de processo](arquitetura/03-visao-processo.md) | fluxo nominal, queda de enlace, pipeline do hub, laço do nó |
| ↳ [Visão de desenvolvimento](arquitetura/04-visao-desenvolvimento.md) | componentes do repositório, interfaces MQTT, configuração |
| ↳ [Visão física](arquitetura/05-visao-fisica.md) | implantação do protótipo e da arquitetura-alvo |

## Documentos relacionados (fora desta pasta)

- [`../README.md`](../README.md): Atividade 01, compreensão do problema e modelagem.
- [`../atv02.md`](../atv02.md): Atividade 02, eventos, processamento temporal e distribuição.
- [`../Diagrama.png`](../Diagrama.png): esboço original da arquitetura.
- READMEs dos componentes: [`publisher`](../publisher/README.md), [`broker`](../broker/README.md), [`consumidor`](../consumidor/README.md), [`dashboard`](../dashboard/README.md).

## Como ler

1. Para entender **o que** o sistema faz, comece pelos [cenários](arquitetura/01-cenarios.md) e pela §3 de [`requisitos.md`](requisitos.md).
2. Para entender **como**, siga a ordem lógica → processo → desenvolvimento → física.
3. Para saber **o que falta** para produção, veja §6 e §8 de [`requisitos.md`](requisitos.md) e a seção "Do protótipo à produção" da [visão física](arquitetura/05-visao-fisica.md#do-protótipo-à-produção).

Os diagramas são PlantUML. Para regenerá-los, veja [`arquitetura/README.md`](arquitetura/README.md#diagramas).
