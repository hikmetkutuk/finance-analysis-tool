from dataclasses import dataclass
from typing import FrozenSet

from .constants import MARKET_AUTO, MARKET_TR, MARKET_US


@dataclass(frozen=True)
class MarketProfile:
    market: str
    default_tax_rate: float
    financial_terms: FrozenSet[str]


TR_PROFILE = MarketProfile(
    market=MARKET_TR,
    default_tax_rate=0.25,
    financial_terms=frozenset(
        {
            "financial",
            "finance",
            "bank",
            "insurance",
            "capital market",
            "asset management",
            "broker",
            "banka",
            "sigorta",
            "araci kurum",
            "yatirim",
        }
    ),
)

US_PROFILE = MarketProfile(
    market=MARKET_US,
    default_tax_rate=0.21,
    financial_terms=frozenset(
        {
            "financial",
            "finance",
            "bank",
            "insurance",
            "capital market",
            "asset management",
            "broker",
        }
    ),
)

PROFILES = {
    MARKET_TR: TR_PROFILE,
    MARKET_US: US_PROFILE,
}


def infer_market_from_symbol(symbol: str) -> str:
    return MARKET_TR if symbol.upper().endswith(".IS") else MARKET_US


def resolve_market(market: str, symbol: str) -> str:
    if market == MARKET_AUTO:
        return infer_market_from_symbol(symbol)
    return market


def get_profile(market: str, symbol: str) -> MarketProfile:
    resolved_market = resolve_market(market, symbol)
    return PROFILES[resolved_market]
