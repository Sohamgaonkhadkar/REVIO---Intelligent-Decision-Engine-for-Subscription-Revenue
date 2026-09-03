"""Deployment-config verification (item 14) — config-level.

The sandbox cannot run Docker (documented limitation), so we verify the
topology STATICALLY: every service, command, mount, healthcheck and module
path the compose file references must actually exist/be importable, and the
web/nginx path must serve the built SPA with API proxying. This catches the
entire class of "compose file drifted from the repo" bugs.
"""
from __future__ import annotations

import importlib
import pathlib
import re

import pytest
import yaml

REPO = pathlib.Path(__file__).resolve().parents[1]
COMPOSE = REPO / "deploy" / "docker-compose.yml"


@pytest.fixture(scope="module")
def compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text())


def test_topology_services(compose):
    assert set(compose["services"]) == {"db", "api", "ops", "web"}
    db = compose["services"]["db"]
    assert db["image"].startswith("pgvector/pgvector:pg16")
    assert db["healthcheck"]["test"][1].startswith("pg_isready")


def test_roles_split(compose):
    api = compose["services"]["api"]["environment"]
    ops = compose["services"]["ops"]["environment"]
    assert api["RUNTIME_ROLE"] == "core" and ops["RUNTIME_ROLE"] == "ops"
    assert ops["COPILOT_ENABLED"] == "false"          # disabled by default
    assert compose["services"]["ops"]["depends_on"]["db"]["condition"] == "service_healthy"


def test_commands_are_importable(compose):
    for cmd in (compose["services"]["api"]["command"], compose["services"]["ops"]["command"]):
        mods = re.findall(r"python -m ([a-zA-Z0-9_.]+)", cmd)
        assert mods, cmd
        for m in mods:
            importlib.import_module(m)                 # must exist in the repo


def test_model_mount_and_fallback(compose):
    """The model JSON is single-sourced: compose mounts it read-only into the
    path the registry expects; in-sandbox the loader falls back to uploads/."""
    api_vols = compose["services"]["api"]["volumes"]
    assert any("xgboost_native_categorical_c5.json" in v and v.endswith(":ro")
               for v in api_vols)
    # and the loader actually resolves + passes the gate right now:
    from core.scoring.artifacts import _resolve_artifact
    p = _resolve_artifact("artifacts/models/c5/xgboost_native_categorical_c5.json")
    assert p.exists() and p.stat().st_size > 10_000_000


def test_dockerfile_copies_only_real_dirs():
    df = (REPO / "deploy" / "Dockerfile").read_text()
    for line in df.splitlines():
        m = re.match(r"COPY (\S+)", line)
        if m:
            target = m.group(1)
            assert (REPO / target).exists(), f"Dockerfile copies missing dir: {target}"


def test_nginx_serves_built_spa_and_proxies_api():
    conf = (REPO / "deploy" / "nginx.conf").read_text()
    assert "try_files $uri $uri/ /index.html" in conf
    assert "proxy_pass http://api:8000" in conf
    spa = REPO / "apps" / "web" / "spa"
    assert (spa / "index.html").exists()
    assert any(a.is_file() for a in (spa / "assets").glob("index-*.js"))


def test_env_file_requirements(compose):
    dev = REPO / "deploy" / "envs" / "dev.env"
    assert dev.exists()
    compose_text = COMPOSE.read_text()
    needed = set(re.findall(r"\$\{(\w+):?\?", compose_text))
    have = {line.split("=")[0] for line in dev.read_text().splitlines() if "=" in line}
    assert needed <= have, f"dev.env missing: {needed - have}"


def test_db_secrets_not_committed():
    """dev.env may hold a demo password; real secrets must never be committed."""
    dev = (REPO / "deploy" / "envs" / "dev.env").read_text()
    assert "POSTGRES_PASSWORD=" in dev
    for line in dev.splitlines():
        if line.startswith("POSTGRES_PASSWORD="):
            val = line.split("=", 1)[1]
            assert val in ("change-me", "dev-only", "") or "dev" in val.lower() or len(val) < 24, (
                "dev.env looks like it holds a real secret")
