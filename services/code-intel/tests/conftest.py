"""Test fixtures — settings come from env vars set here, not real config."""

import os

TEST_ENV = {
    "CI_DATABASE_URL": "postgres://codeintel_service:codeintel_dev_password@localhost:5432/devmind",
    "CI_REDIS_URL": "redis://localhost:6379",
    "CI_QDRANT_URL": "http://localhost:6333",
    "CI_NEO4J_URL": "bolt://localhost:7687",
    "CI_NEO4J_PASSWORD": "devmind_dev_neo4j",
    "CI_S3_ENDPOINT": "http://localhost:9000",
    "CI_S3_ACCESS_KEY": "devmind",
    "CI_S3_SECRET_KEY": "devmind_dev_minio",
    "CI_INTERNAL_SERVICE_TOKEN": "test-internal-token",
    "API_BASE_URL": "http://localhost:4000",
}

for key, value in TEST_ENV.items():
    os.environ.setdefault(key, value)
