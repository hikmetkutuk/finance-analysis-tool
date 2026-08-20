import { useCallback, useMemo, useState } from 'react'
import { translations } from '../i18n'
import type { Lang, SortDir, SortKey, Stock } from '../types'

interface Props {
  readonly stocks: Stock[]
  readonly selected: Stock | null
  readonly onSelect: (s: Stock) => void
  readonly lang: Lang
}

type Col = {
  key: SortKey
  label: string
  align?: 'right' | 'left'
  fmt?: (v: number | string | null, row: Stock) => React.ReactNode
}

function pctColor(v: number): string {
  if (v >= 30)  return 'text-emerald-400 font-semibold'
  if (v >= 10)  return 'text-emerald-500'
  if (v >= 0)   return 'text-slate-300'
  if (v >= -10) return 'text-orange-400'
  return 'text-rose-400 font-semibold'
}

function pct(v: number | null): React.ReactNode {
  if (v === null || v === undefined) return <span className="text-slate-600">—</span>
  return <span className={`tabular-nums ${pctColor(v)}`}>{v >= 0 ? '+' : ''}{v.toFixed(1)}%</span>
}

function price(v: number | null, currency: string): React.ReactNode {
  if (v === null || v === undefined) return <span className="text-slate-600">—</span>
  return (
    <span className="tabular-nums text-slate-200">
      {currency}{v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
    </span>
  )
}

function num(v: number | null): React.ReactNode {
  if (v === null || v === undefined) return <span className="text-slate-600">—</span>
  return <span className="tabular-nums text-slate-400">{v.toFixed(1)}</span>
}

function signalBadgeClass(label: string): string {
  if (label === 'High')   return 'bg-emerald-900/60 text-emerald-400 border-emerald-800'
  if (label === 'Medium') return 'bg-amber-900/60 text-amber-400 border-amber-800'
  return 'bg-rose-900/60 text-rose-400 border-rose-800'
}

function SignalBadge({ label, score, displayLabel }: Readonly<{ label: string | null; score: number | null; displayLabel: string }>) {
  if (!label) return <span className="text-slate-600">—</span>
  const cl = signalBadgeClass(label)
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border ${cl}`}>
      {score !== null && <span className="tabular-nums font-mono">{score}</span>}
      <span>{displayLabel}</span>
    </span>
  )
}

interface SignalColCellProps {
  readonly label: string | null
  readonly score: number | null
  readonly displayLabel: string
}

function SignalColCell({ label, score, displayLabel }: SignalColCellProps) {
  return <SignalBadge label={label} score={score} displayLabel={displayLabel} />
}

function upsideRowColor(upside: number | null): string {
  if (upside === null) return ''
  if (upside >= 30)  return 'bg-emerald-950/40'
  if (upside >= 10)  return 'bg-emerald-950/20'
  if (upside >= 0)   return ''
  if (upside >= -15) return 'bg-rose-950/20'
  return 'bg-rose-950/40'
}

export default function PortfolioTable({ stocks, selected, onSelect, lang }: Readonly<Props>) {
  const [sortKey, setSortKey] = useState<SortKey>('Beklenen Getiri (%)')
  const [sortDir, setSortDir] = useState<SortDir>('desc')
  const [search, setSearch] = useState('')
  const tr = translations[lang]

  const fmtSignal = useCallback((v: number | string | null, row: Stock) => (
    <SignalColCell
      label={v as string | null}
      score={row['Sinyal Kalite Skoru'] as number | null}
      displayLabel={tr.signalLabel(v as string | null)}
    />
  ), [tr.signalLabel])

  const COLUMNS: Col[] = [
    { key: 'Kod', label: tr.colTicker, align: 'left' },
    { key: 'Sektör', label: tr.colSector, align: 'left' },
    { key: 'Güncel Fiyat', label: tr.colPrice, align: 'right', fmt: (v, row) => price(v as number | null, (row['Para Birimi'] as string) || '$') },
    { key: 'Ortalama Adil Fiyat', label: tr.colFairValue, align: 'right', fmt: (v, row) => price(v as number | null, (row['Para Birimi'] as string) || '$') },
    { key: 'Beklenen Getiri (%)', label: tr.colUpside, align: 'right', fmt: (v) => pct(v as number | null) },
    { key: 'Sinyal Güven Seviyesi', label: tr.colSignal, align: 'left', fmt: fmtSignal },
    { key: 'WACC', label: tr.colWacc, align: 'right', fmt: (v) => num(v as number | null) },
    { key: 'DCF Değerlemesi', label: tr.colDcf, align: 'right', fmt: (v, row) => price(v as number | null, (row['Para Birimi'] as string) || '$') },
    { key: 'Trailing P/E', label: tr.colPE, align: 'right', fmt: (v) => v !== null && v !== undefined ? `${(v as number).toFixed(1)}×` : '—' },
    { key: 'Peer EV/EBITDA', label: tr.colEvEbitda, align: 'right', fmt: (v) => v !== null && v !== undefined ? `${(v as number).toFixed(1)}×` : '—' },
  ]

  const sorted = useMemo(() => {
    let filtered = stocks
    if (search.trim()) {
      const q = search.trim().toUpperCase()
      filtered = stocks.filter(s =>
        s.Kod.includes(q) || (s.Sektör || '').toUpperCase().includes(q)
      )
    }
    return [...filtered].sort((a, b) => {
      const av = sortKey === 'Sinyal Güven Seviyesi' ? a['Sinyal Kalite Skoru'] : a[sortKey]
      const bv = sortKey === 'Sinyal Güven Seviyesi' ? b['Sinyal Kalite Skoru'] : b[sortKey]
      if (av === null || av === undefined) return 1
      if (bv === null || bv === undefined) return -1
      if (typeof av === 'string') {
        return sortDir === 'asc'
          ? av.localeCompare(bv as string)
          : (bv as string).localeCompare(av)
      }
      return sortDir === 'asc' ? (av as number) - (bv as number) : (bv as number) - (av as number)
    })
  }, [stocks, sortKey, sortDir, search])

  const toggleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  function renderCell(col: Col, stock: Stock): React.ReactNode {
    if (col.key === 'Kod')    return <span className="font-mono font-semibold text-slate-100">{stock.Kod}</span>
    if (col.key === 'Sektör') return <span className="text-slate-400 text-xs">{stock.Sektör || '—'}</span>
    if (col.fmt)              return col.fmt(stock[col.key], stock)
    return <span className="text-slate-300">{String(stock[col.key] ?? '—')}</span>
  }

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/50 overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-800">
        <input
          type="text"
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder={tr.searchPlaceholder(search)}
          className="w-56 bg-slate-800 border border-slate-700 rounded-lg px-3 py-1.5 text-sm
            text-slate-200 placeholder-slate-500 focus:outline-none focus:border-slate-500 transition"
        />
        <span className="text-xs text-slate-500">{tr.stockCount(sorted.length)}</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="border-b border-slate-800">
              {COLUMNS.map(col => (
                <th
                  key={col.key as string}
                  onClick={() => toggleSort(col.key)}
                  className={`px-4 py-2.5 text-xs font-medium text-slate-400 select-none
                    cursor-pointer hover:text-slate-200 transition-colors whitespace-nowrap
                    ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                >
                  {col.label}
                  {sortKey === col.key && (
                    <span className="ml-1 text-emerald-400">{sortDir === 'asc' ? '↑' : '↓'}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((stock, i) => {
              const isSelected = selected?.Kod === stock.Kod
              const upside = stock['Beklenen Getiri (%)'] as number | null
              return (
                <tr
                  key={stock.Kod}
                  onClick={() => onSelect(stock)}
                  className={`
                    border-b border-slate-800/50 cursor-pointer transition-colors
                    ${upsideRowColor(upside)}
                    ${isSelected
                      ? 'bg-slate-700/60 border-l-2 border-l-emerald-500'
                      : 'hover:bg-slate-800/50'
                    }
                    ${i === sorted.length - 1 ? 'border-b-0' : ''}
                  `}
                >
                  {COLUMNS.map(col => (
                    <td
                      key={col.key as string}
                      className={`px-4 py-2.5 ${col.align === 'right' ? 'text-right' : 'text-left'}`}
                    >
                      {renderCell(col, stock)}
                    </td>
                  ))}
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
