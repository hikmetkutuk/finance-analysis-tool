# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yfinance as yf
from flask import Flask, jsonify, request
from flask_cors import CORS

BACKEND_DIR = Path(__file__).parent
PROJECT_ROOT = BACKEND_DIR.parent
UI_DIST = PROJECT_ROOT / "ui" / "dist"
DB_PATH = PROJECT_ROOT / "data" / "valuation_history.db"
MACRO_FILE = PROJECT_ROOT / "macro_config.json"

MARKET_FILES = {
    "us":   str(PROJECT_ROOT / "tickers.txt"),
    "bist": str(PROJECT_ROOT / "hisseler.txt"),
}
VALID_MARKETS = frozenset(MARKET_FILES)
_INVALID_MARKET = "invalid market"

sys.path.insert(0, str(PROJECT_ROOT))
from valuation import load_tickers, run_valuation  # noqa: E402

app = Flask(__name__, static_folder=str(UI_DIST), static_url_path="")  # NOSONAR
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})

_lock = threading.Lock()
_state: dict[str, Any] = {
    "us":   {"running": False, "last_updated": None, "error": None},
    "bist": {"running": False, "last_updated": None, "error": None},
}
_portfolio: dict[str, list[dict]] = {"us": [], "bist": []}

_price_cache: dict[str, dict] = {}
PRICE_CACHE_TTL_SEC = 3600


def _now() -> datetime:
    return datetime.now(timezone.utc)


def init_db() -> None:
    DB_PATH.parent.mkdir(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS snapshots (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker        TEXT    NOT NULL,
                snapped_at    TEXT    NOT NULL,
                current_price REAL,
                fair_value    REAL,
                upside_pct    REAL,
                signal_score  INTEGER,
                signal_label  TEXT,
                wacc          REAL,
                sector        TEXT,
                market        TEXT    DEFAULT 'us',
                full_data     TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ticker  ON snapshots(ticker)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_snapped ON snapshots(snapped_at)")
        try:
            conn.execute("ALTER TABLE snapshots ADD COLUMN market TEXT DEFAULT 'us'")
        except sqlite3.OperationalError:
            pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_market  ON snapshots(market)")


def _save_snapshots(results: list[dict], market: str) -> None:
    now = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = [
        (
            r.get("Kod"),
            now,
            r.get("Güncel Fiyat"),
            r.get("Ortalama Adil Fiyat"),
            r.get("Beklenen Getiri (%)"),
            r.get("Sinyal Kalite Skoru"),
            r.get("Sinyal Güven Seviyesi"),
            r.get("WACC"),
            r.get("Sektör"),
            market,
            json.dumps(r, ensure_ascii=False),
        )
        for r in results
    ]
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            "INSERT INTO snapshots "
            "(ticker,snapped_at,current_price,fair_value,upside_pct,"
            " signal_score,signal_label,wacc,sector,market,full_data) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows,
        )


def _load_latest_from_db(market: str) -> tuple[list[dict], str | None]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT full_data, snapped_at
            FROM snapshots s1
            WHERE market = ?
              AND snapped_at = (
                SELECT MAX(snapped_at) FROM snapshots s2
                WHERE s2.ticker = s1.ticker AND s2.market = s1.market
              )
            GROUP BY ticker
            ORDER BY ticker
        """, (market,)).fetchall()
    results: list[dict] = []
    last_updated: str | None = None
    for r in rows:
        if r["full_data"]:
            results.append(json.loads(r["full_data"]))
            if last_updated is None:
                last_updated = r["snapped_at"]
    return results, last_updated


def _do_refresh(market: str) -> None:
    global _portfolio
    try:
        tickers = load_tickers(MARKET_FILES[market])
        results = run_valuation(tickers)
        with _lock:
            _portfolio[market] = results
            _state[market]["last_updated"] = _now().isoformat()
            _state[market]["error"] = None
        _save_snapshots(results, market)
    except Exception as exc:
        with _lock:
            _state[market]["error"] = str(exc)
    finally:
        with _lock:
            _state[market]["running"] = False


def start_refresh(market: str) -> bool:
    with _lock:
        if _state[market]["running"]:
            return False
        _state[market]["running"] = True
        _state[market]["error"] = None
    threading.Thread(target=_do_refresh, args=(market,), daemon=True).start()
    return True


@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    market = request.args.get("market", "us")
    if market not in VALID_MARKETS:
        return jsonify({"error": _INVALID_MARKET}), 400
    with _lock:
        data = list(_portfolio[market])
        state = dict(_state[market])
    return jsonify({"stocks": data, "last_updated": state["last_updated"]})


@app.route("/api/portfolio/<ticker>", methods=["GET"])
def get_stock(ticker: str):
    market = request.args.get("market", "us")
    if market not in VALID_MARKETS:
        return jsonify({"error": _INVALID_MARKET}), 400
    with _lock:
        stock = next((s for s in _portfolio[market] if s.get("Kod") == ticker.upper()), None)
    if stock is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(stock)


@app.route("/api/portfolio/<ticker>/history", methods=["GET"])
def get_history(ticker: str):
    market = request.args.get("market", "us")
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT snapped_at, current_price, fair_value, upside_pct, signal_score "
            "FROM snapshots WHERE ticker=? AND market=? ORDER BY snapped_at",
            (ticker.upper(), market),
        ).fetchall()
    return jsonify({"ticker": ticker.upper(), "history": [dict(r) for r in rows]})


@app.route("/api/portfolio/<ticker>/price-history", methods=["GET"])
def get_price_history(ticker: str):
    upper = ticker.upper()
    cached = _price_cache.get(upper)
    if cached:
        age = (_now() - cached["fetched_at"]).total_seconds()
        if age < PRICE_CACHE_TTL_SEC:
            return jsonify({"ticker": upper, "prices": cached["data"]})
    try:
        hist = yf.Ticker(upper).history(period="1y")
        if hist.empty:
            return jsonify({"ticker": upper, "prices": []})
        data = [
            {"date": str(idx.date()), "price": round(float(row["Close"]), 2)}
            for idx, row in hist.iterrows()
        ]
        _price_cache[upper] = {"data": data, "fetched_at": _now()}
        return jsonify({"ticker": upper, "prices": data})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/refresh", methods=["POST"])
def trigger_refresh():
    body = request.get_json(silent=True) or {}
    market = body.get("market", "us")
    if market not in VALID_MARKETS:
        return jsonify({"error": _INVALID_MARKET}), 400
    if not start_refresh(market):
        return jsonify({"status": "already_running"}), 409
    return jsonify({"status": "started"})


@app.route("/api/refresh/status", methods=["GET"])
def refresh_status():
    market = request.args.get("market", "us")
    if market not in VALID_MARKETS:
        return jsonify({"error": _INVALID_MARKET}), 400
    with _lock:
        return jsonify(dict(_state[market]))


@app.route("/api/macro", methods=["GET"])
def get_macro():
    return jsonify(json.loads(MACRO_FILE.read_text(encoding="utf-8")))


@app.route("/", defaults={"path": ""}, methods=["GET"])
@app.route("/<path:path>", methods=["GET"])
def serve_react(path: str):
    if path and (UI_DIST / path).exists():
        return app.send_static_file(path)
    return app.send_static_file("index.html")


def _startup() -> None:
    global _portfolio
    init_db()
    for market in ("us", "bist"):
        results, last_updated = _load_latest_from_db(market)
        if results:
            with _lock:
                _portfolio[market] = results
                _state[market]["last_updated"] = last_updated
            print(f"[api] {market}: {len(results)} hisse DB'den yüklendi (son: {last_updated})")
        else:
            print(f"[api] {market}: DB boş")


if __name__ == "__main__":
    import os
    _startup()
    app.run(host=os.environ.get("FLASK_HOST", "127.0.0.1"), port=5000, debug=False)
