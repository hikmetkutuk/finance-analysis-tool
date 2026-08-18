export interface Stock {
  Kod: string
  Sektör: string
  'Para Birimi': string
  'Sinyal Kalite Skoru': number | null
  'Sinyal Güven Seviyesi': string | null
  'Güncel Fiyat': number | null
  'Beklenen Getiri (%)': number | null
  WACC: number | null
  'Ortalama Büyüme': number | null
  'DCF Değerlemesi': number | null
  'F/K Değerlemesi': number | null
  'PD/DD Finansal Model': number | null
  'EV/EBITDA Değerlemesi': number | null
  'DDM Değerlemesi': number | null
  'EFK Değerlemesi': number | null
  'NDK Değerlemesi': number | null
  'Graham Değerlemesi': number | null
  'Ortalama Adil Fiyat': number | null
  'Model Kalite Uyarı Sayısı': number
  'Model Kalite Uyarıları': string
  [key: string]: number | string | null
}

export interface PortfolioResponse {
  stocks: Stock[]
  last_updated: string | null
}

export interface RefreshState {
  running: boolean
  last_updated: string | null
  error: string | null
}

export interface HistoryPoint {
  snapped_at: string
  current_price: number | null
  fair_value: number | null
  upside_pct: number | null
  signal_score: number | null
}

export interface PricePoint {
  date: string
  price: number
}

export type SortKey = keyof Stock
export type SortDir = 'asc' | 'desc'
export type Market = 'us' | 'bist'
export type Lang = 'tr' | 'en'
