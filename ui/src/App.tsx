import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from './api'
import PortfolioTable from './components/PortfolioTable'
import StockDetail from './components/StockDetail'
import type { RefreshState, Stock } from './types'

const POLL_MS = 30_000

function fmt(dt: string | null): string {
  if (!dt) return '—'
  if (dt === 'from cache') return 'önbellekten'
  try {
    return new Date(dt).toLocaleString('tr-TR', { hour12: false })
  } catch {
    return dt
  }
}

export default function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [lastUpdated, setLastUpdated] = useState<string | null>(null)
  const [refreshState, setRefreshState] = useState<RefreshState>({ running: false, last_updated: null, error: null })
  const [selected, setSelected] = useState<Stock | null>(null)
  const [loading, setLoading] = useState(true)
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchPortfolio = useCallback(async () => {
    try {
      const data = await api.portfolio()
      setStocks(data.stocks)
      setLastUpdated(data.last_updated)
    } catch { /* network error — keep old data */ }
    finally { setLoading(false) }
  }, [])

  const fetchStatus = useCallback(async () => {
    try {
      const s = await api.refreshStatus()
      setRefreshState(s)
      if (!s.running) fetchPortfolio()
    } catch { /* ignore */ }
  }, [fetchPortfolio])

  useEffect(() => {
    fetchPortfolio()
    fetchStatus()
    pollRef.current = setInterval(fetchStatus, POLL_MS)
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [fetchPortfolio, fetchStatus])

  const selectedKod = selected?.Kod
  useEffect(() => {
    if (!selectedKod) return
    const updated = stocks.find(s => s.Kod === selectedKod)
    if (updated) setSelected(updated)
  }, [stocks, selectedKod])

  const handleRefresh = async () => {
    try {
      await api.triggerRefresh()
      setRefreshState(prev => ({ ...prev, running: true }))
    } catch { /* already running or error */ }
  }

  function mainContent() {
    if (loading) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <div className="inline-block w-8 h-8 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin mb-3" />
            <p className="text-slate-400 text-sm">Veriler yükleniyor…</p>
            {refreshState.running && (
              <p className="text-slate-500 text-xs mt-1">İlk hesaplama çalışıyor, birkaç dakika sürebilir</p>
            )}
          </div>
        </div>
      )
    }
    if (stocks.length === 0) {
      return (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-slate-400 text-sm mb-2">Henüz veri yok</p>
            <button type="button" onClick={handleRefresh} className="text-emerald-400 text-sm hover:text-emerald-300">
              Hesaplamayı başlat →
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
        />
        {selected && (
          <StockDetail
            stock={selected}
            onClose={() => setSelected(null)}
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
              <span className="text-xs text-slate-500 tabular-nums">{stocks.length} hisse</span>
            )}
          </div>

          <div className="flex items-center gap-4">
            {refreshState.error && (
              <span className="text-xs text-rose-400 max-w-xs truncate" title={refreshState.error}>
                hata: {refreshState.error}
              </span>
            )}
            <span className="text-xs text-slate-500 hidden sm:block">
              son güncelleme: {fmt(lastUpdated)}
            </span>
            <button
              type="button"
              onClick={handleRefresh}
              disabled={refreshState.running}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium
                bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600
                disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
            >
              <span className={refreshState.running ? 'animate-spin' : ''}>↻</span>
              {refreshState.running ? 'Hesaplanıyor…' : 'Yenile'}
            </button>
          </div>
        </div>

        {refreshState.running && (
          <div className="h-0.5 bg-slate-800 overflow-hidden">
            <div className="h-full bg-emerald-500 animate-[progress_2s_ease-in-out_infinite]"
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
