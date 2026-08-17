import type { HistoryPoint, PortfolioResponse, PricePoint, RefreshState, Stock } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  portfolio: (): Promise<PortfolioResponse> =>
    get('/portfolio'),

  stock: (ticker: string): Promise<Stock> =>
    get(`/portfolio/${ticker}`),

  history: (ticker: string): Promise<{ ticker: string; history: HistoryPoint[] }> =>
    get(`/portfolio/${ticker}/history`),

  priceHistory: (ticker: string): Promise<{ ticker: string; prices: PricePoint[] }> =>
    get(`/portfolio/${ticker}/price-history`),

  refreshStatus: (): Promise<RefreshState> =>
    get('/refresh/status'),

  triggerRefresh: async (): Promise<{ status: string }> => {
    const res = await fetch(`${BASE}/refresh`, { method: 'POST' })
    if (!res.ok && res.status !== 409) throw new Error(`${res.status} ${res.statusText}`)
    return res.json()
  },
}
