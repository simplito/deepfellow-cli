# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

"""Default config values."""

from enum import Enum
from pathlib import Path
from typing import Any, TypedDict

DF_DEEPFELLOW_DIRECTORY = Path.home() / ".deepfellow"

DF_CLI_CONFIG_PATH = DF_DEEPFELLOW_DIRECTORY / "config"  # env style config file
DF_CLI_SECRETS_PATH = DF_DEEPFELLOW_DIRECTORY / "secrets"  # env style secrets file

DF_SUITE_INSTALL_STATE_FILE = DF_DEEPFELLOW_DIRECTORY / "suite_install_state.json"

DF_INFRA_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "infra"
DF_INFRA_IMAGE_HUB = "hub.simplito.com/deepfellow/deepfellow-infra"
DF_INFRA_IMAGE = f"{DF_INFRA_IMAGE_HUB}:latest"
DF_INFRA_PORT = 8086
# Host address the Infra API port is published on; empty means all interfaces (IPv4 and IPv6).
DF_INFRA_BIND_ADDRESS = ""
INFRA_BIND_ADDRESS = f"${{DF_INFRA_BIND_ADDRESS-{DF_INFRA_BIND_ADDRESS}}}"
DF_INFRA_URL = f"http://infra:{DF_INFRA_PORT}"
DF_INFRA_DOCKER_NETWORK = "deepfellow-infra-net"
DF_INFRA_STORAGE_DIR = DF_INFRA_DIRECTORY / "storage"
DF_INFRA_NAME = "infra"

DF_SERVER_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / "server"
DF_SERVER_IMAGE_HUB = "hub.simplito.com/deepfellow/deepfellow-server"
DF_SERVER_IMAGE = f"{DF_SERVER_IMAGE_HUB}:latest"
DF_SERVER_PORT = 8000
# Host address the Server API port is published on; empty means all interfaces (IPv4 and IPv6).
DF_SERVER_BIND_ADDRESS = ""
SERVER_BIND_ADDRESS = f"${{DF_SERVER_BIND_ADDRESS-{DF_SERVER_BIND_ADDRESS}}}"
# NOTE: uploaded files, used by vector stores
DF_SERVER_STORAGE_DIRECTORY = DF_DEEPFELLOW_DIRECTORY / DF_SERVER_DIRECTORY / "storage"

DF_MONGO_URL = "mongo:27017"
DF_MONGO_PORT = 27017
DF_MONGO_DB = "deepfellow"

# Host address for ports of server-only services; `-` keeps an empty value (all interfaces).
DF_INTERNAL_BIND_ADDRESS = "127.0.0.1"
INTERNAL_BIND_ADDRESS = f"${{DF_INTERNAL_BIND_ADDRESS-{DF_INTERNAL_BIND_ADDRESS}}}"

DOCKER_COMPOSE_CONFIG_FILENAME = "compose.yaml"

# ================
# Vector databases
# ================


class VectorDBTypeChoice(str, Enum):
    milvus = "milvus"
    qdrant = "qdrant"


ALLOWED_VECTOR_DB_TYPES = [e.value for e in VectorDBTypeChoice]
QDRANT_DATABASE_URL = "http://qdrant:6333"
SPARSE_EMBEDDING_MODEL = "deepfellow-bge-m3"
SPARSE_EMBEDDING_SIZE = 1024
DOC_CHUNKER_STT_MODEL = "Systran/faster-whisper-large-v3"

DEFAULT_EMBEDDING = {
    "embedding": {"active": 1, "endpoint": "openai", "model": "mxbai-embed-large", "size": "1024"},
}
QDRANT_DATABASE: dict[str, Any] = {
    "provider": {
        "active": 1,
        "type": "qdrant",
        "url": QDRANT_DATABASE_URL,
    }
} | DEFAULT_EMBEDDING
MILVUS_DATABASE_URL = "http://milvus:19530"
MILVUS_DATABASE: dict[str, Any] = {
    "provider": {
        "active": 1,
        "type": "milvus",
        "url": MILVUS_DATABASE_URL,
        "db": "deepfellow",
    }
} | DEFAULT_EMBEDDING
# Define the default vector database.
DEFAULT_VECTOR_DATABASE_TYPE = "qdrant"
VECTOR_DATABASES = {"qdrant": QDRANT_DATABASE, "milvus": MILVUS_DATABASE}
DEFAULT_VECTOR_DATABASE = VECTOR_DATABASES[DEFAULT_VECTOR_DATABASE_TYPE]

# ==============
# Docker compose
# ==============


class _ServiceConfigOptional(TypedDict, total=False):
    """Optional fields of a Docker Compose service definition."""

    container_name: str
    depends_on: dict[str, Any]
    environment: list[str]
    pull_policy: str
    volumes: list[str]
    networks: list[str]


class ServiceConfig(_ServiceConfigOptional):
    """Shape of a single Docker Compose service definition."""

    image: str
    ports: list[str]
    restart: str
    healthcheck: dict[str, Any]


DOCKER_COMPOSE_INFRA: dict[str, ServiceConfig] = {
    DF_INFRA_NAME: {
        "image": "${DF_INFRA_IMAGE}",
        "ports": [f"{INFRA_BIND_ADDRESS}:${{DF_INFRA_PORT}}:8086"],
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
            "DF_HUGGING_FACE_TOKEN=${DF_HUGGING_FACE_TOKEN}",
            "DF_CIVITAI_TOKEN=${DF_CIVITAI_TOKEN}",
            "DF_STORAGE_DIR=${DF_INFRA_STORAGE_DIR}",
            "DF_METRICS_USERNAME=${DF_METRICS_USERNAME}",
            "DF_METRICS_PASSWORD=${DF_METRICS_PASSWORD}",
            "DOCKER_HOST=unix:///var/run/docker.sock",
        ],
        "restart": "unless-stopped",
        "healthcheck": {
            "test": ["CMD", "/app/scripts/healthcheck.py"],
            "interval": "30s",
            "timeout": "5s",
            "retries": 3,
            "start_period": "40s",
        },
        "volumes": [
            "${DF_INFRA_DOCKER_CONFIG}:/root/.docker/config.json:ro",
        ],
    },
}

# Environment shared by `server` and `nightshift`; apply() extends it with the envs of the active
# backing services and gives both services the same list. Both processes create config.json from
# their own environment on first boot, so any difference would let whichever starts first decide
# what an install's config.json contains.
DOCKER_COMPOSE_SERVER_BASE_ENVS = [
    # Not a guard for Nightshift's own metrics port (it isn't password-protected) - Nightshift only
    # needs these so the config.json it may create on first boot matches the server's.
    "DF_METRICS_USERNAME=${DF_METRICS_USERNAME}",
    "DF_METRICS_PASSWORD=${DF_METRICS_PASSWORD}",
    "DF_MONGO_URL=${DF_MONGO_URL}",
    "DF_MONGO_USER=${DF_MONGO_USER}",
    "DF_MONGO_PASSWORD=${DF_MONGO_PASSWORD}",
    "DF_MONGO_DB=${DF_MONGO_DB}",
    "DF_LOG_LEVEL=${DF_LOG_LEVEL}",
    "DF_PLUGINS_SETUP=${DF_PLUGINS_SETUP}",
    "DF_VECTOR_DATABASE__PROVIDER__ACTIVE=${DF_VECTOR_DATABASE__PROVIDER__ACTIVE}",
]

# Its environment is built by apply() from DOCKER_COMPOSE_SERVER_BASE_ENVS.
DOCKER_COMPOSE_SERVER: dict[str, ServiceConfig] = {
    "server": {
        "container_name": "server",
        "image": "${DF_SERVER_IMAGE}",
        "ports": [f"{SERVER_BIND_ADDRESS}:${{DF_SERVER_PORT}}:8000"],
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

DOCKER_COMPOSE_SERVER_VECTOR_DB_ENVS = [
    "DF_VECTOR_DATABASE__PROVIDER__TYPE=${DF_VECTOR_DATABASE__PROVIDER__TYPE}",
    "DF_VECTOR_DATABASE__PROVIDER__URL=${DF_VECTOR_DATABASE__PROVIDER__URL}",
    "DF_VECTOR_DATABASE__EMBEDDING__ACTIVE=${DF_VECTOR_DATABASE__EMBEDDING__ACTIVE}",
    "DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT=${DF_VECTOR_DATABASE__EMBEDDING__ENDPOINT}",
    "DF_VECTOR_DATABASE__EMBEDDING__MODEL=${DF_VECTOR_DATABASE__EMBEDDING__MODEL}",
    "DF_VECTOR_DATABASE__EMBEDDING__SIZE=${DF_VECTOR_DATABASE__EMBEDDING__SIZE}",
]

DOCKER_COMPOSE_SERVER_VECTOR_DB_MILVUS_ENVS = [
    "DF_VECTOR_DATABASE__PROVIDER__DB=${DF_VECTOR_DATABASE__PROVIDER__DB}",
    "DF_VECTOR_DATABASE__PROVIDER__USER=${DF_VECTOR_DATABASE__PROVIDER__USER}",
    "DF_VECTOR_DATABASE__PROVIDER__PASSWORD=${DF_VECTOR_DATABASE__PROVIDER__PASSWORD}",
]

DOCKER_COMPOSE_QDRANT = {
    "qdrant": {
        "container_name": "qdrant",
        "image": "qdrant/qdrant:v1.19.2@sha256:b7b0444c4c351c970b98e90a6f89c2ee4287c65b44e52b4cb503fa5b2aa927ad",
        "restart": "always",
        "expose": [6333, 6334, 6335],
        "volumes": ["qdrant_data:/qdrant/storage"],
        "healthcheck": {
            "test": [
                "CMD",
                "bash",
                "-c",
                "exec 3<>/dev/tcp/127.0.0.1/6333 && "
                "echo -e 'GET /readyz HTTP/1.1\\r\\nHost: localhost\\r\\nConnection: close\\r\\n\\r\\n' >&3 && "
                "grep -q 'HTTP/1.1 200' <&3",
            ],
            "interval": "10s",
            "timeout": "5s",
            "retries": 5,
            "start_period": "5s",
        },
    }
}

DOCKER_COMPOSE_MILVUS = {
    "etcd": {
        "container_name": "etcd",
        "image": "quay.io/coreos/etcd:v3.5.34@sha256:2c029095680c13c2b36116cc3935e1b0cddc0f5af78004457fd863616d8d072b",
        "environment": [
            "ETCD_AUTO_COMPACTION_MODE=revision",
            "ETCD_AUTO_COMPACTION_RETENTION=1000",
            "ETCD_QUOTA_BACKEND_BYTES=4294967296",
            "ETCD_SNAPSHOT_COUNT=50000",
        ],
        "expose": ["2379"],
        "volumes": ["etcd:/etcd"],
        "command": (
            "etcd -advertise-client-urls=http://etcd:2379 -listen-client-urls http://0.0.0.0:2379 --data-dir /etcd"
        ),
        "healthcheck": {
            "test": ["CMD", "etcdctl", "endpoint", "health"],
            "interval": "60s",
            "start_period": "30s",
            "timeout": "30s",
            "retries": 3,
        },
    },
    "seaweedfs": {
        "container_name": "seaweedfs",
        # minio/minio has removed most historical release tags from Docker Hub, so we use
        # SeaweedFS's S3 gateway as an S3-compatible drop-in replacement for Milvus' object storage.
        "image": "chrislusf/seaweedfs:4.48@sha256:4e61d15fd35994cb1e43e1e553dff106794841fd9a99ade2fc8c8bfce4d7872d",
        "volumes": [
            "seaweedfs:/data",
            "./seaweedfs_s3_config.json:/etc/seaweedfs/s3_config.json",
        ],
        "command": "server -dir=/data -s3 -s3.port=9000 -s3.config=/etc/seaweedfs/s3_config.json",
        "expose": ["9000", "9333"],
        "healthcheck": {
            # The master process (port 9333) answers within a second of startup - well before a
            # volume server has registered and the S3 gateway can actually serve writes, so
            # `depends_on: service_healthy` elsewhere would release too early. `/dir/assign` only
            # succeeds once a writable volume exists, which is a much closer proxy for "the S3
            # write path is actually usable" than master liveness alone. That alone isn't enough
            # though: verified live that `/dir/assign` succeeds ~1s after startup while the S3
            # listener on :9000 (what Milvus actually connects to) doesn't accept connections until
            # ~24s in - so also probe :9000 directly. With `SEAWEEDFS_S3_CONFIG` below (no
            # "Anonymous" identity), an unauthenticated GET on :9000 gets a 403, not a 2xx - and
            # this image's wget (BusyBox, not GNU) exits 1 for both a 403 and a refused connection,
            # so a bare exit-code check can't tell "not listening yet" from "listening but denied".
            # `-S` prints the response status line on stderr the moment a real HTTP response comes
            # back (even a 403) - verified live that only a connection refusal produces no such
            # line - so grep for it instead of trusting wget's exit code for this probe.
            "test": (
                "wget -q -O- http://127.0.0.1:9333/dir/assign | grep -q '\"fid\"' && "
                "(wget -q -T2 -S -O /dev/null http://127.0.0.1:9000/ 2>&1 | grep -q 'HTTP/1.1')"
            ),
            "interval": "10s",
            "start_period": "30s",
            "timeout": "10s",
            "retries": 6,
        },
    },
    "milvus": {
        "container_name": "milvus",
        "image": "milvusdb/milvus:v2.6.25@sha256:29f7668e64df1c6d5cdadbfbee99f38c72e4001054f149a298725acae57230ad",
        "command": "milvus run standalone",
        "security_opt": ["seccomp:unconfined"],
        "environment": [
            "ETCD_ENDPOINTS=etcd:2379",
            "MINIO_ADDRESS=seaweedfs:9000",
            "MQ_TYPE=woodpecker",
        ],
        "volumes": ["milvus:/var/lib/milvus"],
        "healthcheck": {
            "test": "curl -f http://localhost:9091/healthz",
            "interval": "60s",
            "start_period": "120s",
            "timeout": "30s",
            "retries": 3,
        },
        "expose": ["19530", "9091"],
        "depends_on": {
            "etcd": {"condition": "service_healthy"},
            "seaweedfs": {"condition": "service_healthy"},
        },
    },
}

# Milvus' own bundled config always authenticates against its object storage with these defaults,
# so every fresh (non-legacy) SeaweedFS install must keep matching identities here - Milvus' config
# is not customized per-install. `minio_migration.py` also relies on these two constants: the
# migration's own temporary destination container is loaded with this exact identity file, so the
# migration's rclone DST remote must authenticate with these credentials, not the old MinIO's real
# ones (which the SRC remote uses instead).
SEAWEEDFS_S3_ACCESS_KEY = "minioadmin"
SEAWEEDFS_S3_SECRET_KEY = "minioadmin"

SEAWEEDFS_S3_CONFIG = f"""
{{
  "identities": [
    {{
      "name": "{SEAWEEDFS_S3_ACCESS_KEY}",
      "credentials": [
        {{
          "accessKey": "{SEAWEEDFS_S3_ACCESS_KEY}",
          "secretKey": "{SEAWEEDFS_S3_SECRET_KEY}"
        }}
      ],
      "actions": ["Admin", "Read", "Write"]
    }}
  ]
}}
"""

MONGO_DB_INIT_SH = """
#!/bin/bash
mongosh -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin <<EOF
db = db.getSiblingDB("admin");
db.createUser({
  user: "$DF_MONGO_USER",
  pwd: "$DF_MONGO_PASSWORD",
  roles: [{ role: "readWrite", db: "$DF_MONGO_DB" }],
});
EOF
"""

DOCKER_COMPOSE_MONGO_DB = {
    "mongo": {
        "container_name": "mongo",
        "image": "mongo:8.2.12@sha256:e0ce8c35124d4a9f9785532d1f268f39e9728ffa1cb38f46fa482436424c4bd3",
        "restart": "always",
        "ports": [f"{INTERNAL_BIND_ADDRESS}:${{DF_MONGO_PORT}}:27017"],
        "volumes": [
            "mongo:/data/db",
            "./init-mongo.sh:/docker-entrypoint-initdb.d/init-mongo.sh:ro",
        ],
        "environment": [
            "MONGO_INITDB_ROOT_USERNAME=${DF_MONGO_INITDB_ROOT_USERNAME}",
            "MONGO_INITDB_ROOT_PASSWORD=${DF_MONGO_INITDB_ROOT_PASSWORD}",
            "DF_MONGO_USER=${DF_MONGO_USER}",
            "DF_MONGO_PASSWORD=${DF_MONGO_PASSWORD}",
            "DF_MONGO_DB=${DF_MONGO_DB}",
            "GLIBC_TUNABLES=glibc.cpu.hwcaps=-SHSTK",
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

DF_FALKORDB_URL = "falkordb:6379"
DF_FALKORDB_PORT = 6379

DOCKER_COMPOSE_SERVER_FALKORDB_ENVS = [
    "DF_GRAPH__ENABLED=${DF_GRAPH__ENABLED}",
    "DF_GRAPH__HOST=${DF_GRAPH__HOST}",
    "DF_GRAPH__PORT=${DF_GRAPH__PORT}",
    "DF_GRAPH__USERNAME=${DF_GRAPH__USERNAME}",
    "DF_GRAPH__PASSWORD=${DF_GRAPH__PASSWORD}",
]

DOCKER_COMPOSE_FALKORDB = {
    "falkordb": {
        "container_name": "falkordb",
        "image": "falkordb/falkordb:v4.22.2@sha256:03f53c46223ac2c0aab05ede7c6a8d9299255b7fd228909424f2c453f7a8cfcd",
        "restart": "always",
        "expose": ["6379", "3000"],
        "volumes": ["falkordb_data:/var/lib/falkordb/data"],
        "environment": ["REDIS_ARGS=--requirepass ${DF_GRAPH__PASSWORD}"],
        "healthcheck": {
            "test": ["CMD", "redis-cli", "-a", "${DF_GRAPH__PASSWORD}", "ping"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "30s",
        },
    }
}

DF_RABBITMQ_URL = "rabbitmq:5672"
DF_RABBITMQ_PORT = 5672
DF_RABBITMQ_MANAGEMENT_PORT = 15672


class NightshiftModeChoice(str, Enum):
    always = "always"
    shift = "shift"


DEFAULT_NIGHTSHIFT_MODE = NightshiftModeChoice.always.value

# What stops working when an install has no Nightshift worker/RabbitMQ - one entry per group of the
# server's Nightshift queues (vector_store_file_processing, knowledge_compression,
# vector_store_migration_file_reembedding, document_summarization, metadata_expansion,
# graph_document_ingestion, ontology_discovery, webhook_deliveries, finetune_prepare_data,
# finetune_pipeline_steps). Keep in sync when the server adds a queue.
NIGHTSHIFT_FEATURES: tuple[str, ...] = (
    "adding files to vector stores (indexing)",
    "knowledge compression and vector store migrations (re-embedding)",
    "document summarization and metadata expansion",
    "the knowledge graph (ingestion, ontology discovery)",
    "webhook delivery",
    "fine-tuning pipelines (data preparation, pipeline steps)",
)

DOCKER_COMPOSE_SERVER_RABBITMQ_ENVS = [
    # AppSettings.rabbitmq_url expects a full "amqp://user:pass@host:port/" URI
    "DF_RABBITMQ_URL=amqp://${DF_RABBITMQ_USER}:${DF_RABBITMQ_PASSWORD}@${DF_RABBITMQ_URL}/",
    "DF_RABBITMQ_USER=${DF_RABBITMQ_USER}",
    "DF_RABBITMQ_PASSWORD=${DF_RABBITMQ_PASSWORD}",
]

DOCKER_COMPOSE_RABBITMQ: dict[str, Any] = {
    "rabbitmq": {
        "container_name": "rabbitmq",
        "image": "rabbitmq:4.3.6-management@sha256:54cb013d76cd1fd6c0a0708f34062ad61c452bb6f016b434c6c33f1a765d2b58",
        "hostname": "rabbitmq",
        "restart": "always",
        "expose": [str(DF_RABBITMQ_PORT), str(DF_RABBITMQ_MANAGEMENT_PORT)],
        "volumes": ["rabbitmq_data:/var/lib/rabbitmq"],
        "environment": [
            "RABBITMQ_DEFAULT_USER=${DF_RABBITMQ_USER}",
            "RABBITMQ_DEFAULT_PASS=${DF_RABBITMQ_PASSWORD}",
            "RABBITMQ_SERVER_ADDITIONAL_ERL_ARGS=-rabbit consumer_timeout 14400000",
        ],
        "healthcheck": {
            "test": ["CMD", "rabbitmq-diagnostics", "-q", "check_running"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 5,
            "start_period": "30s",
        },
    }
}

# NOTE: nightshift reuses the server image, running the worker module instead of the API. Its
# storage volume and the server's environment are added onto this base by apply() - see
# deepfellow/server/utils/install.py - since they depend on which backing services are active.
# The image's own CMD runs "./.venv/bin/uvicorn" (not bare "uvicorn") because every dependency -
# including pydantic - lives in a venv at /app/.venv, not on the system Python; the worker command
# must use that same venv's interpreter for the same reason, or it fails with ModuleNotFoundError.
DOCKER_COMPOSE_NIGHTSHIFT: dict[str, Any] = {
    "nightshift": {
        "container_name": "nightshift",
        "image": "${DF_SERVER_IMAGE}",
        "command": ["./.venv/bin/python", "-m", "server.workers.nightshift"],
        # Only what Nightshift needs on top of the server's environment: listen on all container
        # interfaces so Prometheus can scrape /metrics over the Docker network (no port is published).
        "environment": ["DF_NIGHTSHIFT_METRICS_HOST=0.0.0.0"],
        "restart": "unless-stopped",
        # Fails when the worker's /metrics stops answering, no queue consumer has started yet (e.g.
        # RabbitMQ unreachable), or any consumer has crashed while the others keep running.
        "healthcheck": {
            "test": ["CMD", "./.venv/bin/python", "-m", "server.workers.healthcheck"],
            "interval": "30s",
            "timeout": "10s",
            "retries": 3,
            "start_period": "60s",
            # Probe this often during start_period (Docker Engine >= 25), so `up --wait` doesn't
            # wait a full 30s interval for the first passing check.
            "start_interval": "5s",
        },
        # Docker waits this long after SIGTERM before killing the worker. Keep it above
        # DF_NIGHTSHIFT_RELOAD_DRAIN_TIMEOUT_SECONDS (300s by default), so in-flight jobs can finish
        # once Nightshift drains on shutdown.
        "stop_grace_period": "330s",
        # Run an init process as PID 1 that forwards SIGTERM to the worker. Python as PID 1 has no
        # SIGTERM handler, so the kernel ignores the signal and every stop would wait the full
        # stop_grace_period before Docker kills it.
        "init": True,
    }
}

DEFAULT_OTEL_URL = "http://otel-collector:4317"

DOCKER_COMPOSE_OTEL_COLLECTOR = {
    "otel-collector": {
        "container_name": "otel-collector",
        "image": (
            "otel/opentelemetry-collector-contrib:0.133.0"
            "@sha256:98274b756324abdb2473fa0c898247a246091e861e61d1548f9be483198eecea"
        ),
        "volumes": ["./otel-collector-config.yaml:/etc/otelcol-contrib/config.yaml"],
        "expose": [
            "4317",  # OTLP gRPC receiver
            "4318",  # OTLP HTTP receiver
            "8889",  # Prometheus exporter metrics
            "13133",  # health_check extension
        ],
        # if we allow systems from outside docker network to send telemetry:
        # "ports": [
        #     "4317:4317",  # OTLP gRPC receiver
        #     "4318:4318",  # OTLP HTTP receiver
        # ],
        # "expose": [
        #     "8889",   # Prometheus exporter metrics
        #     "13133",  # health_check extension
        # ],
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

OTEL_COLLECTOR_CONFIG_DEBUG_ONLY = {
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
        "pipelines": {
            "traces": {
                "receivers": ["otlp"],
                "processors": ["memory_limiter", "batch", "resource"],
                "exporters": ["debug"],
            },
            "metrics": {
                "receivers": ["otlp"],
                "processors": ["memory_limiter", "batch"],
                "exporters": ["debug"],
            },
            "logs": {
                "receivers": ["otlp"],
                "processors": ["memory_limiter", "batch"],
                "exporters": ["debug"],
            },
        },
    },
}
