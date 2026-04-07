from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import pandas as pd

from sector import (
    MarketProfile,
    TR_PROFILE,
    US_PROFILE,
    build_sector_maps,
    extract_multiples,
    fetch_info,
    robust_median,
)

CRITICAL_TICKERS = [
    "AKBNK.IS",
    "GARAN.IS",
    "THYAO.IS",
    "TUPRS.IS",
    "BIMAS.IS",
    "ASELS.IS",
    "EREGL.IS",
    "FROTO.IS",
    "TCELL.IS",
    "KCHOL.IS",
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "JPM",
    "XOM",
    "TSLA",
    "BRK.B",
]

OUTPUT_CSV = Path("benchmark_validation_report.csv")
OUTPUT_MD = Path("benchmark_validation_report.md")


class SectorBenchmark(TypedDict):
    sector_pe: Optional[float]
    sector_pb: Optional[float]
    sector_ev_ebitda: Optional[float]
    peer_count: int
    peer_pe_count: int
    peer_pb_count: int
    peer_ev_count: int


class MarketResource(TypedDict):
    profile: MarketProfile
    lookup: Dict[str, str]
    benchmarks: Dict[str, SectorBenchmark]


EMPTY_BENCHMARK: SectorBenchmark = {
    "sector_pe": None,
    "sector_pb": None,
    "sector_ev_ebitda": None,
    "peer_count": 0,
    "peer_pe_count": 0,
    "peer_pb_count": 0,
    "peer_ev_count": 0,
}


def build_sector_lookup(sector_map: Dict[str, List[str]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for sector_name, tickers in sector_map.items():
        for ticker in tickers:
            lookup[ticker] = sector_name
    return lookup


def metric_diff(company_value: Optional[float], sector_value: Optional[float]) -> Optional[float]:
    if company_value is None or sector_value is None or sector_value <= 0:
        return None
    return round((company_value / sector_value - 1) * 100, 2)


def reliability_label(comparable_metric_count: int, expected_metric_count: int, peer_count: int) -> str:
    if expected_metric_count == 0:
        return "low"
    coverage_ratio = comparable_metric_count / expected_metric_count
    if coverage_ratio >= 0.67 and peer_count >= 5:
        return "high"
    if coverage_ratio >= 0.34 and peer_count >= 3:
        return "medium"
    return "low"


def round_or_none(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 2)


def compute_sector_benchmark(sector_tickers: List[str], financial: bool) -> SectorBenchmark:
    pe_values, pb_values, ev_values = [], [], []

    for peer_ticker in sector_tickers:
        info = fetch_info(peer_ticker)
        peer_pe, peer_pb, peer_ev = extract_multiples(info, financial)
        if peer_pe is not None:
            pe_values.append(peer_pe)
        if peer_pb is not None:
            pb_values.append(peer_pb)
        if peer_ev is not None:
            ev_values.append(peer_ev)

    return {
        "sector_pe": round_or_none(robust_median(pe_values)),
        "sector_pb": round_or_none(robust_median(pb_values)),
        "sector_ev_ebitda": round_or_none(robust_median(ev_values)),
        "peer_count": len(sector_tickers),
        "peer_pe_count": len(pe_values),
        "peer_pb_count": len(pb_values),
        "peer_ev_count": len(ev_values),
    }


def prepare_benchmarks(
    sector_map: Dict[str, List[str]],
    profile: MarketProfile,
    target_sectors: List[str],
) -> Dict[str, SectorBenchmark]:
    benchmarks: Dict[str, SectorBenchmark] = {}
    for sector_name in target_sectors:
        financial = sector_name in profile.financial_sectors
        tickers = sector_map.get(sector_name, [])
        benchmarks[sector_name] = compute_sector_benchmark(tickers, financial)
    return benchmarks


def build_market_resources() -> Dict[str, MarketResource]:
    tr_map, us_map = build_sector_maps(auto_classify=False)
    tr_lookup = build_sector_lookup(tr_map)
    us_lookup = build_sector_lookup(us_map)

    tr_sectors = sorted({tr_lookup[t] for t in CRITICAL_TICKERS if t.endswith(".IS") and t in tr_lookup})
    us_sectors = sorted({us_lookup[t] for t in CRITICAL_TICKERS if not t.endswith(".IS") and t in us_lookup})
    return {
        "TR": {
            "profile": TR_PROFILE,
            "lookup": tr_lookup,
            "benchmarks": prepare_benchmarks(tr_map, TR_PROFILE, tr_sectors),
        },
        "US": {
            "profile": US_PROFILE,
            "lookup": us_lookup,
            "benchmarks": prepare_benchmarks(us_map, US_PROFILE, us_sectors),
        },
    }


def build_unmapped_row(as_of: str, ticker: str, market: str) -> Dict[str, Any]:
    return {
        "as_of": as_of,
        "ticker": ticker,
        "market": market,
        "sector": "UNMAPPED",
        "reliability_level": "low",
    }


def count_comparable_metrics(
    company_pe: Optional[float],
    company_pb: Optional[float],
    company_ev: Optional[float],
    benchmark: SectorBenchmark,
) -> int:
    metric_pairs = (
        (company_pe, benchmark.get("sector_pe")),
        (company_pb, benchmark.get("sector_pb")),
        (company_ev, benchmark.get("sector_ev_ebitda")),
    )
    return sum(1 for company_metric, sector_metric in metric_pairs if company_metric is not None and sector_metric is not None)


def build_mapped_row(
    as_of: str,
    ticker: str,
    market: str,
    profile: MarketProfile,
    sector_name: str,
    benchmark: SectorBenchmark,
) -> Dict[str, Any]:
    is_financial = sector_name in profile.financial_sectors
    info = fetch_info(ticker)
    company_pe, company_pb, company_ev = extract_multiples(info, is_financial)
    expected_metric_count = 2 if is_financial else 3
    metric_count = count_comparable_metrics(company_pe, company_pb, company_ev, benchmark)
    peer_count = int(benchmark.get("peer_count") or 0)
    reliability = reliability_label(metric_count, expected_metric_count, peer_count)

    return {
        "as_of": as_of,
        "ticker": ticker,
        "market": market,
        "sector": sector_name,
        "company_pe": round_or_none(company_pe),
        "sector_pe": benchmark.get("sector_pe"),
        "pe_diff_pct": metric_diff(company_pe, benchmark.get("sector_pe")),
        "company_pb": round_or_none(company_pb),
        "sector_pb": benchmark.get("sector_pb"),
        "pb_diff_pct": metric_diff(company_pb, benchmark.get("sector_pb")),
        "company_ev_ebitda": round_or_none(company_ev),
        "sector_ev_ebitda": benchmark.get("sector_ev_ebitda"),
        "ev_ebitda_diff_pct": metric_diff(company_ev, benchmark.get("sector_ev_ebitda")),
        "peer_count": peer_count,
        "comparable_metric_count": metric_count,
        "expected_metric_count": expected_metric_count,
        "reliability_level": reliability,
    }


def build_report_rows() -> List[Dict[str, Any]]:
    market_resources = build_market_resources()
    rows: List[Dict[str, Any]] = []
    as_of = date.today().isoformat()

    for ticker in CRITICAL_TICKERS:
        market = "TR" if ticker.endswith(".IS") else "US"
        resource = market_resources[market]
        profile = resource["profile"]
        lookup = resource["lookup"]
        benchmarks = resource["benchmarks"]
        sector_name = lookup.get(ticker)

        if not sector_name:
            rows.append(build_unmapped_row(as_of, ticker, market))
            continue

        benchmark = benchmarks.get(sector_name, EMPTY_BENCHMARK)
        rows.append(
            build_mapped_row(
                as_of=as_of,
                ticker=ticker,
                market=market,
                profile=profile,
                sector_name=sector_name,
                benchmark=benchmark,
            )
        )
    return rows


def write_markdown(frame: pd.DataFrame) -> None:
    summary = frame["reliability_level"].value_counts().to_dict()
    high_count = int(summary.get("high", 0))
    medium_count = int(summary.get("medium", 0))
    low_count = int(summary.get("low", 0))

    rows: List[str] = [
        f"# Benchmark Validation Report ({date.today().isoformat()})",
        "",
        f"- Total ticker: {len(frame)}",
        f"- High reliability: {high_count}",
        f"- Medium reliability: {medium_count}",
        f"- Low reliability: {low_count}",
        "",
        "| Ticker | Market | Sector | PE Diff % | PB Diff % | EV/EBITDA Diff % | Reliability |",
        "| --- | --- | --- | ---: | ---: | ---: | --- |",
    ]

    for _, report_row in frame.iterrows():
        rows.append(
            "| {ticker} | {market} | {sector} | {pe} | {pb} | {ev} | {rel} |".format(
                ticker=report_row.get("ticker", ""),
                market=report_row.get("market", ""),
                sector=report_row.get("sector", ""),
                pe="" if pd.isna(report_row.get("pe_diff_pct")) else report_row.get("pe_diff_pct"),
                pb="" if pd.isna(report_row.get("pb_diff_pct")) else report_row.get("pb_diff_pct"),
                ev="" if pd.isna(report_row.get("ev_ebitda_diff_pct")) else report_row.get("ev_ebitda_diff_pct"),
                rel=report_row.get("reliability_level", ""),
            )
        )

    OUTPUT_MD.write_text("\n".join(rows), encoding="utf-8")


def main() -> None:
    rows = build_report_rows()
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT_CSV, index=False)
    write_markdown(frame)
    print(f"Kaydedildi -> {OUTPUT_CSV}")
    print(f"Kaydedildi -> {OUTPUT_MD}")
    print(frame[["ticker", "sector", "reliability_level"]].to_string(index=False))


if __name__ == "__main__":
    main()
