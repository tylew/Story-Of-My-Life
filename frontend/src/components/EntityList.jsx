import { useState, useEffect } from 'react'
import { Users, Target, Zap, Calendar, FileText, RefreshCw, Filter, Grid, List, ChevronRight, Timer, AlertCircle } from 'lucide-react'

const API_BASE = '/api'

const typeConfig = {
  people: { icon: Users, color: 'cyan', singular: 'Person', plural: 'People' },
  projects: { icon: Target, color: 'purple', singular: 'Project', plural: 'Projects' },
  goals: { icon: Zap, color: 'green', singular: 'Goal', plural: 'Goals' },
  events: { icon: Calendar, color: 'pink', singular: 'Event', plural: 'Events' },
  notes: { icon: FileText, color: 'blue', singular: 'Note', plural: 'Notes' },
  periods: { icon: Timer, color: 'orange', singular: 'Period', plural: 'Periods' },
}

const colorClasses = {
  cyan: { bg: 'bg-neon-cyan/20', text: 'text-neon-cyan', border: 'border-neon-cyan/40' },
  purple: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple/40' },
  green: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green/40' },
  pink: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink/40' },
  blue: { bg: 'bg-neon-blue/20', text: 'text-neon-blue', border: 'border-neon-blue/40' },
  orange: { bg: 'bg-amber-500/20', text: 'text-amber-500', border: 'border-amber-500/40' },
}

export default function EntityList({ type, onEntitySelect, refreshKey }) {
  const [entities, setEntities] = useState([])
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState('grid') // 'grid' or 'list'
  const [filter, setFilter] = useState('')
  const [sortBy, setSortBy] = useState('created') // 'created', 'name', 'updated'

  const config = typeConfig[type] || typeConfig.notes
  const colors = colorClasses[config.color]
  const Icon = config.icon

  useEffect(() => {
    fetchEntities()
  }, [type, refreshKey])

  const fetchEntities = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/${type}`)
      const data = await res.json()
      setEntities(data[type] || data.entities || [])
    } catch (e) {
      console.error(`Failed to fetch ${type}:`, e)
    }
    setLoading(false)
  }

  const filteredEntities = entities
    .filter(e => {
      const name = (e.name || e.title || '').toLowerCase()
      const disamb = (e.disambiguator || '').toLowerCase()
      return name.includes(filter.toLowerCase()) || disamb.includes(filter.toLowerCase())
    })
    .sort((a, b) => {
      if (sortBy === 'name') {
        return (a.name || a.title || '').localeCompare(b.name || b.title || '')
      }
      if (sortBy === 'updated') {
        return new Date(b.updated_at || 0) - new Date(a.updated_at || 0)
      }
      return new Date(b.created_at || 0) - new Date(a.created_at || 0)
    })

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-slate-700/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center`}>
              <Icon className={`w-5 h-5 ${colors.text}`} />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold">{config.plural}</h1>
              <p className="text-sm text-slate-400">{entities.length} {entities.length === 1 ? config.singular : config.plural}</p>
            </div>
          </div>
          <button
            onClick={fetchEntities}
            className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
          >
            <RefreshCw className="w-5 h-5 text-neon-purple" />
          </button>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-4">
          <div className="flex-1 relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Filter..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
            />
          </div>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
          >
            <option value="created">Newest first</option>
            <option value="updated">Recently updated</option>
            <option value="name">Alphabetical</option>
          </select>
          <div className="flex rounded-lg overflow-hidden border border-slate-700">
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 ${viewMode === 'grid' ? 'bg-neon-purple/20 text-neon-purple' : 'text-slate-400 hover:text-white'}`}
            >
              <Grid className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('list')}
              className={`p-2 ${viewMode === 'list' ? 'bg-neon-purple/20 text-neon-purple' : 'text-slate-400 hover:text-white'}`}
            >
              <List className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {filteredEntities.length === 0 ? (
          <div className="text-center py-12">
            <div className={`w-16 h-16 rounded-xl ${colors.bg} flex items-center justify-center mx-auto mb-4`}>
              <Icon className={`w-8 h-8 ${colors.text}`} />
            </div>
            <p className="text-slate-400">{filter ? 'No matches found' : `No ${type} yet`}</p>
            <p className="text-sm text-slate-500 mt-1">Use the chat to add new {type}</p>
          </div>
        ) : viewMode === 'grid' ? (
          <div className="grid grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredEntities.map((entity, idx) => (
              <EntityCard 
                key={entity.id || idx}
                entity={entity}
                config={config}
                colors={colors}
                onClick={() => onEntitySelect?.(entity)}
                delay={idx * 50}
              />
            ))}
          </div>
        ) : (
          <div className="space-y-2">
            {filteredEntities.map((entity, idx) => (
              <EntityRow
                key={entity.id || idx}
                entity={entity}
                config={config}
                colors={colors}
                onClick={() => onEntitySelect?.(entity)}
                delay={idx * 30}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function EntityCard({ entity, config, colors, onClick, delay }) {
  const Icon = config.icon
  const isPeriod = entity.type === 'period'
  const isComplete = isPeriod ? (entity.start_date && entity.end_date) : true
  
  return (
    <button
      onClick={onClick}
      className="glass neon-border rounded-xl p-4 text-left hover:border-neon-purple/60 transition-all hover:scale-[1.02] animate-fade-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center`}>
          <Icon className={`w-5 h-5 ${colors.text}`} />
        </div>
        <div className="flex items-center gap-2">
          {isPeriod && !isComplete && (
            <span className="flex items-center gap-1 text-xs text-amber-400">
              <AlertCircle className="w-3 h-3" />
              Incomplete
            </span>
          )}
          {entity.confidence && (
            <span className="text-xs font-mono text-slate-500">{Math.round(entity.confidence * 100)}%</span>
          )}
        </div>
      </div>
      
      <h3 className="font-semibold text-lg mb-1 truncate">{entity.name || entity.title || 'Untitled'}</h3>
      
      {entity.disambiguator && (
        <p className="text-sm text-slate-400 mb-2 line-clamp-2">{entity.disambiguator}</p>
      )}
      
      {/* Period-specific: Show date range */}
      {isPeriod && (
        <p className="text-sm text-slate-400 mb-2">
          {entity.start_date ? new Date(entity.start_date).toLocaleDateString() : '?'} 
          {' → '} 
          {entity.end_date ? new Date(entity.end_date).toLocaleDateString() : '?'}
        </p>
      )}
      
      {entity.status && (
        <span className={`px-2 py-0.5 rounded-full text-xs ${colors.bg} ${colors.text}`}>
          {entity.status}
        </span>
      )}
      
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-700/50">
        <p className="text-xs text-slate-500 font-mono">
          {entity.created_at ? new Date(entity.created_at).toLocaleDateString() : '-'}
        </p>
        <ChevronRight className="w-4 h-4 text-slate-500" />
      </div>
    </button>
  )
}

function EntityRow({ entity, config, colors, onClick, delay }) {
  const Icon = config.icon
  
  return (
    <button
      onClick={onClick}
      className="w-full glass neon-border rounded-lg p-4 text-left hover:border-neon-purple/60 transition-all flex items-center gap-4 animate-slide-in"
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className={`w-10 h-10 rounded-lg ${colors.bg} flex items-center justify-center flex-shrink-0`}>
        <Icon className={`w-5 h-5 ${colors.text}`} />
      </div>
      
      <div className="flex-1 min-w-0">
        <h3 className="font-semibold truncate">{entity.name || entity.title || 'Untitled'}</h3>
        {entity.disambiguator && (
          <p className="text-sm text-slate-400 truncate">{entity.disambiguator}</p>
        )}
      </div>
      
      <div className="flex items-center gap-4 flex-shrink-0">
        {entity.status && (
          <span className={`px-2 py-0.5 rounded-full text-xs ${colors.bg} ${colors.text}`}>
            {entity.status}
          </span>
        )}
        <p className="text-xs text-slate-500 font-mono">
          {entity.created_at ? new Date(entity.created_at).toLocaleDateString() : '-'}
        </p>
        <ChevronRight className="w-4 h-4 text-slate-500" />
      </div>
    </button>
  )
}

