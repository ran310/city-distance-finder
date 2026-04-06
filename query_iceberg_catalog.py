#!/usr/bin/env python3
"""
Query an Iceberg REST catalog through DuckDB.

The catalog is expected to implement the Iceberg REST API. When nginx (or
another proxy) enforces HTTP Basic authentication, DuckDB is configured with
AUTHORIZATION_TYPE 'none' and an Authorization header built from credentials in
appconfig.py.
"""

from __future__ import annotations

import sys

import duckdb

import city_catalog


def _print_table(result) -> None:
    cols = [d[0] for d in result.description]
    rows = result.fetchall()
    print(" | ".join(cols))
    for row in rows:
        print(" | ".join(str(v) for v in row))


def main() -> None:
    print('main')
    try:
        cfg = city_catalog._load_app_config()
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)

    print(f"Using appconfig: {city_catalog.app_config_path()}", file=sys.stderr)

    con = duckdb.connect(database=":memory:")
    city_catalog.attach_iceberg_catalog(con, cfg)

    print("Tables visible to DuckDB:")
    _print_table(con.execute("SHOW ALL TABLES;"))

    alias = getattr(cfg, "CATALOG_ALIAS", "iceberg_catalog")
    print(
        f"\nExample: SELECT * FROM {alias}.<namespace>.<table> LIMIT 10;\n"
        "Adjust namespace/table names from the listing above."
    )


if __name__ == "__main__":
    main()
