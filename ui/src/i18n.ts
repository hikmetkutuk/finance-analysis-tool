import type { Lang } from './types'

export interface Translations {
  stockCount: (n: number) => string
  lastUpdated: string
  refresh: string
  calculating: string
  errorPrefix: string
  loading: string
  firstCalcRunning: string
  noData: string
  startCalc: string
  fromCache: string
  marketUS: string
  marketBIST: string
  colTicker: string
  colSector: string
  colPrice: string
  colFairValue: string
  colUpside: string
  colSignal: string
  colWacc: string
  colDcf: string
  colPE: string
  colEvEbitda: string
  searchPlaceholder: (market: string) => string
  price: string
  fairValue: string
  upside: string
  wacc: string
  signal: string
  chart: string
  models: string
  warnings: string
  noPriceData: string
  chartLegend: string
  chartPriceLabel: string
  chartFairValueLabel: string
  chartFairValueRef: (v: number, currency: string) => string
  signalLabel: (v: string | null) => string
  dateLocale: string
}

export const translations: Record<Lang, Translations> = {
  tr: {
    stockCount: (n) => `${n} hisse`,
    lastUpdated: 'son güncelleme:',
    refresh: 'Yenile',
    calculating: 'Hesaplanıyor…',
    errorPrefix: 'hata:',
    loading: 'Veriler yükleniyor…',
    firstCalcRunning: 'İlk hesaplama çalışıyor, birkaç dakika sürebilir',
    noData: 'Henüz veri yok',
    startCalc: 'Hesaplamayı başlat →',
    fromCache: 'önbellekten',
    marketUS: 'ABD',
    marketBIST: 'BIST',
    colTicker: 'Ticker',
    colSector: 'Sektör',
    colPrice: 'Fiyat',
    colFairValue: 'Adil Fiyat',
    colUpside: 'Potansiyel',
    colSignal: 'Sinyal',
    colWacc: 'WACC',
    colDcf: 'DCF',
    colPE: 'F/K',
    colEvEbitda: 'EV/EBITDA',
    searchPlaceholder: () => 'Ticker veya sektör ara…',
    price: 'Fiyat',
    fairValue: 'Adil Fiyat',
    upside: 'Potansiyel',
    wacc: 'WACC',
    signal: 'Sinyal',
    chart: 'Grafik',
    models: 'Modeller',
    warnings: 'Uyarılar:',
    noPriceData: 'Fiyat verisi bulunamadı',
    chartLegend: 'Gri alan: gerçek fiyat · Sarı çizgi: mevcut adil fiyat · Sarı noktalar: geçmiş adil fiyat anlık görüntüleri',
    chartPriceLabel: 'Fiyat',
    chartFairValueLabel: 'Adil Fiyat',
    chartFairValueRef: (v, currency) => `Adil: ${currency}${v.toFixed(0)}`,
    signalLabel: (v) => {
      if (v === 'High') return 'Yüksek'
      if (v === 'Medium') return 'Orta'
      if (v === 'Low') return 'Düşük'
      return v ?? '—'
    },
    dateLocale: 'tr-TR',
  },
  en: {
    stockCount: (n) => `${n} stocks`,
    lastUpdated: 'last updated:',
    refresh: 'Refresh',
    calculating: 'Calculating…',
    errorPrefix: 'error:',
    loading: 'Loading data…',
    firstCalcRunning: 'First calculation running, may take a few minutes',
    noData: 'No data yet',
    startCalc: 'Start calculation →',
    fromCache: 'from cache',
    marketUS: 'US',
    marketBIST: 'BIST',
    colTicker: 'Ticker',
    colSector: 'Sector',
    colPrice: 'Price',
    colFairValue: 'Fair Value',
    colUpside: 'Upside',
    colSignal: 'Signal',
    colWacc: 'WACC',
    colDcf: 'DCF',
    colPE: 'P/E',
    colEvEbitda: 'EV/EBITDA',
    searchPlaceholder: () => 'Search ticker or sector…',
    price: 'Price',
    fairValue: 'Fair Value',
    upside: 'Upside',
    wacc: 'WACC',
    signal: 'Signal',
    chart: 'Chart',
    models: 'Models',
    warnings: 'Warnings:',
    noPriceData: 'No price data found',
    chartLegend: 'Grey area: actual price · Yellow line: current fair value · Yellow dots: historical fair value snapshots',
    chartPriceLabel: 'Price',
    chartFairValueLabel: 'Fair Value',
    chartFairValueRef: (v, currency) => `Fair: ${currency}${v.toFixed(0)}`,
    signalLabel: (v) => v ?? '—',
    dateLocale: 'en-US',
  },
}
