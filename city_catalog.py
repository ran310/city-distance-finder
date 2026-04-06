"""
Shared DuckDB + Iceberg catalog attachment for CLI tools and the Flask API.
"""

from __future__ import annotations

import base64
import importlib.util
import os
import re
import subprocess
from pathlib import Path

import duckdb

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ROOT = Path(__file__).resolve().parent


def app_config_path() -> Path:
    """Absolute path to appconfig.py (same directory as this module)."""
    return (_ROOT / "appconfig.py").resolve()


def is_safe_sql_identifier(name: str) -> bool:
    return bool(_IDENT.fullmatch(name))


def _load_app_config():
    config_path = app_config_path()
    if not config_path.is_file():
        raise FileNotFoundError(
            "Missing appconfig.py — copy appconfig.example.py and set credentials."
        )
    spec = importlib.util.spec_from_file_location("appconfig", config_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _sql_string_literal(value: str) -> str:
    return value.replace("'", "''")


def _apply_s3_credential_chain(con: duckdb.DuckDBPyConnection, cfg) -> None:
    """
    Use the AWS SDK default provider (SSO, ~/.aws/credentials, env vars, IAM role, etc.).
    Requires the DuckDB `aws` extension. Run `aws sso login` (or similar) in your shell first
    if your profile uses SSO.

    Default VALIDATION is 'none' so CREATE SECRET does not fail at catalog attach time when
    credentials are only resolved later (SSO, profiles, or env not visible to validation).
    Use S3_CREDENTIAL_VALIDATION = 'exists' for fail-fast startup checks.
    """
    con.execute("INSTALL aws; LOAD aws;")
    parts = [
        "CREATE OR REPLACE SECRET iceberg_s3 (",
        "TYPE s3,",
        "PROVIDER credential_chain",
    ]
    chain = getattr(cfg, "S3_CREDENTIAL_CHAIN", None) or "env;sso;config;process"
    parts.append(f", CHAIN '{_sql_string_literal(str(chain))}'")
    region = (
        getattr(cfg, "S3_REGION", None)
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
    )
    if region:
        parts.append(f", REGION '{_sql_string_literal(str(region))}'")
    validation = getattr(cfg, "S3_CREDENTIAL_VALIDATION", None)
    if validation is None:
        validation = "none"
    if validation:
        parts.append(f", VALIDATION '{_sql_string_literal(str(validation))}'")
    if getattr(cfg, "S3_REFRESH_AUTO", False):
        parts.append(", REFRESH auto")
    parts.append(");")
    con.execute("".join(parts))


def _sync_credentials_from_aws_cli(cfg) -> None:
    """
    Populate AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN from the same
    source as `aws sts get-caller-identity` (respects AWS_PROFILE, ~/.aws, SSO cache).
    """
    if getattr(cfg, "S3_AWS_CLI_PATH", None):
        aws_bin = str(cfg.S3_AWS_CLI_PATH)
    else:
        aws_bin = "aws"
    try:
        r = subprocess.run(
            [aws_bin, "configure", "export-credentials", "--format", "env"],
            capture_output=True,
            text=True,
            timeout=30,
            env=os.environ.copy(),
            check=False,
        )
    except OSError:
        return
    if r.returncode != 0:
        return
    for raw in r.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        name, _, val = line.partition("=")
        name = name.strip()
        val = val.strip().strip('"').strip("'")
        if name in (
            "AWS_ACCESS_KEY_ID",
            "AWS_SECRET_ACCESS_KEY",
            "AWS_SESSION_TOKEN",
            "AWS_CREDENTIAL_EXPIRATION",
        ):
            os.environ[name] = val


def _apply_s3_static_secret(
    con: duckdb.DuckDBPyConnection, key: str, secret: str, token: str, region: str
) -> None:
    kid = _sql_string_literal(str(key))
    sec = _sql_string_literal(str(secret))
    reg = _sql_string_literal(str(region))
    tok_sql = ""
    if token:
        tok = _sql_string_literal(str(token))
        tok_sql = f", SESSION_TOKEN '{tok}'"
    con.execute(
        f"""
        CREATE OR REPLACE SECRET iceberg_s3 (
            TYPE S3,
            KEY_ID '{kid}',
            SECRET '{sec}',
            REGION '{reg}'{tok_sql}
        );
        """
    )


def _apply_s3_secret(con: duckdb.DuckDBPyConnection, cfg) -> None:
    use_chain = getattr(cfg, "S3_USE_AWS_CREDENTIAL_CHAIN", False)
    force_chain = getattr(cfg, "S3_FORCE_CREDENTIAL_CHAIN", False)

    sync = getattr(cfg, "S3_SYNC_AWS_CLI_CREDENTIALS", None)
    if sync is None:
        sync = bool(use_chain)
    if sync:
        _sync_credentials_from_aws_cli(cfg)

    key = (
        getattr(cfg, "S3_ACCESS_KEY_ID", None)
        or getattr(cfg, "AWS_ACCESS_KEY_ID", None)
        or os.environ.get("AWS_ACCESS_KEY_ID")
    )
    secret = (
        getattr(cfg, "S3_SECRET_ACCESS_KEY", None)
        or getattr(cfg, "AWS_SECRET_ACCESS_KEY", None)
        or os.environ.get("AWS_SECRET_ACCESS_KEY")
    )
    token = (
        getattr(cfg, "AWS_SESSION_TOKEN", None) or os.environ.get("AWS_SESSION_TOKEN") or ""
    )
    region = (
        getattr(cfg, "S3_REGION", None)
        or getattr(cfg, "AWS_DEFAULT_REGION", None)
        or os.environ.get("AWS_DEFAULT_REGION")
        or os.environ.get("AWS_REGION")
        or "us-east-1"
    )

    # Prefer explicit keys (config or env) over DuckDB's credential_chain. The embedded AWS
    # SDK often does not see the same `aws login` / SSO cache as the AWS CLI, which leads to
    # S3 403 even when `aws s3api head-object` works in your terminal.
    if key and secret and not force_chain:
        _apply_s3_static_secret(con, key, secret, token, region)
        return

    if use_chain:
        _apply_s3_credential_chain(con, cfg)


def _env_nonempty(*names: str) -> str:
    for n in names:
        v = os.environ.get(n)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def _iceberg_authorization_sql_value(cfg) -> str:
    """
    Return SQL-safe single-quoted content for the Authorization header value
    (e.g. Basic base64(...) or Bearer ...).

    Environment variables override appconfig (for EC2 / systemd EnvironmentFile
    or GitHub Actions → CodeDeploy): ICEBERG_BEARER_TOKEN, ICEBERG_USER,
    ICEBERG_USERNAME, ICEBERG_PASSWORD.
    """
    bearer = _env_nonempty("ICEBERG_BEARER_TOKEN")
    if not bearer:
        b = getattr(cfg, "ICEBERG_BEARER_TOKEN", None)
        if b is not None and str(b).strip():
            bearer = str(b).strip()
    if bearer:
        raw = f"Bearer {bearer}"
        return _sql_string_literal(raw)

    user = _env_nonempty("ICEBERG_USER", "ICEBERG_USERNAME")
    if not user:
        user = getattr(cfg, "ICEBERG_USER", None) or getattr(cfg, "ICEBERG_USERNAME", None) or ""
        user = str(user).strip()

    password = _env_nonempty("ICEBERG_PASSWORD")
    if not password:
        pw_raw = getattr(cfg, "ICEBERG_PASSWORD", None)
        password = "" if pw_raw is None else str(pw_raw).strip()

    if not user or not password:
        hint = []
        if not _env_nonempty("ICEBERG_USER", "ICEBERG_USERNAME") and not hasattr(
            cfg, "ICEBERG_USER"
        ) and not hasattr(cfg, "ICEBERG_USERNAME"):
            hint.append(
                "No ICEBERG_USER or ICEBERG_USERNAME in environment or appconfig (check for typos, e.g. IICEBERG_USER)."
            )
        if not _env_nonempty("ICEBERG_PASSWORD") and not hasattr(cfg, "ICEBERG_PASSWORD"):
            hint.append("No ICEBERG_PASSWORD in environment or appconfig.")
        hint_s = " " + " ".join(hint) if hint else ""
        raise ValueError(
            "ICEBERG_USER (or ICEBERG_USERNAME) and ICEBERG_PASSWORD must be set and non-empty "
            "(environment variables or appconfig.py after stripping whitespace)."
            + hint_s
            + " Empty values often follow a typo in the variable name. "
            "Use ICEBERG_BEARER_TOKEN instead if nginx expects a bearer token."
        )

    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return _sql_string_literal(f"Basic {token}")


def attach_iceberg_catalog(con: duckdb.DuckDBPyConnection, cfg=None) -> str:
    """
    Install extensions, attach the Iceberg REST catalog, optionally register S3.
    Returns the catalog alias (e.g. iceberg_catalog).
    """
    if cfg is None:
        cfg = _load_app_config()

    ep_env = _env_nonempty("ICEBERG_CATALOG_ENDPOINT")
    if ep_env:
        endpoint = ep_env.rstrip("/")
    else:
        ep_cfg = getattr(cfg, "ICEBERG_CATALOG_ENDPOINT", None)
        endpoint = ("" if ep_cfg is None else str(ep_cfg)).strip().rstrip("/")

    wh_env = _env_nonempty("ICEBERG_WAREHOUSE")
    if wh_env:
        warehouse = wh_env
    else:
        wh_cfg = getattr(cfg, "ICEBERG_WAREHOUSE", "warehouse")
        warehouse = str(wh_cfg).strip() if wh_cfg is not None else "warehouse"
    if not warehouse:
        warehouse = "warehouse"

    al_env = _env_nonempty("CATALOG_ALIAS")
    if al_env:
        alias = al_env
    else:
        al_cfg = getattr(cfg, "CATALOG_ALIAS", "iceberg_catalog")
        alias = str(al_cfg).strip() if al_cfg is not None else "iceberg_catalog"
    if not alias:
        alias = "iceberg_catalog"

    if not endpoint:
        raise ValueError("ICEBERG_CATALOG_ENDPOINT must be set in appconfig.py")
    if not _IDENT.fullmatch(alias):
        raise ValueError("CATALOG_ALIAS must be a simple SQL identifier")

    auth_esc = _iceberg_authorization_sql_value(cfg)

    con.execute("INSTALL iceberg; LOAD iceberg;")
    con.execute("INSTALL httpfs; LOAD httpfs;")

    _apply_s3_secret(con, cfg)

    con.execute(f"DETACH DATABASE IF EXISTS {alias};")

    wh = _sql_string_literal(warehouse)
    ep = _sql_string_literal(endpoint)

    # Prefer an Iceberg SECRET so Authorization is attached to every REST call; some setups
    # only pick up EXTRA_HTTP_HEADERS on ATTACH inconsistently.
    use_iceberg_secret = False
    try:
        con.execute(
            f"""
            CREATE OR REPLACE SECRET iceberg_rest_catalog_auth (
                TYPE iceberg,
                EXTRA_HTTP_HEADERS MAP {{ 'Authorization': '{auth_esc}' }}
            );
            """
        )
        use_iceberg_secret = True
    except duckdb.Error:
        pass

    if use_iceberg_secret:
        con.execute(
            f"""
            ATTACH '{wh}' AS {alias} (
                TYPE iceberg,
                ENDPOINT '{ep}',
                AUTHORIZATION_TYPE 'none',
                SECRET iceberg_rest_catalog_auth
            );
            """
        )
    else:
        con.execute(
            f"""
            ATTACH '{wh}' AS {alias} (
                TYPE iceberg,
                ENDPOINT '{ep}',
                AUTHORIZATION_TYPE 'none',
                EXTRA_HTTP_HEADERS MAP {{ 'Authorization': '{auth_esc}' }}
            );
            """
        )
    return alias


def get_cities_table_fqn(cfg) -> str:
    alias = getattr(cfg, "CATALOG_ALIAS", "iceberg_catalog")
    default = f"{alias}.liewyousheng_geolocation.cities"
    return getattr(cfg, "CITIES_TABLE_FQN", default)


def get_city_column_map(cfg) -> dict[str, str]:
    """
    Logical → physical column names for the cities Iceberg table.
    Override in appconfig.CITY_COLUMNS.

    Default matches liewyousheng_geolocation.cities: id, name, state_name, country_name,
    latitude, longitude. Set "state" to "" to omit state from search and disambiguation.
    """
    defaults = {
        "id": "id",
        "city": "name",
        "country": "country_name",
        "state": "state_name",
        "lat": "latitude",
        "lng": "longitude",
    }
    overrides = getattr(cfg, "CITY_COLUMNS", None) or {}
    return {**defaults, **overrides}


def open_catalog_connection(cfg=None):
    """
    Create an in-memory DuckDB connection with the Iceberg catalog attached.
    Pass cfg from a single _load_app_config() call so attach uses the same module instance
    the app already loaded (avoids loading appconfig.py twice).
    """
    if cfg is None:
        cfg = _load_app_config()
    con = duckdb.connect(database=":memory:")
    attach_iceberg_catalog(con, cfg)
    return con
