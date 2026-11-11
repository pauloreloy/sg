# 08 — Plano de testes e operação

## 1. Estratégia de testes

### Testes unitários

Controller:
- Validação de payload.
- Geração e validação de `request_id`.
- Transições de estado.
- Tratamento de erro ao persistir e publicar.
- Idempotência da submissão e callback.

Serviço Databricks:
- Planner de operação.
- Validação de principal e recurso.
- Análise das permissões atuais.
- Decisão de privilégios a conceder/remover.
- Normalização de erros.
- Idempotência do workflow.

### Testes de contrato

- Cliente → API Gateway/Controller.
- Controller → SQS.
- SQS → Consumer.
- Serviço Databricks → callback Controller.
- Publisher → SNS HUB.

Validar compatibilidade de versões de mensagem e callback.

### Testes de integração

- Integração com DynamoDB em ambiente de teste.
- Publicação e consumo real de SQS.
- Integração com workspace Databricks não produtivo.
- Publicação SNS e validação do evento recebido.

### Testes ponta a ponta

Caminhos mínimos:
1. Grant bem-sucedido, verificando que o produtor recebeu `202` antes do processamento terminar.
2. Revoke bem-sucedido, verificando que o resultado final chega posteriormente por callback/notificação.
3. Requisição inválida rejeitada pelo Controller.
4. Resposta HTTP inicial não aguarda o Databricks, mesmo quando o processamento demora ou fica temporariamente indisponível.
5. Principal inexistente.
6. Recurso inexistente.
7. Falha de autorização no Unity Catalog.
8. Throttling/indisponibilidade temporária do Databricks.
9. Callback indisponível após execução.
10. Reentrega da mensagem SQS.
11. Falha na publicação SNS.

## 2. Testes de resiliência obrigatórios

| Cenário | Comportamento esperado |
|---|---|
| Controller falha após gravar `PENDING` e antes de publicar | Reconciliador identifica registro e tenta despachar |
| SQS aceita mensagem, mas Controller não grava `DISPATCHED` | Reenvio pode ocorrer; consumidor deduplica |
| Consumidor falha antes de executar | Mensagem volta após visibility timeout |
| Consumidor falha depois de aplicar Grant | Reentrega consulta estado atual e não duplica efeito |
| Databricks conclui, callback falha | Serviço tenta reenviar callback |
| Callback chega duas vezes | Controller aplica uma única transição efetiva |
| SNS aceita publicação, resposta se perde | Publisher pode repetir; consumidor deduplica por `event_id` |
| Mensagem excede tentativas | Vai para DLQ e gera alarme |

## 3. Testes de carga

Medir:
- Throughput de entrada do Controller.
- Latência de despacho.
- Tamanho e idade do backlog SQS.
- Tempo médio e percentis do workflow.
- Concorrência real suportada pelo Unity Catalog/workspace.
- CPU e memória por task ECS.
- Taxa de throttling e erros do Databricks.

Ajustar:
- Desired/min/max tasks do ECS.
- Concorrência máxima do event source/consumer.
- Batch size do consumo SQS.
- Visibility timeout.
- Limite global de chamadas simultâneas ao workspace.

Não escalar consumidores sem limite: a capacidade do workspace Databricks e os rate limits externos podem ser o gargalo.

## 4. Operação

### DLQ

Runbook mínimo:
1. Identificar mensagem e `request_id`.
2. Consultar estado global no DynamoDB.
3. Consultar logs usando `request_id` e `correlation_id`.
4. Identificar se houve efeito parcial no Unity Catalog.
5. Corrigir a causa.
6. Redrive controlado ou encerramento manual, conforme política.
7. Registrar decisão e evidência.

Nunca redrive em massa sem avaliar idempotência e efeitos já aplicados.

### Solicitações presas

Criar alarmes para:
- `PENDING` acima do tempo esperado.
- `DISPATCHED` sem início após janela definida.
- `RUNNING` acima do timeout operacional.
- Outbox pendente acima do SLA.
- Callback em retry por tempo excessivo.

A recuperação deve consultar o estado real antes de reenviar operações.

### Deploy

- Deploy gradual do ECS, com health checks.
- Compatibilidade retroativa entre versão do consumidor e versão da mensagem.
- Manter mensagens antigas processáveis durante rollout.
- Definir rollback da imagem e estratégia para mudanças de schema.
- Evitar mudanças incompatíveis de estado enquanto houver solicitações em andamento.

## 5. Runbooks a produzir

- Falha de consumo SQS.
- DLQ e redrive.
- Throttling/indisponibilidade Databricks.
- Falha de autenticação OAuth.
- Callback indisponível.
- Outbox/SNS parado.
- Solicitação em estado inconsistente.
- Reprocessamento seguro de Grant/Revoke.
