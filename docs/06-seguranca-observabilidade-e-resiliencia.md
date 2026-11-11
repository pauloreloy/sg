# 06 — Segurança, observabilidade e resiliência

## 1. Segurança

### Identidades e permissões IAM

Aplicar menor privilégio por componente:
- API Gateway: permissões necessárias para invocar o backend.
- Controller Task Role: acesso à tabela DynamoDB, publicação na fila SQS e publicação no SNS (ou invocação do publisher).
- Databricks Task Role: consumo da fila SQS, acesso a segredos/configuração necessários e conectividade ao endpoint de callback.
- Publisher Role: leitura/atualização da Outbox e publicação no SNS.
- Reconciliador Role: consulta e atualização somente dos registros que precisa recuperar.

Evitar compartilhar uma única Task Role ampla entre todos os serviços.

### Credenciais Databricks

- Usar OAuth/service principal conforme padrão suportado pelo workspace.
- Armazenar `client_secret` em AWS Secrets Manager ou solução corporativa equivalente.
- Não gravar segredo em imagem Docker, código, variáveis versionadas ou logs.
- Definir rotação e política de acesso.
- Preferir injeção segura no runtime e limitar a exposição do segredo ao processo que precisa dele.

### Proteção de rede

- Avaliar subnets privadas para ECS.
- Restringir Security Groups por origem/destino e porta.
- Definir conectividade de saída necessária ao workspace Databricks e aos serviços AWS.
- Usar VPC endpoints para serviços AWS quando aplicável.
- TLS para tráfego HTTP e callback.
- Avaliar WAF, throttling e autenticação no API Gateway.

## 2. Observabilidade

### Logs estruturados

Campos recomendados:
- `timestamp`
- `level`
- `service`
- `request_id`
- `correlation_id`
- `event_id`
- `operation`
- `workspace_id` (se não for dado sensível segundo a política interna)
- `resource_type`
- `step`
- `attempt`
- `duration_ms`
- `error_code`

Não registrar:
- Client secrets, access tokens ou headers de autorização.
- Payloads sensíveis sem necessidade.
- Dados pessoais além do mínimo necessário.

### Métricas

Controller:
- Solicitações recebidas e rejeitadas.
- Falhas de validação.
- Tempo entre recebimento e despacho.
- Quantidade de itens `PENDING` antigos.
- Falhas de callback.
- Itens de Outbox pendentes e idade do mais antigo.

SQS:
- `ApproximateNumberOfMessagesVisible`.
- `ApproximateNumberOfMessagesNotVisible`.
- `ApproximateAgeOfOldestMessage`.
- Mensagens enviadas/recebidas/deletadas.
- Mensagens encaminhadas à DLQ.

ECS Databricks:
- Tasks em execução.
- CPU e memória.
- Mensagens processadas, sucesso e falha.
- Duração do workflow.
- Latência e throttling do Databricks API.
- Retries por tipo de erro.

### Rastreamento

Propagar `correlation_id` e `request_id` entre API, Controller, mensagem SQS, serviço Databricks, callback e evento SNS. Avaliar AWS X-Ray ou OpenTelemetry conforme padrão da plataforma.

## 3. Resiliência e retentativas

### SQS

- Configurar visibility timeout compatível com o tempo máximo esperado de processamento.
- Para processamentos longos, estender a visibilidade periodicamente ou definir estratégia que evite reentrega concorrente.
- Configurar `maxReceiveCount` e DLQ.
- Usar backoff com jitter para erros transitórios.
- Não repetir erros permanentes de validação ou autorização sem alteração da condição.

### Idempotência do consumidor

O processamento pode ser entregue mais de uma vez. O serviço deve:
- Identificar a execução por `request_id`.
- Consultar o estado atual das permissões antes de aplicar alterações.
- Evitar duplicar efeitos.
- Registrar resultado e tentativa.
- Não considerar o recebimento da mensagem como prova de que a execução ainda não ocorreu.

### Callback

- Retry com backoff para falhas transitórias.
- Callback idempotente por `event_id`/`request_id`.
- Definir limite de tentativas e mecanismo de recuperação.
- Se o resultado foi concluído no Databricks mas o callback falhou, manter informação suficiente para reenviar o resultado.

### Controller e SQS

DynamoDB e SQS não compartilham transação. Uma falha após o envio e antes da atualização `DISPATCHED` pode resultar em reenvio pelo reconciliador. O consumidor idempotente é obrigatório.

### SNS e Outbox

A publicação SNS pode ter resultado ambíguo em caso de timeout. O publisher pode repetir e produzir duplicidade. Incluir `event_id` e exigir deduplicação nos consumidores quando o efeito duplicado for relevante.

## 4. Alertas iniciais

- DLQ com uma ou mais mensagens.
- Mensagem mais antiga acima do limite operacional.
- Solicitação em `PENDING` além do SLA.
- Solicitação em `RUNNING` por tempo excessivo.
- Crescimento de falhas ou throttling do Databricks.
- Callback sem sucesso após número definido de tentativas.
- Outbox pendente acima do SLA.
- ECS sem tasks saudáveis.

Os thresholds devem ser definidos com base em métricas reais e SLAs, não apenas em valores arbitrários.
