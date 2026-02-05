import { LayoutDashboard, Network, Users, Target, Zap, Calendar, Clock, Bell, ChevronLeft, ChevronRight, FileText, Timer, MessageSquare } from 'lucide-react'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { id: 'assistant', label: 'Assistant', icon: MessageSquare, highlight: true },
      { id: 'graph', label: 'Knowledge Graph', icon: Network },
      { id: 'timeline', label: 'Timeline', icon: Clock },
    ]
  },
  {
    label: 'Entities',
    items: [
      { id: 'people', label: 'People', icon: Users },
      { id: 'projects', label: 'Projects', icon: Target },
      { id: 'goals', label: 'Goals', icon: Zap },
      { id: 'events', label: 'Events', icon: Calendar },
      { id: 'periods', label: 'Periods', icon: Timer },
    ]
  },
  {
    label: 'Knowledge',
    items: [
      { id: 'documents', label: 'Documents', icon: FileText },
    ]
  },
  {
    label: 'System',
    items: [
      { id: 'open-loops', label: 'Open Loops', icon: Bell, badge: true },
    ]
  }
]

export default function Sidebar({ activeTab, setActiveTab, sidebarOpen, setSidebarOpen, openLoopsCount }) {
  return (
    <aside className={`${sidebarOpen ? 'w-60' : 'w-16'} border-r border-neon-purple/20 flex flex-col transition-all duration-300 bg-obsidian relative`}>
      {/* Toggle button */}
      <button 
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="absolute -right-3 top-20 z-10 w-6 h-6 rounded-full bg-slate-dark border border-neon-purple/40 flex items-center justify-center hover:border-neon-purple transition-colors"
      >
        {sidebarOpen ? (
          <ChevronLeft className="w-4 h-4 text-neon-purple" />
        ) : (
          <ChevronRight className="w-4 h-4 text-neon-purple" />
        )}
      </button>

      {/* Navigation */}
      <nav className="flex-1 py-4 overflow-y-auto">
        {navGroups.map((group, groupIdx) => (
          <div key={group.label} className={groupIdx > 0 ? 'mt-6' : ''}>
            {sidebarOpen && (
              <p className="px-4 mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {group.label}
              </p>
            )}
            <ul className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon
                const isActive = activeTab === item.id
                const showBadge = item.badge && openLoopsCount > 0
                
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => setActiveTab(item.id)}
                      className={`
                        w-full flex items-center gap-3 px-4 py-3 text-sm font-medium
                        transition-all duration-200 relative
                        ${isActive 
                          ? 'bg-neon-purple/20 text-neon-purple border-r-2 border-neon-purple' 
                          : item.highlight 
                            ? 'text-neon-cyan hover:text-white hover:bg-neon-cyan/10 bg-neon-cyan/5' 
                            : 'text-slate-400 hover:text-white hover:bg-slate-dark'
                        }
                      `}
                      title={!sidebarOpen ? item.label : undefined}
                    >
                      <Icon className={`w-5 h-5 flex-shrink-0 ${isActive ? 'text-neon-purple' : item.highlight ? 'text-neon-cyan' : ''}`} />
                      {sidebarOpen && (
                        <>
                          <span className="truncate">{item.label}</span>
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

      {/* Footer */}
      {sidebarOpen && (
        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
            <span className="text-xs text-slate-400">System Active</span>
          </div>
          <p className="text-xs text-slate-500 font-mono text-center">
            SOML v0.1.0
          </p>
        </div>
      )}
    </aside>
  )
}
