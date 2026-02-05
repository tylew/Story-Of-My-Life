import { useState, useEffect, useRef } from 'react'
import { Search, X, Users, Target, Zap, Calendar, FileText, Loader2 } from 'lucide-react'

const API_BASE = '/api'

const typeConfig = {
  person: { icon: Users, color: 'text-neon-cyan', bg: 'bg-neon-cyan/20' },
  project: { icon: Target, color: 'text-neon-purple', bg: 'bg-neon-purple/20' },
  goal: { icon: Zap, color: 'text-neon-green', bg: 'bg-neon-green/20' },
  event: { icon: Calendar, color: 'text-neon-pink', bg: 'bg-neon-pink/20' },
  note: { icon: FileText, color: 'text-neon-blue', bg: 'bg-neon-blue/20' },
}

export default function SearchModal({ isOpen, onClose, onSelect }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [selectedIndex, setSelectedIndex] = useState(0)
  const inputRef = useRef()
  const resultsRef = useRef()

  useEffect(() => {
    if (isOpen) {
      setQuery('')
      setResults([])
      setSelectedIndex(0)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  useEffect(() => {
    if (query.length >= 2) {
      searchEntities()
    } else {
      setResults([])
    }
  }, [query])

  const searchEntities = async () => {
    setLoading(true)
    try {
      // Search across all entity types
      const [people, projects, goals, events] = await Promise.all([
        fetch(`${API_BASE}/people`).then(r => r.json()),
        fetch(`${API_BASE}/projects`).then(r => r.json()),
        fetch(`${API_BASE}/goals`).then(r => r.json()),
        fetch(`${API_BASE}/events`).then(r => r.json()),
      ])

      const allEntities = [
        ...(people.people || []).map(e => ({ ...e, type: 'person' })),
        ...(projects.projects || []).map(e => ({ ...e, type: 'project' })),
        ...(goals.goals || []).map(e => ({ ...e, type: 'goal' })),
        ...(events.events || []).map(e => ({ ...e, type: 'event' })),
      ]

      // Filter by query
      const q = query.toLowerCase()
      const filtered = allEntities.filter(e => {
        const name = (e.name || e.title || '').toLowerCase()
        const disamb = (e.disambiguator || '').toLowerCase()
        return name.includes(q) || disamb.includes(q)
      })

      // Sort by relevance (exact match first, then starts with, then includes)
      filtered.sort((a, b) => {
        const aName = (a.name || a.title || '').toLowerCase()
        const bName = (b.name || b.title || '').toLowerCase()
        
        const aExact = aName === q
        const bExact = bName === q
        if (aExact && !bExact) return -1
        if (!aExact && bExact) return 1
        
        const aStarts = aName.startsWith(q)
        const bStarts = bName.startsWith(q)
        if (aStarts && !bStarts) return -1
        if (!aStarts && bStarts) return 1
        
        return aName.localeCompare(bName)
      })

      setResults(filtered.slice(0, 10))
      setSelectedIndex(0)
    } catch (e) {
      console.error('Search failed:', e)
    }
    setLoading(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(i => Math.min(i + 1, results.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(i => Math.max(i - 1, 0))
    } else if (e.key === 'Enter' && results[selectedIndex]) {
      handleSelect(results[selectedIndex])
    }
  }

  const handleSelect = (entity) => {
    onSelect?.(entity)
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-midnight/80 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative w-full max-w-2xl mx-4 glass neon-border rounded-2xl overflow-hidden animate-fade-in shadow-2xl">
        {/* Search Input */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-slate-700/50">
          <Search className="w-5 h-5 text-neon-purple" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search people, projects, goals, events..."
            className="flex-1 bg-transparent text-lg outline-none placeholder-slate-500"
          />
          {loading && <Loader2 className="w-5 h-5 text-neon-purple animate-spin" />}
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-dark transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Results */}
        <div ref={resultsRef} className="max-h-[50vh] overflow-y-auto">
          {query.length < 2 ? (
            <div className="px-5 py-8 text-center text-slate-500">
              <p>Type at least 2 characters to search</p>
              <div className="flex justify-center gap-4 mt-4">
                <kbd className="px-2 py-1 rounded bg-slate-dark text-xs">↑↓ Navigate</kbd>
                <kbd className="px-2 py-1 rounded bg-slate-dark text-xs">↵ Select</kbd>
                <kbd className="px-2 py-1 rounded bg-slate-dark text-xs">Esc Close</kbd>
              </div>
            </div>
          ) : results.length === 0 && !loading ? (
            <div className="px-5 py-8 text-center text-slate-500">
              <p>No results found for "{query}"</p>
            </div>
          ) : (
            <div className="py-2">
              {results.map((entity, idx) => {
                const config = typeConfig[entity.type] || typeConfig.note
                const Icon = config.icon
                const isSelected = idx === selectedIndex
                
                return (
                  <button
                    key={entity.id || idx}
                    onClick={() => handleSelect(entity)}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`
                      w-full flex items-center gap-4 px-5 py-3 text-left transition-colors
                      ${isSelected ? 'bg-neon-purple/10' : 'hover:bg-slate-dark/50'}
                    `}
                  >
                    <div className={`w-10 h-10 rounded-lg ${config.bg} flex items-center justify-center flex-shrink-0`}>
                      <Icon className={`w-5 h-5 ${config.color}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">
                        {highlightMatch(entity.name || entity.title || 'Untitled', query)}
                      </p>
                      {entity.disambiguator && (
                        <p className="text-sm text-slate-400 truncate">
                          {highlightMatch(entity.disambiguator, query)}
                        </p>
                      )}
                    </div>
                    <span className={`px-2 py-0.5 rounded-full text-xs ${config.bg} ${config.color} capitalize`}>
                      {entity.type}
                    </span>
                    {isSelected && (
                      <kbd className="px-2 py-1 rounded bg-slate-dark text-xs text-slate-400">↵</kbd>
                    )}
                  </button>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-slate-700/50 flex items-center justify-between text-xs text-slate-500">
          <span>{results.length} results</span>
          <div className="flex items-center gap-4">
            <span>Navigate with <kbd className="px-1 rounded bg-slate-dark">↑</kbd><kbd className="px-1 rounded bg-slate-dark ml-1">↓</kbd></span>
            <span>Select <kbd className="px-1 rounded bg-slate-dark">↵</kbd></span>
            <span>Close <kbd className="px-1 rounded bg-slate-dark">Esc</kbd></span>
          </div>
        </div>
      </div>
    </div>
  )
}

function highlightMatch(text, query) {
  if (!query || !text) return text
  
  const idx = text.toLowerCase().indexOf(query.toLowerCase())
  if (idx === -1) return text
  
  return (
    <>
      {text.slice(0, idx)}
      <span className="bg-neon-purple/30 text-neon-purple rounded px-0.5">
        {text.slice(idx, idx + query.length)}
      </span>
      {text.slice(idx + query.length)}
    </>
  )
}

