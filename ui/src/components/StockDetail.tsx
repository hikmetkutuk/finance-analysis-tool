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
import type { HistoryPoint, PricePoint, Stock } from '../types'

interface Props {
  readonly stock: Stock
  readonly onClose: () => void
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

function fmtDate(d: string) {
  try { return new Date(d).toLocaleDateString('tr-TR', { day: '2-digit', month: 'short' }) }
  catch { return d }
}

function fmtPrice(v: number) {
  return `$${v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function getUpsideColorCls(upside: number | null): string {
  if (upside === null) return 'text-slate-400'
  return upside >= 0 ? 'text-emerald-400' : 'text-rose-400'
}

function getSignalColorCls(signal: string | null | undefined): string {
  if (signal === 'High')   return 'text-emerald-400'
  if (signal === 'Medium') return 'text-amber-400'
  return 'text-rose-400'
}

interface ModelRow {
  label: string
  value: number | null
}

function ModelGrid({ stock }: Readonly<{ stock: Stock }>) {
  const models: ModelRow[] = [
    { label: 'DCF', value: stock['DCF Değerlemesi'] as number | null },
    { label: 'F/K (P/E)', value: stock['F/K Değerlemesi'] as number | null },
    { label: 'EV/EBITDA', value: stock['EV/EBITDA Değerlemesi'] as number | null },
    { label: 'PD/DD (P/B)', value: stock['PD/DD Finansal Model'] as number | null },
    { label: 'DDM', value: stock['DDM Değerlemesi'] as number | null },
    { label: 'EFK', value: stock['EFK Değerlemesi'] as number | null },
    { label: 'NDK', value: stock['NDK Değerlemesi'] as number | null },
    { label: 'Graham', value: stock['Graham Değerlemesi'] as number | null },
  ]
  const current = stock['Güncel Fiyat'] as number | null
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {models.map(m => {
        if (m.value === null) return null
        const up = current ? ((m.value / current) - 1) * 100 : null
        let color = ''
        if (up !== null) color = up >= 0 ? 'text-emerald-400' : 'text-rose-400'
        return (
          <div key={m.label} className="bg-slate-800/60 rounded-lg px-3 py-2.5 border border-slate-700/50">
            <div className="text-xs text-slate-500 mb-1">{m.label}</div>
            <div className="text-sm font-mono text-slate-200">{fmtPrice(m.value)}</div>
            {up !== null && (
              <div className={`text-xs tabular-nums mt-0.5 ${color}`}>
                {up >= 0 ? '+' : ''}{up.toFixed(1)}%
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

interface ChartTabProps {
  readonly loadingChart: boolean
  readonly chartData: ChartPoint[]
  readonly fairValue: number | null
}

function ChartTab({ loadingChart, chartData, fairValue }: ChartTabProps) {
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
        Fiyat verisi bulunamadı
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
            tickFormatter={v => `$${v}`}
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
              `$${value.toFixed(2)}`,
              name === 'price' ? 'Fiyat' : 'Adil Fiyat',
            ]}
          />
          {fairValue !== null && (
            <ReferenceLine
              y={fairValue}
              stroke="#f59e0b"
              strokeDasharray="6 3"
              strokeWidth={1.5}
              label={{ value: `Adil: $${fairValue.toFixed(0)}`, fill: '#f59e0b', fontSize: 11, position: 'insideTopRight' }}
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
      <p className="text-xs text-slate-600 text-center mt-1">
        Gri alan: gerçek fiyat · Sarı çizgi: mevcut adil fiyat · Sarı noktalar: geçmiş adil fiyat anlık görüntüleri
      </p>
    </div>
  )
}

export default function StockDetail({ stock, onClose }: Readonly<Props>) {
  const [tab, setTab] = useState<'chart' | 'models'>('chart')
  const [prices, setPrices] = useState<PricePoint[]>([])
  const [history, setHistory] = useState<HistoryPoint[]>([])
  const [loadingChart, setLoadingChart] = useState(true)

  useEffect(() => {
    setLoadingChart(true)
    setPrices([])
    setHistory([])
    Promise.all([
      api.priceHistory(stock.Kod).catch(() => ({ prices: [] as PricePoint[] })),
      api.history(stock.Kod).catch(() => ({ history: [] as HistoryPoint[] })),
    ]).then(([ph, h]) => {
      setPrices(ph.prices)
      setHistory(h.history)
    }).finally(() => setLoadingChart(false))
  }, [stock.Kod])

  const chartData = merge(prices, history)
  const fairValue = stock['Ortalama Adil Fiyat'] as number | null
  const upside = stock['Beklenen Getiri (%)'] as number | null
  const upsideSign = upside !== null && upside >= 0 ? '+' : ''
  const upsideColorCls = getUpsideColorCls(upside)
  const signalColorCls = getSignalColorCls(stock['Sinyal Güven Seviyesi'] as string | null)

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
        <div className="flex items-center gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-xl text-slate-100">{stock.Kod}</span>
              <span className="text-xs text-slate-500 bg-slate-800 px-2 py-0.5 rounded">{stock.Sektör}</span>
            </div>
          </div>
          <div className="flex items-center gap-5 text-sm">
            <div>
              <div className="text-xs text-slate-500 mb-0.5">Fiyat</div>
              <div className="font-mono text-slate-200 tabular-nums">
                {stock['Güncel Fiyat'] !== null ? fmtPrice(stock['Güncel Fiyat'] as number) : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">Adil Fiyat</div>
              <div className="font-mono text-slate-200 tabular-nums">
                {fairValue !== null ? fmtPrice(fairValue) : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">Potansiyel</div>
              <div className={`font-mono font-semibold tabular-nums ${upsideColorCls}`}>
                {upside !== null ? `${upsideSign}${upside.toFixed(1)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">WACC</div>
              <div className="font-mono text-slate-400 tabular-nums">
                {stock.WACC !== null ? `${(stock.WACC as number).toFixed(1)}%` : '—'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-0.5">Sinyal</div>
              <div className={`text-xs font-medium ${signalColorCls}`}>
                {stock['Sinyal Güven Seviyesi'] || '—'} {stock['Sinyal Kalite Skoru'] !== null ? `(${stock['Sinyal Kalite Skoru']})` : ''}
              </div>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex rounded-lg overflow-hidden border border-slate-700">
            {(['chart', 'models'] as const).map(t => (
              <button
                type="button"
                key={t}
                onClick={() => setTab(t)}
                className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                  tab === t
                    ? 'bg-slate-700 text-slate-100'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                {t === 'chart' ? 'Grafik' : 'Modeller'}
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-300 transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-5">
        {tab === 'chart' ? (
          <ChartTab loadingChart={loadingChart} chartData={chartData} fairValue={fairValue} />
        ) : (
          <div className="space-y-4">
            <ModelGrid stock={stock} />
            {stock['Model Kalite Uyarıları'] && (
              <div className="text-xs text-amber-400/70 bg-amber-950/20 border border-amber-900/30 rounded-lg px-3 py-2">
                Uyarılar: {stock['Model Kalite Uyarıları']}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
