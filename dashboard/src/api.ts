let _token: string | null = null

export function setAuthToken(token: string | null) {
  _token = token
}

function authHeaders(): Record<string, string> {
  if (_token) return { Authorization: `Bearer ${_token}` }
  return {}
}

const BASE = '/api'

export async function fetchHealth() {
  const res = await fetch(`${BASE}/health`, { headers: authHeaders() })
  return res.json()
}

export async function fetchManufacturers(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : ''
  const res = await fetch(`${BASE}/manufacturers${qs}`, { headers: authHeaders() })
  return res.json()
}

export async function fetchManufacturer(slug: string) {
  const res = await fetch(`${BASE}/manufacturers/${slug}`, { headers: authHeaders() })
  return res.json()
}

export async function fetchManufacturerHealth(slug: string) {
  const res = await fetch(`${BASE}/health/manufacturer/${slug}`, { headers: authHeaders() })
  return res.json()
}

export interface HealthStats {
  total_manufacturers: number
  total_models: number
  total_floorplans: number
  total_images: number
  tiers: Record<string, {
    total: number
    complete: number
    partial: number
    not_started: number
    models: number
    floorplans: number
  }>
  parent_companies: Array<{
    name: string
    brands: number
    models: number
    floorplans: number
    brands_complete: number
  }>
  rv_classes: Array<{ rv_class: string; models: number; floorplans: number }>
  data_quality: Record<string, number>
  scrape_status: Record<string, number>
  field_completeness: Record<string, number>
}

export interface Manufacturer {
  id: number
  slug: string
  name: string
  display_name: string
  parent_company: string
  website: string
  rv_types: string[]
  tier: string
  scrape_priority: number
  scrape_status: string
  last_scraped_at: string | null
  model_count: number
  floorplan_count: number
  image_count: number
  coverage_pct: number
}
