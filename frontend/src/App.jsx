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
import Settings from './components/Settings'
import DeveloperSettings from './components/DeveloperSettings'
import DevBanner, { isDevMode } from './components/DevBanner'
import { Brain, Search, Bell } from 'lucide-react'

const API_BASE = '/api'

function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedEntity, setSelectedEntity] = useState(null)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [selectedRelationshipPair, setSelectedRelationshipPair] = useState(null) // { sourceEntity, targetEntity }
  const [documentBrowserFilters, setDocumentBrowserFilters] = useState({})
  const [status, setStatus] = useState(null)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [isSmallScreen, setIsSmallScreen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [openLoopsCount, setOpenLoopsCount] = useState(0)
  const [refreshKey, setRefreshKey] = useState(0)
  const [graphFocusEntityId, setGraphFocusEntityId] = useState(null)
  const graphRef = useRef(null)

  useEffect(() => {
    fetchStatus()
    fetchOpenLoopsCount()
  }, [refreshKey])

  // Responsive: detect small screen
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 1024px)')
    const handler = (e) => setIsSmallScreen(e.matches)
    setIsSmallScreen(mq.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Auto-collapse left sidebar for immersive views or small screens
  const fullWidthTabs = ['graph', 'documents']
  useEffect(() => {
    if (isSmallScreen || fullWidthTabs.includes(activeTab)) {
      setSidebarOpen(false)
    }
  }, [activeTab, isSmallScreen])

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

  // On small screens, opening a right panel should close the left sidebar
  const hasRightPanel = !!(selectedEntity || selectedDocument || selectedRelationshipPair)

  const handleEntitySelect = useCallback((entity, options = {}) => {
    const { navigateToGraph = true } = options
    
    setSelectedEntity(entity)
    setSelectedDocument(null)
    setSelectedRelationshipPair(null)
    
    // Navigate to graph view and collapse nav sidebar
    if (navigateToGraph && entity?.id) {
      setActiveTab('graph')
      setSidebarOpen(false) // Collapse navigation menu
      setGraphFocusEntityId(entity.id) // Trigger ego-graph mode
    } else if (isSmallScreen) {
      setSidebarOpen(false) // On small screens, collapse left when right opens
    }
  }, [isSmallScreen])

  // Handle entity selection from EntityDetail relationships tab
  useEffect(() => {
    const handleEntitySelectEvent = (e) => {
      if (e.detail) {
        handleEntitySelect(e.detail)
      }
    }
    window.addEventListener('entity-select', handleEntitySelectEvent)
    return () => window.removeEventListener('entity-select', handleEntitySelectEvent)
  }, [handleEntitySelect])

  const handleDocumentSelect = useCallback((doc) => {
    setSelectedDocument(doc)
    setSelectedEntity(null)
    setSelectedRelationshipPair(null)
    if (isSmallScreen) setSidebarOpen(false)
  }, [isSmallScreen])

  const handleRelationshipPairSelect = useCallback((sourceEntity, targetEntity) => {
    setSelectedRelationshipPair({ sourceEntity, targetEntity })
    setSelectedEntity(null)
    setSelectedDocument(null)
    if (isSmallScreen) setSidebarOpen(false)
    // Focus on the link in graph
    if (graphRef.current && sourceEntity?.id && targetEntity?.id) {
      graphRef.current.focusLink(sourceEntity.id, targetEntity.id)
    }
  }, [isSmallScreen])

  const handleRefresh = useCallback(() => {
    setRefreshKey(k => k + 1)
  }, [])

  const handleViewAllDocuments = useCallback((filters = {}) => {
    setDocumentBrowserFilters(filters)
    setActiveTab('documents')
    // Close any open detail panels
    setSelectedEntity(null)
    setSelectedDocument(null)
    setSelectedRelationshipPair(null)
  }, [])

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard status={status} onEntitySelect={handleEntitySelect} onDocumentSelect={handleDocumentSelect} onRefresh={handleRefresh} onNavigate={setActiveTab} />
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
            focusedEntityId={graphFocusEntityId}
            onClearFocus={() => setGraphFocusEntityId(null)}
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
        return (
          <DocumentBrowser 
            onDocumentSelect={handleDocumentSelect} 
            onEntitySelect={handleEntitySelect}
            onRelationshipSelect={(rel) => {
              // When clicking a relationship from document browser, open the relationship pair view
              // We'd need to fetch the full relationship details - for now just log
              console.log('Relationship selected:', rel)
            }}
            refreshKey={refreshKey}
            initialFilters={documentBrowserFilters}
          />
        )
      case 'assistant':
        return <ChatManager onEntityCreated={handleRefresh} onEntitySelect={handleEntitySelect} fullPage />
      case 'settings':
        return <Settings />
      case 'dev-settings':
        return isDevMode ? <DeveloperSettings onRefresh={handleRefresh} /> : <Dashboard status={status} onEntitySelect={handleEntitySelect} onDocumentSelect={handleDocumentSelect} onRefresh={handleRefresh} onNavigate={setActiveTab} />
      default:
        return <Dashboard status={status} onEntitySelect={handleEntitySelect} onDocumentSelect={handleDocumentSelect} onRefresh={handleRefresh} onNavigate={setActiveTab} />
    }
  }

  return (
    <div className={`h-screen flex flex-col bg-midnight overflow-hidden ${isDevMode ? 'pb-7' : ''}`}>
      <DevBanner />
      {/* Header */}
      <header className="h-16 border-b border-neon-purple/20 flex items-center justify-between px-6 glass flex-shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-display font-bold neon-text">Story of My Life</h1>
            <p className="text-xs text-slate-400 font-mono">Knowledge Assistant</p>
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

        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        <Sidebar 
          activeTab={activeTab} 
          setActiveTab={(tab) => {
            setActiveTab(tab)
            if (isSmallScreen) {
              setSelectedEntity(null)
              setSelectedDocument(null)
              setSelectedRelationshipPair(null)
            }
          }}
          sidebarOpen={sidebarOpen}
          setSidebarOpen={(open) => {
            setSidebarOpen(open)
            if (isSmallScreen && open) {
              setSelectedEntity(null)
              setSelectedDocument(null)
              setSelectedRelationshipPair(null)
            }
          }}
          openLoopsCount={openLoopsCount}
          status={status}
        />

        {/* Main Content */}
        <main className="flex-1 flex overflow-hidden relative">
          {/* Content Area */}
          <div className="flex-1 relative overflow-hidden">
            {renderContent()}
          </div>

          {/* Right panel backdrop — overlay on small screens */}
          {hasRightPanel && isSmallScreen && (
            <div 
              className="absolute inset-0 bg-black/40 z-30"
              onClick={() => {
                setSelectedEntity(null)
                setSelectedDocument(null)
                setSelectedRelationshipPair(null)
              }}
            />
          )}

          {/* Entity Detail Panel */}
          {selectedEntity && (
            <div className={isSmallScreen ? 'absolute right-0 top-0 bottom-0 z-40 max-w-[90vw]' : ''}>
              <EntityDetail 
                entity={selectedEntity} 
                onClose={() => setSelectedEntity(null)}
                onRefresh={handleRefresh}
                onDocumentSelect={handleDocumentSelect}
                onRelationshipPairSelect={handleRelationshipPairSelect}
                onViewAllDocuments={handleViewAllDocuments}
              />
            </div>
          )}

          {/* Document View Panel */}
          {selectedDocument && (
            <div className={isSmallScreen ? 'absolute right-0 top-0 bottom-0 z-40 max-w-[90vw]' : ''}>
              <DocumentView
                document={selectedDocument}
                onClose={() => setSelectedDocument(null)}
                onRefresh={handleRefresh}
              />
            </div>
          )}

          {/* Relationships Between Entities Panel */}
          {selectedRelationshipPair && (
            <div className={isSmallScreen ? 'absolute right-0 top-0 bottom-0 z-40 max-w-[90vw]' : ''}>
              <RelationshipsBetweenEntities
                sourceEntity={selectedRelationshipPair.sourceEntity}
                targetEntity={selectedRelationshipPair.targetEntity}
                onClose={() => setSelectedRelationshipPair(null)}
                onEntitySelect={handleEntitySelect}
                onRefresh={handleRefresh}
                onDocumentSelect={handleDocumentSelect}
                onViewAllDocuments={handleViewAllDocuments}
              />
            </div>
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

export default App
