import { useState, useEffect, useCallback, useRef } from 'react'
import GraphView from './components/GraphView'
import ChatManager from './components/ChatManager'
import Sidebar from './components/Sidebar'
import EntityDetail from './components/EntityDetail'
import EntityList from './components/EntityList'
import Timeline from './components/Timeline'
import Dashboard from './components/Dashboard'
import OpenLoops from './components/OpenLoops'
import SearchModal from './components/SearchModal'
import DocumentBrowser from './components/DocumentBrowser'
import DocumentView from './components/DocumentView'
import RelationshipsBetweenEntities from './components/RelationshipsBetweenEntities'
import { Brain, Search, Bell } from 'lucide-react'

const API_BASE = '/api'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedEntity, setSelectedEntity] = useState(null)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [selectedRelationshipPair, setSelectedRelationshipPair] = useState(null) // { sourceEntity, targetEntity }
  const [status, setStatus] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [searchOpen, setSearchOpen] = useState(false)
  const [openLoopsCount, setOpenLoopsCount] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const graphRef = useRef(null)

  useEffect(() => {
    fetchStatus()
    fetchOpenLoopsCount()
  }, [refreshKey])

  // Keyboard shortcut for search
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(true)
      }
      if (e.key === 'Escape') {
        setSearchOpen(false)
        setSelectedEntity(null)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  // Handle entity selection from EntityDetail relationships tab
  useEffect(() => {
    const handleEntitySelectEvent = (e) => {
      if (e.detail) {
        setSelectedEntity(e.detail)
        setSelectedDocument(null)
      }
    }
    window.addEventListener('entity-select', handleEntitySelectEvent)
    return () => window.removeEventListener('entity-select', handleEntitySelectEvent)
  }, [])

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      const data = await res.json()
      setStatus(data)
    } catch (e) {
      console.error('Failed to fetch status:', e)
    }
  }

  const fetchOpenLoopsCount = async () => {
    try {
      const res = await fetch(`${API_BASE}/open-loops`)
      const data = await res.json()
      setOpenLoopsCount(data.count || 0)
    } catch (e) {
      console.error('Failed to fetch open loops:', e)
    }
  }

  const handleEntitySelect = useCallback((entity) => {
    setSelectedEntity(entity)
    setSelectedDocument(null)
    setSelectedRelationshipPair(null)
    // Focus on entity in graph if we're on graph view
    if (graphRef.current && entity?.id) {
      graphRef.current.focusNode(entity.id)
    }
  }, [])

  const handleDocumentSelect = useCallback((doc) => {
    setSelectedDocument(doc)
    setSelectedEntity(null)
    setSelectedRelationshipPair(null)
  }, [])

  const handleRelationshipPairSelect = useCallback((sourceEntity, targetEntity) => {
    setSelectedRelationshipPair({ sourceEntity, targetEntity })
    setSelectedEntity(null)
    setSelectedDocument(null)
    // Focus on the link in graph
    if (graphRef.current && sourceEntity?.id && targetEntity?.id) {
      graphRef.current.focusLink(sourceEntity.id, targetEntity.id)
    }
  }, [])

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1)
  }, [])

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard status={status} onEntitySelect={handleEntitySelect} onRefresh={handleRefresh} onNavigate={setActiveTab} />
      case 'graph':
        return (
          <GraphView 
            ref={graphRef}
            onNodeSelect={handleEntitySelect} 
            onLinkSelect={handleRelationshipPairSelect}
            refreshKey={refreshKey}
            highlightedNodeId={selectedEntity?.id}
            highlightedLink={selectedRelationshipPair ? {
              sourceId: selectedRelationshipPair.sourceEntity?.id,
              targetId: selectedRelationshipPair.targetEntity?.id,
            } : null}
          />
        )
      case 'people':
        return <EntityList type="people" onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'projects':
        return <EntityList type="projects" onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'goals':
        return <EntityList type="goals" onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'events':
        return <EntityList type="events" onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'periods':
        return <EntityList type="periods" onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'timeline':
        return <Timeline onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'open-loops':
        return <OpenLoops onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'documents':
        return <DocumentBrowser onDocumentSelect={handleDocumentSelect} onEntitySelect={handleEntitySelect} refreshKey={refreshKey} />
      case 'assistant':
        return <ChatManager onEntityCreated={handleRefresh} onEntitySelect={handleEntitySelect} fullPage />
      default:
        return <Dashboard status={status} onEntitySelect={handleEntitySelect} onRefresh={handleRefresh} onNavigate={setActiveTab} />
    }
  }

  return (
    <div className="h-screen flex flex-col bg-midnight overflow-hidden">
      {/* Header */}
      <header className="h-16 border-b border-neon-purple/20 flex items-center justify-between px-6 glass flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-display font-bold neon-text">Story of My Life</h1>
            <p className="text-xs text-slate-400 font-mono">Personal Knowledge Graph</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          {/* Search Button */}
          <button
            onClick={() => setSearchOpen(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-dark border border-slate-700 hover:border-neon-purple/50 transition-colors"
          >
            <Search className="w-4 h-4 text-slate-400" />
            <span className="text-sm text-slate-400">Search...</span>
            <kbd className="ml-2 px-2 py-0.5 rounded bg-slate-700 text-xs text-slate-400 font-mono">⌘K</kbd>
          </button>

          {/* Open Loops Indicator */}
          {openLoopsCount > 0 && (
            <button
              onClick={() => setActiveTab('open-loops')}
              className="relative flex items-center gap-2 px-3 py-2 rounded-lg bg-neon-pink/10 border border-neon-pink/30 hover:border-neon-pink/60 transition-colors"
            >
              <Bell className="w-4 h-4 text-neon-pink" />
              <span className="text-sm text-neon-pink font-medium">{openLoopsCount} Open Loops</span>
              <span className="absolute -top-1 -right-1 w-3 h-3 bg-neon-pink rounded-full animate-pulse" />
            </button>
          )}

          {/* Status indicators */}
          {status && (
            <div className="flex items-center gap-4 text-sm">
              <StatBadge label="People" count={status.counts?.person || 0} color="cyan" />
              <StatBadge label="Projects" count={status.counts?.project || 0} color="purple" />
              <StatBadge label="Goals" count={status.counts?.goal || 0} color="green" />
              <StatBadge label="Events" count={status.counts?.event || 0} color="pink" />
              <StatBadge label="Periods" count={status.counts?.period || 0} color="orange" />
            </div>
          )}

          {/* Connection Status */}
          <div className="h-8 w-px bg-slate-700" />
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-neon-green animate-pulse" />
            <span className="text-xs text-slate-400 font-mono">Connected</span>
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <Sidebar 
          activeTab={activeTab} 
          setActiveTab={setActiveTab}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={setSidebarOpen}
          openLoopsCount={openLoopsCount}
        />

        {/* Main Content */}
        <main className="flex-1 flex overflow-hidden">
          {/* Content Area */}
          <div className="flex-1 relative overflow-hidden">
            {renderContent()}
          </div>

          {/* Entity Detail Panel */}
          {selectedEntity && (
            <EntityDetail 
              entity={selectedEntity} 
              onClose={() => setSelectedEntity(null)}
              onRefresh={handleRefresh}
              onDocumentSelect={handleDocumentSelect}
              onRelationshipPairSelect={handleRelationshipPairSelect}
            />
          )}

          {/* Document View Panel */}
          {selectedDocument && (
            <DocumentView
              document={selectedDocument}
              onClose={() => setSelectedDocument(null)}
              onRefresh={handleRefresh}
            />
          )}

          {/* Relationships Between Entities Panel */}
          {selectedRelationshipPair && (
            <RelationshipsBetweenEntities
              sourceEntity={selectedRelationshipPair.sourceEntity}
              targetEntity={selectedRelationshipPair.targetEntity}
              onClose={() => setSelectedRelationshipPair(null)}
              onEntitySelect={handleEntitySelect}
              onRefresh={handleRefresh}
            />
          )}
        </main>
      </div>

      {/* Search Modal */}
      <SearchModal 
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelect={handleEntitySelect}
      />
    </div>
  )
}

function StatBadge({ label, count, color }) {
  const colorClasses = {
    cyan: 'text-neon-cyan',
    purple: 'text-neon-purple',
    green: 'text-neon-green',
    pink: 'text-neon-pink',
    blue: 'text-neon-blue',
    orange: 'text-amber-500',
  }
  
  return (
    <span className={`flex items-center gap-1 ${colorClasses[color]}`}>
      <span className="font-mono font-bold">{count}</span>
      <span className="text-xs opacity-70">{label}</span>
    </span>
  )
}

export default App
