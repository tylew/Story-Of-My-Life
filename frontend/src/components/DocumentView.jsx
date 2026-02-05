import { useState, useEffect, useCallback } from 'react'
import { 
  X, Save, Edit3, Eye, Lock, FileText, Clock, 
  User, Bot, Plus, Trash2, ArrowLeft, ChevronRight
} from 'lucide-react'
import DocumentEditor from './DocumentEditor'

const API_BASE = '/api'

const documentTypeLabels = {
  general_info: 'General Info',
  note: 'Note',
  meeting: 'Meeting Notes',
  research: 'Research',
  plan: 'Plan',
  custom: 'Document',
}

export default function DocumentView({ document, onClose, onRefresh }) {
  const [fullDocument, setFullDocument] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editedContent, setEditedContent] = useState('')
  const [editedTitle, setEditedTitle] = useState('')
  const [error, setError] = useState(null)

  // For new documents
  const isNewDocument = document?.isNew

  useEffect(() => {
    if (isNewDocument) {
      setFullDocument({
        id: null,
        name: 'New Document',
        content: '',
        document_type: 'custom',
        locked: false,
      })
      setEditedContent('')
      setEditedTitle('New Document')
      setIsEditing(true)
      setLoading(false)
    } else if (document?.id) {
      fetchDocument()
    }
  }, [document])

  const fetchDocument = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`${API_BASE}/documents/${document.id}`)
      if (!res.ok) throw new Error('Failed to fetch document')
      const data = await res.json()
      setFullDocument(data)
      setEditedContent(data.content || '')
      setEditedTitle(data.metadata?.name || data.name || 'Untitled')
    } catch (e) {
      console.error('Failed to fetch document:', e)
      setError('Failed to load document')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    setSaving(true)
    setError(null)

    try {
      if (isNewDocument) {
        // Create new document
        const res = await fetch(`${API_BASE}/documents`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: editedTitle,
            content: editedContent,
            document_type: fullDocument?.document_type || 'custom',
            parent_entity_id: document?.parent_entity_id || null,
            parent_entity_type: document?.parent_entity_type || null,
          }),
        })

        if (!res.ok) throw new Error('Failed to create document')
        
        const data = await res.json()
        setFullDocument(prev => ({ ...prev, id: data.document?.id }))
        setIsEditing(false)
        onRefresh?.()
      } else {
        // Update existing document
        const res = await fetch(`${API_BASE}/documents/${fullDocument.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: editedTitle,
            content: editedContent,
          }),
        })

        if (!res.ok) {
          const data = await res.json()
          throw new Error(data.detail || 'Failed to save document')
        }

        setIsEditing(false)
        await fetchDocument()
        onRefresh?.()
      }
    } catch (e) {
      console.error('Failed to save document:', e)
      setError(e.message || 'Failed to save document')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to delete this document?')) return

    try {
      const res = await fetch(`${API_BASE}/documents/${fullDocument.id}`, {
        method: 'DELETE',
      })

      if (!res.ok) throw new Error('Failed to delete document')

      onRefresh?.()
      onClose?.()
    } catch (e) {
      console.error('Failed to delete document:', e)
      setError('Failed to delete document')
    }
  }

  const isLocked = fullDocument?.locked || fullDocument?.metadata?.locked

  if (loading) {
    return (
      <div className="w-[600px] border-l border-neon-purple/20 bg-obsidian flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
      </div>
    )
  }

  const docType = fullDocument?.document_type || fullDocument?.metadata?.document_type || 'custom'
  const docTypeLabel = documentTypeLabels[docType] || 'Document'

  return (
    <div className="w-[600px] border-l border-neon-purple/20 bg-obsidian flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20 flex-shrink-0">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-slate-dark transition-colors"
              title="Close"
            >
              <ArrowLeft className="w-5 h-5 text-slate-400" />
            </button>
            <FileText className="w-5 h-5 text-neon-purple" />
            <div>
              {isEditing ? (
                <input
                  type="text"
                  value={editedTitle}
                  onChange={(e) => setEditedTitle(e.target.value)}
                  className="bg-slate-dark border border-slate-700 rounded px-2 py-1 text-lg font-semibold focus:border-neon-purple focus:outline-none"
                  placeholder="Document title..."
                />
              ) : (
                <h2 className="text-lg font-semibold">{editedTitle}</h2>
              )}
              <div className="flex items-center gap-2 text-xs text-slate-400">
                <span className="px-1.5 py-0.5 rounded bg-slate-dark capitalize">{docTypeLabel}</span>
                {isLocked && (
                  <span className="flex items-center gap-1 text-neon-cyan">
                    <Lock className="w-3 h-3" />
                    LLM Only
                  </span>
                )}
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {!isLocked && !isEditing && (
              <button
                onClick={() => setIsEditing(true)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-slate-dark hover:bg-slate-700 transition-colors text-sm"
              >
                <Edit3 className="w-4 h-4" />
                Edit
              </button>
            )}
            
            {isEditing && (
              <>
                <button
                  onClick={() => {
                    if (isNewDocument) {
                      onClose?.()
                    } else {
                      setIsEditing(false)
                      setEditedContent(fullDocument?.content || '')
                      setEditedTitle(fullDocument?.metadata?.name || fullDocument?.name || 'Untitled')
                    }
                  }}
                  className="px-3 py-1.5 rounded-lg border border-slate-700 hover:bg-slate-dark transition-colors text-sm"
                  disabled={saving}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-neon-purple hover:bg-neon-purple/80 transition-colors text-sm disabled:opacity-50"
                >
                  <Save className="w-4 h-4" />
                  {saving ? 'Saving...' : 'Save'}
                </button>
              </>
            )}
            
            {!isNewDocument && !isLocked && (
              <button
                onClick={handleDelete}
                className="p-1.5 rounded-lg hover:bg-red-500/20 text-red-400 transition-colors"
                title="Delete document"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
            
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg hover:bg-slate-dark transition-colors"
              title="Close"
            >
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Metadata */}
        <div className="flex items-center gap-4 text-xs text-slate-500">
          {fullDocument?.metadata?.created_at && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Created: {new Date(fullDocument.metadata.created_at).toLocaleDateString()}
            </span>
          )}
          {fullDocument?.metadata?.updated_at && (
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" />
              Updated: {new Date(fullDocument.metadata.updated_at).toLocaleDateString()}
            </span>
          )}
          {fullDocument?.metadata?.last_edited_by && (
            <span className="flex items-center gap-1">
              {fullDocument.metadata.last_edited_by === 'agent' ? (
                <Bot className="w-3 h-3 text-neon-cyan" />
              ) : (
                <User className="w-3 h-3 text-neon-green" />
              )}
              {fullDocument.metadata.last_edited_by}
            </span>
          )}
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-2 p-2 rounded-lg bg-red-500/20 text-red-400 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {isEditing ? (
          <DocumentEditor
            content={editedContent}
            onChange={setEditedContent}
            readOnly={false}
          />
        ) : (
          <div className="p-4">
            <DocumentEditor
              content={fullDocument?.content || ''}
              onChange={() => {}}
              readOnly={true}
            />
          </div>
        )}
      </div>
    </div>
  )
}

