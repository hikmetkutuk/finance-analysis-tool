import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { translations } from './i18n'
import PortfolioTable from './components/PortfolioTable'
import StockDetail from './components/StockDetail'
import type { Lang, Market, RefreshState, Stock } from './types'

const POLL_MS = 30_000

function fmtDateTime(dt: string | null, locale: string, fromCacheLabel: string): string {
  if (!dt) return '—'
  if (dt === 'from cache') return fromCacheLabel
  try {
    return new Date(dt).toLocaleString(locale, { hour12: false })
  } catch {
    return dt
  }
}

export default function App() {
  const [market, setMarket] = useState<Market>('us')
  const [lang, setLang] = useState<Lang>('tr')
  const [stocks, setStocks] = useState<Stock[]>([])
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [refreshState, setRefreshState] = useState<RefreshState>({ running: false, last_updated: null, error: null })
  const [selected, setSelected] = useState<Stock | null>(null)
  const [loading, setLoading] = useState(true)

  const tr = translations[lang]

  useEffect(() => {
    setStocks([])
    setSelected(null)
    setLastUpdated(null)
    setRefreshState({ running: false, last_updated: null, error: null })
    setLoading(true)
  }, [market])

  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await api.portfolio(market)
      setStocks(data.stocks)
      setLastUpdated(data.last_updated)
    } catch { /* network error — keep old data */ }
    finally { setLoading(false) }
  }, [market])

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.refreshStatus(market)
      setRefreshState(s)
      if (!s.running) fetchPortfolio()
    } catch { /* ignore */ }
  }, [market, fetchPortfolio])

  useEffect(() => {
    fetchPortfolio()
    fetchStatus()
    const id = setInterval(fetchStatus, POLL_MS)
    return () => clearInterval(id)
  }, [fetchPortfolio, fetchStatus])

  const selectedKod = selected?.Kod
  useEffect(() => {
    if (!selectedKod) return
    const updated = stocks.find(s => s.Kod === selectedKod)
    if (updated) setSelected(updated)
  }, [stocks, selectedKod])

  const handleRefresh = async () => {
    try {
      await api.triggerRefresh(market)
      setRefreshState(prev => ({ ...prev, running: true }))
    } catch { /* already running or error */ }
  }

  function mainContent() {
    if (loading) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3" />
            <p className="text-slate-400 text-sm">{tr.loading}</p>
            {refreshState.running && (
              <p className="text-slate-500 text-xs mt-1">{tr.firstCalcRunning}</p>
            )}
          </div>
        </div>
      )
    }
    if (stocks.length === 0) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-slate-400 text-sm mb-2">{tr.noData}</p>
            <button type="button" onClick={handleRefresh} className="text-emerald-400 text-sm hover:text-emerald-300">
              {tr.startCalc}
            </button>
          </div>
        </div>
      )
    }
    return (
      <>
        <PortfolioTable
          stocks={stocks}
          selected={selected}
          onSelect={setSelected}
          lang={lang}
        />
        {selected && (
          <StockDetail
            stock={selected}
            onClose={() => setSelected(null)}
            lang={lang}
            market={market}
          />
        )}
      </>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <header className="border-b border-slate-800 bg-slate-950/80 backdrop-blur-sm sticky top-0 z-30">
        <div className="max-w-screen-2xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-600 flex items-center justify-center text-xs font-bold text-white">F</div>
            <span className="font-semibold text-slate-100 tracking-tight">Finance Dashboard</span>
            {stocks.length > 0 && (
              <span className="text-xs text-slate-500 tabular-nums">{tr.stockCount(stocks.length)}</span>
            )}
          </div>

          <div className="flex items-center gap-3">
            {refreshState.error && (
              <span className="text-xs text-rose-400 max-w-xs truncate" title={refreshState.error}>
                {tr.errorPrefix} {refreshState.error}
              </span>
            )}
            <span className="text-xs text-slate-500 hidden sm:block">
              {tr.lastUpdated} {fmtDateTime(lastUpdated, tr.dateLocale, tr.fromCache)}
            </span>

            <div className="flex items-center bg-slate-800 border border-slate-700 rounded-lg p-0.5">
              {(['us', 'bist'] as const).map(m => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setMarket(m)}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    market === m
                      ? 'bg-slate-700 text-slate-100'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {m === 'us' ? tr.marketUS : tr.marketBIST}
                </button>
              ))}
            </div>

            <div className="flex items-center bg-slate-800 border border-slate-700 rounded-lg p-0.5">
              {(['tr', 'en'] as const).map(l => (
                <button
                  key={l}
                  type="button"
                  onClick={() => setLang(l)}
                  className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                    lang === l
                      ? 'bg-slate-700 text-slate-100'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  {l.toUpperCase()}
                </button>
              ))}
            </div>

            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshState.running}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600
                disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
            >
              <span className={refreshState.running ? 'animate-spin' : ''}>↻</span>
              {refreshState.running ? tr.calculating : tr.refresh}
            </button>
          </div>
        </div>

        {refreshState.running && (
          <div className="h-0.5 bg-slate-800 overflow-hidden">
            <div className="h-full bg-emerald-500"
              style={{ width: '60%', animation: 'pulse 1.5s ease-in-out infinite' }} />
          </div>
        )}
      </header>

      <main className="flex-1 max-w-screen-2xl mx-auto w-full px-4 py-4 flex flex-col gap-4">
        {mainContent()}
      </main>
    </div>
  )
}
