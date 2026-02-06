import { useState, useEffect, useCallback } from 'react'
import {
  Clock, User, Bot, Settings, Plus, Pencil, Trash2, Undo2,
  ArrowRight, FileText, Link2, UserCircle, RefreshCw, Filter, ChevronDown,
  ChevronUp, Users, Target, Zap, Calendar, Timer, Archive
} from 'lucide-react'

const API_BASE = '/api'

const ACTION_CONFIG = {
  create: { icon: Plus, color: 'text-neon-green', bg: 'bg-neon-green/10', label: 'Created' },
  update: { icon: Pencil, color: 'text-neon-blue', bg: 'bg-neon-blue/10', label: 'Updated' },
  delete: { icon: Trash2, color: 'text-neon-pink', bg: 'bg-neon-pink/10', label: 'Deleted' },
  soft_delete: { icon: Archive, color: 'text-amber-400', bg: 'bg-amber-400/10', label: 'Archived' },
  restore: { icon: Undo2, color: 'text-neon-cyan', bg: 'bg-neon-cyan/10', label: 'Restored' },
  correct: { icon: Pencil, color: 'text-neon-purple', bg: 'bg-neon-purple/10', label: 'Corrected' },
  merge: { icon: Link2, color: 'text-amber-400', bg: 'bg-amber-400/10', label: 'Merged' },
}

const ACTOR_CONFIG = {
  user: { icon: User, label: 'You' },
  agent: { icon: Bot, label: 'Agent' },
  system: { icon: Settings, label: 'System' },
}

const TYPE_ICON = {
  entity: UserCircle,
  document: FileText,
  relationship: Link2,
}

// Entity type colors matching the sidebar
const ENTITY_TYPE_CONFIG = {
  person: { color: 'text-neon-cyan', bg: 'bg-neon-cyan/10', border: 'border-neon-cyan/30', icon: Users, label: 'Person' },
  project: { color: 'text-neon-purple', bg: 'bg-neon-purple/10', border: 'border-neon-purple/30', icon: Target, label: 'Project' },
  goal: { color: 'text-neon-green', bg: 'bg-neon-green/10', border: 'border-neon-green/30', icon: Zap, label: 'Goal' },
  event: { color: 'text-neon-pink', bg: 'bg-neon-pink/10', border: 'border-neon-pink/30', icon: Calendar, label: 'Event' },
  period: { color: 'text-amber-500', bg: 'bg-amber-500/10', border: 'border-amber-500/30', icon: Timer, label: 'Period' },
  note: { color: 'text-neon-blue', bg: 'bg-neon-blue/10', border: 'border-neon-blue/30', icon: FileText, label: 'Note' },
}

function timeAgo(timestamp) {
  if (!timestamp) return ''
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now - then
  const diffMin = Math.floor(diffMs / 60000)
  const diffHr = Math.floor(diffMin / 60)
  const diffDay = Math.floor(diffHr / 24)

  if (diffMin < 1) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDay < 7) return `${diffDay}d ago`
  return then.toLocaleDateString()
}

// Fields to skip when showing diffs (internal/meta fields)
const SKIP_FIELDS = new Set([
  '_audit_metadata', 'id', 'checksum', 'file_path', 'parent_id',
  'parent_entity_id', 'parent_relationship_id', 'document_type',
  'embedding_status', 'embedding_model',
])

// Friendly field name mapping
const FIELD_LABELS = {
  name: 'Name',
  type: 'Type',
  title: 'Title',
  tags: 'Tags',
  status: 'Status',
  content: 'Content',
  description: 'Description',
  custom_fields: 'Details',
  created_at: 'Created',
  updated_at: 'Updated',
  relationship_type: 'Relationship',
  source_entity: 'From',
  target_entity: 'To',
}

function truncateValue(val, maxLen = 60) {
  if (val === null || val === undefined) return '—'
  const str = typeof val === 'object' ? JSON.stringify(val) : String(val)
  return str.length > maxLen ? str.slice(0, maxLen) + '…' : str
}

function formatFieldValue(key, val) {
  if (val === null || val === undefined) return '—'
  if (Array.isArray(val)) {
    if (val.length === 0) return '(none)'
    return val.map(v => typeof v === 'object' ? JSON.stringify(v) : String(v)).join(', ')
  }
  if (typeof val === 'object') {
    // For custom_fields, show key: value pairs
    const entries = Object.entries(val).filter(([k]) => !k.startsWith('_'))
    if (entries.length === 0) return '(empty)'
    return entries.map(([k, v]) => `${k}: ${truncateValue(v, 40)}`).join(', ')
  }
  if (key === 'content' || key === 'description') {
    return truncateValue(val, 80)
  }
  return truncateValue(val)
}

/**
 * Compute field-level changes between old and new data.
 * Returns { added: [], changed: [], removed: [] }
 */
function computeChanges(oldData, newData) {
  const added = []
  const changed = []
  const removed = []

  if (!oldData && !newData) return { added, changed, removed }

  const oldObj = (typeof oldData === 'object' && oldData) || {}
  const newObj = (typeof newData === 'object' && newData) || {}

  const allKeys = new Set([...Object.keys(oldObj), ...Object.keys(newObj)])

  for (const key of allKeys) {
    if (SKIP_FIELDS.has(key)) continue

    const oldVal = oldObj[key]
    const newVal = newObj[key]
    const oldStr = JSON.stringify(oldVal)
    const newStr = JSON.stringify(newVal)

    if (oldStr === newStr) continue

    if (oldVal === undefined || oldVal === null) {
      if (newVal !== undefined && newVal !== null) {
        added.push({ key, value: newVal })
      }
    } else if (newVal === undefined || newVal === null) {
      removed.push({ key, value: oldVal })
    } else {
      changed.push({ key, oldValue: oldVal, newValue: newVal })
    }
  }

  return { added, changed, removed }
}

function ChangeSummary({ entry }) {
  const [expanded, setExpanded] = useState(false)
  const { action, old_data, new_data } = entry

  // For creates, show key new fields
  if (action === 'create' && new_data && typeof new_data === 'object') {
    const highlights = ['type', 'tags', 'status', 'description', 'custom_fields']
      .filter(k => new_data[k] !== undefined && new_data[k] !== null)
      .slice(0, 3)

    if (highlights.length === 0) return null

    return (
      <div className="mt-1.5 space-y-1">
        {highlights.map(key => (
          <div key={key} className="flex items-start gap-1.5 text-xs">
            <span className="text-slate-500 flex-shrink-0">{FIELD_LABELS[key] || key}:</span>
            <span className="text-slate-400 break-all">{formatFieldValue(key, new_data[key])}</span>
          </div>
        ))}
      </div>
    )
  }

  // For updates/corrections, show diffs
  if ((action === 'update' || action === 'correct') && (old_data || new_data)) {
    const { added, changed, removed } = computeChanges(old_data, new_data)
    const totalChanges = added.length + changed.length + removed.length

    if (totalChanges === 0) return null

    const visibleChanges = expanded ? totalChanges : Math.min(totalChanges, 3)
    const allChanges = [
      ...changed.map(c => ({ type: 'changed', ...c })),
      ...added.map(a => ({ type: 'added', ...a })),
      ...removed.map(r => ({ type: 'removed', ...r })),
    ]
    const displayChanges = allChanges.slice(0, visibleChanges)

    return (
      <div className="mt-1.5 space-y-1">
        {displayChanges.map((change, idx) => (
          <div key={idx} className="flex items-start gap-1.5 text-xs">
            {change.type === 'changed' && (
              <>
                <span className="text-neon-blue flex-shrink-0">~</span>
                <span className="text-slate-500 flex-shrink-0">{FIELD_LABELS[change.key] || change.key}:</span>
                <span className="text-slate-500 line-through">{truncateValue(change.oldValue, 30)}</span>
                <ArrowRight className="w-3 h-3 text-slate-600 flex-shrink-0 mt-0.5" />
                <span className="text-slate-300">{truncateValue(change.newValue, 30)}</span>
              </>
            )}
            {change.type === 'added' && (
              <>
                <span className="text-neon-green flex-shrink-0">+</span>
                <span className="text-slate-500 flex-shrink-0">{FIELD_LABELS[change.key] || change.key}:</span>
                <span className="text-neon-green/80">{formatFieldValue(change.key, change.value)}</span>
              </>
            )}
            {change.type === 'removed' && (
              <>
                <span className="text-neon-pink flex-shrink-0">−</span>
                <span className="text-slate-500 flex-shrink-0">{FIELD_LABELS[change.key] || change.key}:</span>
                <span className="text-neon-pink/70 line-through">{formatFieldValue(change.key, change.value)}</span>
              </>
            )}
          </div>
        ))}
        {totalChanges > 3 && (
          <button
            onClick={(e) => { e.stopPropagation(); setExpanded(!expanded) }}
            className="text-xs text-slate-500 hover:text-slate-300 flex items-center gap-1 mt-0.5"
          >
            {expanded ? (
              <>Show less <ChevronUp className="w-3 h-3" /></>
            ) : (
              <>{totalChanges - 3} more change{totalChanges - 3 > 1 ? 's' : ''} <ChevronDown className="w-3 h-3" /></>
            )}
          </button>
        )}
      </div>
    )
  }

  // For deletes, show what was removed
  if ((action === 'delete' || action === 'soft_delete') && old_data && typeof old_data === 'object') {
    const entityType = old_data.type
    const typeConf = entityType && ENTITY_TYPE_CONFIG[entityType]

    return (
      <div className="mt-1.5 text-xs text-slate-500">
        {typeConf && (
          <span className={typeConf.color}>{typeConf.label}</span>
        )}
        {old_data.tags?.length > 0 && (
          <span className="ml-2">Tags: {old_data.tags.join(', ')}</span>
        )}
      </div>
    )
  }

  return null
}

function ActivityEntry({ entry, onUndo, onItemClick }) {
  const action = ACTION_CONFIG[entry.action] || ACTION_CONFIG.update
  const actor = ACTOR_CONFIG[entry.actor] || ACTOR_CONFIG.system
  const ActionIcon = action.icon
  const ActorIcon = actor.icon

  // Determine entity type from new_data or old_data
  const entityData = entry.new_data || entry.old_data || {}
  const entityType = typeof entityData === 'object' ? entityData.type : null
  const typeConf = entityType && ENTITY_TYPE_CONFIG[entityType]
  const TypeIcon = typeConf?.icon || TYPE_ICON[entry.item_type] || FileText

  // Entity name: prefer item_name, then new_data.name, then old_data.name
  const entityName = entry.item_name
    || (typeof entry.new_data === 'object' && entry.new_data?.name)
    || (typeof entry.old_data === 'object' && entry.old_data?.name)
    || entry.document_id?.slice(0, 8)
    || 'Unknown'

  return (
    <div className="flex items-start gap-3 p-3 rounded-lg bg-slate-dark/30 hover:bg-slate-dark/50 transition-colors group">
      {/* Action icon */}
      <div className={`w-8 h-8 rounded-lg ${action.bg} flex items-center justify-center flex-shrink-0 mt-0.5`}>
        <ActionIcon className={`w-4 h-4 ${action.color}`} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {/* Top row: action + entity type badge + time */}
        <div className="flex items-center gap-2 mb-0.5">
          <span className={`text-xs font-semibold uppercase tracking-wide ${action.color}`}>
            {action.label}
          </span>
          {typeConf ? (
            <span className={`inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded ${typeConf.bg} ${typeConf.color} border ${typeConf.border}`}>
              <TypeIcon className="w-3 h-3" />
              {typeConf.label}
            </span>
          ) : entry.item_type && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <TypeIcon className="w-3 h-3" />
              {entry.item_type}
            </span>
          )}
          <span className="ml-auto text-xs text-slate-600 font-mono flex-shrink-0">
            {timeAgo(entry.timestamp)}
          </span>
        </div>

        {/* Entity name */}
        <button
          onClick={() => onItemClick?.(entry)}
          className={`text-sm font-semibold hover:text-white truncate block max-w-full text-left ${typeConf ? typeConf.color : 'text-slate-200'}`}
          title={entityName}
        >
          {entityName}
        </button>

        {/* Changes summary */}
        <ChangeSummary entry={entry} />

        {/* Actor row */}
        <div className="flex items-center gap-2 mt-1.5">
          <ActorIcon className="w-3 h-3 text-slate-500" />
          <span className="text-xs text-slate-500">{actor.label}</span>
        </div>
      </div>

      {/* Undo button (for undoable actions) */}
      {['update', 'delete', 'soft_delete'].includes(entry.action) && (
        <button
          onClick={(e) => { e.stopPropagation(); onUndo?.(entry.document_id) }}
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-neon-cyan/10 text-slate-500 hover:text-neon-cyan transition-all"
          title="Undo this action"
        >
          <Undo2 className="w-4 h-4" />
        </button>
      )}
    </div>
  )
}

export default function ActivityFeed({
  entityId = null,
  limit = 30,
  compact = false,
  onEntitySelect,
  onDocumentSelect,
}) {
  const [activity, setActivity] = useState([])
  const [loading, setLoading] = useState(true)
  const [undoing, setUndoing] = useState(null)
  const [filter, setFilter] = useState({ item_type: null, actor: null })
  const [showFilters, setShowFilters] = useState(false)

  const fetchActivity = useCallback(async () => {
    setLoading(true)
    try {
      let url
      if (entityId) {
        url = `${API_BASE}/activity/entity/${entityId}?limit=${limit}`
      } else {
        const params = new URLSearchParams({ limit: String(limit) })
        if (filter.item_type) params.append('item_type', filter.item_type)
        if (filter.actor) params.append('actor', filter.actor)
        url = `${API_BASE}/activity?${params}`
      }

      const res = await fetch(url)
      if (res.ok) {
        const data = await res.json()
        setActivity(data.activity || [])
      }
    } catch (e) {
      console.error('Failed to fetch activity:', e)
    }
    setLoading(false)
  }, [entityId, limit, filter])

  useEffect(() => {
    fetchActivity()
  }, [fetchActivity])

  const handleUndo = async (itemId) => {
    setUndoing(itemId)
    try {
      const res = await fetch(`${API_BASE}/activity/undo/${itemId}`, { method: 'POST' })
      if (res.ok) {
        // Refresh activity after undo
        await fetchActivity()
      } else {
        const data = await res.json()
        console.error('Undo failed:', data.detail)
      }
    } catch (e) {
      console.error('Undo error:', e)
    }
    setUndoing(null)
  }

  const handleItemClick = (entry) => {
    if (!entry.document_id) return
    if (entry.item_type === 'entity') {
      onEntitySelect?.({ id: entry.document_id, name: entry.item_name })
    } else if (entry.item_type === 'document') {
      onDocumentSelect?.(entry.document_id)
    }
  }

  if (compact) {
    return (
      <div className="space-y-2">
        {loading ? (
          <div className="flex items-center justify-center py-6">
            <div className="animate-spin w-5 h-5 border-2 border-neon-purple border-t-transparent rounded-full" />
          </div>
        ) : activity.length > 0 ? (
          activity.slice(0, 5).map((entry, idx) => (
            <ActivityEntry
              key={entry.id || idx}
              entry={entry}
              onUndo={handleUndo}
              onItemClick={handleItemClick}
            />
          ))
        ) : (
          <p className="text-sm text-slate-500 text-center py-4">No activity yet</p>
        )}
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-neon-blue" />
          <h2 className="text-lg font-semibold">Activity</h2>
          {activity.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-neon-blue/20 text-neon-blue font-mono">
              {activity.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!entityId && (
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`p-1.5 rounded-lg transition-colors ${showFilters ? 'bg-neon-purple/20 text-neon-purple' : 'text-slate-500 hover:text-white'}`}
            >
              <Filter className="w-4 h-4" />
            </button>
          )}
          <button
            onClick={fetchActivity}
            className="p-1.5 rounded-lg text-slate-500 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Filters */}
      {showFilters && !entityId && (
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          {/* Type filter */}
          <div className="relative">
            <select
              value={filter.item_type || ''}
              onChange={(e) => setFilter(f => ({ ...f, item_type: e.target.value || null }))}
              className="appearance-none bg-slate-dark border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 pr-7 cursor-pointer hover:border-neon-purple/40 transition-colors"
            >
              <option value="">All types</option>
              <option value="entity">Entities</option>
              <option value="document">Documents</option>
              <option value="relationship">Relationships</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500 pointer-events-none" />
          </div>

          {/* Actor filter */}
          <div className="relative">
            <select
              value={filter.actor || ''}
              onChange={(e) => setFilter(f => ({ ...f, actor: e.target.value || null }))}
              className="appearance-none bg-slate-dark border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-300 pr-7 cursor-pointer hover:border-neon-purple/40 transition-colors"
            >
              <option value="">All actors</option>
              <option value="user">You</option>
              <option value="agent">Agent</option>
              <option value="system">System</option>
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3 h-3 text-slate-500 pointer-events-none" />
          </div>

          {/* Active filters */}
          {(filter.item_type || filter.actor) && (
            <button
              onClick={() => setFilter({ item_type: null, actor: null })}
              className="text-xs text-neon-pink hover:text-neon-pink/80 ml-1"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Activity list */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
          </div>
        ) : activity.length > 0 ? (
          activity.map((entry, idx) => (
            <ActivityEntry
              key={entry.id || idx}
              entry={entry}
              onUndo={handleUndo}
              onItemClick={handleItemClick}
            />
          ))
        ) : (
          <div className="text-center py-12">
            <Clock className="w-12 h-12 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400">No activity recorded yet</p>
            <p className="text-xs text-slate-500 mt-1">Actions on entities, documents, and relationships will appear here</p>
          </div>
        )}
      </div>

      {/* Undoing indicator */}
      {undoing && (
        <div className="absolute inset-0 bg-black/30 flex items-center justify-center rounded-xl">
          <div className="bg-slate-dark rounded-lg p-4 flex items-center gap-3 border border-neon-cyan/30">
            <div className="animate-spin w-5 h-5 border-2 border-neon-cyan border-t-transparent rounded-full" />
            <span className="text-sm text-neon-cyan">Undoing...</span>
          </div>
        </div>
      )}
    </div>
  )
}
