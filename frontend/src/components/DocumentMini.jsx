import { useState, useEffect } from 'react'
import { 
  FileText, Plus, File, Lock, ExternalLink, 
  ChevronRight, Loader2, FolderOpen
} from 'lucide-react'

const API_BASE = '/api'

// Document type colors
const DOCUMENT_TYPE_COLORS = {
  general_info: 'text-neon-cyan',
  note: 'text-slate-400',
  meeting_notes: 'text-neon-pink',
  research: 'text-neon-purple',
  journal: 'text-neon-green',
}

/**
 * DocumentMini - Compact document list for embedding in detail sidebars
 * 
 * Props:
 * - entityId: Show documents for this entity
 * - relationshipId: Show documents for this relationship
 * - onDocumentSelect: Callback when document is clicked
 * - onViewAll: Callback to open full browser with filter
 * - maxItems: Maximum items to show (default 5)
 */
export default function DocumentMini({
  entityId,
  relationshipId,
  onDocumentSelect,
  onViewAll,
  maxItems = 5,
  className = '',
}) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (entityId || relationshipId) {
      fetchDocuments()
    }
  }, [entityId, relationshipId])

  const fetchDocuments = async () => {
    setLoading(true)
    setError(null)
    
    try {
      let url
      if (relationshipId) {
        url = `${API_BASE}/relationships/${relationshipId}/documents`
      } else if (entityId) {
        url = `${API_BASE}/entities/${entityId}/documents`
      } else {
        return
      }

      const res = await fetch(url)
      if (!res.ok) throw new Error('Failed to fetch documents')
      
      const data = await res.json()
      setDocuments(data.documents || [])
    } catch (e) {
      console.error('Failed to fetch documents:', e)
      setError('Failed to load documents')
    } finally {
      setLoading(false)
    }
  }

  const handleViewAll = () => {
    const filters = {}
    if (entityId) filters.entityId = entityId
    if (relationshipId) filters.relationshipId = relationshipId
    onViewAll?.(filters)
  }

  const handleCreateNew = () => {
    onDocumentSelect?.({ 
      isNew: true, 
      parentEntityId: entityId,
      parentRelationshipId: relationshipId,
    })
  }

  // Show limited items
  const displayDocs = documents.slice(0, maxItems)
  const hasMore = documents.length > maxItems

  if (loading) {
    return (
      <div className={`flex items-center justify-center py-8 ${className}`}>
        <Loader2 className="w-5 h-5 text-slate-400 animate-spin" />
      </div>
    )
  }

  if (error) {
    return (
      <div className={`text-center py-6 text-sm text-red-400 ${className}`}>
        {error}
      </div>
    )
  }

  return (
    <div className={className}>
      {/* Document list */}
      {documents.length === 0 ? (
        <div className="text-center py-8">
          <FileText className="w-10 h-10 text-slate-700 mx-auto mb-3" />
          <p className="text-sm text-slate-500 mb-3">No documents yet</p>
          <button
            onClick={handleCreateNew}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg bg-neon-purple/20 text-neon-purple hover:bg-neon-purple/30 transition-colors"
          >
            <Plus className="w-3.5 h-3.5" />
            Add Document
          </button>
        </div>
      ) : (
        <div className="space-y-1">
          {displayDocs.map(doc => (
            <MiniDocumentItem
              key={doc.id}
              document={doc}
              onSelect={onDocumentSelect}
            />
          ))}

          {/* Show more / View all */}
          {hasMore && (
            <button
              onClick={handleViewAll}
              className="w-full flex items-center justify-center gap-1 py-2 text-sm text-slate-400 hover:text-neon-purple transition-colors"
            >
              <span>View all {documents.length} documents</span>
              <ChevronRight className="w-4 h-4" />
            </button>
          )}

          {/* Add document button */}
          <button
            onClick={handleCreateNew}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-500 hover:text-neon-purple hover:bg-slate-800/50 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Add Document
          </button>
        </div>
      )}

      {/* View all footer */}
      {documents.length > 0 && (
        <div className="mt-3 pt-3 border-t border-slate-700/50">
          <button
            onClick={handleViewAll}
            className="w-full flex items-center justify-center gap-2 py-2 text-sm text-slate-400 hover:text-white transition-colors"
          >
            <FolderOpen className="w-4 h-4" />
            Open in Document Browser
            <ExternalLink className="w-3 h-3" />
          </button>
        </div>
      )}
    </div>
  )
}

/**
 * MiniDocumentItem - Compact document row
 */
function MiniDocumentItem({ document, onSelect }) {
  const isLocked = document.locked === 1 || document.locked === true
  const docType = document.document_type || 'note'
  const colorClass = DOCUMENT_TYPE_COLORS[docType] || DOCUMENT_TYPE_COLORS.note

  // Format date compactly
  const formatDate = (dateStr) => {
    if (!dateStr) return null
    const date = new Date(dateStr)
    const now = new Date()
    const diffMs = now - date
    const diffHours = diffMs / (1000 * 60 * 60)
    
    if (diffHours < 1) return 'now'
    if (diffHours < 24) return `${Math.floor(diffHours)}h`
    if (diffHours < 48) return '1d'
    if (diffHours < 168) return `${Math.floor(diffHours / 24)}d`
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <button
      onClick={() => onSelect?.(document)}
      className="w-full flex items-center gap-2 px-3 py-2 rounded-lg hover:bg-slate-800 text-left transition-colors group"
    >
      <File className={`w-4 h-4 flex-shrink-0 ${colorClass}`} />
      
      <span className="flex-1 text-sm truncate group-hover:text-white transition-colors">
        {document.name || 'Untitled'}
      </span>

      {isLocked && (
        <Lock className="w-3 h-3 text-neon-cyan flex-shrink-0" title="Locked" />
      )}

      <span className="text-xs text-slate-500 flex-shrink-0">
        {formatDate(document.updated_at)}
      </span>
    </button>
  )
}

/**
 * DocumentMiniHeader - Section header for document mini browser
 */
export function DocumentMiniHeader({ 
  count = 0, 
  onViewAll,
  title = 'Documents',
}) {
  return (
    <div className="flex items-center justify-between mb-2">
      <h4 className="text-sm font-medium flex items-center gap-2">
        <FileText className="w-4 h-4 text-neon-purple" />
        {title}
        {count > 0 && (
          <span className="text-xs text-slate-500">({count})</span>
        )}
      </h4>
      {onViewAll && (
        <button
          onClick={onViewAll}
          className="text-xs text-slate-400 hover:text-neon-purple transition-colors flex items-center gap-1"
        >
          View All
          <ChevronRight className="w-3 h-3" />
        </button>
      )}
    </div>
  )
}

