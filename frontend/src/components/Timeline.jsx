import { useState, useEffect } from 'react'
import { Calendar, Clock, RefreshCw, ChevronLeft, ChevronRight, FileText, Zap } from 'lucide-react'

const API_BASE = '/api'

export default function Timeline({ onEntitySelect, refreshKey }) {
  const [timeline, setTimeline] = useState([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(7)
  const [groupedTimeline, setGroupedTimeline] = useState({})

  useEffect(() => {
    fetchTimeline()
  }, [days, refreshKey])

  useEffect(() => {
    // Group by date
    const grouped = timeline.reduce((acc, item) => {
      const date = new Date(item.date).toLocaleDateString()
      if (!acc[date]) acc[date] = []
      acc[date].push(item)
      return acc
    }, {})
    setGroupedTimeline(grouped)
  }, [timeline])

  const fetchTimeline = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/timeline?days=${days}`)
      const data = await res.json()
      setTimeline(data.timeline || [])
    } catch (e) {
      console.error('Failed to fetch timeline:', e)
    }
    setLoading(false)
  }

  const dateOptions = [
    { value: 7, label: 'Last 7 days' },
    { value: 14, label: 'Last 14 days' },
    { value: 30, label: 'Last 30 days' },
    { value: 90, label: 'Last 90 days' },
  ]

  const getTypeStyles = (type) => {
    const styles = {
      event: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink' },
      note: { bg: 'bg-neon-blue/20', text: 'text-neon-blue', border: 'border-neon-blue' },
      goal: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green' },
      project: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple' },
    }
    return styles[type] || styles.note
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
              <Calendar className="w-5 h-5 text-neon-pink" />
            </div>
            <div>
              <h1 className="text-2xl font-display font-bold">Timeline</h1>
              <p className="text-sm text-slate-400">{timeline.length} activities</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="px-4 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple transition-colors"
            >
              {dateOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <button
              onClick={fetchTimeline}
              className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
            >
              <RefreshCw className="w-5 h-5 text-neon-purple" />
            </button>
          </div>
        </div>
      </div>

      {/* Timeline Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {Object.keys(groupedTimeline).length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 rounded-xl bg-slate-dark flex items-center justify-center mx-auto mb-4">
              <Calendar className="w-8 h-8 text-slate-500" />
            </div>
            <p className="text-slate-400">No activity in this period</p>
            <p className="text-sm text-slate-500 mt-1">Events and notes will appear here</p>
          </div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-6 top-0 bottom-0 w-px bg-gradient-to-b from-neon-purple via-neon-blue to-neon-cyan" />
            
            {Object.entries(groupedTimeline).map(([date, items], dateIdx) => (
              <div key={date} className="mb-8 animate-fade-in" style={{ animationDelay: `${dateIdx * 100}ms` }}>
                {/* Date Header */}
                <div className="relative flex items-center mb-4">
                  <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center z-10">
                    <span className="text-sm font-bold text-white">
                      {new Date(date).getDate()}
                    </span>
                  </div>
                  <div className="ml-4">
                    <p className="font-semibold text-lg">
                      {new Date(date).toLocaleDateString('en-US', { weekday: 'long' })}
                    </p>
                    <p className="text-sm text-slate-400">
                      {new Date(date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}
                    </p>
                  </div>
                </div>

                {/* Items for this date */}
                <div className="space-y-3 pl-6">
                  {items.map((item, idx) => {
                    const styles = getTypeStyles(item.type)
                    return (
                      <button
                        key={item.id || idx}
                        onClick={() => onEntitySelect?.(item)}
                        className="relative w-full text-left animate-slide-in"
                        style={{ animationDelay: `${(dateIdx * items.length + idx) * 50}ms` }}
                      >
                        {/* Timeline dot */}
                        <div className={`absolute -left-[18px] top-4 w-4 h-4 rounded-full ${styles.bg} border-2 ${styles.border}`} />
                        
                        <div className={`ml-6 glass neon-border rounded-xl p-4 hover:border-neon-purple/60 transition-all`}>
                          <div className="flex items-start justify-between">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`px-2 py-0.5 rounded-full text-xs font-mono ${styles.bg} ${styles.text} capitalize`}>
                                  {item.type}
                                </span>
                                <span className="text-xs text-slate-500 font-mono">
                                  {new Date(item.date).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                              </div>
                              <h3 className="font-semibold text-lg">{item.name}</h3>
                              {item.description && (
                                <p className="text-sm text-slate-400 mt-1 line-clamp-2">{item.description}</p>
                              )}
                            </div>
                            <ChevronRight className="w-5 h-5 text-slate-500 flex-shrink-0 ml-4" />
                          </div>
                        </div>
                      </button>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

