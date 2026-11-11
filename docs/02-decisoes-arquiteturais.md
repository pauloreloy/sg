# 02 — Decisões arquiteturais (ADRs)

Este documento registra decisões da baseline. Cada ADR deve ser revisado quando houver mudança relevante de requisito, volume, custo ou operação.

## ADR-001 — Processamento assíncrono via SQS

**Status:** Adotado.

**Contexto:** A API pode receber rajadas de solicitações e o processamento no Unity Catalog não precisa ocorrer durante a conexão HTTP inicial.

**Decisão:** O Controller registra a solicitação e publica uma mensagem na SQS. Após a confirmação de envio e atualização do estado de despacho, responde ao produtor com HTTP 202 Accepted. O ECS Databricks consome e processa a mensagem de forma independente.

**Consequências:**
- A API responde sem aguardar o processamento Databricks, retornando `202 Accepted` e um identificador de solicitação após a aceitação e confirmação do despacho à SQS.
- A SQS absorve picos e desacopla produtores de consumidores.
- O processamento é eventualmente consistente.
- O consumidor deve ser idempotente, pois SQS Standard oferece entrega pelo menos uma vez.

## ADR-002 — Controller como coordenador do fluxo global

**Status:** Adotado.

**Decisão:** O Controller é responsável pelo recebimento, validação de entrada, registro global, despacho, callback, estado final e publicação no SNS HUB.

**Não é responsabilidade do Controller:**
- Executar operações no Unity Catalog.
- Implementar regras de Grant/Revoke.
- Coordenar cada etapa interna do workflow Databricks.
- Conhecer detalhes do SDK Databricks.

**Consequência:** O Controller conhece os contratos dos serviços de domínio, mas não suas regras internas.

## ADR-003 — Um único ECS Databricks na primeira versão

**Status:** Adotado para a versão inicial.

**Contexto:** As etapas internas podem crescer, mas ainda não há evidência de que precisem de deploy, escala ou ciclo de vida independentes.

**Decisão:** Implementar um único serviço ECS Fargate com workflow interno que planeja e executa as etapas necessárias.

**Consequências:**
- Menor complexidade operacional inicial.
- Menos filas e menos componentes distribuídos.
- A aplicação deve manter as etapas desacopladas internamente para permitir extração futura.
- Não criar um orquestrador distribuído antes de existir necessidade concreta.

## ADR-004 — Arquitetura hexagonal no serviço Databricks

**Status:** Adotado.

**Decisão:** Organizar o serviço em Domain, Application, Ports, Adapters e Infrastructure/Bootstrap.

**Regras:**
- Ports são definidos pela camada Application quando representam necessidades dos casos de uso.
- Adapters inbound dependem dos contratos de entrada da aplicação.
- Adapters outbound implementam Ports outbound definidos pela aplicação.
- Application depende do Domain e de abstrações, não de SDKs concretos.
- Domain não depende de Application, Adapters ou infraestrutura.
- `bootstrap.py` compõe as implementações concretas com os casos de uso.

## ADR-005 — Callback HTTP para o resultado

**Status:** Adotado.

**Decisão:** O serviço Databricks envia o resultado final ao Controller por HTTP callback, em uma interação posterior e independente da resposta HTTP original ao produtor.

**Consequências:**
- O Controller centraliza o estado global e as notificações. O callback não mantém aberta nem conclui a requisição HTTP original do produtor; é uma nova requisição serviço-a-serviço.
- O serviço Databricks não precisa publicar diretamente no SNS HUB.
- O callback deve ser autenticado, idempotente e correlacionado por `request_id`.
- Falhas no callback precisam de retry e/ou mecanismo de recuperação.

## ADR-006 — DynamoDB como estado global da solicitação

**Status:** Adotado.

**Decisão:** O Controller mantém o estado global no DynamoDB.

**Consequências:**
- Atualizações devem usar condições para proteger transições.
- Estado global não deve ser confundido com o estado detalhado de cada etapa interna.
- Se futuramente houver execução distribuída por etapa, o orquestrador Databricks poderá manter estado operacional próprio.

## ADR-007 — Publicação final via Outbox

**Status:** Recomendado; confirmar na implementação.

**Contexto:** Atualizar o DynamoDB e publicar no SNS não é uma operação atômica.

**Decisão recomendada:** Gravar o estado final e um item Outbox na mesma transação DynamoDB; um publisher separado lê a Outbox, publica no SNS e marca o item como publicado.

**Consequências:**
- Evita perder a intenção de notificar após uma falha entre persistência e publicação.
- Pode haver publicação duplicada em cenários de timeout ambíguo.
- Consumidores devem deduplicar por `event_id`.

## ADR-008 — Sem garantia exactly-once

**Status:** Adotado.

**Decisão:** Projetar para entrega pelo menos uma vez e efeitos idempotentes.

**Consequências:**
- `request_id` identifica a solicitação.
- `event_id` identifica o evento de resultado.
- Operações no Unity Catalog devem consultar estado atual antes de alterar quando necessário.
- Atualizações do Controller devem ser condicionais.
- Reentregas não podem conceder ou revogar permissões indevidamente.

## ADR-009 — Evolução futura para workflow distribuído

**Status:** Futuro / não implementar inicialmente.

**Gatilhos possíveis:**
- Etapas precisam escalar independentemente.
- Etapas precisam de deploy independente.
- Existem diferentes perfis de recurso ou duração.
- Retomada por etapa e visibilidade granular tornam-se requisitos.
- A coordenação interna passa a limitar throughput ou confiabilidade.

**Direção futura:** Orquestrador Databricks recebe o trabalho, atualiza o estado das etapas e publica nas filas dos workers. Workers reportam resultado ao orquestrador; não escolhem diretamente a próxima etapa.
