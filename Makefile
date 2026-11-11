.PHONY: test test-controller test-dbx test-e2e up down build logs

test:
	@echo "=== Running Controller Tests ==="
	PYTHONPATH="share-grant-controller" pytest share-grant-controller/tests -v
	@echo "\n=== Running Databricks Service Tests ==="
	PYTHONPATH="analytics-share-grant-dbx-service" pytest analytics-share-grant-dbx-service/tests -v
	@echo "\n=== Running End-to-End Integration Tests ==="
	pytest tests/e2e -v

test-controller:
	PYTHONPATH="share-grant-controller" pytest share-grant-controller/tests -v

test-dbx:
	PYTHONPATH="analytics-share-grant-dbx-service" pytest analytics-share-grant-dbx-service/tests -v

test-e2e:
	pytest tests/e2e -v

up:
	docker-compose up --build

down:
	docker-compose down -v

logs:
	docker-compose logs -f
