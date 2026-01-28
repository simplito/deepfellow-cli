# DeepFellow Software Framework.
# Copyright © 2026 Simplito sp. z o.o.
#
# This file is part of the DeepFellow Software Framework (https://deepfellow.ai).
# This software is Licensed under the DeepFellow Free License.
#
# See the License for the specific language governing permissions and
# limitations under the License.

"""Default config values."""

from pathlib import Path
from typing import Any

DF_DEEPFELLOW_DIRECTORY = Path.home() / ".deepfellow"

DF_CLI_CONFIG_PATH = DF_DEEPFELLOW_DIRECTORY / "config"  # env style config file
DF_CLI_SECRETS_PATH = DF_DEEPFELLOW_DIRECTORY / "secrets"  # env style secrets file

DF_INFRA_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "infra"
DF_INFRA_REPO = "ssh://git@github.com/simplito/deepfellow-infra.git"
DF_INFRA_IMAGE_HUB = "hub.simplito.com/deepfellow/deepfellow-infra"
DF_INFRA_IMAGE = f"{DF_INFRA_IMAGE_HUB}:latest"
DF_INFRA_PORT = 8086
DF_INFRA_URL = f"http://infra:{DF_INFRA_PORT}"
DF_INFRA_DOCKER_NETWORK = "deepfellow-infra-net"
DF_INFRA_STORAGE_DIR = DF_INFRA_DIRECTORY / "storage"
DF_INFRA_NAME = "infra"

DF_SERVER_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "server"
DF_SERVER_REPO = "ssh://git@github.com/simplito/deepfellow-server.git"
DF_SERVER_IMAGE_HUB = "hub.simplito.com/deepfellow/deepfellow-server"
DF_SERVER_IMAGE = f"{DF_SERVER_IMAGE_HUB}:latest"
DF_SERVER_PORT = 8000
DF_OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4317"
# NOTE: uploaded files, used by vector stores
DF_SERVER_STORAGE_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / DF_SERVER_DIRECTORY / "storage"

DF_MONGO_URL = "mongo:27017"
DF_MONGO_USER = "deepfellow-usr"
DF_MONGO_PASSWORD = "some-fake-password"
DF_MONGO_DB = "deepfellow"

API_ENDPOINTS = {"openai": {"url": "https://api.openai.com", "api_key": "some-fake-key", "name": "openai"}}

DF_VECTOR_DATABASE_URL = "http://milvus:19530"
VECTOR_DATABASE: dict[str, Any] = {
    "provider": {
        "active": 1,
        "type": "milvus",
        "url": DF_VECTOR_DATABASE_URL,
        "db": "deepfellow",
        "user": "deepfellow_usr",
        "password": "some-fake-password",
    },
    "embedding": {"active": 1, "endpoint": "openai", "model": "mxbai-embed-large", "size": "1024"},
}
DF_ADMIN_KEY = "some-admin-key"


DOCKER_COMPOSE_INFRA = {
    DF_INFRA_NAME: {
        "image": "${DF_INFRA_IMAGE}",
        "ports": ["${DF_INFRA_PORT}:8086"],
        "environment": [
            "DF_NAME=${DF_NAME}",
            "DF_INFRA_ADMIN_API_KEY=${DF_INFRA_ADMIN_API_KEY}",
            "DF_INFRA_API_KEY=${DF_INFRA_API_KEY}",
            "DF_INFRA_URL=${DF_INFRA_URL}",
            "DF_MESH_KEY=${DF_MESH_KEY}",
            "DF_CONNECT_TO_MESH_URL=${DF_CONNECT_TO_MESH_URL}",
            "DF_CONNECT_TO_MESH_KEY=${DF_CONNECT_TO_MESH_KEY}",
            "DF_DOCKER_SUBNET=${DF_INFRA_DOCKER_SUBNET}",
            "DF_COMPOSE_PREFIX=${DF_INFRA_COMPOSE_PREFIX}",
            "DF_HUGGING_FACE_API_KEY=${DF_HUGGING_FACE_API_KEY}",
            "DF_CIVITAI_TOKEN=${DF_CIVITAI_TOKEN}",
            "DF_STORAGE_DIR=${DF_INFRA_STORAGE_DIR}",
            "DOCKER_HOST=unix:///var/run/docker.sock",
        ],
        "restart": "unless-stopped",
        "volumes": [
            "${DF_INFRA_DOCKER_CONFIG}:/root/.docker/config.json:ro",
        ],
    },
}

DOCKER_COMPOSE_SERVER = {
    "server": {
        "container_name": "server",
        "image": "${DF_SERVER_IMAGE}",
        "ports": ["${DF_SERVER_PORT}:8000"],
        "environment": [
            "DF_MONGO_URL=${DF_MONGO_URL}",
            "DF_MONGO_USER=${DF_MONGO_USER}",
            "DF_MONGO_PASSWORD=${DF_MONGO_PASSWORD}",
            "DF_MONGO_DB=${DF_MONGO_DB}",
            "DF_VECTOR_DATABASE__PROVIDER__ACTIVE=${DF_VECTOR_DATABASE__PROVIDER__ACTIVE}",
            "DF_VECTOR_DATABASE__PROVIDER__TYPE=${DF_VECTOR_DATABASE__PROVIDER__TYPE}",
            "DF_VECTOR_DATABASE__PROVIDER__URL=${DF_VECTOR_DATABASE__PROVIDER__URL}",
            "DF_VECTOR_DATABASE__PROVIDER__DB=${DF_VECTOR_DATABASE__PROVIDER__DB}",
            "DF_VECTOR_DATABASE__PROVIDER__USER=${DF_VECTOR_DATABASE__PROVIDER__USER}",
            "DF_VECTOR_DATABASE__PROVIDER__PASSWORD=${DF_VECTOR_DATABASE__PROVIDER__PASSWORD}",
            "DF_VECTOR_DATABASE__EMBEDDING__ACTIVE=${DF_VECTOR_DATABASE__EMBEDDING__ACTIVE}",
            "DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT=${DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT}",
            "DF_VECTOR_DATABASE__EMBEDDING__MODEL=${DF_VECTOR_DATABASE__EMBEDDING__MODEL}",
            "DF_VECTOR_DATABASE__EMBEDDING__SIZE=${DF_VECTOR_DATABASE__EMBEDDING__SIZE}",
        ],
        "restart": "unless-stopped",
        "healthcheck": {
            "test": ["CMD", "/app/scripts/healthcheck.py"],
            "interval": "30s",
            "timeout": "5s",
            "retries": 3,
            "start_period": "40s",
        },
    }
}

DOCKER_COMPOSE_VECTOR_DB = {
    "etcd": {
        "container_name": "etcd",
        "image": "quay.io/coreos/etcd:v3.5.18",
        "environment": [
            "ETCD_AUTO_COMPACTION_MODE=revision",
            "ETCD_AUTO_COMPACTION_RETENTION=1000",
            "ETCD_QUOTA_BACKEND_BYTES=4294967296",
            "ETCD_SNAPSHOT_COUNT=50000",
        ],
        "ports": ["2379:2379"],
        "volumes": ["etcd:/etcd"],
        "command": (
            "etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd"
        ),
        "healthcheck": {
            "test": ["CMD", "etcdctl", "endpoint", "health"],
            "interval": "30s",
            "timeout": "20s",
            "retries": 3,
        },
    },
    "minio": {
        "container_name": "minio",
        "image": "minio/minio:RELEASE.2024-12-18T13-15-44Z",
        "environment": [
            "MINIO_ACCESS_KEY=minioadmin",
            "MINIO_SECRET_KEY=minioadmin",
        ],
        "ports": ["9001:9001", "9000:9000"],
        "volumes": ["minio:/minio_data"],
        "command": 'minio server /minio_data --console-address ":9001"',
        "healthcheck": {
            "test": "curl -f http://localhost:9000/minio/health/live",
            "interval": "30s",
            "timeout": "20s",
            "retries": 3,
        },
    },
    "milvus": {
        "container_name": "milvus",
        "image": "milvusdb/milvus:v2.6.2",
        "command": "milvus run standalone",
        "security_opt": ["seccomp:unconfined"],
        "environment": [
            "ETCD_ENDPOINTS=etcd:2379",
            "MINIO_ADDRESS=minio:9000",
            "MQ_TYPE=woodpecker",
        ],
        "volumes": ["milvus:/var/lib/milvus"],
        "healthcheck": {
            "test": "curl -f http://localhost:9091/healthz",
            "interval": "30s",
            "start_period": "90s",
            "timeout": "20s",
            "retries": 3,
        },
        "ports": ["19530:19530", "9091:9091"],
        "depends_on": ["etcd", "minio"],
    },
}

DOCKER_COMPOSE_MONGO_DB = {
    "mongo": {
        "container_name": "mongo",
        "image": "mongo:8",
        "restart": "always",
        "expose": ["27017"],
        "ports": ["27017:27017"],
        "volumes": ["mongo:/data/db"],
        "environment": [
            "MONGO_INITDB_ROOT_USERNAME=${DF_MONGO_USER}",
            "MONGO_INITDB_ROOT_PASSWORD=${DF_MONGO_PASSWORD}",
        ],
        "healthcheck": {
            "test": "mongosh --eval 'db.runCommand(\"ping\")'",
            "interval": "10s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "5s",
        },
    }
}

DEFAULT_OTEL_URL = "http://otel-collector:4317"

DOCKER_COMPOSE_OTEL_COLLECTOR = {
    "otel-collector": {
        "container_name": "otel-collector",
        "image": "otel/opentelemetry-collector-contrib:0.133.0",
        "volumes": ["./otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml"],
        "ports": [
            "1888:1888",  # pprof extension
            "8888:8888",  # Prometheus metrics exposed by the Collector
            "8889:8889",  # Prometheus exporter metrics
            "13133:13133",  # health_check extension
            "4317:4317",  # OTLP gRPC receiver
            "4318:4318",  # OTLP http receiver
            "55679:55679",  # zpages extension
        ],
    }
}

OTEL_COLLECTOR_CONFIG = {
    "receivers": {
        "otlp": {
            "protocols": {
                "grpc": {
                    "endpoint": "0.0.0.0:4317",
                },
                "http": {
                    "endpoint": "0.0.0.0:4318",
                },
            },
        },
    },
    "exporters": {
        "debug": {
            "verbosity": "detailed",
        },
        "elasticsearch": {
            "endpoint": "https://elastic:9200",
            "auth": {
                "authenticator": "basicauth",
            },
            "traces_index": "YOUR_INDEX_NAME",
            "mapping": {
                "mode": "none",
            },
        },
    },
    "extensions": {
        "basicauth": {
            "client_auth": {
                "username": "username",
                "password": "password",
            },
        },
    },
    "processors": {
        "memory_limiter": {
            "check_interval": "1s",
            "limit_mib": 2000,
        },
        "batch": {
            "timeout": "5s",
            "send_batch_size": 512,
            "send_batch_max_size": 1024,
        },
        "resource": {
            "attributes": [
                {"key": "environment", "value": "testing", "action": "upsert"},
                {"key": "service.version", "value": "1.2.3", "action": "upsert"},
            ],
        },
    },
    "service": {
        "extensions": ["basicauth"],
        "pipelines": {
            "traces": {
                "receivers": ["otlp"],
                "processors": ["memory_limiter", "batch", "resource"],
                "exporters": ["debug", "elasticsearch"],
            },
            "metrics": {
                "receivers": ["otlp"],
                "processors": ["memory_limiter", "batch"],
                "exporters": ["debug", "elasticsearch"],
            },
            "logs": {
                "receivers": ["otlp"],
                "processors": ["memory_limiter", "batch"],
                "exporters": ["debug", "elasticsearch"],
            },
        },
    },
}
