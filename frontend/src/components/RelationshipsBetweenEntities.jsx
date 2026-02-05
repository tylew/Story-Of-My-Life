import { useState, useEffect } from 'react'
import { 
  X, Link2, Plus, ArrowRight, ArrowLeft, ArrowLeftRight,
  Users, Target, Zap, Calendar, Timer, ExternalLink, Loader2,
  ChevronLeft
} from 'lucide-react'
import RelationshipDetail, { RelationshipRow } from './RelationshipDetail'

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

export default function RelationshipsBetweenEntities({ 
  sourceEntity, 
  targetEntity, 
  onClose, 
  onEntitySelect,
  onRefresh 
}) {
  const [relationships, setRelationships] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedRelationship, setSelectedRelationship] = useState(null)
  const [creating, setCreating] = useState(false)
  const [newRelType, setNewRelType] = useState('related_to')
  const [newRelDirection, setNewRelDirection] = useState('outgoing')

  useEffect(() => {
    if (sourceEntity?.id && targetEntity?.id) {
      fetchRelationships()
    }
  }, [sourceEntity?.id, targetEntity?.id])

  const fetchRelationships = async () => {
    setLoading(true)
    try {
      const res = await fetch(
        `${API_BASE}/relationships/between?source_id=${sourceEntity.id}&target_id=${targetEntity.id}`
      )
      if (res.ok) {
        const data = await res.json()
        setRelationships(data.relationships || [])
      }
    } catch (e) {
      console.error('Failed to fetch relationships:', e)
    }
    setLoading(false)
  }

  const handleSaveRelationship = async (updatedRel) => {
    try {
      const res = await fetch(`${API_BASE}/relationships/${updatedRel.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updatedRel),
      })
      if (res.ok) {
        fetchRelationships()
        setSelectedRelationship(null)
        onRefresh?.()
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
        setRelationships(rels => rels.filter(r => r.id !== relId))
        setSelectedRelationship(null)
        onRefresh?.()
      }
    } catch (e) {
      console.error('Failed to delete relationship:', e)
    }
  }

  const handleCreateRelationship = async () => {
    setCreating(true)
    try {
      const res = await fetch(`${API_BASE}/relationships`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_id: sourceEntity.id,
          target_id: targetEntity.id,
          relationship_type: newRelType,
          direction: newRelDirection,
          allow_multiple: true,
        }),
      })
      if (res.ok) {
        fetchRelationships()
        setNewRelType('related_to')
        setNewRelDirection('outgoing')
        onRefresh?.()
      }
    } catch (e) {
      console.error('Failed to create relationship:', e)
    }
    setCreating(false)
  }

  const SourceIcon = entityIcons[sourceEntity?.type] || Users
  const TargetIcon = entityIcons[targetEntity?.type] || Target
  const sourceColors = entityColors[sourceEntity?.type] || entityColors.person
  const targetColors = entityColors[targetEntity?.type] || entityColors.person
  
  // Normalize names (graph uses 'label', components use 'name')
  const sourceName = sourceEntity?.name || sourceEntity?.label || 'Unknown'
  const targetName = targetEntity?.name || targetEntity?.label || 'Unknown'

  return (
    <div className="w-[450px] border-l border-neon-purple/20 flex flex-col bg-obsidian h-full animate-slide-in">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-neon-purple/20 flex items-center justify-center">
              <Link2 className="w-6 h-6 text-neon-purple" />
            </div>
            <div>
              <h2 className="font-semibold text-lg">Relationships</h2>
              <p className="text-xs text-slate-400">
                {relationships.length} connection{relationships.length !== 1 ? 's' : ''} between entities
              </p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
          >
            <X className="w-5 h-5 text-slate-400" />
          </button>
        </div>

        {/* Entity Cards - Compact */}
        <div className="flex items-center gap-2">
          <button
            onClick={() => onEntitySelect?.(sourceEntity)}
            className={`flex-1 flex items-center gap-2 p-2 rounded-lg ${sourceColors.bg} border ${sourceColors.border}/30 hover:${sourceColors.border}/60 transition-colors group`}
          >
            <SourceIcon className={`w-4 h-4 ${sourceColors.text}`} />
            <span className={`text-sm font-medium ${sourceColors.text} truncate`}>{sourceName}</span>
            <ExternalLink className={`w-3 h-3 ${sourceColors.text} opacity-0 group-hover:opacity-100 transition-opacity ml-auto`} />
          </button>

          <div className="flex flex-col items-center px-1">
            <ArrowLeftRight className="w-4 h-4 text-neon-purple" />
          </div>

          <button
            onClick={() => onEntitySelect?.(targetEntity)}
            className={`flex-1 flex items-center gap-2 p-2 rounded-lg ${targetColors.bg} border ${targetColors.border}/30 hover:${targetColors.border}/60 transition-colors group`}
          >
            <TargetIcon className={`w-4 h-4 ${targetColors.text}`} />
            <span className={`text-sm font-medium ${targetColors.text} truncate`}>{targetName}</span>
            <ExternalLink className={`w-3 h-3 ${targetColors.text} opacity-0 group-hover:opacity-100 transition-opacity ml-auto`} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-6 h-6 text-neon-purple animate-spin" />
            <span className="ml-3 text-slate-400">Loading...</span>
          </div>
        ) : selectedRelationship ? (
          <div className="p-4">
            <button
              onClick={() => setSelectedRelationship(null)}
              className="flex items-center gap-1 text-sm text-slate-400 hover:text-white mb-4 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
              Back to list
            </button>
            <RelationshipDetail
              relationship={selectedRelationship}
              sourceEntity={sourceEntity}
              targetEntity={targetEntity}
              onClose={() => setSelectedRelationship(null)}
              onSave={handleSaveRelationship}
              onDelete={handleDeleteRelationship}
              onEntitySelect={onEntitySelect}
            />
          </div>
        ) : (
          <div className="p-4 space-y-4">
            {/* Relationship List */}
            {relationships.length > 0 ? (
              <div className="space-y-2">
                {relationships.map((rel) => (
                  <RelationshipRow
                    key={rel.id}
                    relationship={{
                      ...rel,
                      other_entity_name: rel.target_id === sourceEntity?.id 
                        ? (sourceEntity?.name || sourceEntity?.label || 'Unknown')
                        : (targetEntity?.name || targetEntity?.label || 'Unknown'),
                    }}
                    onSelect={() => setSelectedRelationship(rel)}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <div className="w-14 h-14 rounded-xl bg-slate-dark flex items-center justify-center mx-auto mb-3">
                  <Link2 className="w-7 h-7 text-slate-500" />
                </div>
                <p className="text-slate-400 text-sm">No relationships yet</p>
                <p className="text-xs text-slate-500 mt-1">Add one below</p>
              </div>
            )}

            {/* Add New Relationship */}
            <div className="pt-4 border-t border-slate-700">
              <h4 className="text-sm font-medium text-slate-300 mb-3 flex items-center gap-2">
                <Plus className="w-4 h-4" />
                Add New Relationship
              </h4>
              
              {/* Type Selection */}
              <div className="mb-3">
                <label className="text-xs text-slate-400 mb-1 block">Type</label>
                <select
                  value={newRelType}
                  onChange={(e) => setNewRelType(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
                >
                  <optgroup label="Personal">
                    <option value="friend">Friend</option>
                    <option value="family">Family</option>
                    <option value="collaborator">Collaborator</option>
                    <option value="mentor">Mentor</option>
                    <option value="mentee">Mentee</option>
                    <option value="works_with">Works With</option>
                  </optgroup>
                  <optgroup label="Professional">
                    <option value="investor">Investor</option>
                    <option value="advisor">Advisor</option>
                    <option value="client">Client</option>
                    <option value="negotiating_with">Negotiating With</option>
                  </optgroup>
                  <optgroup label="Structural">
                    <option value="related_to">Related To</option>
                    <option value="part_of">Part Of</option>
                    <option value="depends_on">Depends On</option>
                    <option value="stakeholder_of">Stakeholder Of</option>
                  </optgroup>
                </select>
              </div>
              
              {/* Direction Selection */}
              <div className="mb-3">
                <label className="text-xs text-slate-400 mb-2 block">Direction</label>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => setNewRelDirection('outgoing')}
                    className={`flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg border text-xs transition-all ${
                      newRelDirection === 'outgoing'
                        ? 'bg-neon-purple/20 border-neon-purple text-neon-purple'
                        : 'bg-slate-dark border-slate-700 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    <ArrowRight className="w-3 h-3" />
                    Out
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewRelDirection('incoming')}
                    className={`flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg border text-xs transition-all ${
                      newRelDirection === 'incoming'
                        ? 'bg-neon-purple/20 border-neon-purple text-neon-purple'
                        : 'bg-slate-dark border-slate-700 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    <ArrowLeft className="w-3 h-3" />
                    In
                  </button>
                  <button
                    type="button"
                    onClick={() => setNewRelDirection('bidirectional')}
                    className={`flex-1 flex items-center justify-center gap-1 px-2 py-1.5 rounded-lg border text-xs transition-all ${
                      newRelDirection === 'bidirectional'
                        ? 'bg-neon-purple/20 border-neon-purple text-neon-purple'
                        : 'bg-slate-dark border-slate-700 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    <ArrowLeftRight className="w-3 h-3" />
                    Both
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 mt-1 text-center">
                  {newRelDirection === 'outgoing' && `${sourceName} → ${targetName}`}
                  {newRelDirection === 'incoming' && `${sourceName} ← ${targetName}`}
                  {newRelDirection === 'bidirectional' && `${sourceName} ↔ ${targetName}`}
                </p>
              </div>
              
              {/* Create Button */}
              <button
                onClick={handleCreateRelationship}
                disabled={creating}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-neon-purple/20 text-neon-purple hover:bg-neon-purple/30 transition-colors disabled:opacity-50 text-sm"
              >
                {creating ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Plus className="w-4 h-4" />
                )}
                Create Relationship
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-neon-purple/20 bg-slate-dark/50">
        <button
          onClick={onClose}
          className="w-full px-4 py-2 rounded-lg bg-neon-purple/20 text-neon-purple text-sm font-medium hover:bg-neon-purple/30 transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  )
}
