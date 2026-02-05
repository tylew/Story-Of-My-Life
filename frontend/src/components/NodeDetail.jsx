import { useState, useEffect } from 'react'
import { X, Link2, Calendar, Tag, User, Target, Zap, FileText } from 'lucide-react'

const API_BASE = '/api'

const typeIcons = {
  person: User,
  project: Target,
  goal: Zap,
  event: Calendar,
  note: FileText,
}

const typeColors = {
  person: 'neon-cyan',
  project: 'neon-purple',
  goal: 'neon-green',
  event: 'neon-pink',
  note: 'neon-blue',
}

export default function NodeDetail({ node, onClose }) {
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (node?.id) {
      fetchDetails()
    }
  }, [node?.id])

  const fetchDetails = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/graph/node/${node.id}`)
      if (res.ok) {
        const data = await res.json()
        setDetails(data)
      }
    } catch (e) {
      console.error('Failed to fetch node details:', e)
    }
    setLoading(false)
  }

  const Icon = typeIcons[node?.type] || FileText
  const color = typeColors[node?.type] || 'neon-blue'

  return (
    <div className="flex flex-col h-full bg-obsidian">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20 flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl bg-${color}/20 flex items-center justify-center`}>
            <Icon className={`w-5 h-5 text-${color}`} />
          </div>
          <div>
            <h2 className="font-semibold text-lg">{node?.label || 'Unknown'}</h2>
            <span className={`text-xs font-mono text-${color} capitalize`}>{node?.type}</span>
          </div>
        </div>
        <button 
          onClick={onClose}
          className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
        >
          <X className="w-5 h-5 text-slate-400" />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
          </div>
        ) : details ? (
          <div className="space-y-6">
            {/* Metadata */}
            <section>
              <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                <Tag className="w-4 h-4" />
                Metadata
              </h3>
              <div className="glass neon-border rounded-xl p-4 space-y-2">
                {details.metadata?.created_at && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Created</span>
                    <span className="font-mono text-slate-300">
                      {new Date(details.metadata.created_at).toLocaleDateString()}
                    </span>
                  </div>
                )}
                {details.metadata?.confidence && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Confidence</span>
                    <span className="font-mono text-slate-300">
                      {Math.round(details.metadata.confidence * 100)}%
                    </span>
                  </div>
                )}
                {details.metadata?.disambiguator && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Context</span>
                    <span className="text-slate-300 text-right max-w-[60%]">
                      {details.metadata.disambiguator}
                    </span>
                  </div>
                )}
                {details.metadata?.source && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Source</span>
                    <span className="font-mono text-slate-300 capitalize">
                      {details.metadata.source}
                    </span>
                  </div>
                )}
              </div>
            </section>

            {/* Content */}
            {details.content && (
              <section>
                <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <FileText className="w-4 h-4" />
                  Content
                </h3>
                <div className="glass neon-border rounded-xl p-4">
                  <div className="prose prose-sm prose-invert max-w-none">
                    <div className="text-sm text-slate-300 whitespace-pre-wrap leading-relaxed">
                      {details.content}
                    </div>
                  </div>
                </div>
              </section>
            )}

            {/* Relationships */}
            {details.relationships && details.relationships.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
                  <Link2 className="w-4 h-4" />
                  Relationships ({details.relationships.length})
                </h3>
                <div className="space-y-2">
                  {details.relationships.map((rel, idx) => (
                    <div 
                      key={idx}
                      className="glass neon-border rounded-lg p-3 flex items-center justify-between"
                    >
                      <div>
                        <span className="text-sm font-medium text-slate-300">
                          {rel.other_name || 'Unknown'}
                        </span>
                        <span className="text-xs text-slate-500 ml-2">
                          ({rel.type || 'related'})
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 font-mono">
                        {rel.category || ''}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {/* Tags */}
            {details.metadata?.tags && details.metadata.tags.length > 0 && (
              <section>
                <h3 className="text-sm font-semibold text-slate-300 mb-3">Tags</h3>
                <div className="flex flex-wrap gap-2">
                  {details.metadata.tags.map((tag, idx) => (
                    <span 
                      key={idx}
                      className="px-2 py-1 rounded-full text-xs bg-neon-purple/20 text-neon-purple border border-neon-purple/30"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </section>
            )}
          </div>
        ) : (
          <p className="text-slate-400 text-center py-8">
            No details available
          </p>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-neon-purple/20">
        <p className="text-xs text-slate-500 font-mono text-center truncate">
          ID: {node?.id}
        </p>
      </div>
    </div>
  )
}

