import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { fetchManufacturerHealth } from '../api'

interface ModelInfo {
  id: number
  model_name: string
  model_year: number | null
  rv_class: string | null
  data_quality: string
  floorplan_count: number
  image_count: number
  has_msrp: boolean
}

interface MfrHealth {
  manufacturer: {
    slug: string
    name: string
    display_name: string
    parent_company: string
    tier: string
    scrape_status: string
    last_scraped_at: string | null
  }
  totals: {
    models: number
    floorplans: number
    images: number
  }
  models: ModelInfo[]
  scrape_history: Array<{
    id: number
    started_at: string
    status: string
    models_found: number
    floorplans_added: number
    duration_s: number | null
  }>
}

const QUALITY_COLORS: Record<string, string> = {
  scraped: 'text-emerald-400',
  ai_generated: 'text-amber-400',
  manual: 'text-blue-400',
  pending: 'text-slate-500',
}

export default function ManufacturerDetail() {
  const { slug } = useParams<{ slug: string }>()
  const [data, setData] = useState<MfrHealth | null>(null)

  useEffect(() => {
    if (slug) fetchManufacturerHealth(slug).then(setData)
  }, [slug])

  if (!data) {
    return <div className="text-slate-400 text-center py-20">Loading...</div>
  }

  const mfr = data.manufacturer

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="text-sm text-slate-400">
        <Link to="/manufacturers" className="hover:text-white">Manufacturers</Link>
        <span className="mx-2">/</span>
        <span className="text-white">{mfr.display_name}</span>
      </div>

      {/* Header */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-bold text-white">{mfr.display_name}</h1>
            <p className="text-slate-400 mt-1">{mfr.parent_company} -- {mfr.tier.replace('_', ' ')}</p>
          </div>
          <div className="flex gap-2">
            <StatusBadge status={mfr.scrape_status} />
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mt-6">
          <div className="text-center">
            <div className="text-3xl font-bold text-white">{data.totals.models}</div>
            <div className="text-sm text-slate-400">Models</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-white">{data.totals.floorplans}</div>
            <div className="text-sm text-slate-400">Floorplans</div>
          </div>
          <div className="text-center">
            <div className="text-3xl font-bold text-white">{data.totals.images}</div>
            <div className="text-sm text-slate-400">Images</div>
          </div>
        </div>

        {mfr.last_scraped_at && (
          <p className="text-xs text-slate-500 mt-4">
            Last scraped: {new Date(mfr.last_scraped_at).toLocaleDateString()}
          </p>
        )}
      </div>

      {/* Models table */}
      <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
        <h2 className="text-lg font-semibold text-white mb-4">
          Models ({data.models.length})
        </h2>

        {data.models.length === 0 ? (
          <div className="text-slate-500 text-center py-8 border border-dashed border-slate-700 rounded-lg">
            No models scraped yet. This manufacturer is queued for data collection.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-slate-400 border-b border-slate-700">
                  <th className="pb-2 font-medium">Model</th>
                  <th className="pb-2 font-medium">Year</th>
                  <th className="pb-2 font-medium">Class</th>
                  <th className="pb-2 font-medium text-right">Floorplans</th>
                  <th className="pb-2 font-medium text-right">Images</th>
                  <th className="pb-2 font-medium text-right">MSRP</th>
                  <th className="pb-2 font-medium text-right">Quality</th>
                </tr>
              </thead>
              <tbody>
                {data.models.map(m => (
                  <tr key={m.id} className="border-b border-slate-700/50 text-slate-300 hover:bg-slate-700/30">
                    <td className="py-2.5 font-medium text-white">{m.model_name}</td>
                    <td className="py-2.5">{m.model_year || '--'}</td>
                    <td className="py-2.5">{m.rv_class || '--'}</td>
                    <td className="py-2.5 text-right">
                      <span className={m.floorplan_count > 0 ? 'text-emerald-400' : 'text-slate-600'}>
                        {m.floorplan_count}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      <span className={m.image_count > 0 ? 'text-blue-400' : 'text-slate-600'}>
                        {m.image_count}
                      </span>
                    </td>
                    <td className="py-2.5 text-right">
                      {m.has_msrp
                        ? <span className="text-emerald-400">Yes</span>
                        : <span className="text-slate-600">--</span>
                      }
                    </td>
                    <td className="py-2.5 text-right">
                      <span className={QUALITY_COLORS[m.data_quality] || 'text-slate-500'}>
                        {m.data_quality}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Scrape history */}
      {data.scrape_history.length > 0 && (
        <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
          <h2 className="text-lg font-semibold text-white mb-4">Scrape History</h2>
          <div className="space-y-2">
            {data.scrape_history.map(run => (
              <div key={run.id} className="flex items-center justify-between bg-slate-700/30 rounded px-4 py-2.5 text-sm">
                <div className="flex items-center gap-3">
                  <StatusBadge status={run.status} />
                  <span className="text-slate-300">{new Date(run.started_at).toLocaleString()}</span>
                </div>
                <div className="flex gap-4 text-slate-400 text-xs">
                  <span>{run.models_found} models found</span>
                  <span>{run.floorplans_added} FPs added</span>
                  {run.duration_s != null && <span>{run.duration_s.toFixed(1)}s</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    complete: 'bg-emerald-500/20 text-emerald-400',
    success: 'bg-emerald-500/20 text-emerald-400',
    partial: 'bg-amber-500/20 text-amber-400',
    in_progress: 'bg-blue-500/20 text-blue-400',
    running: 'bg-blue-500/20 text-blue-400',
    error: 'bg-red-500/20 text-red-400',
    not_started: 'bg-slate-600/30 text-slate-500',
  }
  return (
    <span className={`${colors[status] || colors.not_started} text-xs px-2.5 py-1 rounded-full font-medium`}>
      {status.replace('_', ' ')}
    </span>
  )
}
