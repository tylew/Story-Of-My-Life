import { useState } from 'react'
import { 
  Check, Users, Target, Zap, Calendar, Timer, Link2, FileText,
  ChevronDown, ChevronUp, ExternalLink, ArrowRight, Edit3
} from 'lucide-react'

const entityIcons = {
  person: Users,
  project: Target,
  goal: Zap,
  event: Calendar,
  period: Timer,
  document: FileText,
}

const entityColors = {
  person: { bg: 'bg-neon-cyan/20', text: 'text-neon-cyan', border: 'border-neon-cyan', glow: 'shadow-neon-cyan/20' },
  project: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple', glow: 'shadow-neon-purple/20' },
  goal: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green', glow: 'shadow-neon-green/20' },
  event: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink', glow: 'shadow-neon-pink/20' },
  period: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500', glow: 'shadow-amber-500/20' },
  document: { bg: 'bg-neon-blue/20', text: 'text-neon-blue', border: 'border-neon-blue', glow: 'shadow-neon-blue/20' },
}

/**
 * ChangeSummary displays the results of a proposal execution with
 * clickable entity and relationship blocks that open detail views.
 */
export default function ChangeSummary({ 
  createdEntities = [], 
  linkedEntities = [], 
  createdRelationships = [],
  updatedDocuments = [],
  errors = [],
  onEntitySelect,
  onRelationshipSelect,
  expanded: defaultExpanded = true 
}) {
  const [expanded, setExpanded] = useState(defaultExpanded)
  
  const hasContent = createdEntities.length > 0 || 
                     linkedEntities.length > 0 || 
                     createdRelationships.length > 0 ||
                     updatedDocuments.length > 0

  if (!hasContent && errors.length === 0) {
    return null
  }

  return (
    <div className="mt-4 rounded-xl border border-neon-green/30 overflow-hidden animate-fade-in">
      {/* Summary Header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-3 bg-neon-green/10 hover:bg-neon-green/15 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Check className="w-4 h-4 text-neon-green" />
          <span className="font-medium text-sm text-neon-green">Changes Applied</span>
          <div className="flex items-center gap-1 ml-2">
            {createdEntities.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-neon-cyan/20 text-neon-cyan">
                {createdEntities.length} created
              </span>
            )}
            {linkedEntities.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-neon-blue/20 text-neon-blue">
                {linkedEntities.length} linked
              </span>
            )}
            {createdRelationships.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs bg-neon-purple/20 text-neon-purple">
                {createdRelationships.length} relationships
              </span>
            )}
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="w-4 h-4 text-slate-400" />
        ) : (
          <ChevronDown className="w-4 h-4 text-slate-400" />
        )}
      </button>

      {/* Expanded Content */}
      {expanded && (
        <div className="p-4 bg-slate-dark/30 space-y-4">
          {/* Created Entities */}
          {createdEntities.length > 0 && (
            <Section title="Created Entities" icon={<Check className="w-3 h-3 text-neon-green" />}>
              <div className="flex flex-wrap gap-2">
                {createdEntities.map((entity, idx) => (
                  <EntityBlock 
                    key={idx} 
                    entity={entity} 
                    action="created"
                    onClick={() => onEntitySelect?.(entity)}
                  />
                ))}
              </div>
            </Section>
          )}

          {/* Linked Entities */}
          {linkedEntities.length > 0 && (
            <Section title="Linked to Existing" icon={<Link2 className="w-3 h-3 text-neon-blue" />}>
              <div className="flex flex-wrap gap-2">
                {linkedEntities.map((entity, idx) => (
                  <EntityBlock 
                    key={idx} 
                    entity={{
                      id: entity.entity_id,
                      name: entity.mention,
                      type: entity.type,
                      ...entity,
                    }} 
                    action="linked"
                    onClick={() => onEntitySelect?.({ 
                      id: entity.entity_id, 
                      name: entity.mention, 
                      type: entity.type 
                    })}
                  />
                ))}
              </div>
            </Section>
          )}

          {/* Relationships */}
          {createdRelationships.length > 0 && (
            <Section title="Relationships" icon={<Link2 className="w-3 h-3 text-neon-purple" />}>
              <div className="space-y-2">
                {createdRelationships.map((rel, idx) => (
                  <RelationshipBlock 
                    key={idx} 
                    relationship={rel}
                    onSourceClick={() => onEntitySelect?.({ id: rel.source_id, name: rel.source_name })}
                    onTargetClick={() => onEntitySelect?.({ id: rel.target_id, name: rel.target_name })}
                    onRelationshipClick={() => onRelationshipSelect?.(rel)}
                  />
                ))}
              </div>
            </Section>
          )}

          {/* Updated Documents */}
          {updatedDocuments.length > 0 && (
            <Section title="Documents Updated" icon={<FileText className="w-3 h-3 text-neon-green" />}>
              <div className="flex flex-wrap gap-2">
                {updatedDocuments.map((doc, idx) => (
                  <button
                    key={idx}
                    onClick={() => onEntitySelect?.({ id: doc.entity_id, name: doc.entity_name, type: doc.entity_type })}
                    className="flex items-center gap-2 px-3 py-2 rounded-lg bg-neon-green/10 border border-neon-green/30 hover:border-neon-green/50 transition-all group"
                  >
                    <FileText className="w-4 h-4 text-neon-green" />
                    <span className="text-sm font-medium text-neon-green">{doc.entity_name}</span>
                    <span className="text-xs text-slate-500">({doc.action})</span>
                    <ExternalLink className="w-3 h-3 text-neon-green opacity-0 group-hover:opacity-100 transition-opacity" />
                  </button>
                ))}
              </div>
            </Section>
          )}

          {/* Errors */}
          {errors.length > 0 && (
            <Section title="Issues" icon={<span className="text-xs">⚠️</span>}>
              <div className="space-y-1">
                {errors.map((error, idx) => (
                  <p key={idx} className="text-sm text-amber-400">{error}</p>
                ))}
              </div>
            </Section>
          )}
        </div>
      )}
    </div>
  )
}

function Section({ title, icon, children }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</h4>
      </div>
      {children}
    </div>
  )
}

function EntityBlock({ entity, action, onClick }) {
  const type = entity?.type || 'event'
  const colors = entityColors[type] || entityColors.event
  const Icon = entityIcons[type] || Calendar
  
  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-3 py-2 rounded-lg 
        ${colors.bg} border ${colors.border}/30 
        hover:${colors.border}/60 hover:shadow-lg hover:${colors.glow}
        transition-all cursor-pointer group
      `}
    >
      <div className={`w-6 h-6 rounded-md ${colors.bg} flex items-center justify-center`}>
        <Icon className={`w-3.5 h-3.5 ${colors.text}`} />
      </div>
      <div className="text-left">
        <span className={`text-sm font-medium ${colors.text}`}>{entity?.name || 'Unknown'}</span>
        <span className="text-xs text-slate-500 ml-2 capitalize">({type})</span>
      </div>
      <ExternalLink className={`w-3.5 h-3.5 ${colors.text} opacity-0 group-hover:opacity-100 transition-opacity`} />
    </button>
  )
}

function RelationshipBlock({ relationship, onSourceClick, onTargetClick, onRelationshipClick }) {
  const formatRelType = (type) => type?.replace(/_/g, ' ') || 'related to'
  
  return (
    <div className="flex items-center gap-2 p-3 rounded-lg bg-slate-dark/50 border border-slate-700/50 hover:border-neon-purple/40 transition-all group">
      {/* Source */}
      <button
        onClick={(e) => { e.stopPropagation(); onSourceClick?.() }}
        className="flex items-center gap-2 px-2 py-1 rounded-md bg-neon-cyan/10 hover:bg-neon-cyan/20 transition-colors"
      >
        <Users className="w-3.5 h-3.5 text-neon-cyan" />
        <span className="text-sm font-medium text-neon-cyan truncate max-w-[100px]">
          {relationship.source_name || relationship.source_id?.slice(0, 8)}
        </span>
        <ExternalLink className="w-3 h-3 text-neon-cyan opacity-0 group-hover:opacity-70 transition-opacity" />
      </button>

      {/* Relationship Type (clickable) */}
      <button
        onClick={(e) => { e.stopPropagation(); onRelationshipClick?.() }}
        className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-neon-purple/10 border border-neon-purple/30 hover:border-neon-purple/60 hover:bg-neon-purple/20 transition-all"
      >
        <ArrowRight className="w-3 h-3 text-neon-purple" />
        <span className="text-xs font-medium text-neon-purple capitalize">
          {formatRelType(relationship.type)}
        </span>
        <Edit3 className="w-3 h-3 text-neon-purple opacity-0 group-hover:opacity-70 transition-opacity" />
      </button>

      {/* Target */}
      <button
        onClick={(e) => { e.stopPropagation(); onTargetClick?.() }}
        className="flex items-center gap-2 px-2 py-1 rounded-md bg-neon-cyan/10 hover:bg-neon-cyan/20 transition-colors"
      >
        <Target className="w-3.5 h-3.5 text-neon-cyan" />
        <span className="text-sm font-medium text-neon-cyan truncate max-w-[100px]">
          {relationship.target_name || relationship.target_id?.slice(0, 8)}
        </span>
        <ExternalLink className="w-3 h-3 text-neon-cyan opacity-0 group-hover:opacity-70 transition-opacity" />
      </button>

      {/* Direction indicator */}
      {relationship.direction && relationship.direction !== 'outgoing' && (
        <span className="text-xs text-slate-500 ml-auto">
          {relationship.direction === 'bidirectional' ? '↔' : '←'}
        </span>
      )}
    </div>
  )
}

/**
 * Inline citation block for use in text responses.
 * Appears as a small clickable chip that opens the entity view.
 */
export function EntityCitation({ entity, onClick }) {
  const type = entity?.type || 'event'
  const colors = entityColors[type] || entityColors.event
  const Icon = entityIcons[type] || Calendar
  
  return (
    <button
      onClick={onClick}
      className={`
        inline-flex items-center gap-1.5 px-2 py-1 mx-0.5 rounded-md
        ${colors.bg} border ${colors.border}/30 
        hover:${colors.border}/60 
        transition-all cursor-pointer group text-sm
      `}
    >
      <Icon className={`w-3 h-3 ${colors.text}`} />
      <span className={`font-medium ${colors.text}`}>{entity?.name || 'Unknown'}</span>
      <ExternalLink className={`w-2.5 h-2.5 ${colors.text} opacity-0 group-hover:opacity-100 transition-opacity`} />
    </button>
  )
}

/**
 * Relationship citation for inline use.
 */
export function RelationshipCitation({ sourceEntity, targetEntity, relationType, onClick }) {
  const formatRelType = (type) => type?.replace(/_/g, ' ') || 'related to'
  
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-1 mx-0.5 rounded-md bg-neon-purple/10 border border-neon-purple/30 hover:border-neon-purple/60 transition-all cursor-pointer group text-sm"
    >
      <span className="text-neon-cyan">{sourceEntity?.name}</span>
      <ArrowRight className="w-3 h-3 text-neon-purple" />
      <span className="text-xs text-neon-purple">{formatRelType(relationType)}</span>
      <ArrowRight className="w-3 h-3 text-neon-purple" />
      <span className="text-neon-cyan">{targetEntity?.name}</span>
      <Edit3 className="w-2.5 h-2.5 text-neon-purple opacity-0 group-hover:opacity-100 transition-opacity" />
    </button>
  )
}

