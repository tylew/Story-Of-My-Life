import { useState, useEffect } from 'react'
import { 
  X, Link2, Edit3, Save, Trash2, ArrowRight, ArrowLeft, ArrowLeftRight,
  Calendar, FileText, Tag, Clock, ChevronDown, ChevronUp,
  ExternalLink, Users, Target, Zap, Timer
} from 'lucide-react'

const API_BASE = '/api'

const entityIcons = {
  person: Users,
  project: Target,
  goal: Zap,
  event: Calendar,
  period: Timer,
}

const entityColors = {
  person: { bg: 'bg-neon-cyan/20', text: 'text-neon-cyan', border: 'border-neon-cyan' },
  project: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple' },
  goal: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green' },
  event: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink' },
  period: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500' },
}

// Standard relationship types
const RELATIONSHIP_TYPES = {
  personal: ['friend', 'family', 'partner', 'acquaintance', 'works_with', 'worked_with', 'coworker', 'collaborator', 'mentor', 'mentee', 'professional', 'introduced_by'],
  professional: ['investor', 'advisor', 'client', 'vendor', 'competitor', 'negotiating_with', 'contracted_with'],
  structural: ['part_of', 'depends_on', 'blocks', 'related_to', 'references', 'stakeholder_of', 'during', 'leads_to', 'derived_from'],
}

export default function RelationshipDetail({ 
  relationship, 
  sourceEntity, 
  targetEntity,
  onClose, 
  onSave, 
  onDelete,
  onEntitySelect 
}) {
  const [isEditing, setIsEditing] = useState(false)
  const [editData, setEditData] = useState({
    type: relationship?.type || 'related_to',
    direction: relationship?.direction || 'outgoing',
    context: relationship?.context || '',
    notes: relationship?.notes || '',
    started_at: relationship?.started_at || '',
    ended_at: relationship?.ended_at || '',
  })
  const [saving, setSaving] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave?.({
        ...relationship,
        ...editData,
      })
      setIsEditing(false)
    } catch (e) {
      console.error('Failed to save relationship:', e)
    }
    setSaving(false)
  }

  const handleDelete = async () => {
    if (confirm('Are you sure you want to delete this relationship?')) {
      await onDelete?.(relationship.id)
    }
  }

  const DirectionIcon = ({ direction }) => {
    switch (direction) {
      case 'incoming': return <ArrowLeft className="w-4 h-4" />
      case 'bidirectional': return <ArrowLeftRight className="w-4 h-4" />
      default: return <ArrowRight className="w-4 h-4" />
    }
  }

  const formatRelType = (type) => {
    return type?.replace(/_/g, ' ') || 'related to'
  }

  return (
    <div className="glass neon-border rounded-xl overflow-hidden animate-fade-in">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20 bg-slate-dark/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Link2 className="w-5 h-5 text-neon-purple" />
            <h3 className="font-semibold">Relationship Details</h3>
          </div>
          <div className="flex items-center gap-1">
            <button 
              onClick={() => setIsEditing(!isEditing)}
              className={`p-2 rounded-lg transition-colors ${
                isEditing 
                  ? 'bg-neon-purple/20 text-neon-purple' 
                  : 'hover:bg-slate-dark text-slate-400'
              }`}
            >
              <Edit3 className="w-4 h-4" />
            </button>
            <button 
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
            >
              <X className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        </div>

        {/* Source → Target Display */}
        <div className="flex items-center gap-3 p-3 bg-slate-dark/50 rounded-lg">
          {/* Source Entity */}
          <button 
            onClick={() => onEntitySelect?.(sourceEntity)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neon-cyan/10 hover:bg-neon-cyan/20 transition-colors group"
          >
            {(() => {
              const Icon = entityIcons[sourceEntity?.type] || Users
              return <Icon className="w-4 h-4 text-neon-cyan" />
            })()}
            <span className="text-sm font-medium">{sourceEntity?.name || 'Unknown'}</span>
            <ExternalLink className="w-3 h-3 text-neon-cyan opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>

          {/* Direction & Type */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-neon-purple/10 border border-neon-purple/30">
            <DirectionIcon direction={relationship?.direction} />
            <span className="text-xs font-medium text-neon-purple capitalize">
              {formatRelType(isEditing ? editData.type : relationship?.type)}
            </span>
          </div>

          {/* Target Entity */}
          <button 
            onClick={() => onEntitySelect?.(targetEntity)}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neon-cyan/10 hover:bg-neon-cyan/20 transition-colors group"
          >
            {(() => {
              const Icon = entityIcons[targetEntity?.type] || Target
              return <Icon className="w-4 h-4 text-neon-cyan" />
            })()}
            <span className="text-sm font-medium">{targetEntity?.name || 'Unknown'}</span>
            <ExternalLink className="w-3 h-3 text-neon-cyan opacity-0 group-hover:opacity-100 transition-opacity" />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="p-4 space-y-4">
        {isEditing ? (
          /* Edit Mode */
          <>
            {/* Relationship Type */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Relationship Type</label>
              <select
                value={editData.type}
                onChange={(e) => setEditData({ ...editData, type: e.target.value })}
                className="w-full px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
              >
                <optgroup label="Personal">
                  {RELATIONSHIP_TYPES.personal.map(t => (
                    <option key={t} value={t}>{formatRelType(t)}</option>
                  ))}
                </optgroup>
                <optgroup label="Professional">
                  {RELATIONSHIP_TYPES.professional.map(t => (
                    <option key={t} value={t}>{formatRelType(t)}</option>
                  ))}
                </optgroup>
                <optgroup label="Structural">
                  {RELATIONSHIP_TYPES.structural.map(t => (
                    <option key={t} value={t}>{formatRelType(t)}</option>
                  ))}
                </optgroup>
              </select>
            </div>

            {/* Direction */}
            <div>
              <label className="text-xs text-slate-400 mb-2 block">Direction</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setEditData({ ...editData, direction: 'outgoing' })}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border transition-all ${
                    editData.direction === 'outgoing'
                      ? 'bg-neon-purple/20 border-neon-purple text-neon-purple'
                      : 'bg-slate-dark border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <ArrowRight className="w-4 h-4" />
                  <span className="text-sm">Outgoing</span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditData({ ...editData, direction: 'incoming' })}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border transition-all ${
                    editData.direction === 'incoming'
                      ? 'bg-neon-purple/20 border-neon-purple text-neon-purple'
                      : 'bg-slate-dark border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <ArrowLeft className="w-4 h-4" />
                  <span className="text-sm">Incoming</span>
                </button>
                <button
                  type="button"
                  onClick={() => setEditData({ ...editData, direction: 'bidirectional' })}
                  className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border transition-all ${
                    editData.direction === 'bidirectional'
                      ? 'bg-neon-purple/20 border-neon-purple text-neon-purple'
                      : 'bg-slate-dark border-slate-700 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  <ArrowLeftRight className="w-4 h-4" />
                  <span className="text-sm">Both</span>
                </button>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                {editData.direction === 'outgoing' && `${sourceEntity?.name} → ${targetEntity?.name}`}
                {editData.direction === 'incoming' && `${sourceEntity?.name} ← ${targetEntity?.name}`}
                {editData.direction === 'bidirectional' && `${sourceEntity?.name} ↔ ${targetEntity?.name}`}
              </p>
            </div>

            {/* Context */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Context</label>
              <input
                type="text"
                value={editData.context}
                onChange={(e) => setEditData({ ...editData, context: e.target.value })}
                placeholder="How/why this relationship exists..."
                className="w-full px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
              />
            </div>

            {/* Notes */}
            <div>
              <label className="text-xs text-slate-400 mb-1 block">Notes</label>
              <textarea
                value={editData.notes}
                onChange={(e) => setEditData({ ...editData, notes: e.target.value })}
                placeholder="Additional notes about this relationship..."
                rows={2}
                className="w-full px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors resize-none"
              />
            </div>

            {/* Advanced Options */}
            <div>
              <button 
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="flex items-center gap-2 text-xs text-slate-400 hover:text-slate-300"
              >
                {showAdvanced ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                Advanced Options
              </button>
              
              {showAdvanced && (
                <div className="mt-3 space-y-3 pl-3 border-l-2 border-slate-700">
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Started At</label>
                    <input
                      type="date"
                      value={editData.started_at?.split('T')[0] || ''}
                      onChange={(e) => setEditData({ ...editData, started_at: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Ended At</label>
                    <input
                      type="date"
                      value={editData.ended_at?.split('T')[0] || ''}
                      onChange={(e) => setEditData({ ...editData, ended_at: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-2 pt-2 border-t border-slate-700">
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-neon-green/20 text-neon-green hover:bg-neon-green/30 transition-colors"
              >
                <Save className="w-4 h-4" />
                Save Changes
              </button>
              <button
                onClick={handleDelete}
                className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          </>
        ) : (
          /* View Mode */
          <>
            {/* Direction Display */}
            <div className="p-3 rounded-lg bg-slate-dark/50 flex items-center justify-center gap-3">
              <span className="text-sm text-slate-300">{sourceEntity?.name}</span>
              <div className="flex items-center gap-1 px-2 py-1 rounded bg-neon-purple/20">
                {(relationship?.direction || 'outgoing') === 'outgoing' && (
                  <>
                    <ArrowRight className="w-4 h-4 text-neon-purple" />
                    <span className="text-xs text-neon-purple">outgoing</span>
                  </>
                )}
                {relationship?.direction === 'incoming' && (
                  <>
                    <ArrowLeft className="w-4 h-4 text-neon-purple" />
                    <span className="text-xs text-neon-purple">incoming</span>
                  </>
                )}
                {relationship?.direction === 'bidirectional' && (
                  <>
                    <ArrowLeftRight className="w-4 h-4 text-neon-purple" />
                    <span className="text-xs text-neon-purple">bidirectional</span>
                  </>
                )}
              </div>
              <span className="text-sm text-slate-300">{targetEntity?.name}</span>
            </div>

            {/* Context & Notes */}
            {(relationship?.context || relationship?.notes) && (
              <div className="space-y-3">
                {relationship?.context && (
                  <div className="p-3 rounded-lg bg-slate-dark/50">
                    <div className="flex items-center gap-1 mb-1">
                      <Tag className="w-3 h-3 text-slate-400" />
                      <span className="text-xs text-slate-400">Context</span>
                    </div>
                    <p className="text-sm text-slate-300">{relationship.context}</p>
                  </div>
                )}
                {relationship?.notes && (
                  <div className="p-3 rounded-lg bg-slate-dark/50">
                    <div className="flex items-center gap-1 mb-1">
                      <FileText className="w-3 h-3 text-slate-400" />
                      <span className="text-xs text-slate-400">Notes</span>
                    </div>
                    <p className="text-sm text-slate-300">{relationship.notes}</p>
                  </div>
                )}
              </div>
            )}

            {/* Metadata */}
            <div className="pt-3 border-t border-slate-700/50 space-y-1">
              {relationship?.created_at && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Created</span>
                  <span className="text-slate-400 font-mono">
                    {new Date(relationship.created_at).toLocaleDateString()}
                  </span>
                </div>
              )}
              {relationship?.started_at && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Started</span>
                  <span className="text-slate-400 font-mono">
                    {new Date(relationship.started_at).toLocaleDateString()}
                  </span>
                </div>
              )}
              {relationship?.ended_at && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Ended</span>
                  <span className="text-slate-400 font-mono">
                    {new Date(relationship.ended_at).toLocaleDateString()}
                  </span>
                </div>
              )}
              {relationship?.source && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">Source</span>
                  <span className="text-slate-400 capitalize">{relationship.source}</span>
                </div>
              )}
              {relationship?.id && (
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-500">ID</span>
                  <span className="text-slate-400 font-mono">{relationship.id.slice(0, 8)}...</span>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}

// Compact view for lists
export function RelationshipRow({ relationship, onSelect, onEntitySelect }) {
  const formatRelType = (type) => type?.replace(/_/g, ' ') || 'related to'
  
  return (
    <button
      onClick={() => onSelect?.(relationship)}
      className="w-full flex items-center gap-3 p-3 rounded-lg bg-slate-dark/30 hover:bg-slate-dark/50 border border-slate-700/50 hover:border-neon-purple/40 transition-all group"
    >
      <div className="w-8 h-8 rounded-lg bg-neon-purple/10 flex items-center justify-center">
        <Link2 className="w-4 h-4 text-neon-purple" />
      </div>
      
      <div className="flex-1 min-w-0 text-left">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium truncate">
            {relationship.other_entity_name || 'Unknown'}
          </span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-neon-purple/20 text-neon-purple capitalize">
            {formatRelType(relationship.type)}
          </span>
        </div>
        {relationship.context && (
          <p className="text-xs text-slate-500 truncate">{relationship.context}</p>
        )}
      </div>

      <ExternalLink className="w-4 h-4 text-slate-500 group-hover:text-neon-purple transition-colors" />
    </button>
  )
}

