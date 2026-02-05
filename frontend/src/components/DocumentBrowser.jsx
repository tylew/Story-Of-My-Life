import { useState, useEffect, useCallback } from 'react'
import { 
  FileText, Search, Plus, Folder, FolderOpen, 
  ChevronRight, ChevronDown, File, Lock, User,
  Target, Zap, Calendar, RefreshCw
} from 'lucide-react'

const API_BASE = '/api'

const entityIcons = {
  person: User,
  project: Target,
  goal: Zap,
  event: Calendar,
}

const documentTypeColors = {
  general_info: 'text-neon-cyan',
  note: 'text-slate-400',
  meeting: 'text-neon-pink',
  research: 'text-neon-purple',
  plan: 'text-neon-green',
  custom: 'text-slate-300',
}

export default function DocumentBrowser({ onDocumentSelect, onEntitySelect, refreshKey }) {
  const [documents, setDocuments] = useState([])
  const [entities, setEntities] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedEntities, setExpandedEntities] = useState(new Set())
  const [viewMode, setViewMode] = useState('by-entity') // 'by-entity' or 'all'

  useEffect(() => {
    fetchDocuments()
    fetchEntities()
  }, [refreshKey])

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents`)
      const data = await res.json()
      setDocuments(data.documents || [])
    } catch (e) {
      console.error('Failed to fetch documents:', e)
      setError('Failed to load documents')
    }
  }

  const fetchEntities = async () => {
    setLoading(true)
    try {
      // Fetch all entity types
      const types = ['people', 'projects', 'goals', 'events']
      const results = await Promise.all(
        types.map(type => 
          fetch(`${API_BASE}/${type}`).then(r => r.json())
        )
      )
      
      const allEntities = []
      const typeMap = { people: 'person', projects: 'project', goals: 'goal', events: 'event' }
      
      results.forEach((result, idx) => {
        const type = types[idx]
        const entityType = typeMap[type]
        const items = result[type] || []
        
        items.forEach(item => {
          allEntities.push({
            ...item,
            entityType,
          })
        })
      })
      
      setEntities(allEntities)
    } catch (e) {
      console.error('Failed to fetch entities:', e)
    } finally {
      setLoading(false)
    }
  }

  const toggleEntity = (entityId) => {
    const newExpanded = new Set(expandedEntities)
    if (newExpanded.has(entityId)) {
      newExpanded.delete(entityId)
    } else {
      newExpanded.add(entityId)
    }
    setExpandedEntities(newExpanded)
  }

  const getEntityDocuments = (entityId) => {
    return documents.filter(doc => doc.parent_entity_id === entityId)
  }

  const filteredEntities = entities.filter(entity => {
    if (!searchQuery) return true
    const name = entity.name?.toLowerCase() || ''
    return name.includes(searchQuery.toLowerCase())
  })

  const filteredDocuments = documents.filter(doc => {
    if (!searchQuery) return true
    const name = doc.name?.toLowerCase() || ''
    return name.includes(searchQuery.toLowerCase())
  })

  // Group entities by type for organized display
  const groupedEntities = filteredEntities.reduce((acc, entity) => {
    const type = entity.entityType || 'other'
    if (!acc[type]) acc[type] = []
    acc[type].push(entity)
    return acc
  }, {})

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold flex items-center gap-2">
            <FileText className="w-5 h-5 text-neon-purple" />
            Documents
          </h2>
          <button
            onClick={() => fetchDocuments()}
            className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-slate-400" />
          </button>
        </div>
        
        {/* Search */}
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder="Search documents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple focus:outline-none"
          />
        </div>

        {/* View toggle */}
        <div className="flex gap-2 mt-3">
          <button
            onClick={() => setViewMode('by-entity')}
            className={`flex-1 px-3 py-1.5 text-xs rounded-lg transition-colors ${
              viewMode === 'by-entity'
                ? 'bg-neon-purple/20 text-neon-purple'
                : 'bg-slate-dark text-slate-400 hover:text-white'
            }`}
          >
            By Entity
          </button>
          <button
            onClick={() => setViewMode('all')}
            className={`flex-1 px-3 py-1.5 text-xs rounded-lg transition-colors ${
              viewMode === 'all'
                ? 'bg-neon-purple/20 text-neon-purple'
                : 'bg-slate-dark text-slate-400 hover:text-white'
            }`}
          >
            All Documents
          </button>
        </div>
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-6 h-6 border-2 border-neon-purple border-t-transparent rounded-full" />
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-400">{error}</div>
        ) : viewMode === 'by-entity' ? (
          // Grouped by entity view
          <div className="space-y-4">
            {Object.entries(groupedEntities).map(([type, typeEntities]) => {
              const Icon = entityIcons[type] || FileText
              
              return (
                <div key={type} className="space-y-1">
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-2 mb-2">
                    <Icon className="w-3 h-3" />
                    {type}s ({typeEntities.length})
                  </p>
                  
                  {typeEntities.map(entity => {
                    const entityDocs = getEntityDocuments(entity.id)
                    const isExpanded = expandedEntities.has(entity.id)
                    const hasDocuments = entityDocs.length > 0
                    
                    return (
                      <div key={entity.id} className="ml-2">
                        <button
                          onClick={() => {
                            if (hasDocuments) {
                              toggleEntity(entity.id)
                            } else {
                              onEntitySelect?.(entity)
                            }
                          }}
                          className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-dark text-left transition-colors group"
                        >
                          {hasDocuments ? (
                            isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-slate-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-slate-400" />
                            )
                          ) : (
                            <div className="w-4" />
                          )}
                          {isExpanded ? (
                            <FolderOpen className="w-4 h-4 text-neon-cyan" />
                          ) : (
                            <Folder className="w-4 h-4 text-slate-400 group-hover:text-neon-cyan" />
                          )}
                          <span className="flex-1 truncate text-sm">{entity.name}</span>
                          {hasDocuments && (
                            <span className="text-xs text-slate-500">{entityDocs.length}</span>
                          )}
                        </button>
                        
                        {/* Entity's documents */}
                        {isExpanded && hasDocuments && (
                          <div className="ml-6 mt-1 space-y-1">
                            {entityDocs.map(doc => (
                              <DocumentItem 
                                key={doc.id} 
                                document={doc} 
                                onSelect={onDocumentSelect}
                              />
                            ))}
                            
                            {/* Add document button */}
                            <button
                              onClick={() => onEntitySelect?.(entity)}
                              className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-slate-500 hover:text-neon-purple hover:bg-slate-dark/50 text-sm transition-colors"
                            >
                              <Plus className="w-4 h-4" />
                              <span>Add document...</span>
                            </button>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })}
          </div>
        ) : (
          // All documents flat view
          <div className="space-y-1">
            {filteredDocuments.length === 0 ? (
              <p className="text-center text-slate-500 py-8">No documents found</p>
            ) : (
              filteredDocuments.map(doc => (
                <DocumentItem 
                  key={doc.id} 
                  document={doc} 
                  onSelect={onDocumentSelect}
                  showEntityName
                />
              ))
            )}
          </div>
        )}
      </div>

      {/* Create document button */}
      <div className="p-4 border-t border-neon-purple/20">
        <button
          onClick={() => onDocumentSelect?.({ isNew: true })}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-neon-purple/20 text-neon-purple hover:bg-neon-purple/30 transition-colors"
        >
          <Plus className="w-4 h-4" />
          New Document
        </button>
      </div>
    </div>
  )
}

function DocumentItem({ document, onSelect, showEntityName = false }) {
  const isLocked = document.locked === 1 || document.locked === true
  const docType = document.document_type || 'custom'
  const colorClass = documentTypeColors[docType] || documentTypeColors.custom
  
  return (
    <button
      onClick={() => onSelect?.(document)}
      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-dark text-left transition-colors group"
    >
      <File className={`w-4 h-4 ${colorClass}`} />
      <div className="flex-1 min-w-0">
        <p className="text-sm truncate group-hover:text-white transition-colors">
          {document.name || 'Untitled'}
        </p>
        {showEntityName && document.parent_entity_id && (
          <p className="text-xs text-slate-500 truncate">
            Entity: {document.parent_entity_id.slice(0, 8)}...
          </p>
        )}
      </div>
      {isLocked && (
        <Lock className="w-3 h-3 text-neon-cyan flex-shrink-0" title="Locked - LLM only" />
      )}
      <span className={`text-xs px-1.5 py-0.5 rounded ${colorClass} bg-slate-dark/50 capitalize`}>
        {docType.replace('_', ' ')}
      </span>
    </button>
  )
}

