import { useEffect, useState } from 'react'

interface ScrapeRun {
  id: number
  manufacturer_slug: string
  manufacturer_name: string
  started_at: string
  finished_at: string | null
  status: string
  models_found: number
  models_added: number
  floorplans_added: number
  images_downloaded: number
  duration_s: number | null
  errors: string[]
}

interface ActiveMfr {
  slug: string
  display_name: string
  scrape_status: string
}

const TIERS = [
  { value: 'wave_1', label: 'Wave 1 (Flagships)' },
  { value: 'wave_2', label: 'Wave 2 (Secondary)' },
  { value: 'wave_3', label: 'Wave 3 (Mid-Tier)' },
  { value: 'wave_4', label: 'Wave 4 (Long Tail)' },
]

const STATUS_COLORS: Record<string, string> = {
  success: 'bg-emerald-500/20 text-emerald-400',
  partial: 'bg-amber-500/20 text-amber-400',
  running: 'bg-blue-500/20 text-blue-400 animate-pulse',
  error: 'bg-red-500/20 text-red-400',
}

export default function ScrapeRuns() {
  const [runs, setRuns] = useState<ScrapeRun[]>([])
  const [active, setActive] = useState<ActiveMfr[]>([])
  const [loading, setLoading] = useState(true)

  const fetchData = () => {
    Promise.all([
      fetch('/api/scrape/runs?limit=100', { headers: authHeader() }).then(r => r.json()),
      fetch('/api/scrape/active', { headers: authHeader() }).then(r => r.json()),
    ]).then(([r, a]) => {
      setRuns(r)
      setActive(a)
      setLoading(false)
    })
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [])

  const triggerWave = async (wave: string) => {
    await fetch('/api/scrape/trigger', {
      method: 'POST',
      headers: { ...authHeader(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ wave }),
    })
    fetchData()
  }

  if (loading) {
    return <div className="text-slate-400 text-center py-20">Loading...</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-3xl font-bold text-white">Scrape Runs</h1>
        <div className="flex gap-2">
          {TIERS.map(t => (
            <button
              key={t.value}
              onClick={() => triggerWave(t.value)}
              className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded text-sm font-medium transition-colors"
            >
              Run {t.label}
            </button>
          ))}
        </div>
      </div>

      {active.length > 0 && (
        <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
            <h2 className="text-blue-300 font-semibold">In Progress ({active.length})</h2>
          </div>
          <div className="flex flex-wrap gap-2">
            {active.map(m => (
              <span key={m.slug} className="bg-blue-500/20 text-blue-300 text-sm px-3 py-1 rounded-full">
                {m.display_name}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="bg-slate-800 rounded-lg border border-slate-700 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-400 border-b border-slate-700 bg-slate-900/50">
              <th className="px-4 py-3 font-medium">Manufacturer</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Started</th>
              <th className="px-4 py-3 font-medium text-right">Duration</th>
              <th className="px-4 py-3 font-medium text-right">Models</th>
              <th className="px-4 py-3 font-medium text-right">Floorplans</th>
              <th className="px-4 py-3 font-medium text-right">Images</th>
              <th className="px-4 py-3 font-medium text-right">Errors</th>
            </tr>
          </thead>
          <tbody>
            {runs.map(run => (
              <tr key={run.id} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                <td className="px-4 py-3 font-medium text-white">{run.manufacturer_name}</td>
                <td className="px-4 py-3">
                  <span className={`${STATUS_COLORS[run.status] || 'bg-slate-600/30 text-slate-400'} text-xs px-2.5 py-1 rounded-full font-medium`}>
                    {run.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-400">
                  {new Date(run.started_at + 'Z').toLocaleTimeString()}
                </td>
                <td className="px-4 py-3 text-right text-slate-400">
                  {run.duration_s != null ? `${run.duration_s.toFixed(0)}s` : '--'}
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={run.models_added > 0 ? 'text-white' : 'text-slate-600'}>
                    {run.models_added}/{run.models_found}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={run.floorplans_added > 0 ? 'text-emerald-400' : 'text-slate-600'}>
                    {run.floorplans_added}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <span className={run.images_downloaded > 0 ? 'text-blue-400' : 'text-slate-600'}>
                    {run.images_downloaded}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  {run.errors.length > 0
                    ? <span className="text-red-400">{run.errors.length}</span>
                    : <span className="text-slate-600">--</span>
                  }
                </td>
              </tr>
            ))}
            {runs.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-12 text-center text-slate-500">
                  No scrape runs yet. Click a "Run Wave" button above to start.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function authHeader(): Record<string, string> {
  const token = sessionStorage.getItem('rv_catalog_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
