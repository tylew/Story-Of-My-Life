import { useState, useEffect } from 'react'
import { AlertCircle, Bell, CheckCircle, Clock, RefreshCw, ChevronRight, Zap, Users, Target } from 'lucide-react'

const API_BASE = '/api'

export default function OpenLoops({ onEntitySelect, refreshKey }) {
  const [loops, setLoops] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchLoops()
  }, [refreshKey])

  const fetchLoops = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/open-loops`)
      const data = await res.json()
      setLoops(data.loops || [])
    } catch (e) {
      console.error('Failed to fetch open loops:', e)
    }
    setLoading(false)
  }

  const getLoopIcon = (type) => {
    const icons = {
      relationship: Users,
      project: Target,
      goal: Zap,
      followup: Clock,
    }
    return icons[type] || Bell
  }

  const getUrgencyColor = (urgency) => {
    if (urgency >= 80) return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/40' }
    if (urgency >= 50) return { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink/40' }
    return { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/40' }
  }

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-slate-700/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-neon-pink/20 flex items-center justify-center">
              <Bell className="w-5 h-5 text-neon-pink" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold">Open Loops</h1>
              <p className="text-sm text-slate-400">{loops.length} items need attention</p>
            </div>
          </div>
          <button
            onClick={fetchLoops}
            className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
          >
            <RefreshCw className="w-5 h-5 text-neon-purple" />
          </button>
        </div>

        {/* Summary Stats */}
        <div className="flex gap-4">
          <div className="flex-1 glass neon-border rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-neon-pink font-mono">{loops.filter(l => l.urgency >= 80).length}</p>
            <p className="text-xs text-slate-400">High Priority</p>
          </div>
          <div className="flex-1 glass neon-border rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-yellow-400 font-mono">{loops.filter(l => l.urgency >= 50 && l.urgency < 80).length}</p>
            <p className="text-xs text-slate-400">Medium Priority</p>
          </div>
          <div className="flex-1 glass neon-border rounded-lg p-3 text-center">
            <p className="text-2xl font-bold text-neon-green font-mono">{loops.filter(l => l.urgency < 50).length}</p>
            <p className="text-xs text-slate-400">Low Priority</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {loops.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-20 h-20 rounded-full bg-neon-green/10 flex items-center justify-center mx-auto mb-4">
              <CheckCircle className="w-10 h-10 text-neon-green" />
            </div>
            <h2 className="text-xl font-semibold text-neon-green mb-2">All Caught Up!</h2>
            <p className="text-slate-400">No open loops requiring attention</p>
            <p className="text-sm text-slate-500 mt-1">Keep adding notes and events to track progress</p>
          </div>
        ) : (
          <div className="space-y-4">
            {loops.map((loop, idx) => {
              const Icon = getLoopIcon(loop.type)
              const urgencyColors = getUrgencyColor(loop.urgency || 0)
              
              return (
                <button
                  key={idx}
                  onClick={() => loop.entity && onEntitySelect?.(loop.entity)}
                  className={`w-full text-left glass rounded-xl p-5 border ${urgencyColors.border} hover:border-neon-purple/60 transition-all animate-fade-in`}
                  style={{ animationDelay: `${idx * 100}ms` }}
                >
                  <div className="flex items-start gap-4">
                    <div className={`w-12 h-12 rounded-xl ${urgencyColors.bg} flex items-center justify-center flex-shrink-0`}>
                      <Icon className={`w-6 h-6 ${urgencyColors.text}`} />
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-2">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-mono ${urgencyColors.bg} ${urgencyColors.text} capitalize`}>
                          {loop.type || 'reminder'}
                        </span>
                        {loop.urgency > 0 && (
                          <span className={`text-xs font-mono ${urgencyColors.text}`}>
                            {loop.urgency}% urgent
                          </span>
                        )}
                      </div>
                      
                      <p className="text-lg font-medium mb-2">{loop.prompt}</p>
                      
                      {loop.entity && (
                        <div className="flex items-center gap-2 text-sm text-slate-400">
                          <span>Related:</span>
                          <span className="text-neon-cyan">{loop.entity.name || loop.entity.title}</span>
                        </div>
                      )}
                      
                      {loop.last_activity && (
                        <p className="text-xs text-slate-500 mt-2 font-mono">
                          Last activity: {new Date(loop.last_activity).toLocaleDateString()}
                        </p>
                      )}
                    </div>
                    
                    <ChevronRight className="w-5 h-5 text-slate-500 flex-shrink-0" />
                  </div>

                  {/* Urgency bar */}
                  {loop.urgency > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-700/50">
                      <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
                        <span>Urgency</span>
                        <span className="font-mono">{loop.urgency}%</span>
                      </div>
                      <div className="w-full h-2 rounded-full bg-slate-700 overflow-hidden">
                        <div 
                          className={`h-full transition-all ${
                            loop.urgency >= 80 ? 'bg-red-500' :
                            loop.urgency >= 50 ? 'bg-neon-pink' :
                            'bg-yellow-500'
                          }`}
                          style={{ width: `${loop.urgency}%` }}
                        />
                      </div>
                    </div>
                  )}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

