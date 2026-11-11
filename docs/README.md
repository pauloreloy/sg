# Share & Grant Databricks — Pacote de Arquitetura

Este pacote documenta a arquitetura de referência do fluxo de **Grant/Revoke de permissões no Databricks Unity Catalog**, conforme o diagrama aprovado.

## Conteúdo

| Arquivo | Objetivo |
|---|---|
| `01-visao-geral-arquitetura.md` | Contexto, escopo, componentes e fluxo ponta a ponta |
| `02-decisoes-arquiteturais.md` | ADRs e decisões técnicas adotadas |
| `03-controller-api-e-integracao.md` | Contratos de entrada, callback e integração |
| `04-modelo-de-dados-e-estados.md` | Modelo lógico no DynamoDB e ciclo de vida |
| `05-servico-databricks-arquitetura-hexagonal.md` | Estrutura interna, Ports & Adapters e responsabilidades |
| `06-seguranca-observabilidade-e-resiliencia.md` | IAM, segredos, logs, métricas, retries e idempotência |
| `07-plano-de-implementacao.md` | Fases, entregáveis e critérios de aceite |
| `08-plano-de-testes-e-operacao.md` | Estratégia de testes, deploy e operação |

## Premissas importantes

1. O **Controller** é responsável pelo estado global da solicitação, despacho para a fila e publicação do resultado no SNS.
2. O **serviço Databricks** é responsável pelo processamento de negócio e pelo workflow interno de Grant/Revoke.
3. A comunicação de entrada no serviço Databricks ocorre por **SQS**.
4. O retorno do serviço Databricks ao Controller ocorre por **HTTP callback**. O serviço não publica diretamente na SQS original nem no SNS HUB.
5. O DynamoDB guarda o estado global da solicitação. Persistência detalhada das etapas internas só deve ser adicionada se houver necessidade real de retomada, auditoria ou execução distribuída.
6. A arquitetura inicial utiliza um único serviço ECS Fargate Databricks. A separação futura em workers independentes é uma evolução, não um requisito inicial.

## Como utilizar

- Trate os documentos como uma **baseline arquitetural**, não como especificação final de todos os detalhes de implementação.
- Itens marcados como **A definir** precisam de decisão antes da entrada em produção.
- Ajuste nomes de filas, tabelas, endpoints, atributos e parâmetros de infraestrutura ao padrão do ambiente AWS.
