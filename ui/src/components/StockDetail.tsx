import { useEffect, useState } from 'react'
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { api } from '../api'
import { translations } from '../i18n'
import type { HistoryPoint, Lang, Market, PricePoint, Stock } from '../types'

interface Props {
  readonly stock: Stock
  readonly onClose: () => void
  readonly onRefreshTicker: (ticker: string) => Promise<void>
  readonly lang: Lang
  readonly market: Market
}

interface ChartPoint {
  date: string
  price?: number
  fairValue?: number
}

function merge(prices: PricePoint[], history: HistoryPoint[]): ChartPoint[] {
  const map = new Map<string, ChartPoint>()
  for (const p of prices) {
    map.set(p.date, { date: p.date, price: p.price })
  }
  for (const h of history) {
    const d = h.snapped_at.split('T')[0]
    const existing = map.get(d) || { date: d }
    if (h.fair_value !== null) existing.fairValue = h.fair_value
    map.set(d, existing)
  }
  return [...map.values()].sort((a, b) => a.date.localeCompare(b.date))
}

function fmtPrice(v: number | null | undefined, currency: string): string {
  if (v === null || v === undefined) return '—'
  return `${currency}${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function fmtMult(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${v.toFixed(1)}×`
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return `${v.toFixed(2)}%`
}

function fmtBigNum(v: number | null | undefined, currency: string): string {
  if (v === null || v === undefined) return '—'
  if (Math.abs(v) >= 1e12) return `${currency}${(v / 1e12).toFixed(2)}T`
  if (Math.abs(v) >= 1e9) return `${currency}${(v / 1e9).toFixed(2)}B`
  if (Math.abs(v) >= 1e6) return `${currency}${(v / 1e6).toFixed(2)}M`
  return `${currency}${v.toFixed(2)}`
}

function getUpsideColorCls(upside: number | null): string {
  if (upside === null) return 'text-slate-400'
  return upside >= 0 ? 'text-emerald-400' : 'text-rose-400'
}

function getSignalColorCls(signal: string | null | undefined): string {
  if (signal === 'High') return 'text-emerald-400'
  if (signal === 'Medium') return 'text-amber-400'
  return 'text-rose-400'
}

function SectionLabel({ children }: { readonly children: React.ReactNode }) {
  return (
    <div className="text-xs font-semibold tracking-widest uppercase text-slate-500 mb-2 mt-5 first:mt-0 border-b border-slate-800 pb-1">
      {children}
    </div>
  )
}

function Row({ label, value, highlight }: { readonly label: string; readonly value: string; readonly highlight?: boolean }) {
  return (
    <div className="flex justify-between items-baseline py-1 border-b border-slate-800/60 last:border-0">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={`text-xs font-mono tabular-nums ${highlight ? 'text-emerald-400 font-semibold' : 'text-slate-200'}`}>{value}</span>
    </div>
  )
}

interface AnalysisTabProps {
  readonly stock: Stock
  readonly currency: string
}

function AnalysisTab({ stock, currency }: AnalysisTabProps) {
  const dcf = (stock['DCF Değerlemesi'] ?? null) as number | null
  const rel = (stock['Rölatif Değerleme'] ?? null) as number | null
  const blended = (stock['Ortalama Adil Fiyat'] ?? null) as number | null
  const price = (stock['Güncel Fiyat'] ?? null) as number | null

  const wacc = (stock.WACC ?? null) as number | null
  const waccRf = (stock['WACC rf'] ?? null) as number | null
  const waccBeta = (stock['WACC beta'] ?? null) as number | null
  const waccKe = (stock['WACC ke'] ?? null) as number | null
  const waccKd = (stock['WACC kd'] ?? null) as number | null
  const waccTax = (stock['WACC tax'] ?? null) as number | null
  const waccEV = (stock['WACC E/V'] ?? null) as number | null

  const trailingPE = (stock['Trailing P/E'] ?? null) as number | null
  const forwardPE = (stock['Forward P/E'] ?? null) as number | null
  const marketCap = (stock['Market Cap'] ?? null) as number | null
  const enterpriseValue = (stock['Enterprise Value'] ?? null) as number | null
  const ttmRevenue = (stock['TTM Revenue'] ?? null) as number | null
  const ebitMargin = (stock['EBIT Margin'] ?? null) as number | null
  const ttmEbitda = (stock['TTM EBITDA'] ?? null) as number | null
  const netDebt = (stock['Net Debt'] ?? null) as number | null
  const revGrowth = (stock['Revenue Growth'] ?? null) as number | null

  const peerPE = (stock['Peer P/E'] ?? null) as number | null
  const peerEvRev = (stock['Peer EV/Rev'] ?? null) as number | null
  const peerEvEbitda = (stock['Peer EV/EBITDA'] ?? null) as number | null
  const implPE = (stock['Impl Price P/E'] ?? null) as number | null
  const implEvRev = (stock['Impl Price EV/Rev'] ?? null) as number | null
  const implEvEbitda = (stock['Impl Price EV/EBITDA'] ?? null) as number | null

  function upside(target: number | null): string {
    if (target === null || price === null) return '—'
    const pct = ((target / price) - 1) * 100
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(1)}%`
  }

  function upsideColor(target: number | null): string {
    if (target === null || price === null) return 'text-slate-400'
    return ((target / price) - 1) >= 0 ? 'text-emerald-400' : 'text-rose-400'
  }

  const hasMethodData = dcf !== null || rel !== null
  const hasWacc = wacc !== null
  const hasSnapshot = trailingPE !== null || marketCap !== null || ttmRevenue !== null
  const hasRelative = peerPE !== null || peerEvRev !== null || peerEvEbitda !== null

  if (!hasMethodData && !hasWacc && !hasSnapshot) {
    return (
      <div className="h-48 flex items-center justify-center text-slate-500 text-sm">
        Detay verisi henüz yüklenmedi — Yenile butonunu kullanın.
      </div>
    )
  }

  return (
    <div className="space-y-1">
      {/* Method Summary */}
      {hasMethodData && (
        <>
          <SectionLabel>Değerleme Özeti</SectionLabel>
          <div className="grid grid-cols-3 gap-2 mb-2">
            {[
              { label: 'DCF (50%)', value: dcf },
              { label: 'Rölatif (50%)', value: rel },
              { label: 'Blended', value: blended, bold: true },
            ].map(({ label, value, bold }) => (
              <div key={label} className={`rounded-lg px-3 py-2.5 border ${bold ? 'bg-slate-700/50 border-slate-600' : 'bg-slate-800/60 border-slate-700/50'}`}>
                <div className="text-xs text-slate-500 mb-1">{label}</div>
                <div className={`text-sm font-mono tabular-nums ${bold ? 'text-amber-400 font-bold' : 'text-slate-200'}`}>
                  {fmtPrice(value, currency)}
                </div>
                <div className={`text-xs tabular-nums mt-0.5 ${upsideColor(value)}`}>
                  {upside(value)}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* WACC Breakdown */}
      {hasWacc && (
        <>
          <SectionLabel>WACC Detayı</SectionLabel>
          <div className="bg-slate-800/40 rounded-lg px-3 py-2 space-y-0">
            <Row label="WACC" value={wacc !== null ? `${wacc.toFixed(2)}%` : '—'} highlight />
            <Row label="Risk-Free Rate (rf)" value={fmtPct(waccRf)} />
            <Row label="Beta" value={waccBeta !== null ? waccBeta.toFixed(3) : '—'} />
            <Row label="Cost of Equity (ke)" value={fmtPct(waccKe)} />
            <Row label="Cost of Debt (kd)" value={fmtPct(waccKd)} />
            <Row label="Vergi Oranı (efektif)" value={fmtPct(waccTax)} />
            <Row label="E/V (Özsermaye Ağırlığı)" value={waccEV !== null ? `${waccEV.toFixed(1)}%` : '—'} />
          </div>
        </>
      )}

      {/* Market Snapshot */}
      {hasSnapshot && (
        <>
          <SectionLabel>Piyasa Verileri</SectionLabel>
          <div className="bg-slate-800/40 rounded-lg px-3 py-2 space-y-0">
            <Row label="Güncel Fiyat" value={fmtPrice(price, currency)} />
            <Row label="F/K (Trailing P/E)" value={fmtMult(trailingPE)} />
            <Row label="Forward P/E" value={fmtMult(forwardPE)} />
            <Row label="Piyasa Değeri" value={fmtBigNum(marketCap, currency)} />
            <Row label="Enterprise Value (EV)" value={fmtBigNum(enterpriseValue, currency)} />
            <Row label="TTM Gelir" value={fmtBigNum(ttmRevenue, currency)} />
            <Row label="EBIT Marjı" value={ebitMargin !== null ? `${ebitMargin.toFixed(1)}%` : '—'} />
            <Row label="TTM EBITDA" value={fmtBigNum(ttmEbitda, currency)} />
            <Row label="Net Borç" value={fmtBigNum(netDebt, currency)} />
            <Row label="Gelir Büyümesi" value={revGrowth !== null ? `${revGrowth.toFixed(1)}%` : '—'} />
          </div>
        </>
      )}

      {/* Relative Valuation */}
      {hasRelative && (
        <>
          <SectionLabel>Rölatif Değerleme Detayı</SectionLabel>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 border-b border-slate-800">
                  <th className="text-left py-1.5 font-medium">Yöntem</th>
                  <th className="text-right py-1.5 font-medium">Peer Medyan</th>
                  <th className="text-right py-1.5 font-medium">Zımni Fiyat</th>
                  <th className="text-right py-1.5 font-medium">Upside</th>
                </tr>
              </thead>
              <tbody className="font-mono tabular-nums">
                {[
                  { label: 'P/E', peer: peerPE !== null ? fmtMult(peerPE) : '—', impl: implPE },
                  { label: 'EV/Revenue', peer: peerEvRev !== null ? `${peerEvRev.toFixed(1)}×` : '—', impl: implEvRev },
                  { label: 'EV/EBITDA', peer: peerEvEbitda !== null ? `${peerEvEbitda.toFixed(1)}×` : '—', impl: implEvEbitda },
                ].map(({ label, peer, impl }) => (
                  <tr key={label} className="border-b border-slate-800/60 last:border-0">
                    <td className="py-1.5 text-slate-400">{label}</td>
                    <td className="py-1.5 text-right text-slate-300">{peer}</td>
                    <td className="py-1.5 text-right text-slate-200">{fmtPrice(impl, currency)}</td>
                    <td className={`py-1.5 text-right ${upsideColor(impl)}`}>{upside(impl)}</td>
                  </tr>
                ))}
                <tr className="border-t border-slate-700 bg-slate-800/30">
                  <td className="py-1.5 text-slate-300 font-semibold" colSpan={2}>Medyan (Rölatif)</td>
                  <td className="py-1.5 text-right text-amber-400 font-semibold">{fmtPrice(rel, currency)}</td>
                  <td className={`py-1.5 text-right font-semibold ${upsideColor(rel)}`}>{upside(rel)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Other models */}
      <SectionLabel>Diğer Modeller</SectionLabel>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {([
          { label: 'PD/DD', key: 'PD/DD Finansal Model' },
          { label: 'DDM', key: 'DDM Değerlemesi' },
          { label: 'EFK', key: 'EFK Değerlemesi' },
          { label: 'NDK', key: 'NDK Değerlemesi' },
          { label: 'Graham', key: 'Graham Değerlemesi' },
        ] as const).map(({ label, key }) => {
          const val = (stock[key] ?? null) as number | null
          if (val === null) return null
          return (
            <div key={label} className="bg-slate-800/60 rounded-lg px-3 py-2.5 border border-slate-700/50">
              <div className="text-xs text-slate-500 mb-1">{label}</div>
              <div className="text-sm font-mono text-slate-200">{fmtPrice(val, currency)}</div>
              <div className={`text-xs tabular-nums mt-0.5 ${upsideColor(val)}`}>{upside(val)}</div>
            </div>
          )
        })}
      </div>

      {stock['Model Kalite Uyarıları'] && (
        <div className="text-xs text-amber-400/70 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2 mt-2">
          ⚠ {stock['Model Kalite Uyarıları']}
        </div>
      )}
    </div>
  )
}

interface ChartTabProps {
  readonly loadingChart: boolean
  readonly chartData: ChartPoint[]
  readonly fairValue: number | null
  readonly currency: string
  readonly lang: Lang
}

function ChartTab({ loadingChart, chartData, fairValue, currency, lang }: ChartTabProps) {
  const tr = translations[lang]

  function fmtDate(d: string) {
    try { return new Date(d).toLocaleDateString(tr.dateLocale, { day: '2-digit', month: 'short' }) }
    catch { return d }
  }

  if (loadingChart) {
    return (
      <div className="h-64 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }
  if (chartData.length === 0) {
    return (
      <div className="h-64 flex items-center justify-center text-slate-500 text-sm">
        {tr.noPriceData}
      </div>
    )
  }
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={chartData} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
          <defs>
            <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#64748b" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#64748b" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={fmtDate}
            tick={{ fill: '#64748b', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: '#64748b', fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={v => `${currency}${v}`}
            width={60}
            domain={['auto', 'auto']}
          />
          <Tooltip
            contentStyle={{
              background: '#1e293b',
              border: '1px solid #334155',
              borderRadius: 8,
              fontSize: 12,
              color: '#f1f5f9',
            }}
            labelFormatter={fmtDate}
            formatter={(value: number, name: string) => [
              fmtPrice(value, currency),
              name === 'price' ? tr.chartPriceLabel : tr.chartFairValueLabel,
            ]}
          />
          {fairValue !== null && (
            <ReferenceLine
              y={fairValue}
              stroke="#f59e0b"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={{ value: tr.chartFairValueRef(fairValue, currency), fill: '#f59e0b', fontSize: 11, position: 'insideTopRight' }}
            />
          )}
          <Area
            type="monotone"
            dataKey="price"
            stroke="#94a3b8"
            strokeWidth={1.5}
            fill="url(#priceGrad)"
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="fairValue"
            stroke="#f59e0b"
            strokeWidth={0}
            dot={{ fill: '#f59e0b', r: 5, strokeWidth: 2, stroke: '#1e293b' }}
            connectNulls={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="text-xs text-slate-600 text-center mt-1">{tr.chartLegend}</p>
    </div>
  )
}

export default function StockDetail({ stock, onClose, onRefreshTicker, lang, market }: Readonly<Props>) {
  const [tab, setTab] = useState<'chart' | 'analysis'>('analysis')
  const [prices, setPrices] = useState<PricePoint[]>([])
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [loadingChart, setLoadingChart] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const tr = translations[lang]

  const handleRefreshTicker = async () => {
    setRefreshing(true)
    try { await onRefreshTicker(stock.Kod) }
    finally { setRefreshing(false) }
  }

  useEffect(() => {
    setLoadingChart(true)
    setPrices([])
    setHistory([])
    Promise.all([
      api.priceHistory(stock.Kod).catch(() => ({ prices: [] as PricePoint[] })),
      api.history(stock.Kod, market).catch(() => ({ history: [] as HistoryPoint[] })),
    ]).then(([ph, h]) => {
      setPrices(ph.prices)
      setHistory(h.history)
    }).finally(() => setLoadingChart(false))
  }, [stock.Kod, market])

  const currency = (stock['Para Birimi'] as string) || '$'
  const chartData = merge(prices, history)
  const fairValue = stock['Ortalama Adil Fiyat'] as number | null
  const upside = stock['Beklenen Getiri (%)'] as number | null
  const upsideSign = upside !== null && upside >= 0 ? '+' : ''
  const upsideColorCls = getUpsideColorCls(upside)
  const signalColorCls = getSignalColorCls(stock['Sinyal Güven Seviyesi'] as string | null)
  const trailingPE = stock['Trailing P/E'] as number | null

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 border-b border-slate-800">
        <div className="flex flex-wrap items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-xl text-slate-100">{stock.Kod}</span>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">{stock.Sektör}</span>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-5 text-sm">
            <div>
              <div className="text-xs text-slate-500 mb-0.5">{tr.price}</div>
              <div className="font-mono text-slate-200 tabular-nums">
                {stock['Güncel Fiyat'] !== null ? fmtPrice(stock['Güncel Fiyat'] as number, currency) : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">{tr.fairValue}</div>
              <div className="font-mono text-slate-200 tabular-nums">
                {fairValue !== null ? fmtPrice(fairValue, currency) : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">{tr.upside}</div>
              <div className={`font-mono font-semibold tabular-nums ${upsideColorCls}`}>
                {upside !== null ? `${upsideSign}${upside.toFixed(1)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">F/K (P/E)</div>
              <div className="font-mono text-slate-400 tabular-nums">
                {trailingPE !== null ? `${trailingPE.toFixed(1)}×` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">{tr.wacc}</div>
              <div className="font-mono text-slate-400 tabular-nums">
                {stock.WACC !== null ? `${(stock.WACC as number).toFixed(2)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">{tr.signal}</div>
              <div className={`text-xs font-medium ${signalColorCls}`}>
                {tr.signalLabel(stock['Sinyal Güven Seviyesi'] as string | null)}{' '}
                {stock['Sinyal Kalite Skoru'] !== null ? `(${stock['Sinyal Kalite Skoru']})` : ''}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex rounded-lg overflow-hidden border border-slate-700">
            {(['analysis', 'chart'] as const).map(t => (
              <button
                type="button"
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${tab === t
                  ? 'bg-slate-700 text-slate-100'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                  }`}
              >
                {t === 'chart' ? tr.chart : 'Analiz'}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={handleRefreshTicker}
            disabled={refreshing}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
              bg-slate-800 hover:bg-slate-700 border border-slate-700 hover:border-slate-600
              disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150"
          >
            <span className={refreshing ? 'animate-spin inline-block' : ''}>↻</span>
            {refreshing ? tr.refreshingTicker : tr.refreshTicker}
          </button>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>
      </div>

      <div className="p-5">
        {tab === 'chart' ? (
          <ChartTab
            loadingChart={loadingChart}
            chartData={chartData}
            fairValue={fairValue}
            currency={currency}
            lang={lang}
          />
        ) : (
          <AnalysisTab stock={stock} currency={currency} />
        )}
      </div>
    </div>
  )
}
