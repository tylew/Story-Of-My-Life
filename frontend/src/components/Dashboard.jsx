import { useState, useEffect } from 'react'
import { Users, Target, Zap, Calendar, TrendingUp, Clock, AlertCircle, RefreshCw } from 'lucide-react'
import ActivityFeed from './ActivityFeed'

const API_BASE = '/api'

export default function Dashboard({ status, onEntitySelect, onDocumentSelect, onRefresh, onNavigate }) {
  const [openLoops, setOpenLoops] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    setLoading(true)
    try {
      const loopsRes = await fetch(`${API_BASE}/open-loops`)
      const loopsData = await loopsRes.json()
      setOpenLoops(loopsData.loops?.slice(0, 3) || [])
    } catch (e) {
      console.error('Failed to fetch dashboard data:', e)
    }
    setLoading(false)
  }

  const stats = [
    { label: 'People', count: status?.counts?.person || 0, icon: Users, color: 'cyan', type: 'people' },
    { label: 'Projects', count: status?.counts?.project || 0, icon: Target, color: 'purple', type: 'projects' },
    { label: 'Goals', count: status?.counts?.goal || 0, icon: Zap, color: 'green', type: 'goals' },
    { label: 'Events', count: status?.counts?.event || 0, icon: Calendar, color: 'pink', type: 'events' },
  ]

  const colorClasses = {
    cyan: { bg: 'bg-neon-cyan/20', text: 'text-neon-cyan', border: 'border-neon-cyan/40' },
    purple: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple/40' },
    green: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green/40' },
    pink: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink/40' },
  }

  return (
    <div className="h-full overflow-y-auto p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-display font-bold neon-text">Dashboard</h1>
          <p className="text-slate-400 mt-1">Your knowledge graph at a glance</p>
        </div>
        <button
          onClick={() => { fetchData(); onRefresh?.(); }}
          className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
        >
          <RefreshCw className="w-5 h-5 text-neon-purple" />
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-4 gap-4 mb-8">
        {stats.map((stat) => {
          const Icon = stat.icon
          const colors = colorClasses[stat.color]
          
          return (
            <button
              key={stat.label}
              onClick={() => onNavigate?.(stat.type)}
              className={`
                glass rounded-xl p-6 border ${colors.border}
                hover:scale-[1.02] transition-all duration-200 text-left
                hover:border-opacity-100
              `}
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 rounded-xl ${colors.bg} flex items-center justify-center`}>
                  <Icon className={`w-6 h-6 ${colors.text}`} />
                </div>
                <TrendingUp className={`w-5 h-5 ${colors.text} opacity-50`} />
              </div>
              <p className={`text-4xl font-bold font-mono ${colors.text}`}>{stat.count}</p>
              <p className="text-slate-400 text-sm mt-1">{stat.label}</p>
            </button>
          )
        })}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Recent Activity (Audit-based) */}
        <div className="glass neon-border rounded-xl p-6 relative">
          <ActivityFeed
            limit={15}
            compact={false}
            onEntitySelect={onEntitySelect}
            onDocumentSelect={onDocumentSelect}
          />
        </div>

        {/* Open Loops */}
        <div className="glass neon-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <AlertCircle className="w-5 h-5 text-neon-pink" />
            <h2 className="text-lg font-semibold">Needs Attention</h2>
          </div>
          
          {loading ? (
            <div className="flex items-center justify-center h-40">
              <div className="animate-spin w-8 h-8 border-2 border-neon-purple border-t-transparent rounded-full" />
            </div>
          ) : openLoops.length > 0 ? (
            <div className="space-y-3">
              {openLoops.map((loop, idx) => (
                <div
                  key={idx}
                  className="p-4 rounded-lg bg-neon-pink/5 border border-neon-pink/20"
                >
                  <div className="flex items-start justify-between mb-2">
                    <span className="px-2 py-0.5 rounded-full text-xs font-mono bg-neon-pink/20 text-neon-pink capitalize">
                      {loop.type || 'reminder'}
                    </span>
                    {loop.urgency > 0 && (
                      <span className="text-xs text-neon-pink font-mono">{loop.urgency}% urgent</span>
                    )}
                  </div>
                  <p className="text-sm text-slate-300">{loop.prompt}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8">
              <div className="w-16 h-16 rounded-full bg-neon-green/10 flex items-center justify-center mx-auto mb-4">
                <Zap className="w-8 h-8 text-neon-green" />
              </div>
              <p className="text-slate-400">All caught up!</p>
              <p className="text-sm text-slate-500 mt-1">No open loops requiring attention</p>
            </div>
          )}
        </div>
      </div>

      {/* Quick Tips */}
      <div className="mt-6 glass neon-border rounded-xl p-6">
        <h2 className="text-lg font-semibold mb-4">Quick Actions</h2>
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 rounded-lg bg-slate-dark/50 border border-slate-700">
            <p className="font-medium text-neon-cyan mb-1">💬 Chat</p>
            <p className="text-sm text-slate-400">Use the chat panel to ask questions or add notes</p>
          </div>
          <div className="p-4 rounded-lg bg-slate-dark/50 border border-slate-700">
            <p className="font-medium text-neon-purple mb-1">🔍 Search</p>
            <p className="text-sm text-slate-400">Press ⌘K to search your knowledge graph</p>
          </div>
          <div className="p-4 rounded-lg bg-slate-dark/50 border border-slate-700">
            <p className="font-medium text-neon-green mb-1">📊 Graph</p>
            <p className="text-sm text-slate-400">Explore connections in the Knowledge Graph view</p>
          </div>
        </div>
      </div>
    </div>
  )
}

