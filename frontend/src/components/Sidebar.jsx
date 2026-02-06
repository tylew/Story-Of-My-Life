import { useRef, useCallback } from 'react'
import { LayoutDashboard, Network, Users, Target, Zap, Calendar, Clock, Bell, FileText, Timer, MessageSquare, Settings, Code2 } from 'lucide-react'
import { isDevMode } from './DevBanner'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'assistant', label: 'Assistant', icon: MessageSquare, highlight: true },
      { id: 'timeline', label: 'Timeline', icon: Clock },
    ]
  },
  {
    label: 'Knowledge',
    items: [
      { id: 'documents', label: 'Documents', icon: FileText },
      { id: 'graph', label: 'Knowledge Graph', icon: Network },
    ]
  },
  {
    label: 'Entities',
    items: [
      { id: 'people', label: 'People', icon: Users, countKey: 'person', countColor: 'text-neon-cyan', activeClasses: 'bg-neon-cyan/20 text-neon-cyan border-r-2 border-neon-cyan' },
      { id: 'projects', label: 'Projects', icon: Target, countKey: 'project', countColor: 'text-neon-purple', activeClasses: 'bg-neon-purple/20 text-neon-purple border-r-2 border-neon-purple' },
      { id: 'goals', label: 'Goals', icon: Zap, countKey: 'goal', countColor: 'text-neon-green', activeClasses: 'bg-neon-green/20 text-neon-green border-r-2 border-neon-green' },
      { id: 'events', label: 'Events', icon: Calendar, countKey: 'event', countColor: 'text-neon-pink', activeClasses: 'bg-neon-pink/20 text-neon-pink border-r-2 border-neon-pink' },
      { id: 'periods', label: 'Periods', icon: Timer, countKey: 'period', countColor: 'text-amber-500', activeClasses: 'bg-amber-500/20 text-amber-500 border-r-2 border-amber-500' },
    ]
  },
  {
    label: 'System',
    items: [
      { id: 'open-loops', label: 'Open Loops', icon: Bell, badge: true },
      { id: 'settings', label: 'Settings', icon: Settings },
      ...(isDevMode ? [{ id: 'dev-settings', label: 'Developer Settings', icon: Code2, devOnly: true }] : []),
    ]
  }
]

export default function Sidebar({ activeTab, setActiveTab, sidebarOpen, setSidebarOpen, openLoopsCount, status }) {
  const hoverTimerRef = useRef(null)
  const leaveTimerRef = useRef(null)
  const hoverOpenedRef = useRef(false) // Track if we opened via hover (so we can auto-close)

  const handleMouseEnter = useCallback(() => {
    // Clear any pending close
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current)
      leaveTimerRef.current = null
    }
    // Only hover-expand if currently collapsed
    if (!sidebarOpen) {
      hoverTimerRef.current = setTimeout(() => {
        hoverOpenedRef.current = true
        setSidebarOpen(true)
      }, 250)
    }
  }, [sidebarOpen, setSidebarOpen])

  const handleMouseLeave = useCallback(() => {
    // Clear any pending open
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current)
      hoverTimerRef.current = null
    }
    // Only auto-close if we opened via hover
    if (hoverOpenedRef.current) {
      leaveTimerRef.current = setTimeout(() => {
        hoverOpenedRef.current = false
        setSidebarOpen(false)
      }, 300)
    }
  }, [setSidebarOpen])

  return (
    <div 
      className="w-16 h-full flex-shrink-0 relative z-40"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
    <aside 
      className={`${sidebarOpen ? 'w-60' : 'w-16'} h-full border-r border-neon-purple/20 flex flex-col transition-all duration-300 bg-obsidian absolute left-0 top-0`}
    >
      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto overflow-x-hidden">
        {navGroups.map((group, groupIdx) => (
          <div key={group.label} className={groupIdx > 0 ? 'mt-4' : ''}>
            {/* Always render the label to preserve height; show asterisk when collapsed */}
            <p className={`px-4 mb-1 text-xs font-semibold uppercase tracking-wider h-5 flex items-center justify-center transition-opacity duration-200 ${
              sidebarOpen ? 'text-slate-500 opacity-100 justify-start' : 'text-slate-600 opacity-100'
            }`}>
              {sidebarOpen ? group.label : <span className="text-base font-bold text-slate-600">✱</span>}
            </p>
            <ul>
              {group.items.map((item) => {
                const Icon = item.icon
                const isActive = activeTab === item.id
                const showBadge = item.badge && openLoopsCount > 0
                const entityCount = item.countKey && status?.counts ? (status.counts[item.countKey] || 0) : null
                
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => setActiveTab(item.id)}
                      className={`
                        w-full flex items-center gap-3 h-11 px-4 text-sm font-medium
                        transition-all duration-200 relative
                        ${isActive 
                          ? (item.activeClasses || 'bg-neon-purple/20 text-neon-purple border-r-2 border-neon-purple')
                          : item.devOnly
                            ? 'text-red-400 hover:text-red-300 hover:bg-red-900/10'
                            : item.highlight 
                              ? 'text-neon-cyan hover:text-white hover:bg-neon-cyan/10 bg-neon-cyan/5' 
                              : 'text-slate-400 hover:text-white hover:bg-slate-dark'
                        }
                      `}
                      title={!sidebarOpen ? item.label : undefined}
                    >
                      <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? (item.countColor || 'text-neon-purple') : item.devOnly ? 'text-red-400' : item.highlight ? 'text-neon-cyan' : item.countColor || ''}`} />
                      {sidebarOpen && (
                        <>
                          <span className="truncate">{item.label}</span>
                          {entityCount !== null && (
                            <span className={`ml-auto text-xs font-mono ${item.countColor || 'text-slate-500'}`}>
                              {entityCount}
                            </span>
                          )}
                          {showBadge && (
                            <span className="ml-auto px-2 py-0.5 rounded-full text-xs bg-neon-pink/20 text-neon-pink font-mono">
                              {openLoopsCount}
                            </span>
                          )}
                        </>
                      )}
                      {!sidebarOpen && showBadge && (
                        <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-neon-pink animate-pulse" />
                      )}
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Footer — pulse dot always visible, text only when expanded */}
      <div className="p-4 border-t border-slate-700 overflow-hidden flex flex-col items-center">
        <div className={`flex items-center gap-2 transition-all duration-200 ${sidebarOpen ? 'w-full' : 'w-full justify-center'}`}>
          <div className={`rounded-full animate-pulse flex-shrink-0 ${status ? 'bg-neon-green w-2.5 h-2.5' : 'bg-red-500 w-2.5 h-2.5'}`} />
          {sidebarOpen && (
            <span className="text-xs text-slate-400 whitespace-nowrap">
              {status ? 'System Active' : 'Disconnected'}
            </span>
          )}
        </div>
        {sidebarOpen && (
          <p className="text-xs text-slate-500 font-mono text-center whitespace-nowrap mt-2">
            SOML v0.1.0
          </p>
        )}
      </div>
    </aside>
    </div>
  )
}
