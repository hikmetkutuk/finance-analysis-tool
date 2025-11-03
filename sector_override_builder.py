import pandas as pd

# Türkiye ve ABD sektör-hisse eşlemesi
sector_tickers_tr = {
    "Banka": [
        "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "VAKBN.IS", "HALKB.IS", "TSKB.IS", "GARAN.IS"
    ],
    "Enerji": [
        "AKSEN.IS", "ENJSA.IS", "PETKM.IS", "TUPRS.IS", "ASTOR.IS"
    ],
    "Sanayi & Üretim": [
        "ARCLK.IS", "ASELS.IS", "BRSAN.IS", "CIMSA.IS", "EGEEN.IS", "KOZAA.IS", "KOZAL.IS", "ENKAI.IS", "TKFEN.IS", "AKSA.IS", "OTKAR.IS", "GUBRF.IS", "HEKTS.IS", "SASA.IS"
    ],
    "Otomotiv": [
        "TOASO.IS", "FROTO.IS", "DOAS.IS"
    ],
    "Perakende & Tüketim": [
        "BIMAS.IS", "MGROS.IS"
    ],
    "Havacılık": [
        "PGSUS.IS", "THYAO.IS", "TAVHL.IS"
    ],
    "Sigorta": [
        "ANSGR.IS"
    ],
    "Gıda & İçecek": [
        "CCOLA.IS", "AEFES.IS"
    ],
    "Holding & Karma": [
        "KCHOL.IS", "SAHOL.IS", "AGHOL.IS", "ALARK.IS", "DOHOL.IS", "BINHO.IS", "ECILC.IS",
    ],
    "Telekomünikasyon": [
        "TCELL.IS", "TTKOM.IS"
    ],
}

sector_tickers_us = {
    "Teknoloji": [
        "AAPL", "GOOG", "GOOGL", "MSFT", "META", "NET", "PLTR", "ORCL", "ADBE", "CRM", "AMZN", "CSCO", "DELL"
    ],
    "Yarı İletken": [
        "QCOM", "AMD", "NVDA", "INTL", "BABA", "AVGO"
    ],
    "E-Ticaret": [
        "BABA"
    ],
    "İletişim & Medya": [
        "DIS", "NFLX"
    ],
    "Sağlık & İlaç": [
        "LLY", "JNJ", "MRK", "UNH", "PFE", "NVO", "TMO"
    ],
    "Finans": [
        "JPM", "WFC", "MA", "V"
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

def build_overrides(sector_csv: str, sector_map: dict) -> dict:
    df = pd.read_csv(sector_csv)
    overrides = {}

    for _, row in df.iterrows():
        sector = row['sector']
        pe = row.get('pe')
        ev = row.get('ev_ebitda')

        tickers = sector_map.get(sector, [])
        for t in tickers:
            overrides[t] = {}
            if pd.notna(pe): overrides[t]["pe"] = float(pe)
            if pd.notna(ev): overrides[t]["ev_ebitda"] = float(ev)
    
    return overrides

# Türkiye ve ABD için override'ları birleştir
overrides_tr = build_overrides("sector_multiples_tr.csv", sector_tickers_tr)
overrides_us = build_overrides("sector_multiples_us.csv", sector_tickers_us)

# Son sözlük
SECTOR_OVERRIDES = {**overrides_tr, **overrides_us}

# Yazdır
print("SECTOR_OVERRIDES = {")
for k, v in SECTOR_OVERRIDES.items():
    print(f'    "{k}": {v},')
print("}")
