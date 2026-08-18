import type { HistoryPoint, Market, PortfolioResponse, PricePoint, RefreshState, Stock } from './types'

const BASE = '/api'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

export const api = {
  portfolio: (market: Market): Promise<PortfolioResponse> =>
    get(`/portfolio?market=${market}`),

  stock: (ticker: string, market: Market): Promise<Stock> =>
    get(`/portfolio/${ticker}?market=${market}`),

  history: (ticker: string, market: Market): Promise<{ ticker: string; history: HistoryPoint[] }> =>
    get(`/portfolio/${ticker}/history?market=${market}`),

  priceHistory: (ticker: string): Promise<{ ticker: string; prices: PricePoint[] }> =>
    get(`/portfolio/${ticker}/price-history`),

  refreshStatus: (market: Market): Promise<RefreshState> =>
    get(`/refresh/status?market=${market}`),

  triggerRefresh: async (market: Market): Promise<{ status: string }> => {
    const res = await fetch(`${BASE}/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ market }),
    })
    if (!res.ok && res.status !== 409) throw new Error(`${res.status} ${res.statusText}`)
    return res.json()
  },
}
