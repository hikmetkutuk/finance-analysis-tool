from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import pickle
import re
from typing import Any, Optional


CACHE_ROOT = Path(__file__).resolve().parent.parent / ".cache"


@dataclass(frozen=True)
class CachePayload:
    payload: Any
    saved_at: datetime


def _safe_key(key: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", key.strip())
    return normalized or "unknown"


def _latest_path(namespace: str, key: str) -> Path:
    return CACHE_ROOT / namespace / "latest" / f"{_safe_key(key)}.pkl"


def _snapshot_path(namespace: str, key: str, saved_at: datetime) -> Path:
    stamp = saved_at.astimezone(timezone.utc).strftime("%Y-%m-%d")
    return CACHE_ROOT / namespace / "snapshots" / stamp / f"{_safe_key(key)}.pkl"


def _read_pickle(path: Path) -> Optional[CachePayload]:
    if not path.exists():
        return None
    try:
        with path.open("rb") as handle:
            raw = pickle.load(handle)
    except (OSError, pickle.PickleError, EOFError, AttributeError, ValueError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None
    saved_at = raw.get("saved_at")
    payload = raw.get("payload")
    if not isinstance(saved_at, datetime):
        return None
    return CachePayload(payload=payload, saved_at=saved_at)


def load_latest_cache(namespace: str, key: str) -> Optional[CachePayload]:
    return _read_pickle(_latest_path(namespace, key))


def load_fresh_cache(namespace: str, key: str, max_age_seconds: int) -> Optional[CachePayload]:
    cached = load_latest_cache(namespace, key)
    if cached is None:
        return None
    age_seconds = (datetime.now(timezone.utc) - cached.saved_at.astimezone(timezone.utc)).total_seconds()
    if age_seconds > max_age_seconds:
        return None
    return cached


def save_cache(namespace: str, key: str, payload: Any) -> CachePayload:
    saved_at = datetime.now(timezone.utc)
    envelope = {"saved_at": saved_at, "payload": payload}
    latest_path = _latest_path(namespace, key)
    snapshot_path = _snapshot_path(namespace, key, saved_at)
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with latest_path.open("wb") as handle:
        pickle.dump(envelope, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with snapshot_path.open("wb") as handle:
        pickle.dump(envelope, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return CachePayload(payload=payload, saved_at=saved_at)
