import { useState, useEffect, useCallback, useMemo } from 'react'
import { 
  FileText, Plus, File, Lock, RefreshCw, 
  User, Briefcase, Target, Calendar, Link2,
  ChevronLeft, ChevronRight, ExternalLink
} from 'lucide-react'
import DocumentFilterBar from './DocumentFilterBar'
import DocumentTree from './DocumentTree'

const API_BASE = '/api'

// Entity type icons
const ENTITY_TYPE_ICONS = {
  person: User,
  project: Briefcase,
  goal: Target,
  event: Calendar,
  period: Calendar,
  organization: Briefcase,
}

// Document type colors
const DOCUMENT_TYPE_COLORS = {
  general_info: 'text-neon-cyan',
  note: 'text-slate-400',
  meeting_notes: 'text-neon-pink',
  research: 'text-neon-purple',
  journal: 'text-neon-green',
}

/**
 * DocumentBrowser - Unified document browsing interface
 * 
 * Features:
 * - Filter bar with entity type, entity, tags, and search
 * - Hierarchical sidebar tree
 * - Document list with metadata
 * - Collapsible sidebar
 */
export default function DocumentBrowser({ 
  onDocumentSelect, 
  onEntitySelect, 
  onRelationshipSelect,
  refreshKey,
  initialFilters = {},
}) {
  // State
  const [documents, setDocuments] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(initialFilters)
  const [selectedTreePath, setSelectedTreePath] = useState(null)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [entities, setEntities] = useState([])

  // Fetch data on mount and refresh
  useEffect(() => {
    fetchSummary()
    fetchEntities()
  }, [refreshKey])

  // Fetch documents when filters change
  useEffect(() => {
    fetchDocuments()
  }, [filters, refreshKey])

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/documents/summary`)
      const data = await res.json()
      setSummary(data)
    } catch (e) {
      console.error('Failed to fetch document summary:', e)
    }
  }

  const fetchEntities = async () => {
    try {
      const res = await fetch(`${API_BASE}/entities`)
      const data = await res.json()
      setEntities(data.entities || [])
    } catch (e) {
      console.error('Failed to fetch entities:', e)
    }
  }

  const fetchDocuments = async () => {
    setLoading(true)
    try {
      // Build query params from filters
      const params = new URLSearchParams()
      if (filters.entityId) params.set('entity_id', filters.entityId)
      if (filters.relationshipId && filters.relationshipId !== '__any__') {
        params.set('relationship_id', filters.relationshipId)
      }
      if (filters.entityType) params.set('entity_type', filters.entityType)
      if (filters.tags?.length) params.set('tags', filters.tags.join(','))
      if (filters.search) params.set('search', filters.search)
      
      const url = `${API_BASE}/documents${params.toString() ? '?' + params.toString() : ''}`
      const res = await fetch(url)
      const data = await res.json()
      setDocuments(data.documents || [])
    } catch (e) {
      console.error('Failed to fetch documents:', e)
      setDocuments([])
    } finally {
      setLoading(false)
    }
  }

  // Handle tree selection
  const handleTreeSelect = useCallback((selection) => {
    setSelectedTreePath(selection)
    
    // Update filters based on tree selection
    const newFilters = {}
    
    switch (selection.type) {
      case 'all':
        // Clear all filters
        break
      case 'entityType':
        newFilters.entityType = selection.entityType
        break
      case 'entity':
        newFilters.entityId = selection.entityId
        newFilters.entityType = selection.entityType
        break
      case 'relationship':
        newFilters.relationshipId = selection.relationshipId
        break
      case 'relationships':
        newFilters.relationshipId = '__any__'
        break
      case 'tag':
        newFilters.tags = [selection.tag]
        break
      case 'folder':
        newFilters.entityId = selection.entityId
        newFilters.folderId = selection.folderId
        break
      case 'orphan':
        newFilters.orphan = true
        break
    }
    
    setFilters(newFilters)
  }, [])

  // Handle filter bar changes
  const handleFiltersChange = useCallback((newFilters) => {
    setFilters(newFilters)
    // Clear tree selection when filters change from filter bar
    setSelectedTreePath(null)
  }, [])

  // Get entity name by ID
  const getEntityName = useCallback((entityId) => {
    const entity = entities.find(e => e.id === entityId)
    return entity?.name || entity?.label || 'Unknown'
  }, [entities])

  // Refresh all data
  const handleRefresh = () => {
    fetchSummary()
    fetchDocuments()
  }

  return (
    <div className="h-full flex flex-col bg-slate-900">
      {/* Header with filter bar */}
      <div className="p-4 border-b border-slate-700/50 space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FileText className="w-5 h-5 text-neon-purple" />
            Documents
            {summary?.total_count !== undefined && (
              <span className="text-sm text-slate-500 font-normal">
                ({summary.total_count})
              </span>
            )}
          </h2>
          <button
            onClick={handleRefresh}
            className="p-2 rounded-lg hover:bg-slate-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4 text-slate-400" />
          </button>
        </div>

        <DocumentFilterBar
          filters={filters}
          onFiltersChange={handleFiltersChange}
          summary={summary}
        />
      </div>

      {/* Main content: sidebar + document list */}
      <div className="flex-1 flex overflow-hidden">
        {/* Collapsible sidebar tree */}
        <div 
          className={`
            border-r border-slate-700/50 bg-slate-900/50 transition-all duration-200
            ${sidebarCollapsed ? 'w-0 overflow-hidden' : 'w-64'}
          `}
        >
          <div className="h-full overflow-y-auto p-2">
            <DocumentTree
              summary={summary}
              selectedPath={selectedTreePath}
              onSelect={handleTreeSelect}
            />
          </div>
        </div>

        {/* Sidebar toggle */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex-shrink-0 w-5 flex items-center justify-center hover:bg-slate-800 transition-colors border-r border-slate-700/50"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-3 h-3 text-slate-500" />
          ) : (
            <ChevronLeft className="w-3 h-3 text-slate-500" />
          )}
        </button>

        {/* Document list */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center h-full">
              <div className="animate-spin w-6 h-6 border-2 border-neon-purple border-t-transparent rounded-full" />
            </div>
          ) : documents.length === 0 ? (
            <EmptyState filters={filters} />
          ) : (
            <div className="p-3 space-y-1">
              {documents.map(doc => (
                <DocumentCard
                  key={doc.id}
                  document={doc}
                  onSelect={onDocumentSelect}
                  onEntityClick={onEntitySelect}
                  onRelationshipClick={onRelationshipSelect}
                  getEntityName={getEntityName}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer with create button */}
      <div className="p-3 border-t border-slate-700/50">
        <button
          onClick={() => onDocumentSelect?.({ isNew: true })}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-neon-purple/20 text-neon-purple hover:bg-neon-purple/30 transition-colors font-medium"
        >
          <Plus className="w-4 h-4" />
          New Document
        </button>
      </div>
    </div>
  )
}

/**
 * DocumentCard - Single document in the list
 */
function DocumentCard({ document, onSelect, onEntityClick, onRelationshipClick, getEntityName }) {
  const isLocked = document.locked === 1 || document.locked === true
  const docType = document.document_type || 'note'
  const colorClass = DOCUMENT_TYPE_COLORS[docType] || DOCUMENT_TYPE_COLORS.note
  const EntityIcon = ENTITY_TYPE_ICONS[document.parent_entity_type] || FileText

  // Format date
  const formatDate = (dateStr) => {
    if (!dateStr) return null
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now - date
    const diffHours = diffMs / (1000 * 60 * 60)
    
    if (diffHours < 1) return 'Just now'
    if (diffHours < 24) return `${Math.floor(diffHours)}h ago`
    if (diffHours < 48) return 'Yesterday'
    return date.toLocaleDateString()
  }

  return (
    <div
      onClick={() => onSelect?.(document)}
      className="group p-3 rounded-lg bg-slate-800/50 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 cursor-pointer transition-all"
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={`p-2 rounded-lg bg-slate-900/50 ${colorClass}`}>
          <File className="w-4 h-4" />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-sm truncate group-hover:text-white transition-colors">
              {document.name || 'Untitled'}
            </h3>
            {isLocked && (
              <Lock className="w-3 h-3 text-neon-cyan flex-shrink-0" title="Locked" />
            )}
          </div>

          {/* Metadata row */}
          <div className="flex items-center gap-2 mt-1 text-xs text-slate-500">
            {/* Parent entity/relationship */}
            {document.parent_entity_id && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onEntityClick?.({ id: document.parent_entity_id, type: document.parent_entity_type })
                }}
                className="flex items-center gap-1 hover:text-neon-purple transition-colors"
              >
                <EntityIcon className="w-3 h-3" />
                <span className="truncate max-w-[100px]">
                  {getEntityName(document.parent_entity_id)}
                </span>
              </button>
            )}

            {document.parent_relationship_id && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onRelationshipClick?.({ id: document.parent_relationship_id })
                }}
                className="flex items-center gap-1 hover:text-cyan-400 transition-colors"
              >
                <Link2 className="w-3 h-3" />
                <span>Relationship</span>
              </button>
            )}

            {/* Separator */}
            {(document.parent_entity_id || document.parent_relationship_id) && (
              <span className="text-slate-600">·</span>
            )}

            {/* Date */}
            <span>{formatDate(document.updated_at)}</span>

            {/* Type badge */}
            <span className={`px-1.5 py-0.5 rounded ${colorClass} bg-slate-900/50 capitalize`}>
              {docType.replace(/_/g, ' ')}
            </span>
          </div>

          {/* Tags */}
          {document.tags && document.tags.length > 0 && (
            <div className="flex items-center gap-1 mt-2 flex-wrap">
              {document.tags.split(',').slice(0, 3).map(tag => (
                <span
                  key={tag}
                  className="px-1.5 py-0.5 text-xs rounded-full bg-neon-purple/20 text-neon-purple"
                >
                  #{tag.trim()}
                </span>
              ))}
              {document.tags.split(',').length > 3 && (
                <span className="text-xs text-slate-500">
                  +{document.tags.split(',').length - 3}
                </span>
              )}
            </div>
          )}
        </div>

        {/* Open icon */}
        <ExternalLink className="w-4 h-4 text-slate-600 group-hover:text-slate-400 transition-colors flex-shrink-0" />
      </div>
    </div>
  )
}

/**
 * EmptyState - Shown when no documents match filters
 */
function EmptyState({ filters }) {
  const hasFilters = Object.keys(filters).some(k => 
    filters[k] !== null && filters[k] !== undefined && 
    (Array.isArray(filters[k]) ? filters[k].length > 0 : true)
  )

  return (
    <div className="flex flex-col items-center justify-center h-full text-center p-8">
      <FileText className="w-16 h-16 text-slate-700 mb-4" />
      <h3 className="text-lg font-medium text-slate-400 mb-2">
        {hasFilters ? 'No documents match your filters' : 'No documents yet'}
      </h3>
      <p className="text-sm text-slate-500 max-w-sm">
        {hasFilters 
          ? 'Try adjusting your filters or search query to find what you\'re looking for.'
          : 'Create your first document to get started organizing your knowledge.'}
      </p>
    </div>
  )
}
