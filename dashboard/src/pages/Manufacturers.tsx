import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchManufacturers, type Manufacturer } from '../api'

const TIER_LABELS: Record<string, string> = {
  wave_1: 'Wave 1 -- Flagships',
  wave_2: 'Wave 2 -- Secondary',
  wave_3: 'Wave 3 -- Mid-Tier',
  wave_4: 'Wave 4 -- Long Tail',
}

const STATUS_BADGES: Record<string, { bg: string; text: string }> = {
  complete: { bg: 'bg-emerald-500/20', text: 'text-emerald-400' },
  partial: { bg: 'bg-amber-500/20', text: 'text-amber-400' },
  in_progress: { bg: 'bg-blue-500/20', text: 'text-blue-400' },
  not_started: { bg: 'bg-slate-600/30', text: 'text-slate-500' },
}

const PARENT_COLORS: Record<string, string> = {
  'Thor Industries': 'border-l-red-500',
  'Forest River (Berkshire Hathaway)': 'border-l-blue-500',
  'Winnebago Industries': 'border-l-amber-500',
  'REV Group': 'border-l-purple-500',
  'Independent': 'border-l-slate-500',
}

export default function Manufacturers() {
  const [mfrs, setMfrs] = useState<Manufacturer[]>([])
  const [filter, setFilter] = useState<string>('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetchManufacturers().then(setMfrs)
  }, [])

  const filtered = mfrs.filter(m => {
    if (filter !== 'all' && m.tier !== filter) return false
    if (search && !m.display_name.toLowerCase().includes(search.toLowerCase()) &&
        !m.parent_company.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  // Group by tier
  const grouped: Record<string, Manufacturer[]> = {}
  for (const m of filtered) {
    if (!grouped[m.tier]) grouped[m.tier] = []
    grouped[m.tier].push(m)
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-3xl font-bold text-white">Manufacturers ({mfrs.length})</h1>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
          <select
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="bg-slate-800 border border-slate-600 rounded px-3 py-1.5 text-sm text-white focus:outline-none focus:border-blue-500"
          >
            <option value="all">All Tiers</option>
            <option value="wave_1">Wave 1</option>
            <option value="wave_2">Wave 2</option>
            <option value="wave_3">Wave 3</option>
            <option value="wave_4">Wave 4</option>
          </select>
        </div>
      </div>

      {Object.entries(grouped).sort().map(([tier, items]) => (
        <div key={tier}>
          <h2 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3">
            {TIER_LABELS[tier] || tier}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            {items.map(m => {
              const badge = STATUS_BADGES[m.scrape_status] || STATUS_BADGES.not_started
              const parentBorder = PARENT_COLORS[m.parent_company] || 'border-l-slate-600'

              return (
                <Link
                  key={m.slug}
                  to={`/manufacturers/${m.slug}`}
                  className={`bg-slate-800 border border-slate-700 border-l-4 ${parentBorder} rounded-lg p-4 hover:bg-slate-750 hover:border-slate-600 transition-colors block`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="text-white font-semibold">{m.display_name}</h3>
                      <p className="text-xs text-slate-500">{m.parent_company}</p>
                    </div>
                    <span className={`${badge.bg} ${badge.text} text-xs px-2 py-0.5 rounded-full font-medium`}>
                      {m.scrape_status.replace('_', ' ')}
                    </span>
                  </div>
                  <div className="flex gap-4 text-xs text-slate-400">
                    <span>{m.model_count} models</span>
                    <span>{m.floorplan_count} floorplans</span>
                    <span>{m.image_count} images</span>
                  </div>
                  <div className="flex gap-1.5 mt-2">
                    {m.rv_types.map(t => (
                      <span key={t} className="bg-slate-700 text-slate-300 text-xs px-2 py-0.5 rounded">
                        {t}
                      </span>
                    ))}
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
