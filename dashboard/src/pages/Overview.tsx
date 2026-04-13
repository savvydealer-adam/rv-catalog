import { useEffect, useState } from 'react'
import { fetchHealth, type HealthStats } from '../api'

const TIER_LABELS: Record<string, string> = {
  wave_1: 'Wave 1 -- Flagships',
  wave_2: 'Wave 2 -- Secondary',
  wave_3: 'Wave 3 -- Mid-Tier',
  wave_4: 'Wave 4 -- Long Tail',
}

const STATUS_COLORS: Record<string, string> = {
  complete: 'bg-emerald-500',
  partial: 'bg-amber-500',
  in_progress: 'bg-blue-500',
  not_started: 'bg-slate-600',
}

export default function Overview() {
  const [stats, setStats] = useState<HealthStats | null>(null)

  useEffect(() => {
    fetchHealth().then(setStats)
  }, [])

  if (!stats) {
    return <div className="text-slate-400 text-center py-20">Loading...</div>
  }

  const completePct = stats.total_manufacturers > 0
    ? Math.round((stats.scrape_status['complete'] || 0) / stats.total_manufacturers * 100)
    : 0

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold text-white">RV Catalog Coverage</h1>

      {/* Top-level stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Manufacturers" value={stats.total_manufacturers} />
        <StatCard label="Models" value={stats.total_models} />
        <StatCard label="Floorplans" value={stats.total_floorplans} />
        <StatCard label="Images" value={stats.total_images} />
      </div>

      {/* Overall progress bar */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-white">Overall Scrape Progress</h2>
          <span className="text-2xl font-bold text-blue-400">{completePct}%</span>
        </div>
        <div className="w-full bg-slate-700 rounded-full h-4 overflow-hidden flex">
          {(['complete', 'partial', 'in_progress', 'not_started'] as const).map(status => {
            const count = stats.scrape_status[status] || 0
            const pct = count / stats.total_manufacturers * 100
            return pct > 0 ? (
              <div
                key={status}
                className={`${STATUS_COLORS[status]} h-full transition-all`}
                style={{ width: `${pct}%` }}
                title={`${status}: ${count}`}
              />
            ) : null
          })}
        </div>
        <div className="flex gap-4 mt-3 text-xs text-slate-400">
          {Object.entries(stats.scrape_status).map(([status, count]) => (
            <div key={status} className="flex items-center gap-1.5">
              <div className={`w-2.5 h-2.5 rounded-full ${STATUS_COLORS[status] || 'bg-slate-600'}`} />
              {status.replace('_', ' ')}: {count}
            </div>
          ))}
        </div>
      </div>

      {/* Tier breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {Object.entries(stats.tiers).map(([tier, data]) => (
          <div key={tier} className="bg-slate-800 rounded-lg p-5 border border-slate-700">
            <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3">
              {TIER_LABELS[tier] || tier}
            </h3>
            <div className="grid grid-cols-3 gap-3 mb-3">
              <MiniStat label="Brands" value={data.total} />
              <MiniStat label="Models" value={data.models} />
              <MiniStat label="Floorplans" value={data.floorplans} />
            </div>
            <div className="w-full bg-slate-700 rounded-full h-2 overflow-hidden flex">
              <div className="bg-emerald-500 h-full" style={{ width: `${data.complete / data.total * 100}%` }} />
              <div className="bg-amber-500 h-full" style={{ width: `${data.partial / data.total * 100}%` }} />
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {data.complete}/{data.total} complete
              {data.partial > 0 && `, ${data.partial} partial`}
            </p>
          </div>
        ))}
      </div>

      {/* Parent companies */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold text-white mb-4">Parent Companies</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-400 border-b border-slate-700">
                <th className="pb-2 font-medium">Company</th>
                <th className="pb-2 font-medium text-right">Brands</th>
                <th className="pb-2 font-medium text-right">Models</th>
                <th className="pb-2 font-medium text-right">Floorplans</th>
                <th className="pb-2 font-medium text-right">Complete</th>
              </tr>
            </thead>
            <tbody>
              {stats.parent_companies.map(pc => (
                <tr key={pc.name} className="border-b border-slate-700/50 text-slate-300">
                  <td className="py-2.5 font-medium text-white">{pc.name}</td>
                  <td className="py-2.5 text-right">{pc.brands}</td>
                  <td className="py-2.5 text-right">{pc.models}</td>
                  <td className="py-2.5 text-right">{pc.floorplans}</td>
                  <td className="py-2.5 text-right">
                    <span className={pc.brands_complete === pc.brands ? 'text-emerald-400' : 'text-amber-400'}>
                      {pc.brands_complete}/{pc.brands}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Field completeness */}
      {stats.field_completeness && Object.keys(stats.field_completeness).length > 1 && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">
            Floorplan Data Completeness ({stats.field_completeness.total_floorplans} floorplans)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Object.entries(stats.field_completeness)
              .filter(([k]) => k !== 'total_floorplans')
              .map(([field, pct]) => (
                <div key={field}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-slate-400">{field.replace(/_/g, ' ')}</span>
                    <span className={pct >= 90 ? 'text-emerald-400' : pct >= 50 ? 'text-amber-400' : 'text-red-400'}>
                      {pct}%
                    </span>
                  </div>
                  <div className="w-full bg-slate-700 rounded-full h-1.5">
                    <div
                      className={`h-full rounded-full ${pct >= 90 ? 'bg-emerald-500' : pct >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* RV Classes */}
      {stats.rv_classes.length > 0 && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Coverage by RV Class</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            {stats.rv_classes.map(c => (
              <div key={c.rv_class} className="bg-slate-700/50 rounded-lg px-4 py-3 flex items-center justify-between">
                <span className="text-white text-sm font-medium">{c.rv_class}</span>
                <div className="text-right">
                  <span className="text-blue-400 font-bold">{c.models}</span>
                  <span className="text-slate-500 text-xs ml-1">models</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="bg-slate-800 rounded-lg p-5 border border-slate-700 text-center">
      <div className="text-3xl font-bold text-white">{value.toLocaleString()}</div>
      <div className="text-sm text-slate-400 mt-1">{label}</div>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center">
      <div className="text-xl font-bold text-white">{value}</div>
      <div className="text-xs text-slate-500">{label}</div>
    </div>
  )
}
