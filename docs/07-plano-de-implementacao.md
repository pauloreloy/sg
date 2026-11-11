# 07 — Plano de implementação

## 1. Estratégia

Implementar de forma incremental, validando primeiro o caminho ponta a ponta e depois aprofundando confiabilidade, segurança e operação. Evitar antecipar a separação do workflow Databricks em vários serviços.

## 2. Fases

### Fase 0 — Fechamento de decisões

Entregáveis:
- Contrato final da API de submissão.
- Contrato final da mensagem SQS.
- Contrato do callback.
- Definição de autenticação entre serviços.
- Definição de tabela DynamoDB, filas, DLQ e SNS topic.
- Definição de estados e SLA.
- Matriz de operações/privilégios/recurso do Unity Catalog.

Critério de saída:
- Contratos revisados pelos donos do Controller, Databricks e plataforma.

### Fase 1 — Infraestrutura base

Entregáveis:
- API Gateway e integração com Controller.
- ECS Cluster/Service/Task Definition do Controller.
- DynamoDB.
- SQS e DLQ.
- SNS HUB ou integração com o tópico existente.
- IAM Roles e Security Groups.
- Secrets Manager para credenciais Databricks.
- Logs, métricas e alarmes básicos.

Critério de saída:
- Recursos provisionados por IaC e pipeline executável em ambiente não produtivo.

### Fase 2 — Controller: submissão e despacho

Entregáveis:
- Endpoint `POST /share-grant`.
- Validação do payload.
- Geração de `request_id`.
- Persistência inicial `PENDING`.
- Publicação na SQS.
- Atualização `DISPATCHED`.
- Resposta HTTP `202 Accepted` imediata após confirmação de despacho, sem aguardar o serviço Databricks.
- Tratamento de falhas e logs correlacionados.

Critério de saída:
- Teste integrado comprova submissão, persistência, mensagem na fila e resposta `202` antes da conclusão do processamento Databricks.
- Teste comprova que a conexão HTTP do produtor não depende do callback.
- Testes cobrem falha entre persistência e envio/atualização.

### Fase 3 — Serviço Databricks: estrutura hexagonal

Entregáveis:
- Estrutura de pacotes.
- Domain e DTOs.
- Inbound Port e use case de processamento.
- SQS Consumer.
- Unity Catalog outbound Port e adapter.
- Configuração OAuth.
- Bootstrap e health checks.

Critério de saída:
- Serviço consome mensagem em ambiente de desenvolvimento e chama o adapter Databricks por meio do Port.

### Fase 4 — Workflow Grant/Revoke

Entregáveis:
- Planner de operação.
- Validação de principal e recurso.
- Leitura de permissões atuais.
- Aplicação de privilégios necessários.
- Regras de Grant e Revoke.
- Normalização de erros.
- Idempotência.
- Testes unitários e integração com workspace de teste.

Critério de saída:
- Grant/Revoke executam conforme matriz de privilégios aprovada.
- Reentrega da mesma mensagem não causa efeitos indevidos.

### Fase 5 — Callback e conclusão

Entregáveis:
- Outbound Port do Controller.
- HTTP adapter de callback.
- Endpoint autenticado no Controller.
- Atualização do estado global.
- Registro do evento final.
- Publisher SNS com Outbox (recomendado).
- Deduplicação de callback e evento.

Critério de saída:
- Sucesso e falha no Databricks chegam ao SNS HUB com correlação e sem perda silenciosa de evento.

### Fase 6 — Resiliência e operação

Entregáveis:
- DLQ e processo operacional de redrive.
- Reconciliador de solicitações presas em `PENDING`.
- Retry de callback.
- Retry de Outbox.
- Alarmes e dashboards.
- Runbooks.
- Testes de carga e falha.

Critério de saída:
- Cenários de falha conhecidos são detectados, recuperáveis e auditáveis.

### Fase 7 — Produção e estabilização

Entregáveis:
- Deploy controlado.
- Testes smoke.
- Validação de alarmes.
- Acompanhamento de backlog e latência.
- Ajuste de concorrência ECS/SQS conforme limites do workspace Databricks.
- Revisão pós-implantação.

Critério de saída:
- Operação estável dentro do SLA e dos limites de capacidade acordados.

## 3. Backlog técnico inicial

| Prioridade | Item | Componente |
|---|---|---|
| P0 | Definir contrato de submissão | API / Controller |
| P0 | Definir estados e persistência | Controller / DynamoDB |
| P0 | Criar fila e DLQ | SQS |
| P0 | Implementar publicação e consumo | Controller / Databricks |
| P0 | Implementar Ports e adapters | Databricks |
| P0 | Implementar Grant/Revoke | Databricks |
| P0 | Implementar callback autenticado | Databricks / Controller |
| P0 | Implementar idempotência | Todos |
| P1 | Outbox SNS | Controller |
| P1 | Reconciliador de dispatch | Controller |
| P1 | Retry de callback | Databricks |
| P1 | Dashboards e alarmes | Plataforma |
| P1 | Testes de carga | Plataforma / Databricks |
| P2 | Consulta de status | Controller / API |
| P2 | Workflow distribuído por etapa | Evolução futura |

## 4. Critérios gerais de pronto

- Contratos versionados.
- Testes unitários e de integração aprovados.
- Lint, formatter e análise estática no CI.
- Imagem de container com scan de vulnerabilidade.
- IAM de menor privilégio.
- Segredos fora do código e da imagem.
- Logs estruturados e correlação ponta a ponta.
- DLQ, alarmes e runbooks disponíveis.
- Idempotência comprovada por testes.
- Deploy e rollback documentados.
