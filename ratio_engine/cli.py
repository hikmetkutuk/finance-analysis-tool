import argparse
import logging
from typing import Iterable, List, Optional

from .constants import (
    COLUMNS_ORDER,
    DEFAULT_ERROR_FILE,
    DEFAULT_INPUT_FILE,
    DEFAULT_OUTPUT_FILE,
    MARKET_AUTO,
    MARKET_TR,
    MARKET_US,
    NUMERIC_COLUMNS,
)
from .dependencies import pd
from .service import analyze_symbols

logger = logging.getLogger("ratio")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BIST ve ABD hisseleri icin oran analizi")
    parser.add_argument("--market", choices=[MARKET_AUTO, MARKET_TR, MARKET_US], default=MARKET_AUTO)
    parser.add_argument("--input", default=DEFAULT_INPUT_FILE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--errors", default=DEFAULT_ERROR_FILE)
    return parser.parse_args(list(argv) if argv is not None else None)


def load_symbols(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as file_obj:
        return [line.strip() for line in file_obj if line.strip()]


def write_outputs(rows: List[dict], failed_symbols: List[dict], output_path: str, error_path: str) -> None:
    output_frame = pd.DataFrame(rows)
    output_frame = output_frame[[column for column in COLUMNS_ORDER if column in output_frame.columns]]
    existing_numeric_cols = [column for column in NUMERIC_COLUMNS if column in output_frame.columns]
    if existing_numeric_cols:
        output_frame[existing_numeric_cols] = output_frame[existing_numeric_cols].round(2)
    output_frame.to_excel(output_path, index=False)
    if failed_symbols:
        pd.DataFrame(failed_symbols).to_csv(error_path, index=False)
        logger.warning("Some symbols failed. Details written to %s", error_path)
    logger.info("Process completed: %s", output_path)


def main(argv: Optional[Iterable[str]] = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args(argv)
    symbols = load_symbols(args.input)
    rows, failed_symbols = analyze_symbols(symbols, market=args.market)
    write_outputs(rows, failed_symbols, args.output, args.errors)
    return 0
