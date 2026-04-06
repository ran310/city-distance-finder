"""
Flask API for city search (Iceberg via DuckDB) and great-circle distance.
Serves the Vite production build from frontend/dist when present.
"""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import city_catalog
from city_labels import assign_labels

_ROOT = Path(__file__).resolve().parent
_FRONTEND_DIST = _ROOT / "frontend" / "dist"

_db_lock = threading.Lock()
_con = None
_cfg = None

app = Flask(__name__, static_folder=None)
CORS(app)


def _parse_table_fqn(fqn: str) -> str:
    parts = fqn.split(".")
    for p in parts:
        if not city_catalog.is_safe_sql_identifier(p):
            raise ValueError(f"Invalid SQL identifier in table path: {p!r}")
    return fqn


def _quote_ident(name: str) -> str:
    if not city_catalog.is_safe_sql_identifier(name):
        raise ValueError(f"Invalid column name: {name!r}")
    return name


def get_db():
    global _con, _cfg
    with _db_lock:
        if _con is None:
            _cfg = city_catalog._load_app_config()
            _con = city_catalog.open_catalog_connection(_cfg)
        return _con, _cfg


@app.route("/api/health")
def health():
    cfg_path = city_catalog.app_config_path()
    out = {
        "ok": True,
        "appconfig_path": str(cfg_path),
        "appconfig_exists": cfg_path.is_file(),
        "duckdb_catalog_initialized": _con is not None,
    }
    if _cfg is not None:
        ep = getattr(_cfg, "ICEBERG_CATALOG_ENDPOINT", None)
        if ep:
            out["iceberg_catalog_endpoint"] = str(ep).strip().rstrip("/")
    out["iceberg_credentials_from_env"] = bool(
        (os.environ.get("ICEBERG_USER") or os.environ.get("ICEBERG_USERNAME") or "").strip()
        or (os.environ.get("ICEBERG_PASSWORD") or "").strip()
        or (os.environ.get("ICEBERG_BEARER_TOKEN") or "").strip()
    )
    return jsonify(out)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@app.route("/api/distance", methods=["POST"])
def distance():
    data = request.get_json(silent=True) or {}
    try:
        o = data["origin"]
        d = data["destination"]
        lat1, lon1 = float(o["lat"]), float(o["lng"])
        lat2, lon2 = float(d["lat"]), float(d["lng"])
    except (KeyError, TypeError, ValueError):
        return jsonify({"error": "Expected origin/destination with lat,lng numbers"}), 400
    km = haversine_km(lat1, lon1, lat2, lon2)
    mi = km * 0.621371
    return jsonify({"kilometers": round(km, 2), "miles": round(mi, 2)})


@app.route("/api/cities")
def cities():
    q = (request.args.get("q") or "").strip()
    if len(q) < 1:
        return jsonify({"cities": []})

    try:
        limit = min(int(request.args.get("limit", 120)), 500)
    except ValueError:
        limit = 120

    try:
        con, cfg = get_db()
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        return jsonify({"error": f"Catalog connection failed: {e}"}), 500

    fqn = _parse_table_fqn(city_catalog.get_cities_table_fqn(cfg))
    cols = city_catalog.get_city_column_map(cfg)
    c_id = _quote_ident(cols["id"])
    c_city = _quote_ident(cols["city"])
    c_country = _quote_ident(cols["country"])
    c_lat = _quote_ident(cols["lat"])
    c_lng = _quote_ident(cols["lng"])
    state_col = (cols.get("state") or "").strip()
    if state_col:
        c_state = _quote_ident(state_col)
        state_select = f"CAST({c_state} AS VARCHAR) AS state"
        state_or = f" OR {c_state} ILIKE $pattern"
    else:
        state_select = "CAST('' AS VARCHAR) AS state"
        state_or = ""

    pattern = f"%{q}%"
    sql = f"""
        SELECT
            CAST({c_id} AS VARCHAR) AS id,
            CAST({c_city} AS VARCHAR) AS city,
            CAST({c_country} AS VARCHAR) AS country,
            {state_select},
            CAST({c_lat} AS DOUBLE) AS lat,
            CAST({c_lng} AS DOUBLE) AS lng
        FROM {fqn}
        WHERE
            {c_city} ILIKE $pattern
            OR {c_country} ILIKE $pattern{state_or}
        LIMIT $lim
    """

    try:
        with _db_lock:
            cur = con.execute(sql, {"pattern": pattern, "lim": limit})
            desc = [x[0] for x in cur.description]
            raw = [dict(zip(desc, row)) for row in cur.fetchall()]
    except Exception as e:
        return jsonify({"error": str(e), "hint": "Check CITIES_TABLE_FQN and CITY_COLUMNS in appconfig.py"}), 500

    labeled = assign_labels(raw)
    return jsonify({"cities": labeled})


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path):
    if path.startswith("api/"):
        return jsonify({"error": "Not found"}), 404
    file_path = _FRONTEND_DIST / path
    if path and file_path.is_file():
        return send_from_directory(_FRONTEND_DIST, path)
    index = _FRONTEND_DIST / "index.html"
    if index.is_file():
        return send_from_directory(_FRONTEND_DIST, "index.html")
    return (
        jsonify(
            {
                "message": "Frontend not built. Run: cd frontend && npm install && npm run build",
                "api": "/api/cities?q=paris",
            }
        ),
        503,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8086"))
    _fd = os.environ.get("FLASK_DEBUG")
    if _fd is None:
        debug = True
    else:
        debug = _fd.lower() in ("1", "true", "yes")
    app.run(host="127.0.0.1", port=port, debug=debug, threaded=True)
