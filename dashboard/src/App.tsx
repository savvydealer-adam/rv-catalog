import { Routes, Route, Link, useLocation } from 'react-router-dom'
import Overview from './pages/Overview'
import Manufacturers from './pages/Manufacturers'
import ManufacturerDetail from './pages/ManufacturerDetail'

const NAV = [
  { path: '/', label: 'Overview' },
  { path: '/manufacturers', label: 'Manufacturers' },
]

export default function App() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-slate-900">
      {/* Header */}
      <header className="border-b border-slate-700 bg-slate-800/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center h-14 gap-8">
          <Link to="/" className="text-white font-bold text-lg tracking-tight">
            RV Catalog
          </Link>
          <nav className="flex gap-1">
            {NAV.map(n => (
              <Link
                key={n.path}
                to={n.path}
                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                  location.pathname === n.path
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                {n.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/manufacturers" element={<Manufacturers />} />
          <Route path="/manufacturers/:slug" element={<ManufacturerDetail />} />
        </Routes>
      </main>
    </div>
  )
}
