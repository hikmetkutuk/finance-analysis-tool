import argparse
import json
import logging
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger("sector")

try:
    curl_request_exceptions = import_module("curl_cffi.requests.exceptions")
    NetworkRequestError = getattr(curl_request_exceptions, "RequestException")
except ModuleNotFoundError:
    NetworkRequestError = OSError

FETCH_ERRORS = (NetworkRequestError, RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError)
INFO_CACHE: dict[str, dict] = {}
SECTOR_FINANCIAL_SERVICES = "Finansal Hizmetler"
SECTOR_ASSIGNMENTS_FILE = Path("sector_assignments.json")


@dataclass(frozen=True)
class MarketProfile:
    market: str
    universe_path: str
    ticker_suffix: str
    other_label: str
    base_sector_map: dict[str, list[str]]
    financial_sectors: set[str]
    classifier_rules: list[tuple[str, tuple[str, ...]]]


BASE_SECTOR_TICKERS_TR = {
    "Banka": [
        "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "VAKBN.IS", "HALKB.IS", "TSKB.IS", "GARAN.IS", "ALBRK.IS"
    ],
    SECTOR_FINANCIAL_SERVICES: [
        "A1CAP.IS", "ISMEN.IS", "GEDIK.IS", "INFO.IS", "UNLU.IS", "QNBTR.IS", "QNBFK.IS", "BRKVY.IS", "VAKFA.IS"
    ],
    "Enerji": [
        "AKSEN.IS", "ENJSA.IS", "ZOREN.IS", "GWIND.IS", "TATEN.IS", "ARFYE.IS", "BESTE.IS", "ECOGR.IS", "AYDEM.IS", "AYEN.IS", "AKENR.IS", "CANTE.IS", "CATES.IS", "BIOEN.IS"
    ],
    "Enerji Ekipman & Taahhüt": [
        "GESAN.IS", "ASTOR.IS", "ALFAS.IS", "CWENE.IS", "EUPWR.IS", "EMKEL.IS", "EKOS.IS", "KONTR.IS", "SMRTG.IS", "YEOTK.IS", "ORGE.IS", "PRKAB.IS", "SAYAS.IS", "GEREL.IS"
    ],
    "Petrol": [
        "PETKM.IS", "TUPRS.IS", "TRENJ.IS", "TRCAS.IS"
    ],
    "Sanayi & Üretim": [
        "BRSAN.IS", "EGEEN.IS", "TRMET.IS", "TRALT.IS", "ENKAI.IS", "AKSA.IS", "GUBRF.IS", "HEKTS.IS", "SASA.IS", "CEMTS.IS", "KCAER.IS", "KRDMD.IS", "ISDMR.IS", "EREGL.IS", "GENKM.IS", "EMPAE.IS", "UCAYM.IS", "FRMPL.IS"
    ],
    "Dayanıklı Tüketim": [
        "ARCLK.IS", "VESTL.IS", "VESBE.IS"
    ],
    "Teknoloji": [
        "ARDYZ.IS", "KFEIN.IS", "NETCD.IS", "DOFRB.IS", "GATEG.IS", "PATEK.IS", "KRONT.IS"
    ],
    "Savunma": [
        "ASELS.IS", "ALTNY.IS", "FORTE.IS", "ONRYT.IS", "KAREL.IS"
    ],
    "Gayrimenkul": [
        "EKGYO.IS", "TRGYO.IS", "KLGYO.IS", "PAGYO.IS", "PSGYO.IS", "LXGYO.IS", "SVGYO.IS", "ZGYO.IS", "ZERGY.IS"
    ],
    "Çimento": [
        "CIMSA.IS", "GOLTS.IS", "BOBET.IS", "LMKDC.IS", "OYAKC.IS", "KONYA.IS", "BUCIM.IS", "AFYON.IS", "NUHCM.IS"
    ],
    "Otomotiv": [
        "TOASO.IS", "FROTO.IS", "DOAS.IS", "OTKAR.IS", "TTRAK.IS"
    ],
    "Perakende": [
        "BIMAS.IS", "MGROS.IS", "SOKM.IS", "TKNSA.IS"
    ],
    "Havacılık": [
        "PGSUS.IS", "THYAO.IS", "TAVHL.IS", "CLEBI.IS"
    ],
    "Turizm": [
        "DOCO.IS", "ATATR.IS", "BLUME.IS"
    ],
    "Sigorta": [
        "ANSGR.IS", "AGESA.IS", "TURSG.IS", "ANHYT.IS"
    ],
    "Gıda": [
        "ULUUN.IS", "ULKER.IS", "KRVGD.IS", "YYLGD.IS", "GOKNR.IS", "OBAMS.IS"
    ],
    "İçecek": [
        "CCOLA.IS", "AEFES.IS", "TBORG.IS", "ELITE.IS"
    ],
    "İlaç & Sağlık": [
        "ECILC.IS", "LKMNH.IS", "MPARK.IS", "SELEC.IS"
    ],
    "Holding & Karma": [
        "KCHOL.IS", "SAHOL.IS", "AGHOL.IS", "ALARK.IS", "DOHOL.IS", "BINHO.IS", "TKFEN.IS", "PAHOL.IS", "MARMR.IS", "DUNYH.IS"
    ],
    "Telekomünikasyon": [
        "TCELL.IS", "TTKOM.IS", "BIGTK.IS"
    ],
}

BASE_SECTOR_TICKERS_US = {
    "Teknoloji": [
        "AAPL", "GOOG", "GOOGL", "MSFT", "META", "PLTR", "ORCL", "ADBE", "CRM", "AMZN", "CSCO", "DELL", "APP", "NET"
    ],
    "Yarı İletken": [
        "QCOM", "AMD", "NVDA", "INTC", "INTL", "AVGO", "SNDK"
    ],
    "E-Ticaret": [
        "BABA"
    ],
    "İletişim & Medya": [
        "DIS", "NFLX"
    ],
    "Sağlık & İlaç": [
        "LLY", "JNJ", "MRK", "UNH", "PFE", "TMO", "NVO"
    ],
    "Finans": [
        "JPM", "WFC", "MA", "V", "BRK.B"
    ],
    "Enerji": [
        "XOM"
    ],
    "Perakende & Tüketim": [
        "MCD", "WMT", "COST", "HD", "KO", "PEP"
    ],
    "Sanayi & Savunma": [
        "BA", "L"
    ],
    "Otomotiv": [
        "TSLA"
    ],
}

TR_CLASSIFIER_RULES = [
    ("Banka", ("bank", "banka", "katilim bank", "depositary bank", "regional bank", "banks-diversified")),
    ("Sigorta", ("insurance", "sigorta", "insur", "reinsurance", "hayat emeklilik")),
    (SECTOR_FINANCIAL_SERVICES, ("financial services", "capital markets", "asset management", "broker", "araci kurum", "factoring", "leasing", "finansal hizmet")),
    ("Gayrimenkul", ("real estate", "gayrimenkul", "reit", "gmyo", "property")),
    ("Enerji Ekipman & Taahhüt", ("electrical equipment", "power equipment", "energy equipment", "engineering", "epc", "contracting", "taahhut", "taahhüt", "transformer", "cable", "inverter", "panel", "solar equipment")),
    ("Enerji", ("utilities", "electric utility", "renewable power", "power generation", "independent power", "enerji", "electricity", "solar", "wind")),
    ("Petrol", ("oil", "gas", "refining", "petroleum", "petrokimya", "petrol")),
    ("Otomotiv", ("auto", "automotive", "vehicle", "trucks", "car", "motor")),
    ("Perakende", ("retail", "discount stores", "supermarket", "grocery", "market")),
    ("Havacılık", ("airline", "air freight", "airport", "havac", "airports")),
    ("Savunma", ("aerospace", "defense", "savunma")),
    ("Teknoloji", ("software", "technology", "internet", "semiconductor", "tech", "yazilim", "bilisim")),
    ("İlaç & Sağlık", ("health", "pharma", "biotech", "drug", "medical", "hospital", "saglik", "ilac")),
    ("İçecek", ("beverage", "brew", "distiller", "soft drinks")),
    ("Gıda", ("food", "packaged foods", "tarim", "agricultural", "dairy", "gida")),
    ("Telekomünikasyon", ("telecom", "wireless", "communication services", "telefon", "mobile")),
    ("Çimento", ("cement", "construction materials", "ready-mix", "cim")),
    ("Dayanıklı Tüketim", ("consumer electronics", "furnishing", "home appliance", "durable", "white goods")),
    ("Turizm", ("travel", "tourism", "hotel", "hospitality", "leisure")),
    ("Holding & Karma", ("holding", "conglomerate", "investment company", "karma")),
]

US_CLASSIFIER_RULES = [
    ("Finans", ("financial services", "capital markets", "asset management", "banks", "insurance", "broker", "credit services")),
    ("Teknoloji", ("software", "internet", "technology", "it services", "communication equipment")),
    ("Yarı İletken", ("semiconductor", "semiconductors", "chip")),
    ("E-Ticaret", ("internet retail", "e-commerce", "online retail")),
    ("İletişim & Medya", ("entertainment", "media", "streaming", "broadcasting", "communication services")),
    ("Sağlık & İlaç", ("health", "pharma", "biotech", "medical", "drug", "life sciences")),
    ("Enerji", ("oil", "gas", "energy", "integrated oil", "exploration")),
    ("Perakende & Tüketim", ("retail", "consumer staples", "restaurants", "beverages", "household")),
    ("Sanayi & Savunma", ("aerospace", "defense", "industrial", "machinery", "transportation")),
    ("Otomotiv", ("auto", "automotive", "vehicle", "ev manufacturer")),
]

TR_PROFILE = MarketProfile(
    market="tr",
    universe_path="hisseler.txt",
    ticker_suffix=".IS",
    other_label="Diğer BIST",
    base_sector_map=BASE_SECTOR_TICKERS_TR,
    financial_sectors={"Banka", "Sigorta", SECTOR_FINANCIAL_SERVICES},
    classifier_rules=TR_CLASSIFIER_RULES,
)

US_PROFILE = MarketProfile(
    market="us",
    universe_path="tickers.txt",
    ticker_suffix=".IS",
    other_label="Diğer ABD",
    base_sector_map=BASE_SECTOR_TICKERS_US,
    financial_sectors={"Finans"},
    classifier_rules=US_CLASSIFIER_RULES,
)

PROFILES = {"tr": TR_PROFILE, "us": US_PROFILE}


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def robust_median(values: Iterable[float]) -> Optional[float]:
    series = pd.Series(list(values), dtype="float64").dropna()
    if series.empty:
        return None
    if series.shape[0] >= 5:
        lower = series.quantile(0.10)
        upper = series.quantile(0.90)
        series = series.clip(lower=lower, upper=upper)
    return round(float(series.median()), 2)


def load_sector_assignments(path: Path = SECTOR_ASSIGNMENTS_FILE) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for market, mapping in raw.items():
        if not isinstance(market, str) or not isinstance(mapping, dict):
            continue
        market_map: dict[str, str] = {}
        for ticker, sector_name in mapping.items():
            if isinstance(ticker, str) and isinstance(sector_name, str) and ticker and sector_name:
                market_map[ticker.upper()] = sector_name
        if market_map:
            normalized[market] = market_map
    return normalized


def save_sector_assignments(assignments: dict[str, dict[str, str]], path: Path = SECTOR_ASSIGNMENTS_FILE) -> None:
    path.write_text(json.dumps(assignments, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def load_universe(path: str, market: str) -> set[str]:
    file_path = Path(path)
    if not file_path.exists():
        return set()
    lines = {line.strip().upper() for line in file_path.read_text(encoding="utf-8").splitlines() if line.strip()}
    if market == "tr":
        return {ticker for ticker in lines if ticker.endswith(".IS")}
    return {ticker for ticker in lines if not ticker.endswith(".IS")}


def fetch_info(ticker: str) -> dict:
    if ticker in INFO_CACHE:
        return INFO_CACHE[ticker]
    try:
        info = yf.Ticker(ticker).info
        info = info if isinstance(info, dict) else {}
    except FETCH_ERRORS as error:
        logger.warning("%s -> %s", ticker, error)
        info = {}
    INFO_CACHE[ticker] = info
    return info


def infer_sector_from_info(info: dict, profile: MarketProfile) -> Optional[str]:
    fields = [
        info.get("sector"),
        info.get("industry"),
        info.get("sectorKey"),
        info.get("industryKey"),
        info.get("longBusinessSummary"),
    ]
    haystack = " ".join(normalize_text(field) for field in fields if field)
    if not haystack:
        return None
    for sector_name, keywords in profile.classifier_rules:
        for keyword in keywords:
            if keyword in haystack:
                return sector_name
    return None


def resolve_universe(profile: MarketProfile) -> set[str]:
    universe = load_universe(profile.universe_path, profile.market)
    if not universe:
        universe = {ticker for tickers in profile.base_sector_map.values() for ticker in tickers}
    return universe


def seed_prepared_map(profile: MarketProfile, universe: set[str]) -> tuple[dict[str, list[str]], set[str]]:
    prepared: dict[str, list[str]] = {}
    used: set[str] = set()
    for sector, tickers in profile.base_sector_map.items():
        filtered = []
        for ticker in tickers:
            if ticker in universe and ticker not in used:
                filtered.append(ticker)
                used.add(ticker)
        if filtered:
            prepared[sector] = filtered
    return prepared, used


def auto_classify_missing_tickers(profile: MarketProfile, universe: set[str], prepared: dict[str, list[str]], used: set[str]) -> None:
    missing = sorted(universe - used)
    for ticker in missing:
        info = fetch_info(ticker)
        inferred_sector = infer_sector_from_info(info, profile)
        if inferred_sector and inferred_sector != profile.other_label:
            prepared.setdefault(inferred_sector, []).append(ticker)
            used.add(ticker)


def append_remaining_bucket(profile: MarketProfile, universe: set[str], prepared: dict[str, list[str]], used: set[str]) -> None:
    remaining = sorted(universe - used)
    if remaining:
        prepared[profile.other_label] = remaining


def apply_cached_assignments(
    profile: MarketProfile,
    universe: set[str],
    prepared: dict[str, list[str]],
    used: set[str],
    assignments: dict[str, dict[str, str]],
) -> None:
    market_assignments = assignments.get(profile.market, {})
    if not market_assignments:
        return
    valid_sectors = set(profile.base_sector_map) | {profile.other_label}
    for ticker in sorted(universe - used):
        sector_name = market_assignments.get(ticker)
        if not sector_name or sector_name not in valid_sectors or sector_name == profile.other_label:
            continue
        prepared.setdefault(sector_name, []).append(ticker)
        used.add(ticker)


def update_assignments_from_prepared(
    profile: MarketProfile,
    prepared: dict[str, list[str]],
    assignments: dict[str, dict[str, str]],
) -> bool:
    market_assignments = assignments.setdefault(profile.market, {})
    changed = False
    for sector_name, tickers in prepared.items():
        if sector_name == profile.other_label:
            continue
        for ticker in tickers:
            previous = market_assignments.get(ticker)
            if previous != sector_name:
                market_assignments[ticker] = sector_name
                changed = True
    return changed


def prepare_sector_map(profile: MarketProfile, auto_classify: bool = False) -> dict[str, list[str]]:
    assignments = load_sector_assignments()
    universe = resolve_universe(profile)
    prepared, used = seed_prepared_map(profile, universe)
    apply_cached_assignments(profile, universe, prepared, used, assignments)
    if auto_classify:
        auto_classify_missing_tickers(profile, universe, prepared, used)
        if update_assignments_from_prepared(profile, prepared, assignments):
            save_sector_assignments(assignments)
    append_remaining_bucket(profile, universe, prepared, used)
    return prepared


def extract_multiples(info: dict, is_financial_sector: bool) -> tuple[Optional[float], Optional[float], Optional[float]]:
    pe = safe_float(info.get("trailingPE"))
    pb = safe_float(info.get("priceToBook"))
    ev = safe_float(info.get("enterpriseValue"))
    ebitda = safe_float(info.get("ebitda"))
    pe = pe if pe is not None and pe > 0 else None
    pb = pb if pb is not None and pb > 0 else None
    if is_financial_sector:
        return pe, pb, None
    ev_ebitda = None
    if ev is not None and ebitda is not None and ev > 0 and ebitda > 0:
        ev_ebitda = ev / ebitda
    return pe, pb, ev_ebitda


def build_sector_row(sector: str, tickers: list[str], profile: MarketProfile) -> dict:
    pe_values, pb_values, ev_ebitda_values, fd_values = [], [], [], []
    valid_ticker_count = 0
    is_financial_sector = sector in profile.financial_sectors
    for ticker in tickers:
        info = fetch_info(ticker)
        pe, pb, ev_ebitda = extract_multiples(info, is_financial_sector)
        enterprise_value = safe_float(info.get("enterpriseValue"))
        if pe is not None:
            pe_values.append(pe)
        if pb is not None:
            pb_values.append(pb)
        if ev_ebitda is not None:
            ev_ebitda_values.append(ev_ebitda)
        if enterprise_value is not None and enterprise_value > 0:
            fd_values.append(enterprise_value)
        if pe is not None or pb is not None or ev_ebitda is not None:
            valid_ticker_count += 1
    return {
        "sector": sector,
        "pe": robust_median(pe_values),
        "pb": robust_median(pb_values),
        "fd": robust_median(fd_values),
        "ev_ebitda": robust_median(ev_ebitda_values),
        "ticker_count": valid_ticker_count,
        "ticker_count_total": len(tickers),
        "pe_count": len(pe_values),
        "pb_count": len(pb_values),
        "fd_count": len(fd_values),
        "ev_ebitda_count": len(ev_ebitda_values),
    }


def calculate_sector_multiples(sector_tickers: dict[str, list[str]], filename: str, profile: MarketProfile) -> None:
    rows = [build_sector_row(sector, tickers, profile) for sector, tickers in sector_tickers.items()]
    result_frame = pd.DataFrame(rows)
    result_frame.to_csv(filename, index=False)
    logger.info("Kaydedildi -> %s", filename)


def build_sector_maps(auto_classify: bool = False) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    tr_map = prepare_sector_map(TR_PROFILE, auto_classify=auto_classify)
    us_map = prepare_sector_map(US_PROFILE, auto_classify=auto_classify)
    return tr_map, us_map


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sektorel carpani hesaplama")
    parser.add_argument("--market", choices=["all", "tr", "us"], default="all")
    parser.add_argument("--no-auto-classify", action="store_true")
    return parser.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()
    auto_classify = not args.no_auto_classify
    tr_map, us_map = build_sector_maps(auto_classify=auto_classify)
    if args.market in ("all", "tr"):
        calculate_sector_multiples(tr_map, "sector_multiples_tr.csv", TR_PROFILE)
    if args.market in ("all", "us"):
        calculate_sector_multiples(us_map, "sector_multiples_us.csv", US_PROFILE)


sector_tickers_tr, sector_tickers_us = build_sector_maps(auto_classify=False)

if __name__ == "__main__":
    main()
