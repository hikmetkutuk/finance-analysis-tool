from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Optional, Sequence

import pandas as pd
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.comments import Comment
from openpyxl.utils.cell import range_boundaries
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import TableColumn

from data.macro_config import load_macro_config


DEFAULT_TEMPLATE_PATH = Path("data/report_template.xlsx")
CODE_COLUMN = "Kod"
SECTOR_COLUMN = "Sektör"
INDEX_COLUMN = "Endeks"
VALUE_COLUMN = "Değer"
INDEX_XU100 = "XU100"
INDEX_XUTUM = "XUTUM"
INDEX_US = "US"
INA_VALUE_COLUMN = "Profesyonel Değer"
SHEET_HISSE = "Hisse"
SHEET_PUAN = "Puan"
SHEET_ENDEKS = INDEX_COLUMN
SHEET_SEKTOR = SECTOR_COLUMN
SHEET_VARS = "Vars"
SHEET_RASYO = "Rasyo"
OUTPUT_SHEETS = (SHEET_HISSE, SHEET_PUAN, SHEET_ENDEKS, SHEET_SEKTOR, SHEET_VARS, SHEET_RASYO)
VALUE_NUMBER_FORMAT = "#,##0.00"
PERCENT_NUMBER_FORMAT = "0.00%"

PUAN_CODE = "1-Kod"
PUAN_NAME = "2-İsim"
PUAN_EBITDA = "3-FAVÖK"
PUAN_ROE = "4-Özs. Kar. (ROE) (%) Yıllık"
PUAN_EV_EBITDA = "5-FD/ FAVÖK"
PUAN_PCF = "6-F/NA"
PUAN_PE = "7-FK"
PUAN_EPS = "8-HBK"
PUAN_PB = "9-PD / DD"
PUAN_PS = "10-PD / NS"
PUAN_BETA = "11-Beta"
PUAN_ASSET_GROWTH = "12-Aktif Büyüme"
PUAN_NET_INCOME_GROWTH = "13-Net Kar Büyüme(Yıllık)"
PUAN_NET_INCOME = "14-NDK(Yıllık)"
PUAN_OPERATING_INCOME = "15-EFK(Yıllık)"
PUAN_EQUITY = "16-Özkaynaklar"
PUAN_DEBT_SOURCE = "17-Borç Kaynak"
PUAN_PAID_IN_CAPITAL = "18-HÖS"
PUAN_NET_WORKING_CAPITAL = "19-NİS"
PUAN_NET_DEBT_TO_EBITDA = "20-NB / FAVÖK (Yıllık) (%)"

RASYO_STOCK = "Hisse"
RASYO_CURRENT_RATIO = "Cari Oran"
RASYO_QUICK_RATIO = "Likit Oran"
RASYO_CASH_RATIO = "Nakit Oran"
RASYO_ROE = "Özsermaye Karlılığı (ROE) (%) Yıllık"
RASYO_PE = "FK - Fiyat Kazanç (Dönem Sonu)"
RASYO_PB = "PD / DD"
RASYO_EBITDA_GROWTH = "FAVÖK Büyüme (%) (Yıllık)"
RASYO_PEG = "Peg Oranı"
RASYO_ROIC = "Roic"
RASYO_ASSET_TURNOVER = "Aktif Devir Hızı"
RASYO_SCORE = "Oran"

HISSE_PRICE = "Fiyat"
HISSE_PE = "FK"
HISSE_PB = "PD/DD"
HISSE_NIS = "Nis"
HISSE_RATIO = "Rasyo"
HISSE_AVERAGE = "D. Ort"
HISSE_UPSIDE = "GP %"

SECTOR_PB = RASYO_PB
SECTOR_PE = "F/K"
SECTOR_FD = "FD"
SECTOR_EV_EBITDA = "Firma Değeri/Favök"

PUAN_COLUMNS = (
    PUAN_CODE,
    PUAN_NAME,
    PUAN_EBITDA,
    PUAN_ROE,
    PUAN_EV_EBITDA,
    PUAN_PCF,
    PUAN_PE,
    PUAN_EPS,
    PUAN_PB,
    PUAN_PS,
    PUAN_BETA,
    PUAN_ASSET_GROWTH,
    PUAN_NET_INCOME_GROWTH,
    PUAN_NET_INCOME,
    PUAN_OPERATING_INCOME,
    PUAN_EQUITY,
    PUAN_DEBT_SOURCE,
    PUAN_PAID_IN_CAPITAL,
    PUAN_NET_WORKING_CAPITAL,
    PUAN_NET_DEBT_TO_EBITDA,
)

RASYO_COLUMNS = (
    RASYO_STOCK,
    RASYO_CURRENT_RATIO,
    RASYO_QUICK_RATIO,
    RASYO_CASH_RATIO,
    RASYO_ROE,
    RASYO_PE,
    RASYO_PB,
    RASYO_EBITDA_GROWTH,
    RASYO_PEG,
    RASYO_ROIC,
    RASYO_ASSET_TURNOVER,
    RASYO_SCORE,
)

HISSE_COLUMNS = (
    CODE_COLUMN,
    SECTOR_COLUMN,
    INDEX_COLUMN,
    HISSE_PRICE,
    HISSE_PE,
    HISSE_PB,
    HISSE_NIS,
    HISSE_RATIO,
    "D1",
    "D2",
    "D3",
    "D4",
    "D5",
    "D6",
    "D7",
    "D8",
    "D9",
    "D10",
    "D11",
    "D12",
    HISSE_AVERAGE,
    HISSE_UPSIDE,
)

HISSE_HEADER_COMMENTS = {
    "D1": "S(F/K) * HBK",
    "D2": "EFK * 10 / HOS",
    "D3": "NDK * 10 / HOS",
    "D4": "(Ozkaynaklar / HOS) * S(PD/DD)",
    "D5": "Ozkaynaklar / HOS",
    "D6": "HBK * (1 + Aktif Buyume / 100) * FK",
    "D7": "((FAVOK * S(FD/FAVOK)) - Net Borc) / HOS",
    "D8": "(HBK * S(F/K)) / 2Y Tahvil",
    "D9": "(EFK * (1 + terminal_growth) / (AOSM - terminal_growth)) / HOS",
    "D10": "(NDK * (1 + terminal_growth) / (AOSM - terminal_growth)) / HOS",
    "D11": "DCF/INA profesyonel deger. Pozitif olmayan degerler bos birakilir.",
    "D12": "(Ozkaynaklar / HOS) * ((ROE - terminal_growth) / (Ozkaynak Maliyeti - terminal_growth))",
}


@dataclass(frozen=True)
class MacroRates:
    two_year_bond: Optional[float]
    market_premium: Optional[float]
    terminal_growth: Optional[float]
    cost_of_debt: Optional[float]
    tax_rate: Optional[float]
    risk_free_rate: Optional[float]


@dataclass(frozen=True)
class RowLookups:
    valuation: pd.DataFrame
    puan: pd.DataFrame
    rasyo: pd.DataFrame
    endeks: pd.DataFrame
    sektor: pd.DataFrame
    ina: pd.DataFrame


@dataclass(frozen=True)
class HisseInputs:
    code: str
    sector_name: str
    index_name: str
    price: Optional[float]
    company_pe: Optional[float]
    company_pb: Optional[float]
    nis_sign: str
    ratio_score: Optional[float]
    sector_pe: Optional[float]
    sector_pb: Optional[float]
    sector_ev_ebitda: Optional[float]
    eps: Optional[float]
    roe: Optional[float]
    beta: Optional[float]
    debt_ratio: Optional[float]
    net_income: Optional[float]
    operating_income: Optional[float]
    equity: Optional[float]
    paid_in_capital: Optional[float]
    ebitda: Optional[float]
    net_debt: float
    asset_growth: Optional[float]
    dcf_value: Optional[float]

SHEET_UPDATES_Q2_2026_XU100_ADD = {"CVKMD", "EUREN", "PAHOL", "PSGYO", "SARKY"}
SHEET_UPDATES_Q2_2026_XU100_REMOVE = {"EGEEN", "KCAER", "LINK", "TTRAK", "YEOTK"}


def _round_or_none(value: Any, digits: int = 2) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _positive_or_none(value: Any) -> Optional[float]:
    number = _safe_float(value)
    if number is None or number <= 0:
        return None
    return number


def _normalized_code(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    code = str(value).strip().upper()
    return code[:-3] if code.endswith(".IS") else code


def _safe_divide(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    try:
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return None


def _rate_decimal(value: Any) -> Optional[float]:
    rate = _safe_float(value)
    if rate is None:
        return None
    return rate / 100.0 if abs(rate) > 1 else rate


def _debt_weight_from_debt_source(value: Any) -> Optional[float]:
    debt_source = _rate_decimal(value)
    if debt_source is None:
        return None
    denominator = 1.0 + debt_source
    if denominator == 0:
        return None
    return max(0.0, min(1.0, debt_source / denominator))


def _discount_rate(
    debt_ratio: Optional[float],
    beta: Optional[float],
    cost_of_debt: Optional[float],
    tax_rate: Optional[float],
    risk_free_rate: Optional[float],
    market_premium: Optional[float],
) -> Optional[float]:
    if cost_of_debt is None or tax_rate is None or risk_free_rate is None or market_premium is None:
        return None
    normalized_debt_ratio = debt_ratio if debt_ratio is not None else 0.0
    equity_ratio = 1.0 - normalized_debt_ratio
    normalized_beta = beta if beta is not None else 1.0
    cost_of_equity = risk_free_rate + (normalized_beta * market_premium)
    after_tax_debt_cost = cost_of_debt * (1.0 - tax_rate)
    return (after_tax_debt_cost * normalized_debt_ratio) + (cost_of_equity * equity_ratio)


def _cost_of_equity(
    beta: Optional[float],
    risk_free_rate: Optional[float],
    market_premium: Optional[float],
) -> Optional[float]:
    if risk_free_rate is None or market_premium is None:
        return None
    normalized_beta = beta if beta is not None else 1.0
    return risk_free_rate + (normalized_beta * market_premium)


def _roe_justified_pb_value(
    book_value_per_share: Optional[float],
    roe: Optional[float],
    cost_of_equity: Optional[float],
    terminal_growth: Optional[float],
) -> Optional[float]:
    if (
        book_value_per_share is None
        or roe is None
        or cost_of_equity is None
        or terminal_growth is None
        or cost_of_equity <= terminal_growth
    ):
        return None
    justified_pb = (roe - terminal_growth) / (cost_of_equity - terminal_growth)
    if justified_pb <= 0:
        return None
    return book_value_per_share * justified_pb


def _mean_nonempty(values: Iterable[Any]) -> Optional[float]:
    numeric_values = [float(value) for value in values if _safe_float(value) is not None]
    if not numeric_values:
        return None
    return mean(numeric_values)


def _median_or_none(series: pd.Series) -> Optional[float]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return None
    return _round_or_none(numeric.median())


def _column_index(columns: Sequence[str]) -> pd.Index:
    return pd.Index(columns)


def _clear_sheet(ws, start_row: int, start_col: int, end_col: Optional[int] = None) -> None:
    last_col = end_col if end_col is not None else ws.max_column
    for row in ws.iter_rows(min_row=start_row, max_row=ws.max_row, min_col=start_col, max_col=last_col):
        for cell in row:
            if isinstance(cell, MergedCell):
                continue
            cell.value = None


def _unmerge_sheet(ws) -> None:
    for merged_range in tuple(ws.merged_cells.ranges):
        ws.unmerge_cells(str(merged_range))


def _write_table(ws, frame: pd.DataFrame, header_row: int = 1, first_col: int = 1, include_header: bool = True) -> None:
    row_index = header_row
    if include_header:
        for col_offset, column_name in enumerate(frame.columns, start=first_col):
            ws.cell(row=row_index, column=col_offset).value = column_name
        row_index += 1
    for _, row in frame.iterrows():
        for col_offset, column_name in enumerate(frame.columns, start=first_col):
            value = row[column_name]
            ws.cell(row=row_index, column=col_offset).value = None if pd.isna(value) else value
        row_index += 1


def _sync_excel_table(ws, table_name: str, columns: Sequence[str], header_row: int, row_count: int) -> None:
    if table_name not in ws.tables:
        return
    table = ws.tables[table_name]
    end_col = get_column_letter(len(columns))
    end_row = max(header_row + row_count, header_row + 1)
    table.ref = f"A{header_row}:{end_col}{end_row}"
    table.tableColumns = [
        TableColumn(id=index, name=str(column_name))
        for index, column_name in enumerate(columns, start=1)
    ]
    if table.autoFilter is not None:
        table.autoFilter.ref = table.ref


def _apply_header_comments(ws, columns: Sequence[str], comments: dict[str, str], header_row: int) -> None:
    for column_index, column_name in enumerate(columns, start=1):
        comment_text = comments.get(column_name)
        if comment_text is None:
            continue
        ws.cell(row=header_row, column=column_index).comment = Comment(comment_text, "finance-analysis-tool")


def _remove_conditional_formatting_for_columns(ws, column_indexes: set[int]) -> None:
    retained_rules = []
    cf_rules = getattr(ws.conditional_formatting, "_cf_rules")
    for conditional_range, rules in cf_rules.items():
        keep_range = True
        for cell_range in conditional_range.sqref.ranges:
            min_col, _, max_col, _ = range_boundaries(str(cell_range))
            if any(min_col <= column_index <= max_col for column_index in column_indexes):
                keep_range = False
                break
        if keep_range:
            retained_rules.append((conditional_range, rules))

    cf_rules.clear()
    for conditional_range, rules in retained_rules:
        cf_rules[conditional_range] = rules


def _apply_hisse_number_formats(ws, columns: Sequence[str], header_row: int, row_count: int) -> None:
    headers = {column_name: index for index, column_name in enumerate(columns, start=1)}
    first_data_row = header_row + 1
    last_data_row = header_row + row_count

    value_columns = tuple(f"D{index}" for index in range(1, 13)) + (HISSE_AVERAGE,)
    for column_name in value_columns:
        column_index = headers.get(column_name)
        if column_index is None:
            continue
        for row_index in range(first_data_row, last_data_row + 1):
            cell = ws.cell(row=row_index, column=column_index)
            cell.number_format = VALUE_NUMBER_FORMAT
            if column_name == "D12":
                cell.font = copy(ws.cell(row=row_index, column=headers["D11"]).font)

    gp_column = headers.get(HISSE_UPSIDE)
    if gp_column is not None:
        for row_index in range(first_data_row, last_data_row + 1):
            ws.cell(row=row_index, column=gp_column).number_format = PERCENT_NUMBER_FORMAT

    d12_column = headers.get("D12")
    d_ort_column = headers.get(HISSE_AVERAGE)
    affected_columns = {column for column in (d12_column, d_ort_column) if column is not None}
    _remove_conditional_formatting_for_columns(ws, affected_columns)


def _keep_only_sheets(workbook, sheet_names: Sequence[str]) -> None:
    keep = set(sheet_names)
    for sheet_name in tuple(workbook.sheetnames):
        if sheet_name not in keep:
            del workbook[sheet_name]
    for target_index, sheet_name in enumerate(sheet_names):
        current_index = workbook.sheetnames.index(sheet_name)
        workbook.move_sheet(workbook[sheet_name], offset=target_index - current_index)


def _load_template_index_map(template_path: Path) -> dict[str, str]:
    workbook = load_workbook(template_path, data_only=False)
    ws = workbook[SHEET_ENDEKS]
    index_map: dict[str, str] = {}
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=3, values_only=True):
        code = row[0]
        index_name = row[2]
        if isinstance(code, str) and code.strip() and isinstance(index_name, str) and index_name.strip():
            index_map[code.strip().upper()] = index_name.strip()
    workbook.close()
    return index_map


def _current_xu100_set(template_path: Path) -> set[str]:
    base_map = _load_template_index_map(template_path)
    current = {code for code, index_name in base_map.items() if index_name == INDEX_XU100}
    current.update(SHEET_UPDATES_Q2_2026_XU100_ADD)
    current.difference_update(SHEET_UPDATES_Q2_2026_XU100_REMOVE)
    return current


def _sector_from_valuation_lookup(valuation_lookup: pd.DataFrame, code: str) -> str:
    if valuation_lookup.empty or code not in valuation_lookup.index:
        return ""
    return str(valuation_lookup.loc[code].get(SECTOR_COLUMN, "") or "")


def _ticker_index_name(ticker: str, code: str, xu100_codes: set[str]) -> str:
    if not ticker.upper().endswith(".IS"):
        return INDEX_US
    return INDEX_XU100 if code in xu100_codes else INDEX_XUTUM


def build_endeks_frame(
    tickers: list[str],
    valuation_frame: pd.DataFrame,
    template_path: Path,
) -> pd.DataFrame:
    xu100_codes = _current_xu100_set(template_path)
    valuation_lookup = valuation_frame.set_index(CODE_COLUMN) if not valuation_frame.empty and CODE_COLUMN in valuation_frame.columns else pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        code = _normalized_code(ticker)
        sector_name = _sector_from_valuation_lookup(valuation_lookup, code)
        index_name = _ticker_index_name(ticker, code, xu100_codes)
        rows.append({CODE_COLUMN: code, SECTOR_COLUMN: sector_name, INDEX_COLUMN: index_name})
    return pd.DataFrame(rows, columns=_column_index((CODE_COLUMN, SECTOR_COLUMN, INDEX_COLUMN)))


def build_sector_frame(endeks_frame: pd.DataFrame, puan_frame: pd.DataFrame) -> pd.DataFrame:
    columns = (SECTOR_COLUMN, SECTOR_PB, SECTOR_PE, SECTOR_FD, SECTOR_EV_EBITDA)
    if endeks_frame.empty or puan_frame.empty:
        return pd.DataFrame(columns=_column_index(columns))

    merged = endeks_frame.merge(puan_frame, left_on=CODE_COLUMN, right_on=PUAN_CODE, how="left")
    rows: list[dict[str, Any]] = []
    for sector_name, sector_slice in merged.groupby(SECTOR_COLUMN, dropna=False):
        fd_series = (
            pd.to_numeric(sector_slice[PUAN_EV_EBITDA], errors="coerce")
            * pd.to_numeric(sector_slice[PUAN_EBITDA], errors="coerce")
        ).dropna()
        rows.append(
            {
                SECTOR_COLUMN: sector_name or "",
                SECTOR_PB: _median_or_none(sector_slice[PUAN_PB]),
                SECTOR_PE: _median_or_none(sector_slice[PUAN_PE]),
                SECTOR_FD: _median_or_none(fd_series),
                SECTOR_EV_EBITDA: _median_or_none(sector_slice[PUAN_EV_EBITDA]),
            }
        )
    return pd.DataFrame(rows, columns=_column_index(columns))


def build_vars_frame() -> pd.DataFrame:
    config = load_macro_config()["tr"]
    risk_free = float(config["risk_free_rate"])
    bond_yield_2 = float(config["bond_yield_2"])
    cost_of_debt = float(config["cost_of_debt"])
    market_premium = float(config["market_premium"])
    sovereign_spread = max(bond_yield_2 - risk_free, 0.0)
    five_year_yield = risk_free + sovereign_spread
    ten_year_yield = risk_free
    rows = [
        {"Tür": " 2Tahvil", VALUE_COLUMN: bond_yield_2},
        {"Tür": " 5Tahvil", VALUE_COLUMN: five_year_yield},
        {"Tür": "10Tahvil", VALUE_COLUMN: ten_year_yield},
        {"Tür": "K. Vergisi", VALUE_COLUMN: float(config["tax_rate"])},
        {"Tür": "Faiz Oranı", VALUE_COLUMN: cost_of_debt},
        {"Tür": "Risksiz Faiz", VALUE_COLUMN: risk_free},
        {"Tür": "CDS 5(Ülke Riski)", VALUE_COLUMN: sovereign_spread},
        {"Tür": "Borçlanma Maliyeti", VALUE_COLUMN: cost_of_debt},
        {"Tür": "Piyasa Risk Primi", VALUE_COLUMN: market_premium},
    ]
    return pd.DataFrame(rows, columns=_column_index(("Tür", VALUE_COLUMN)))


def build_puan_frame(financials_frame: pd.DataFrame) -> pd.DataFrame:
    if financials_frame.empty:
        return pd.DataFrame(columns=_column_index(PUAN_COLUMNS))
    renamed = financials_frame.rename(
        columns={
            "Symbol": PUAN_CODE,
            "Name": PUAN_NAME,
            "EBITDA": PUAN_EBITDA,
            "ROE (%) Annual": PUAN_ROE,
            "EV/EBITDA": PUAN_EV_EBITDA,
            "P/CF": PUAN_PCF,
            "P/E": PUAN_PE,
            "EPS": PUAN_EPS,
            "P/B": PUAN_PB,
            "P/S": PUAN_PS,
            "Beta": PUAN_BETA,
            "Asset Growth (%)": PUAN_ASSET_GROWTH,
            "Net Income Growth (Annual, %)": PUAN_NET_INCOME_GROWTH,
            "Net Income": PUAN_NET_INCOME,
            "Operating Income": PUAN_OPERATING_INCOME,
            "Shareholders' Equity": PUAN_EQUITY,
            "Debt-to-Assets Ratio": PUAN_DEBT_SOURCE,
            "Paid-in Capital": PUAN_PAID_IN_CAPITAL,
            "Net Working Capital": PUAN_NET_WORKING_CAPITAL,
            "Net Debt/EBITDA(Annual, %)": PUAN_NET_DEBT_TO_EBITDA,
        }
    )
    return renamed.reindex(columns=_column_index(PUAN_COLUMNS))


def _between(value: Any, lower: float, upper: float) -> Optional[bool]:
    number = _safe_float(value)
    if number is None:
        return None
    return lower < number < upper


def _greater_than(value: Any, threshold: float) -> Optional[bool]:
    number = _safe_float(value)
    if number is None:
        return None
    return number > threshold


def _ratio_score(row: pd.Series) -> Optional[float]:
    checks = [
        _between(row.get(RASYO_CURRENT_RATIO), 1, 2),
        _between(row.get(RASYO_QUICK_RATIO), 1, 2),
        _between(row.get(RASYO_CASH_RATIO), 0.2, 1),
        _greater_than(row.get(RASYO_ROE), 15),
        _between(row.get(RASYO_PE), 0, 20),
        _between(row.get(RASYO_PB), 0, 2),
        _greater_than(row.get(RASYO_EBITDA_GROWTH), 10),
        _between(row.get(RASYO_PEG), 0, 1),
        _greater_than(row.get(RASYO_ROIC), 10),
        _greater_than(row.get(RASYO_ASSET_TURNOVER), 1),
    ]
    present = [check for check in checks if check is not None]
    if not present:
        return None
    return round(sum(1 for check in present if check) / len(present), 4)


def build_rasyo_frame(ratio_frame: pd.DataFrame) -> pd.DataFrame:
    if ratio_frame.empty:
        return pd.DataFrame(columns=_column_index(RASYO_COLUMNS))
    renamed = ratio_frame.rename(
        columns={
            HISSE_PE: RASYO_PE,
            HISSE_PB: RASYO_PB,
            "PEG Oranı": RASYO_PEG,
            "ROIC (%)": RASYO_ROIC,
            RASYO_STOCK: RASYO_STOCK,
        }
    )
    renamed[RASYO_SCORE] = renamed.apply(_ratio_score, axis=1)
    return renamed.reindex(columns=_column_index(RASYO_COLUMNS))


def _load_macro_rates() -> MacroRates:
    macro_config = load_macro_config()["tr"]
    return MacroRates(
        two_year_bond=_rate_decimal(macro_config.get("bond_yield_2")),
        market_premium=_rate_decimal(macro_config.get("market_premium")),
        terminal_growth=_rate_decimal(macro_config.get("terminal_growth")),
        cost_of_debt=_rate_decimal(macro_config.get("cost_of_debt")),
        tax_rate=_rate_decimal(macro_config.get("tax_rate")),
        risk_free_rate=_rate_decimal(macro_config.get("risk_free_rate")),
    )


def _empty_series() -> pd.Series:
    return pd.Series(dtype="object")


def _lookup_row(frame: pd.DataFrame, key: str) -> pd.Series:
    if frame.empty or key not in frame.index:
        return _empty_series()
    row = frame.loc[key]
    if isinstance(row, pd.DataFrame):
        return row.iloc[-1]
    return row


def _build_rasyo_lookup(rasyo_frame: pd.DataFrame) -> pd.DataFrame:
    if rasyo_frame.empty or RASYO_STOCK not in rasyo_frame.columns:
        return pd.DataFrame()
    rasyo_indexed = rasyo_frame.copy()
    rasyo_indexed["_Kod"] = rasyo_indexed[RASYO_STOCK].apply(_normalized_code)
    return rasyo_indexed.drop_duplicates(subset=["_Kod"], keep="last").set_index("_Kod")


def _build_row_lookups(
    valuation_frame: pd.DataFrame,
    puan_frame: pd.DataFrame,
    rasyo_frame: pd.DataFrame,
    endeks_frame: pd.DataFrame,
    sektor_frame: pd.DataFrame,
    ina_frame: pd.DataFrame,
) -> RowLookups:
    return RowLookups(
        valuation=valuation_frame.set_index(CODE_COLUMN) if not valuation_frame.empty else pd.DataFrame(),
        puan=puan_frame.set_index(PUAN_CODE) if not puan_frame.empty else pd.DataFrame(),
        rasyo=_build_rasyo_lookup(rasyo_frame),
        endeks=endeks_frame.set_index(CODE_COLUMN) if not endeks_frame.empty else pd.DataFrame(),
        sektor=sektor_frame.set_index(SECTOR_COLUMN) if not sektor_frame.empty else pd.DataFrame(),
        ina=ina_frame.set_index(CODE_COLUMN) if not ina_frame.empty and CODE_COLUMN in ina_frame.columns else pd.DataFrame(),
    )


def _nis_sign(value: Any) -> str:
    nis_value = _safe_float(value)
    if nis_value is None or nis_value == 0:
        return ""
    return "+" if nis_value > 0 else "-"


def _net_debt_from_ratio(ebitda: Optional[float], net_debt_to_ebitda: Optional[float]) -> float:
    if ebitda is None or net_debt_to_ebitda is None:
        return 0.0
    return ebitda * net_debt_to_ebitda


def _hisse_inputs(ticker: str, lookups: RowLookups) -> HisseInputs:
    code = _normalized_code(ticker)
    valuation_row = _lookup_row(lookups.valuation, code)
    puan_row = _lookup_row(lookups.puan, code)
    rasyo_row = _lookup_row(lookups.rasyo, code)
    endeks_row = _lookup_row(lookups.endeks, code)
    ina_row = _lookup_row(lookups.ina, code)
    sector_name = str(endeks_row.get(SECTOR_COLUMN, valuation_row.get(SECTOR_COLUMN, "")) or "")
    sektor_row = _lookup_row(lookups.sektor, sector_name)
    ebitda = _safe_float(puan_row.get(PUAN_EBITDA))
    net_debt_to_ebitda = _rate_decimal(puan_row.get(PUAN_NET_DEBT_TO_EBITDA))
    index_default = INDEX_US if not ticker.upper().endswith(".IS") else INDEX_XUTUM
    return HisseInputs(
        code=code,
        sector_name=sector_name,
        index_name=str(endeks_row.get(INDEX_COLUMN, index_default) or index_default),
        price=_safe_float(valuation_row.get("Güncel Fiyat")),
        company_pe=_safe_float(puan_row.get(PUAN_PE)),
        company_pb=_safe_float(puan_row.get(PUAN_PB)),
        nis_sign=_nis_sign(puan_row.get(PUAN_NET_WORKING_CAPITAL)),
        ratio_score=_safe_float(rasyo_row.get(RASYO_SCORE)),
        sector_pe=_safe_float(sektor_row.get(SECTOR_PE)),
        sector_pb=_safe_float(sektor_row.get(SECTOR_PB)),
        sector_ev_ebitda=_safe_float(sektor_row.get(SECTOR_EV_EBITDA)),
        eps=_safe_float(puan_row.get(PUAN_EPS)),
        roe=_rate_decimal(puan_row.get(PUAN_ROE)),
        beta=_safe_float(puan_row.get(PUAN_BETA)),
        debt_ratio=_debt_weight_from_debt_source(puan_row.get(PUAN_DEBT_SOURCE)),
        net_income=_safe_float(puan_row.get(PUAN_NET_INCOME)),
        operating_income=_safe_float(puan_row.get(PUAN_OPERATING_INCOME)),
        equity=_safe_float(puan_row.get(PUAN_EQUITY)),
        paid_in_capital=_safe_float(puan_row.get(PUAN_PAID_IN_CAPITAL)),
        ebitda=ebitda,
        net_debt=_net_debt_from_ratio(ebitda, net_debt_to_ebitda),
        asset_growth=_safe_float(puan_row.get(PUAN_ASSET_GROWTH)),
        dcf_value=_positive_or_none(ina_row.get(INA_VALUE_COLUMN)),
    )


def _terminal_value_per_share(
    base_value: Optional[float],
    paid_in_capital: Optional[float],
    discount_rate: Optional[float],
    terminal_growth: Optional[float],
) -> Optional[float]:
    if discount_rate is None or terminal_growth is None:
        return None
    numerator = base_value * (1 + terminal_growth) if base_value is not None else None
    total_value = _safe_divide(numerator, discount_rate - terminal_growth)
    return _safe_divide(total_value, paid_in_capital)


def _valuation_points(inputs: HisseInputs, macro_rates: MacroRates) -> dict[str, Optional[float]]:
    book_value_per_share = _safe_divide(inputs.equity, inputs.paid_in_capital)
    enterprise_value = None
    if inputs.ebitda is not None and inputs.sector_ev_ebitda is not None:
        enterprise_value = inputs.ebitda * inputs.sector_ev_ebitda
    discount_rate = _discount_rate(
        debt_ratio=inputs.debt_ratio,
        beta=inputs.beta,
        cost_of_debt=macro_rates.cost_of_debt,
        tax_rate=macro_rates.tax_rate,
        risk_free_rate=macro_rates.risk_free_rate,
        market_premium=macro_rates.market_premium,
    )
    cost_of_equity = _cost_of_equity(
        beta=inputs.beta,
        risk_free_rate=macro_rates.risk_free_rate,
        market_premium=macro_rates.market_premium,
    )
    d6 = None
    if inputs.eps is not None and inputs.asset_growth is not None and inputs.company_pe is not None:
        d6 = inputs.eps * (1 + inputs.asset_growth / 100.0) * inputs.company_pe
    d1 = None
    if inputs.sector_pe is not None and inputs.eps is not None:
        d1 = inputs.sector_pe * inputs.eps
    d2_numerator = inputs.operating_income * 10 if inputs.operating_income is not None else None
    d3_numerator = inputs.net_income * 10 if inputs.net_income is not None else None
    d4 = None
    if book_value_per_share is not None and inputs.sector_pb is not None:
        d4 = book_value_per_share * inputs.sector_pb
    d7_numerator = enterprise_value - inputs.net_debt if enterprise_value is not None else None
    d8_numerator = None
    if inputs.eps is not None and inputs.sector_pe is not None:
        d8_numerator = inputs.eps * inputs.sector_pe
    return {
        "D1": d1,
        "D2": _safe_divide(d2_numerator, inputs.paid_in_capital),
        "D3": _safe_divide(d3_numerator, inputs.paid_in_capital),
        "D4": d4,
        "D5": book_value_per_share,
        "D6": d6,
        "D7": _safe_divide(d7_numerator, inputs.paid_in_capital),
        "D8": _safe_divide(d8_numerator, macro_rates.two_year_bond),
        "D9": _terminal_value_per_share(inputs.operating_income, inputs.paid_in_capital, discount_rate, macro_rates.terminal_growth),
        "D10": _terminal_value_per_share(inputs.net_income, inputs.paid_in_capital, discount_rate, macro_rates.terminal_growth),
        "D11": inputs.dcf_value,
        "D12": _roe_justified_pb_value(
            book_value_per_share=book_value_per_share,
            roe=inputs.roe,
            cost_of_equity=cost_of_equity,
            terminal_growth=macro_rates.terminal_growth,
        ),
    }


def _hisse_output_row(inputs: HisseInputs, values: dict[str, Optional[float]]) -> dict[str, Any]:
    avg_fair = _mean_nonempty(values.values())
    gp_pct = None
    if avg_fair is not None and inputs.price not in (None, 0):
        gp_pct = (avg_fair - inputs.price) / inputs.price
    return {
        CODE_COLUMN: inputs.code,
        SECTOR_COLUMN: inputs.sector_name,
        INDEX_COLUMN: inputs.index_name,
        HISSE_PRICE: inputs.price,
        HISSE_PE: inputs.company_pe,
        HISSE_PB: inputs.company_pb,
        HISSE_NIS: inputs.nis_sign,
        HISSE_RATIO: inputs.ratio_score,
        **values,
        HISSE_AVERAGE: _round_or_none(avg_fair),
        HISSE_UPSIDE: _round_or_none(gp_pct, 4),
    }


def build_hisse_frame(
    tickers: list[str],
    valuation_frame: pd.DataFrame,
    puan_frame: pd.DataFrame,
    rasyo_frame: pd.DataFrame,
    endeks_frame: pd.DataFrame,
    sektor_frame: pd.DataFrame,
    ina_frame: pd.DataFrame,
) -> pd.DataFrame:
    lookups = _build_row_lookups(valuation_frame, puan_frame, rasyo_frame, endeks_frame, sektor_frame, ina_frame)
    macro_rates = _load_macro_rates()
    rows = []
    for ticker in tickers:
        inputs = _hisse_inputs(ticker, lookups)
        values = _valuation_points(inputs, macro_rates)
        rows.append(_hisse_output_row(inputs, values))
    return pd.DataFrame(rows, columns=_column_index(HISSE_COLUMNS))


def write_template_report(
    output_path: str,
    tickers: list[str],
    valuation_frame: pd.DataFrame,
    financials_frame: pd.DataFrame,
    dcf_frame: pd.DataFrame,
    ratio_frame: pd.DataFrame,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> None:
    workbook = load_workbook(template_path, data_only=False)

    endeks_frame = build_endeks_frame(tickers, valuation_frame, template_path)
    puan_frame = build_puan_frame(financials_frame)
    sektor_frame = build_sector_frame(endeks_frame, puan_frame)
    vars_frame = build_vars_frame()
    rasyo_frame = build_rasyo_frame(ratio_frame)
    ina_frame = dcf_frame.copy()
    if not ina_frame.empty and INA_VALUE_COLUMN not in ina_frame.columns:
        ina_frame[INA_VALUE_COLUMN] = pd.NA
    hisse_frame = build_hisse_frame(tickers, valuation_frame, puan_frame, rasyo_frame, endeks_frame, sektor_frame, ina_frame)

    ws_endeks = workbook[SHEET_ENDEKS]
    _unmerge_sheet(ws_endeks)
    _clear_sheet(ws_endeks, start_row=1, start_col=1, end_col=3)
    _write_table(ws_endeks, endeks_frame, header_row=1, include_header=False)

    ws_sektor = workbook[SHEET_SEKTOR]
    _unmerge_sheet(ws_sektor)
    _clear_sheet(ws_sektor, start_row=1, start_col=1, end_col=6)
    _write_table(ws_sektor, sektor_frame, header_row=1)

    ws_vars = workbook[SHEET_VARS]
    _unmerge_sheet(ws_vars)
    _clear_sheet(ws_vars, start_row=1, start_col=1, end_col=2)
    _write_table(ws_vars, vars_frame, header_row=1)

    ws_rasyo = workbook[SHEET_RASYO]
    _unmerge_sheet(ws_rasyo)
    _clear_sheet(ws_rasyo, start_row=1, start_col=1, end_col=len(RASYO_COLUMNS))
    _write_table(ws_rasyo, rasyo_frame, header_row=1)

    ws_puan = workbook[SHEET_PUAN]
    _unmerge_sheet(ws_puan)
    _clear_sheet(ws_puan, start_row=1, start_col=1, end_col=len(PUAN_COLUMNS))
    _write_table(ws_puan, puan_frame, header_row=1)

    ws_hisse = workbook[SHEET_HISSE]
    _unmerge_sheet(ws_hisse)
    _clear_sheet(ws_hisse, start_row=2, start_col=1, end_col=len(HISSE_COLUMNS))
    _write_table(ws_hisse, hisse_frame, header_row=2)
    _sync_excel_table(ws_hisse, "Hisseler", HISSE_COLUMNS, header_row=2, row_count=len(hisse_frame))
    _apply_header_comments(ws_hisse, HISSE_COLUMNS, HISSE_HEADER_COMMENTS, header_row=2)
    _apply_hisse_number_formats(ws_hisse, HISSE_COLUMNS, header_row=2, row_count=len(hisse_frame))

    _keep_only_sheets(workbook, OUTPUT_SHEETS)

    workbook.save(output_path)
    workbook.close()
