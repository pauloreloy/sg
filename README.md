# Share & Grant Databricks — Microserviços

Implementação dos microserviços assíncronos para concessão e revogação de permissões no Databricks Unity Catalog, baseada na arquitetura hexagonal e desacoplamento via mensageria.

---

## 🏛️ Visão Geral da Arquitetura

O ecossistema é composto por dois microserviços em **Python**:

1. **`share-grant-controller`**:
   - Desenvolvido em **FastAPI** / **Uvicorn** com **Arquitetura Hexagonal**.
   - API Gateway externo cuida da autenticação de entrada (sem necessidade de validação de token interna no controller).
   - Registra a solicitação inicial no **DynamoDB** (`dispatch_status = PENDING`).
   - Despacha mensagem para a fila **Amazon SQS** (`share-grant-requests-queue`).
   - Atualiza estado para `DISPATCHED` e responde imediatamente com HTTP `202 Accepted` + `request_id`.
   - Expõe endpoint de callback HTTP (`POST /share-grant/{request_id}/result`) para receber o resultado do processamento.
   - Registra o resultado e o evento no **Outbox** do DynamoDB em transação atômica (`transact_write_items`).
   - Publicador de Outbox em background publica eventos no **Amazon SNS HUB** (`share-grant-hub-topic`).
   - Reconciliador periódico recupera solicitações presas em `PENDING`.

2. **`analytics-share-grant-dbx-service`**:
   - Desenvolvido estritamente em **Arquitetura Hexagonal** (Domain, Application, Ports & Adapters, Bootstrap).
   - Inbound Adapter consome mensagens da fila SQS.
   - Use Cases coordenam o workflow interno de permissões (`PermissionWorkflow`).
   - Valida o principal e o recurso no Unity Catalog via Outbound Port.
   - Analisa permissões vigentes e calcula diff de privilégios para garantir idempotência.
   - Aplica alterações via `UnityCatalogAdapter` (suporta modo simulado em memória para dev/testes ou SDK Databricks real).
   - Envia callback HTTP com o resultado final para o Controller via `ControllerHttpAdapter`.

---

## ⚙️ Configuração LocalStack e AWS

Conforme requisito:
> Os serviços AWS utilizam **LocalStack** se a variável de ambiente `LOCALSTACK_ENDPOINT` ou `AWS_ENDPOINT_URL` estiver definida. Por padrão inicial, ela está definida como `http://localstack:4566` (no Docker) e `http://localhost:4566` (localmente).

Para utilizar a AWS real, basta remover ou definir a variável `LOCALSTACK_ENDPOINT=""`.

### Recursos provisionados no LocalStack (`localstack-init/01-init-aws.sh`):
- **SQS DLQ**: `share-grant-requests-dlq`
- **SQS Queue**: `share-grant-requests-queue` (com RedrivePolicy apontando para a DLQ)
- **SNS Topic**: `share-grant-hub-topic`
- **SQS Subscriber Queue**: `share-grant-sns-subscriber-queue` (inscrita no tópico SNS para validação)
- **DynamoDB Table**: `share-grant-requests` (PK: `request_id`, GSI: `idempotency_key-index`)
- **DynamoDB Table**: `share-grant-outbox` (PK: `event_id`, GSI: `status-created_at-index`)

---

## 🚀 Como Executar com Docker Compose

### 1. Iniciar todos os serviços
```bash
docker-compose up --build
```

Isso irá subir:
1. `share-grant-localstack`: porta `4566` (com init script automático para criar DynamoDB, SQS e SNS).
2. `share-grant-controller`: porta `8000` (FastAPI / Uvicorn).
3. `analytics-share-grant-dbx-service`: consumidor em background das mensagens SQS e executor Databricks.

### 2. Verificar a saúde dos serviços
```bash
curl http://localhost:8000/health
```

---

## 📬 Contratos e Exemplos de Uso

### Submeter Solicitação (Grant / Revoke)
```bash
curl -X POST http://localhost:8000/share-grant \
  -H "Content-Type: application/json" \
  -d '{
    "operation": "GRANT",
    "workspace_id": "workspace-123",
    "principal": {
      "type": "GROUP",
      "name": "analytics_readers"
    },
    "resource": {
      "type": "TABLE",
      "catalog": "shared",
      "schema": "sales",
      "name": "orders"
    },
    "requested_privileges": [
      "SELECT"
    ],
    "metadata": {
      "requested_by": "system-a",
      "correlation_id": "corr-123",
      "idempotency_key": "idemp-001"
    }
  }'
```

**Resposta imediata (HTTP 202 Accepted):**
```json
{
  "request_id": "req-9c48b2a1-...",
  "status": "ACCEPTED",
  "dispatch_status": "DISPATCHED"
}
```

### Consultar Status da Solicitação
```bash
curl http://localhost:8000/share-grant/<request_id>
```

**Resposta:**
```json
{
  "request_id": "req-9c48b2a1-...",
  "operation": "GRANT",
  "target": "DATABRICKS",
  "workspace_id": "workspace-123",
  "principal": {
    "type": "GROUP",
    "name": "analytics_readers"
  },
  "resource": {
    "type": "TABLE",
    "catalog": "shared",
    "schema": "sales",
    "name": "orders"
  },
  "requested_privileges": ["SELECT"],
  "dispatch_status": "DISPATCHED",
  "execution_status": "SUCCEEDED",
  "notification_status": "PUBLISHED",
  "created_at": "2026-11-10T22:00:00Z",
  "updated_at": "2026-11-10T22:00:05Z",
  "correlation_id": "corr-123",
  "result": {
    "operation": "GRANT",
    "resource": "shared.sales.orders",
    "principal": "analytics_readers",
    "applied_privileges": ["SELECT"]
  }
}
```

---

## 🧪 Como Executar os Testes

Com as dependências instaladas:
```bash
# Executar todos os testes (unitários e ponta a ponta)
PYTHONPATH="share-grant-controller:analytics-share-grant-dbx-service" pytest -v
```
