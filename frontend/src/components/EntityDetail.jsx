import { useState, useEffect } from 'react'
import { X, Link2, Calendar, Tag, User, Target, Zap, FileText, Edit3, Trash2, Clock, ExternalLink, ChevronRight, Plus, Lock, File, Timer, AlertCircle, ArrowRight, ArrowLeft, ArrowLeftRight } from 'lucide-react'
import EntityEditor from './EntityEditor'
import RelationshipDetail from './RelationshipDetail'
import DocumentMini, { DocumentMiniHeader } from './DocumentMini'
import ActivityFeed from './ActivityFeed'

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

export default function EntityDetail({ entity, onClose, onRefresh, onDocumentSelect, onRelationshipPairSelect, onViewAllDocuments }) {
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

  const [relatedItems, setRelatedItems] = useState([])
  const [loadingRelated, setLoadingRelated] = useState(false)

  const fetchRelatedItems = async () => {
    if (!entity?.id) return
    setLoadingRelated(true)
    try {
      const res = await fetch(`${API_BASE}/entities/${entity.id}/related`)
      if (res.ok) {
        const data = await res.json()
        setRelatedItems(Array.isArray(data) ? data : [])
      }
    } catch (e) {
      console.error('Failed to fetch related items:', e)
    }
    setLoadingRelated(false)
  }

  useEffect(() => {
    if (activeTab === 'related' && entity?.id && relatedItems.length === 0) {
      fetchRelatedItems()
    }
  }, [activeTab, entity?.id])

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'documents', label: 'Docs', count: documents.length },
    { id: 'relationships', label: 'Relations' },
    { id: 'related', label: 'Related', count: relatedItems.length },
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
            onDelete={() => {
              // Close the sidebar and refresh the list
              onClose?.()
              onRefresh?.()
            }}
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
                onViewAllDocuments={onViewAllDocuments}
              />
            )}
            {activeTab === 'relationships' && (
              <RelationshipsTab 
                details={details} 
                entity={entity}
                onEntitySelect={(e) => {
                  // Close current panel and select new entity
                  onClose?.()
                  setTimeout(() => {
                    // Small delay to allow panel to close
                    window.dispatchEvent(new CustomEvent('entity-select', { detail: e }))
                  }, 50)
                }}
                onRefresh={() => {
                  fetchDetails()
                  onRefresh?.()
                }}
                onRelationshipPairSelect={onRelationshipPairSelect}
              />
            )}
            {activeTab === 'related' && (
              <RelatedTab 
                relatedItems={relatedItems}
                loading={loadingRelated}
                onEntitySelect={(e) => {
                  onClose?.()
                  setTimeout(() => {
                    window.dispatchEvent(new CustomEvent('entity-select', { detail: e }))
                  }, 50)
                }}
                onDocumentSelect={onDocumentSelect}
              />
            )}
            {activeTab === 'activity' && entity?.id && (
              <div className="p-4">
                <ActivityFeed
                  entityId={entity.id}
                  limit={30}
                  compact={false}
                  onEntitySelect={(e) => {
                    onClose?.()
                    setTimeout(() => {
                      window.dispatchEvent(new CustomEvent('entity-select', { detail: e }))
                    }, 50)
                  }}
                  onDocumentSelect={onDocumentSelect}
                />
              </div>
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

function RelationshipsTab({ details, entity, onEntitySelect, onRefresh, onRelationshipPairSelect }) {
  const relationships = details?.relationships || []
  const [selectedRel, setSelectedRel] = useState(null)
  const [creating, setCreating] = useState(false)

  const formatRelType = (type) => type?.replace(/_/g, ' ') || 'related to'

  const handleSaveRelationship = async (updatedRel) => {
    try {
      const res = await fetch(`${API_BASE}/relationships/${updatedRel.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedRel),
      })
      if (res.ok) {
        onRefresh?.()
        setSelectedRel(null)
      }
    } catch (e) {
      console.error('Failed to save relationship:', e)
    }
  }

  const handleDeleteRelationship = async (relId) => {
    try {
      const res = await fetch(`${API_BASE}/relationships/${relId}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        onRefresh?.()
        setSelectedRel(null)
      }
    } catch (e) {
      console.error('Failed to delete relationship:', e)
    }
  }

  if (selectedRel) {
    return (
      <div className="p-4">
        <RelationshipDetail
          relationship={selectedRel}
          sourceEntity={entity}
          targetEntity={{ id: selectedRel.other_id, name: selectedRel.other_name, type: selectedRel.other_type }}
          onClose={() => setSelectedRel(null)}
          onSave={handleSaveRelationship}
          onDelete={handleDeleteRelationship}
          onEntitySelect={(e) => {
            onEntitySelect?.(e)
            setSelectedRel(null)
          }}
        />
      </div>
    )
  }

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
        <div
          key={rel.id || idx}
          className="glass neon-border rounded-lg p-4 hover:border-neon-purple/60 transition-all group"
        >
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 rounded-lg bg-neon-purple/10 flex items-center justify-center">
              {/* Direction icon */}
              {rel.direction === 'incoming' ? (
                <ArrowLeft className="w-5 h-5 text-neon-purple" />
              ) : rel.direction === 'bidirectional' ? (
                <ArrowLeftRight className="w-5 h-5 text-neon-purple" />
              ) : (
                <ArrowRight className="w-5 h-5 text-neon-purple" />
              )}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="font-medium truncate">{rel.other_name || 'Unknown'}</p>
                <span className="px-2 py-0.5 rounded-full text-xs bg-neon-purple/20 text-neon-purple capitalize">
                  {formatRelType(rel.type)}
                </span>
                {rel.direction && rel.direction !== 'outgoing' && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-dark text-slate-400">
                    {rel.direction === 'incoming' ? '←' : '↔'}
                  </span>
                )}
              </div>
              {rel.context && (
                <p className="text-xs text-slate-500 truncate mt-1">{rel.context}</p>
              )}
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setSelectedRel(rel)}
                className="p-1.5 rounded-lg hover:bg-neon-purple/10 transition-colors"
                title="Edit relationship"
              >
                <Edit3 className="w-4 h-4 text-slate-400 hover:text-neon-purple" />
              </button>
              {onRelationshipPairSelect && (
                <button
                  onClick={() => {
                    // Construct the other entity to pass to the relationship pair view
                    const otherEntity = {
                      id: rel.other_id,
                      name: rel.other_name,
                      type: rel.other_type || 'unknown',
                    }
                    onRelationshipPairSelect(entity, otherEntity)
                  }}
                  className="p-1.5 rounded-lg hover:bg-neon-cyan/10 transition-colors"
                  title="View all relationships between these entities"
                >
                  <Link2 className="w-4 h-4 text-slate-400 hover:text-neon-cyan" />
                </button>
              )}
            </div>
          </div>
          
          {/* Context row */}
          {(rel.context || rel.category) && (
            <div className="flex items-center gap-2 mt-3 pt-3 border-t border-slate-700/50">
              {rel.context && (
                <span className="text-xs text-slate-400 truncate flex-1">{rel.context}</span>
              )}
              {rel.category && (
                <span className="px-2 py-0.5 rounded-full text-xs bg-slate-dark text-slate-400">
                  {rel.category}
                </span>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ActivityTab is now replaced by the inline ActivityFeed component

function DocumentsTab({ documents, loading, colors, entityId, entityType, onDocumentSelect, onRefresh, onViewAllDocuments }) {
  return (
    <div className="p-4">
      <DocumentMini
        entityId={entityId}
        onDocumentSelect={onDocumentSelect}
        onViewAll={(filters) => onViewAllDocuments?.(filters)}
        maxItems={10}
      />
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

function RelatedTab({ relatedItems, loading, onEntitySelect, onDocumentSelect }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
      </div>
    )
  }

  const entities = relatedItems.filter(item => item.item_type === 'entity')
  const documents = relatedItems.filter(item => item.item_type === 'document')

  if (relatedItems.length === 0) {
    return (
      <div className="p-4 text-center py-12">
        <div className="w-16 h-16 rounded-xl bg-slate-dark flex items-center justify-center mx-auto mb-4">
          <Tag className="w-8 h-8 text-slate-500" />
        </div>
        <p className="text-slate-400">No related items found</p>
        <p className="text-sm text-slate-500 mt-1">Add tags to find connections</p>
      </div>
    )
  }

  return (
    <div className="p-4 space-y-6">
      {/* Related Entities */}
      {entities.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Related Entities ({entities.length})
          </h3>
          <div className="space-y-2">
            {entities.map(item => {
              const itemConfig = typeConfig[item.type] || typeConfig.note
              const ItemIcon = itemConfig.icon
              const itemColors = colorClasses[itemConfig.color]
              
              return (
                <button
                  key={item.id}
                  onClick={() => onEntitySelect?.({ id: item.id, name: item.name, type: item.type })}
                  className="w-full glass neon-border rounded-lg p-3 text-left hover:border-neon-purple/60 transition-all"
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg ${itemColors.bg} flex items-center justify-center`}>
                      <ItemIcon className={`w-4 h-4 ${itemColors.text}`} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate text-sm">{item.name}</p>
                      <p className="text-xs text-slate-500 capitalize">{item.type}</p>
                    </div>
                    {item.shared_tags?.length > 0 && (
                      <div className="flex items-center gap-1">
                        <Tag className="w-3 h-3 text-slate-400" />
                        <span className="text-xs text-slate-400">
                          {item.shared_tags.length} shared
                        </span>
                      </div>
                    )}
                  </div>
                  {item.shared_tags?.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2 pt-2 border-t border-slate-700/50">
                      {item.shared_tags.slice(0, 5).map(tag => (
                        <span key={tag} className="px-1.5 py-0.5 rounded text-[10px] bg-neon-purple/20 text-neon-purple">
                          {tag}
                        </span>
                      ))}
                      {item.shared_tags.length > 5 && (
                        <span className="text-[10px] text-slate-500">+{item.shared_tags.length - 5} more</span>
                      )}
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        </section>
      )}

      {/* Related Documents */}
      {documents.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Related Documents ({documents.length})
          </h3>
          <div className="space-y-2">
            {documents.map(item => (
              <button
                key={item.id}
                onClick={() => onDocumentSelect?.({ id: item.id, name: item.name })}
                className="w-full glass neon-border rounded-lg p-3 text-left hover:border-neon-purple/60 transition-all"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-lg bg-neon-blue/20 flex items-center justify-center">
                    <FileText className="w-4 h-4 text-neon-blue" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-sm">{item.name}</p>
                    {item.shared_tags?.length > 0 && (
                      <p className="text-xs text-slate-500">
                        {item.shared_tags.length} shared tags
                      </p>
                    )}
                  </div>
                  <ChevronRight className="w-4 h-4 text-slate-500" />
                </div>
              </button>
            ))}
          </div>
        </section>
      )}
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

