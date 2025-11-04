import yfinance as yf
import pandas as pd

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
        "BIMAS.IS", "MGROS.IS", "SOKM.IS"
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
        "KCHOL.IS", "SAHOL.IS", "AGHOL.IS", "ALARK.IS", "DOHOL.IS", "BINHO.IS", "TKFEN.IS"
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

def calculate_sector_multiples(sector_tickers: dict, filename: str):
    rows = []
    for sector, tickers in sector_tickers.items():
        pe, pb, ev_ebitda = [], [], []
        for t in tickers:
            try:
                info = yf.Ticker(t).info
                if info.get("trailingPE"): pe.append(info["trailingPE"])
                if info.get("priceToBook"): pb.append(info["priceToBook"])
                ev, ebitda = info.get("enterpriseValue"), info.get("ebitda")
                if ev and ebitda:
                    ev_ebitda.append(ev / ebitda)
            except Exception as e:
                print(f"{t} → {e}")
        rows.append({
            "sector": sector,
            "pe": round(sum(pe)/len(pe), 2) if pe else None,
            "pb": round(sum(pb)/len(pb), 2) if pb else None,
            "ev_ebitda": round(sum(ev_ebitda)/len(ev_ebitda), 2) if ev_ebitda else None,
            "ticker_count": len(tickers)
        })

    df = pd.DataFrame(rows)
    df.to_csv(filename, index=False)
    print(f"✅ Kaydedildi → {filename}")

# Türkiye için
calculate_sector_multiples(sector_tickers_tr, "sector_multiples_tr.csv")

# ABD için
calculate_sector_multiples(sector_tickers_us, "sector_multiples_us.csv")
