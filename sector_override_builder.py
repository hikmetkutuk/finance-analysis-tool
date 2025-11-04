import pandas as pd

# Türkiye ve ABD sektör-hisse eşlemesi
sector_tickers_tr = {
    "Banka": [
        "AKBNK.IS", "ISCTR.IS", "YKBNK.IS", "VAKBN.IS", "HALKB.IS", "TSKB.IS", "GARAN.IS", "ALBRK.IS"
    ],
    "Enerji": [
        "AKSEN.IS", "ENJSA.IS", "ASTOR.IS", "ZOREN.IS", "GWIND.IS", "CWENE.IS", "SMRTG.IS", "TATEN.IS"
    ],
    "Petrol": [
        "PETKM.IS", "TUPRS.IS", "IPEKE.IS"
    ],
    "Sanayi & Üretim": [
        "BRSAN.IS", "EGEEN.IS", "KOZAA.IS", "KOZAL.IS", "ENKAI.IS", "AKSA.IS", "GUBRF.IS", "HEKTS.IS", "SASA.IS", "CEMTS.IS", "KCAER.IS", "KRDMD.IS", "ISDMR.IS", "EREGL.IS"
    ],
    "Dayanıklı Tüketim": [
        "ARCLK.IS", "VESTL.IS", "VESBE.IS"
    ],
    "Savunma": [
        "ASELS.IS", "ALTNY.IS", "FORTE.IS", "ONRYT.IS", "KAREL.IS"
    ],
    "Çimento": [
        "CIMSA.IS", "GOLTS.IS", "BOBET.IS", "LMKDC.IS", "OYAKC.IS", "KONYA.IS", "BUCIM.IS", "AFYON.IS", "NUHCM.IS"
    ],
    "Otomotiv": [
        "TOASO.IS", "FROTO.IS", "DOAS.IS", "OTKAR.IS", "TTRAK.IS"
    ],
    "Perakende": [
        "BIMAS.IS", "MGROS.IS", "TKNSA.IS", "SOKM.IS"
    ],
    "Havacılık": [
        "PGSUS.IS", "THYAO.IS", "TAVHL.IS", "CLEBI.IS"
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
        "KCHOL.IS", "SAHOL.IS", "AGHOL.IS", "ALARK.IS", "DOHOL.IS", "BINHO.IS", "TKFEN.IS", "BERA.IS"
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
