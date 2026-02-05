import { useState, useEffect } from 'react'
import { X, Link2, Calendar, Tag, User, Target, Zap, FileText, Edit3, Trash2, Clock, ExternalLink, ChevronRight, Plus, Lock, File, Timer, AlertCircle } from 'lucide-react'
import EntityEditor from './EntityEditor'

const API_BASE = '/api'

const typeConfig = {
  person: { icon: User, color: 'cyan' },
  project: { icon: Target, color: 'purple' },
  goal: { icon: Zap, color: 'green' },
  event: { icon: Calendar, color: 'pink' },
  note: { icon: FileText, color: 'blue' },
  period: { icon: Timer, color: 'orange' },
}

const colorClasses = {
  cyan: { bg: 'bg-neon-cyan/20', text: 'text-neon-cyan', border: 'border-neon-cyan/40' },
  purple: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple/40' },
  green: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green/40' },
  pink: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink/40' },
  blue: { bg: 'bg-neon-blue/20', text: 'text-neon-blue', border: 'border-neon-blue/40' },
  orange: { bg: 'bg-amber-500/20', text: 'text-amber-500', border: 'border-amber-500/40' },
}

export default function EntityDetail({ entity, onClose, onRefresh, onDocumentSelect }) {
  const [details, setDetails] = useState(null)
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingDocs, setLoadingDocs] = useState(true)
  const [activeTab, setActiveTab] = useState('overview')
  const [isEditing, setIsEditing] = useState(false)

  const entityType = entity?.type || 'note'
  const config = typeConfig[entityType] || typeConfig.note
  const colors = colorClasses[config.color]
  const Icon = config.icon

  useEffect(() => {
    if (entity?.id) {
      fetchDetails()
      fetchDocuments()
    } else {
      setLoading(false)
      setLoadingDocs(false)
      setDetails({ metadata: entity })
    }
  }, [entity?.id])

  const fetchDetails = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/graph/node/${entity.id}`)
      if (res.ok) {
        const data = await res.json()
        setDetails(data)
      } else {
        setDetails({ metadata: entity })
      }
    } catch (e) {
      console.error('Failed to fetch details:', e)
      setDetails({ metadata: entity })
    }
    setLoading(false)
  }

  const fetchDocuments = async () => {
    setLoadingDocs(true)
    try {
      const res = await fetch(`${API_BASE}/entities/${entity.id}/documents`)
      if (res.ok) {
        const data = await res.json()
        setDocuments(data.documents || [])
      }
    } catch (e) {
      console.error('Failed to fetch documents:', e)
    }
    setLoadingDocs(false)
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'documents', label: 'Documents', count: documents.length },
    { id: 'relationships', label: 'Relationships' },
    { id: 'activity', label: 'Activity' },
  ]

  return (
    <div className="w-[450px] border-l border-neon-purple/20 flex flex-col bg-obsidian h-full animate-slide-in">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl ${colors.bg} flex items-center justify-center`}>
              <Icon className={`w-6 h-6 ${colors.text}`} />
            </div>
            <div>
              <h2 className="font-semibold text-xl">
                {entity?.label || entity?.name || entity?.title || 'Unknown'}
              </h2>
              <span className={`text-xs font-mono ${colors.text} capitalize`}>{entityType}</span>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <button 
              onClick={() => setIsEditing(!isEditing)}
              className={`p-2 rounded-lg transition-colors ${
                isEditing 
                  ? 'bg-neon-purple/20 text-neon-purple' 
                  : 'hover:bg-slate-dark text-slate-400'
              }`} 
              title={isEditing ? "Cancel editing" : "Edit"}
            >
              <Edit3 className="w-4 h-4" />
            </button>
            <button 
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
            >
              <X className="w-5 h-5 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Tabs - hide when editing */}
        {!isEditing && (
          <div className="flex gap-1 bg-slate-dark rounded-lg p-1">
            {tabs.map(tab => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-1 ${
                  activeTab === tab.id
                    ? 'bg-neon-purple/20 text-neon-purple'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-slate-700">{tab.count}</span>
                )}
              </button>
            ))}
          </div>
        )}
        
        {/* Edit Mode Banner */}
        {isEditing && (
          <div className="flex items-center gap-2 px-3 py-2 bg-neon-purple/10 border border-neon-purple/30 rounded-lg">
            <Edit3 className="w-4 h-4 text-neon-purple" />
            <span className="text-sm text-neon-purple font-medium">Edit Mode</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
          </div>
        ) : isEditing ? (
          <EntityEditor
            entity={entity}
            metadata={details?.metadata}
            onSave={() => {
              setIsEditing(false)
              fetchDetails()
              onRefresh?.()
            }}
            onCancel={() => setIsEditing(false)}
          />
        ) : (
          <>
            {activeTab === 'overview' && (
              <OverviewTab details={details} colors={colors} entity={entity} />
            )}
            {activeTab === 'documents' && (
              <DocumentsTab 
                documents={documents} 
                loading={loadingDocs} 
                colors={colors}
                entityId={entity?.id}
                entityType={entity?.type}
                onDocumentSelect={onDocumentSelect}
                onRefresh={fetchDocuments}
              />
            )}
            {activeTab === 'relationships' && (
              <RelationshipsTab details={details} colors={colors} />
            )}
            {activeTab === 'activity' && (
              <ActivityTab details={details} colors={colors} />
            )}
          </>
        )}
      </div>

      {/* Footer - hide when editing */}
      {!isEditing && (
        <div className="p-4 border-t border-neon-purple/20 bg-slate-dark/50">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500 font-mono truncate flex-1">
              ID: {entity?.id?.slice(0, 8)}...
            </p>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-neon-purple/20 text-neon-purple text-sm font-medium hover:bg-neon-purple/30 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function OverviewTab({ details, colors, entity }) {
  const [generalInfo, setGeneralInfo] = useState(null)
  const [loadingInfo, setLoadingInfo] = useState(true)
  
  const metadata = details?.metadata || entity || {}
  const isPeriod = metadata.type === 'period'
  const isComplete = isPeriod ? (metadata.start_date && metadata.end_date) : true
  
  // Fetch General Info document
  useEffect(() => {
    const fetchGeneralInfo = async () => {
      if (!entity?.id) {
        setLoadingInfo(false)
        return
      }
      
      try {
        const res = await fetch(`${API_BASE}/entities/${entity.id}/general-info`)
        if (res.ok) {
          const data = await res.json()
          setGeneralInfo(data)
        }
      } catch (e) {
        console.error('Failed to fetch general info:', e)
      }
      setLoadingInfo(false)
    }
    
    fetchGeneralInfo()
  }, [entity?.id])
  
  // Extract content from General Info document (strip the # Title header)
  const getGeneralInfoContent = () => {
    // API returns { exists: bool, document: { content: ... } }
    const content = generalInfo?.document?.content
    if (!content) return null
    // Remove the first line if it's a heading
    const lines = content.split('\n')
    if (lines[0]?.startsWith('#')) {
      return lines.slice(1).join('\n').trim()
    }
    return content.trim()
  }
  
  const infoContent = getGeneralInfoContent()
  
  return (
    <div className="p-4 space-y-6">
      {/* Period Completeness Warning */}
      {isPeriod && !isComplete && (
        <section>
          <div className="glass rounded-xl p-4 border border-amber-500/40 bg-amber-500/10">
            <div className="flex items-center gap-3">
              <AlertCircle className="w-5 h-5 text-amber-500" />
              <div>
                <p className="text-sm font-medium text-amber-400">Incomplete Period</p>
                <p className="text-xs text-amber-300/70">
                  This period is missing {!metadata.start_date && !metadata.end_date ? 'start and end dates' : 
                    !metadata.start_date ? 'start date' : 'end date'}
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Period Date Range */}
      {isPeriod && (
        <section>
          <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Time Span
          </h3>
          <div className="glass neon-border rounded-xl p-4">
            <div className="flex items-center justify-between">
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-1">Start Date</p>
                <p className={`text-lg font-mono ${metadata.start_date ? 'text-amber-400' : 'text-slate-500'}`}>
                  {metadata.start_date ? formatDate(metadata.start_date) : '?'}
                </p>
              </div>
              <div className="text-2xl text-slate-500">→</div>
              <div className="text-center">
                <p className="text-xs text-slate-500 mb-1">End Date</p>
                <p className={`text-lg font-mono ${metadata.end_date ? 'text-amber-400' : 'text-slate-500'}`}>
                  {metadata.end_date ? formatDate(metadata.end_date) : '?'}
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {/* Disambiguator - short context line */}
      {metadata.disambiguator && (
        <section>
          <div className="glass neon-border rounded-xl p-3">
            <p className="text-sm text-slate-400 italic">
              {metadata.disambiguator}
            </p>
          </div>
        </section>
      )}

      {/* General Info Document - LLM managed */}
      <section>
        <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
          <FileText className="w-4 h-4" />
          About
          <span className="ml-auto flex items-center gap-1 text-xs text-slate-500 font-normal">
            <Lock className="w-3 h-3" />
            AI-managed
          </span>
        </h3>
        <div className="glass neon-border rounded-xl p-4">
          {loadingInfo ? (
            <div className="flex items-center justify-center py-4">
              <div className="animate-spin w-5 h-5 border-2 border-neon-purple border-t-transparent rounded-full" />
            </div>
          ) : infoContent ? (
            <div className="prose prose-sm prose-invert max-w-none">
              <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                {infoContent}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500 text-center py-2">
              No information yet. Chat with the assistant to add details about this {metadata.type || 'entity'}.
            </p>
          )}
        </div>
      </section>

      {/* Metadata */}
      <section>
        <h3 className="text-sm font-semibold text-slate-300 mb-2 flex items-center gap-2">
          <Tag className="w-4 h-4" />
          Properties
        </h3>
        <div className="glass neon-border rounded-xl divide-y divide-slate-700/50">
          {metadata.created_at && (
            <MetadataRow label="Created" value={formatDate(metadata.created_at)} />
          )}
          {metadata.updated_at && (
            <MetadataRow label="Updated" value={formatDate(metadata.updated_at)} />
          )}
          {metadata.confidence !== undefined && (
            <MetadataRow 
              label="Confidence" 
              value={
                <div className="flex items-center gap-2">
                  <div className="w-20 h-2 rounded-full bg-slate-700 overflow-hidden">
                    <div 
                      className={`h-full ${colors.bg.replace('/20', '')}`}
                      style={{ width: `${Math.round(metadata.confidence * 100)}%` }}
                    />
                  </div>
                  <span>{Math.round(metadata.confidence * 100)}%</span>
                </div>
              } 
            />
          )}
          {metadata.source && (
            <MetadataRow label="Source" value={metadata.source} />
          )}
          {metadata.status && (
            <MetadataRow 
              label="Status" 
              value={
                <span className={`px-2 py-0.5 rounded-full text-xs ${colors.bg} ${colors.text} capitalize`}>
                  {metadata.status}
                </span>
              } 
            />
          )}
          {metadata.email && (
            <MetadataRow label="Email" value={metadata.email} />
          )}
          {metadata.phone && (
            <MetadataRow label="Phone" value={metadata.phone} />
          )}
          {metadata.last_interaction && (
            <MetadataRow label="Last Interaction" value={formatDate(metadata.last_interaction)} />
          )}
          {metadata.target_date && (
            <MetadataRow label="Target Date" value={formatDate(metadata.target_date)} />
          )}
          {metadata.progress !== undefined && (
            <MetadataRow 
              label="Progress" 
              value={
                <div className="flex items-center gap-2">
                  <div className="w-20 h-2 rounded-full bg-slate-700 overflow-hidden">
                    <div 
                      className="h-full bg-neon-green"
                      style={{ width: `${metadata.progress}%` }}
                    />
                  </div>
                  <span>{metadata.progress}%</span>
                </div>
              } 
            />
          )}
        </div>
      </section>

      {/* Tags */}
      {metadata.tags && metadata.tags.length > 0 && (
        <section>
          <h3 className="text-sm font-semibold text-slate-300 mb-2">Tags</h3>
          <div className="flex flex-wrap gap-2">
            {metadata.tags.map((tag, idx) => (
              <span 
                key={idx}
                className="px-3 py-1 rounded-full text-xs bg-neon-purple/20 text-neon-purple border border-neon-purple/30"
              >
                {tag}
              </span>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function RelationshipsTab({ details }) {
  const relationships = details?.relationships || []

  if (relationships.length === 0) {
    return (
      <div className="p-4 text-center py-12">
        <div className="w-16 h-16 rounded-xl bg-slate-dark flex items-center justify-center mx-auto mb-4">
          <Link2 className="w-8 h-8 text-slate-500" />
        </div>
        <p className="text-slate-400">No relationships found</p>
        <p className="text-sm text-slate-500 mt-1">Connections will appear here</p>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-2">
      {relationships.map((rel, idx) => (
        <button
          key={idx}
          className="w-full glass neon-border rounded-lg p-4 text-left hover:border-neon-purple/60 transition-all flex items-center gap-4"
        >
          <div className="w-10 h-10 rounded-lg bg-slate-dark flex items-center justify-center">
            <Link2 className="w-5 h-5 text-neon-purple" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{rel.other_name || 'Unknown'}</p>
            <p className="text-xs text-slate-500">{rel.type || 'related'}</p>
          </div>
          {rel.category && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-slate-dark text-slate-400">
              {rel.category}
            </span>
          )}
          <ChevronRight className="w-4 h-4 text-slate-500" />
        </button>
      ))}
    </div>
  )
}

function ActivityTab({ details }) {
  // This would show audit history
  return (
    <div className="p-4 text-center py-12">
      <div className="w-16 h-16 rounded-xl bg-slate-dark flex items-center justify-center mx-auto mb-4">
        <Clock className="w-8 h-8 text-slate-500" />
      </div>
      <p className="text-slate-400">Activity Timeline</p>
      <p className="text-sm text-slate-500 mt-1">Changes and updates will appear here</p>
    </div>
  )
}

function DocumentsTab({ documents, loading, colors, entityId, entityType, onDocumentSelect, onRefresh }) {
  const documentTypeLabels = {
    general_info: 'General Info',
    note: 'Note',
    meeting: 'Meeting',
    research: 'Research',
    plan: 'Plan',
    custom: 'Document',
  }

  const documentTypeColors = {
    general_info: 'text-neon-cyan',
    note: 'text-slate-400',
    meeting: 'text-neon-pink',
    research: 'text-neon-purple',
    plan: 'text-neon-green',
    custom: 'text-slate-300',
  }

  if (loading) {
    return (
      <div className="p-4 flex items-center justify-center py-12">
        <div className="animate-spin w-6 h-6 border-2 border-neon-purple border-t-transparent rounded-full" />
      </div>
    )
  }

  // Filter out General Info docs - they're shown in the Overview tab
  const otherDocs = documents.filter(d => d.document_type !== 'general_info')

  return (
    <div className="p-4 space-y-4">
      {/* User & LLM Documents (excluding General Info which is in Overview) */}
      <section>
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Documents</h3>
          <button
            onClick={() => onDocumentSelect?.({ 
              isNew: true, 
              parent_entity_id: entityId,
              parent_entity_type: entityType 
            })}
            className="flex items-center gap-1 text-xs text-neon-purple hover:text-neon-purple/80 transition-colors"
          >
            <Plus className="w-3 h-3" />
            New
          </button>
        </div>

        {otherDocs.length === 0 ? (
          <div className="text-center py-8 glass neon-border rounded-lg">
            <div className="w-12 h-12 rounded-xl bg-slate-dark flex items-center justify-center mx-auto mb-3">
              <File className="w-6 h-6 text-slate-500" />
            </div>
            <p className="text-sm text-slate-400">No documents yet</p>
            <button
              onClick={() => onDocumentSelect?.({ 
                isNew: true, 
                parent_entity_id: entityId,
                parent_entity_type: entityType 
              })}
              className="mt-3 text-sm text-neon-purple hover:underline"
            >
              Create first document
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            {otherDocs.map(doc => {
              const docType = doc.document_type || 'custom'
              const colorClass = documentTypeColors[docType] || documentTypeColors.custom
              
              return (
                <button
                  key={doc.id}
                  onClick={() => onDocumentSelect?.(doc)}
                  className="w-full glass neon-border rounded-lg p-3 text-left hover:border-neon-purple/60 transition-all flex items-center gap-3"
                >
                  <File className={`w-5 h-5 ${colorClass}`} />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-sm">{doc.name || 'Untitled'}</p>
                    <p className="text-xs text-slate-500">
                      {documentTypeLabels[docType] || 'Document'}
                    </p>
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </button>
              )
            })}
          </div>
        )}
      </section>
    </div>
  )
}

function MetadataRow({ label, value }) {
  return (
    <div className="flex items-center justify-between p-3">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="text-sm text-slate-300 font-mono">{value}</span>
    </div>
  )
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

