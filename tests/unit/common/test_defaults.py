# SPDX-License-Identifier: LicenseRef-DeepFellow-Free
# SPDX-FileCopyrightText: 2026 Simplito sp. z o.o.

import json

from deepfellow.common.defaults import MONGO_REPLICA_SET, mongo_replica_set_service


def test_mongo_replica_set_service_has_no_host_ports() -> None:
    service = mongo_replica_set_service("db", "vol", "root", "PW", "KEY")["db"]

    assert "ports" not in service


def test_mongo_replica_set_service_uses_name_for_container_volume_and_member_host() -> None:
    service = mongo_replica_set_service("my-db", "my-vol", "root", "PW", "KEY")["my-db"]

    assert service["container_name"] == "my-db"
    assert service["volumes"] == ["my-vol:/data/db"]
    assert 'host: "my-db:27017"' in service["healthcheck"]["test"][-1]


def test_mongo_replica_set_service_healthcheck_initiates_only_when_missing_and_requires_primary() -> None:
    service = mongo_replica_set_service("db", "vol", "root", "PW", "KEY")["db"]

    healthcheck = service["healthcheck"]
    assert healthcheck["test"][0] == "CMD-SHELL"
    script = healthcheck["test"][-1]
    assert "try { rs.status() } catch (e) { rs.initiate(" in script
    assert script.endswith("quit(db.hello().isWritablePrimary ? 0 : 1)'")
    assert '{_id: "rs0", members: [{_id: 0, host: "db:27017"}]}' in script
    assert healthcheck["retries"] == 20
    assert service["command"][:3] == ["mongod", "--replSet", MONGO_REPLICA_SET]


def test_mongo_replica_set_service_requires_authentication_with_keyfile() -> None:
    service = mongo_replica_set_service("db", "vol", "root", "PW", "KEY")["db"]

    assert "MONGO_INITDB_ROOT_USERNAME=root" in service["environment"]
    assert "MONGO_INITDB_ROOT_PASSWORD=${PW}" in service["environment"]
    assert "MONGO_KEY=${KEY}" in service["environment"]
    assert service["command"][-2:] == ["--keyFile", "/data/keyfile"]
    assert "--authenticationDatabase admin" in service["healthcheck"]["test"][-1]
    assert "ports" not in service


def test_mongo_replica_set_service_two_callers_differ_only_by_name_and_volume() -> None:
    first = mongo_replica_set_service("name-one", "vol-one", "root", "PW", "KEY")["name-one"]
    second = mongo_replica_set_service("name-two", "vol-two", "root", "PW", "KEY")["name-two"]

    assert first["container_name"] != second["container_name"]
    assert first["volumes"] != second["volumes"]
    normalised = json.dumps(second).replace("name-two", "name-one").replace("vol-two", "vol-one")
    assert normalised == json.dumps(first)
