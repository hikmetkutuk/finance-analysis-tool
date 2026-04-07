from ratio_engine.cli import main
from ratio_engine.service import analyze_symbols, get_stock_data

__all__ = ["main", "analyze_symbols", "get_stock_data"]

if __name__ == "__main__":
    raise SystemExit(main())
