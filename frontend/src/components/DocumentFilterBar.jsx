import { useState, useEffect, useRef } from 'react'
import { 
  Search, 
  X, 
  ChevronDown, 
  Tag, 
  User, 
  Briefcase, 
  Target, 
  Calendar,
  Link2,
  FileText,
  Filter
} from 'lucide-react'

const API_BASE = '/api'

// Entity type icons and labels
const ENTITY_TYPE_CONFIG = {
  person: { icon: User, label: 'People', color: '#8B5CF6' },
  project: { icon: Briefcase, label: 'Projects', color: '#10B981' },
  goal: { icon: Target, label: 'Goals', color: '#F59E0B' },
  event: { icon: Calendar, label: 'Events', color: '#EC4899' },
  period: { icon: Calendar, label: 'Periods', color: '#6366F1' },
  organization: { icon: Briefcase, label: 'Organizations', color: '#14B8A6' },
}

/**
 * DocumentFilterBar - Filter bar for document browser
 * 
 * Features:
 * - Entity type dropdown
 * - Specific entity dropdown
 * - Tag multi-select
 * - Search input
 * - Active filter pills
 */
export default function DocumentFilterBar({
  filters = {},
  onFiltersChange,
  summary = null,
  className = '',
}) {
  const [entities, setEntities] = useState([])
  const [tags, setTags] = useState([])
  const [showEntityTypeDropdown, setShowEntityTypeDropdown] = useState(false)
  const [showEntityDropdown, setShowEntityDropdown] = useState(false)
  const [showTagDropdown, setShowTagDropdown] = useState(false)
  const [entitySearch, setEntitySearch] = useState('')
  const [tagSearch, setTagSearch] = useState('')

  const entityTypeRef = useRef(null)
  const entityRef = useRef(null)
  const tagRef = useRef(null)

  // Fetch entities and tags
  useEffect(() => {
    fetchEntities()
    fetchTags()
  }, [])

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (entityTypeRef.current && !entityTypeRef.current.contains(e.target)) {
        setShowEntityTypeDropdown(false)
      }
      if (entityRef.current && !entityRef.current.contains(e.target)) {
        setShowEntityDropdown(false)
      }
      if (tagRef.current && !tagRef.current.contains(e.target)) {
        setShowTagDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchEntities = async () => {
    try {
      const res = await fetch(`${API_BASE}/entities`)
      const data = await res.json()
      setEntities(data.entities || [])
    } catch (e) {
      console.error('Failed to fetch entities:', e)
    }
  }

  const fetchTags = async () => {
    try {
      const res = await fetch(`${API_BASE}/tags`)
      const data = await res.json()
      setTags(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('Failed to fetch tags:', e)
    }
  }

  const updateFilter = (key, value) => {
    const newFilters = { ...filters }
    if (value === null || value === undefined || value === '' || (Array.isArray(value) && value.length === 0)) {
      delete newFilters[key]
    } else {
      newFilters[key] = value
    }
    onFiltersChange(newFilters)
  }

  const clearFilter = (key) => {
    const newFilters = { ...filters }
    delete newFilters[key]
    onFiltersChange(newFilters)
  }

  const clearAllFilters = () => {
    onFiltersChange({})
  }

  // Filter entities by type and search
  const filteredEntities = entities.filter(e => {
    if (filters.entityType && e.type !== filters.entityType) return false
    if (entitySearch) {
      const name = e.name || e.label || ''
      return name.toLowerCase().includes(entitySearch.toLowerCase())
    }
    return true
  })

  // Filter tags by search
  const filteredTags = tags.filter(t => 
    t.name.toLowerCase().includes(tagSearch.toLowerCase()) &&
    !(filters.tags || []).includes(t.name)
  )

  const hasActiveFilters = Object.keys(filters).some(k => 
    k !== 'search' && filters[k] !== null && filters[k] !== undefined
  )

  const selectedEntityType = filters.entityType ? ENTITY_TYPE_CONFIG[filters.entityType] : null
  const selectedEntity = filters.entityId ? entities.find(e => e.id === filters.entityId) : null

  return (
    <div className={`space-y-3 ${className}`}>
      {/* Filter controls row */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Entity Type Dropdown */}
        <div ref={entityTypeRef} className="relative">
          <button
            onClick={() => setShowEntityTypeDropdown(!showEntityTypeDropdown)}
            className={`
              flex items-center gap-2 px-3 py-2 rounded-lg text-sm
              bg-slate-800 border border-slate-700 hover:border-slate-600
              transition-colors
              ${filters.entityType ? 'border-neon-purple text-neon-purple' : ''}
            `}
          >
            {selectedEntityType ? (
              <>
                <selectedEntityType.icon className="w-4 h-4" />
                <span>{selectedEntityType.label}</span>
              </>
            ) : (
              <>
                <Filter className="w-4 h-4" />
                <span>Type</span>
              </>
            )}
            <ChevronDown className="w-4 h-4" />
          </button>

          {showEntityTypeDropdown && (
            <div className="absolute z-30 mt-1 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
              <button
                onClick={() => {
                  clearFilter('entityType')
                  clearFilter('entityId')
                  setShowEntityTypeDropdown(false)
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-700 text-left"
              >
                <FileText className="w-4 h-4 text-slate-400" />
                <span>All Types</span>
              </button>
              {Object.entries(ENTITY_TYPE_CONFIG).map(([type, config]) => (
                <button
                  key={type}
                  onClick={() => {
                    updateFilter('entityType', type)
                    clearFilter('entityId')
                    setShowEntityTypeDropdown(false)
                  }}
                  className={`
                    w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-700 text-left
                    ${filters.entityType === type ? 'bg-neon-purple/20 text-neon-purple' : ''}
                  `}
                >
                  <config.icon className="w-4 h-4" style={{ color: config.color }} />
                  <span>{config.label}</span>
                  {summary?.by_entity_type?.[type] && (
                    <span className="ml-auto text-xs text-slate-500">
                      {summary.by_entity_type[type]}
                    </span>
                  )}
                </button>
              ))}
              <div className="border-t border-slate-700">
                <button
                  onClick={() => {
                    updateFilter('relationshipId', '__any__')
                    clearFilter('entityType')
                    clearFilter('entityId')
                    setShowEntityTypeDropdown(false)
                  }}
                  className={`
                    w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-700 text-left
                    ${filters.relationshipId ? 'bg-neon-purple/20 text-neon-purple' : ''}
                  `}
                >
                  <Link2 className="w-4 h-4 text-cyan-400" />
                  <span>Relationships</span>
                  {summary?.by_relationship?.length > 0 && (
                    <span className="ml-auto text-xs text-slate-500">
                      {summary.by_relationship.reduce((acc, r) => acc + r.document_count, 0)}
                    </span>
                  )}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Entity Dropdown (only when type selected) */}
        {filters.entityType && (
          <div ref={entityRef} className="relative">
            <button
              onClick={() => setShowEntityDropdown(!showEntityDropdown)}
              className={`
                flex items-center gap-2 px-3 py-2 rounded-lg text-sm
                bg-slate-800 border border-slate-700 hover:border-slate-600
                transition-colors max-w-[200px]
                ${filters.entityId ? 'border-neon-purple text-neon-purple' : ''}
              `}
            >
              <span className="truncate">
                {selectedEntity ? (selectedEntity.name || selectedEntity.label) : 'Select entity...'}
              </span>
              <ChevronDown className="w-4 h-4 flex-shrink-0" />
            </button>

            {showEntityDropdown && (
              <div className="absolute z-30 mt-1 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
                <div className="p-2 border-b border-slate-700">
                  <input
                    type="text"
                    value={entitySearch}
                    onChange={(e) => setEntitySearch(e.target.value)}
                    placeholder="Search entities..."
                    className="w-full px-2 py-1 text-sm bg-slate-900 border border-slate-700 rounded focus:outline-none focus:border-neon-purple"
                  />
                </div>
                <div className="max-h-60 overflow-y-auto">
                  <button
                    onClick={() => {
                      clearFilter('entityId')
                      setShowEntityDropdown(false)
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-700 text-left"
                  >
                    <span className="text-slate-400">All {selectedEntityType?.label || 'Entities'}</span>
                  </button>
                  {filteredEntities.map(entity => (
                    <button
                      key={entity.id}
                      onClick={() => {
                        updateFilter('entityId', entity.id)
                        setShowEntityDropdown(false)
                        setEntitySearch('')
                      }}
                      className={`
                        w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-700 text-left
                        ${filters.entityId === entity.id ? 'bg-neon-purple/20 text-neon-purple' : ''}
                      `}
                    >
                      <span className="truncate">{entity.name || entity.label}</span>
                      {summary?.by_entity?.find(e => e.id === entity.id)?.count && (
                        <span className="ml-auto text-xs text-slate-500">
                          {summary.by_entity.find(e => e.id === entity.id).count}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tag Dropdown */}
        <div ref={tagRef} className="relative">
          <button
            onClick={() => setShowTagDropdown(!showTagDropdown)}
            className={`
              flex items-center gap-2 px-3 py-2 rounded-lg text-sm
              bg-slate-800 border border-slate-700 hover:border-slate-600
              transition-colors
              ${(filters.tags?.length || 0) > 0 ? 'border-neon-purple text-neon-purple' : ''}
            `}
          >
            <Tag className="w-4 h-4" />
            <span>Tags</span>
            {(filters.tags?.length || 0) > 0 && (
              <span className="px-1.5 py-0.5 text-xs bg-neon-purple/30 rounded-full">
                {filters.tags.length}
              </span>
            )}
            <ChevronDown className="w-4 h-4" />
          </button>

          {showTagDropdown && (
            <div className="absolute z-30 mt-1 w-64 bg-slate-800 border border-slate-700 rounded-lg shadow-xl overflow-hidden">
              <div className="p-2 border-b border-slate-700">
                <input
                  type="text"
                  value={tagSearch}
                  onChange={(e) => setTagSearch(e.target.value)}
                  placeholder="Search tags..."
                  className="w-full px-2 py-1 text-sm bg-slate-900 border border-slate-700 rounded focus:outline-none focus:border-neon-purple"
                />
              </div>
              <div className="max-h-60 overflow-y-auto">
                {filteredTags.length === 0 ? (
                  <div className="px-3 py-4 text-sm text-slate-500 text-center">
                    No tags found
                  </div>
                ) : (
                  filteredTags.map(tag => (
                    <button
                      key={tag.name}
                      onClick={() => {
                        updateFilter('tags', [...(filters.tags || []), tag.name])
                      }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-slate-700 text-left"
                    >
                      <Tag className="w-3 h-3" />
                      <span className="flex-1">{tag.name}</span>
                      {tag.color && (
                        <span
                          className="w-3 h-3 rounded-full"
                          style={{ backgroundColor: tag.color }}
                        />
                      )}
                      {summary?.by_tag?.[tag.name] && (
                        <span className="text-xs text-slate-500">
                          {summary.by_tag[tag.name]}
                        </span>
                      )}
                    </button>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* Search Input */}
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={filters.search || ''}
            onChange={(e) => updateFilter('search', e.target.value)}
            placeholder="Search documents..."
            className="w-full pl-9 pr-8 py-2 text-sm bg-slate-800 border border-slate-700 rounded-lg focus:outline-none focus:border-neon-purple"
          />
          {filters.search && (
            <button
              onClick={() => clearFilter('search')}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-700 rounded"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Clear All */}
        {hasActiveFilters && (
          <button
            onClick={clearAllFilters}
            className="px-3 py-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Active filter pills */}
      {hasActiveFilters && (
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs text-slate-500">Active:</span>
          
          {filters.entityType && (
            <FilterPill
              label={`Type: ${ENTITY_TYPE_CONFIG[filters.entityType]?.label || filters.entityType}`}
              onRemove={() => {
                clearFilter('entityType')
                clearFilter('entityId')
              }}
            />
          )}
          
          {filters.entityId && selectedEntity && (
            <FilterPill
              label={selectedEntity.name || selectedEntity.label}
              onRemove={() => clearFilter('entityId')}
            />
          )}
          
          {filters.relationshipId && (
            <FilterPill
              label="Relationships"
              onRemove={() => clearFilter('relationshipId')}
            />
          )}
          
          {(filters.tags || []).map(tag => (
            <FilterPill
              key={tag}
              label={`#${tag}`}
              onRemove={() => updateFilter('tags', filters.tags.filter(t => t !== tag))}
              color="purple"
            />
          ))}
        </div>
      )}
    </div>
  )
}

/**
 * FilterPill - Dismissible filter indicator
 */
function FilterPill({ label, onRemove, color = 'slate' }) {
  const colorClasses = {
    slate: 'bg-slate-700 text-slate-200',
    purple: 'bg-neon-purple/20 text-neon-purple',
  }

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs ${colorClasses[color]}`}>
      {label}
      <button
        onClick={onRemove}
        className="ml-0.5 hover:text-white transition-colors"
      >
        <X className="w-3 h-3" />
      </button>
    </span>
  )
}

