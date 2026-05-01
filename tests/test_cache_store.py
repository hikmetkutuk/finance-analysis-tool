from __future__ import annotations

from pathlib import Path

from data import cache_store


def test_save_and_load_latest_cache(tmp_path: Path) -> None:
    original_root = cache_store.CACHE_ROOT
    cache_store.CACHE_ROOT = tmp_path / ".cache"
    try:
        saved = cache_store.save_cache("unit", "TEST.IS", {"value": 42})
        loaded = cache_store.load_latest_cache("unit", "TEST.IS")
        assert loaded is not None
        assert loaded.payload == {"value": 42}
        assert loaded.saved_at == saved.saved_at
    finally:
        cache_store.CACHE_ROOT = original_root
