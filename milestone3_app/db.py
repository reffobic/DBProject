"""MySQL connection for the Streamlit application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import mysql.connector


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def connect():
    host = os.environ.get("MYSQL_HOST", "127.0.0.1")
    port = _env_int("MYSQL_PORT", 3306)
    user = os.environ.get("MYSQL_USER", "root")
    password = os.environ.get("MYSQL_PASSWORD", "")
    database = os.environ.get("MYSQL_DATABASE", "DataGov_DB")

    ssl_ca = os.environ.get("MYSQL_SSL_CA", "").strip()
    ssl_disabled = os.environ.get("MYSQL_SSL_DISABLED", "").lower() in ("1", "true", "yes")

    params: dict[str, Any] = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": database,
        "autocommit": True,
    }

    if ssl_ca and Path(ssl_ca).expanduser().exists():
        params["ssl_ca"] = str(Path(ssl_ca).expanduser())
    elif host not in ("127.0.0.1", "localhost", "::1") and not ssl_disabled:
        raise RuntimeError(
            "TLS is required for this host: set MYSQL_SSL_CA to a readable CA certificate path, "
            "or set MYSQL_SSL_DISABLED=true for local development only."
        )

    return mysql.connector.connect(**params)


def fileformat_has_dataset_column(cur) -> bool:
    """Return whether `FileFormat` includes a `Dataset_identifier` column."""
    cur.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = 'FileFormat'
          AND COLUMN_NAME = 'Dataset_identifier'
        """
    )
    row = cur.fetchone()
    return bool(row and row[0])
