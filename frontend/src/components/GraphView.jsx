import { useEffect, useRef, useState, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react'
import ForceGraph2D from 'react-force-graph-2d'
import { 
  ZoomIn, ZoomOut, Maximize, RefreshCw, Eye, EyeOff, 
  Settings, ChevronDown, ChevronUp, ExternalLink, FileText, 
  Link2, Trash2, MessageSquare 
} from 'lucide-react'

const API_BASE = '/api'

// Node colors by type
const nodeColors = {
  person: '#06b6d4',   // cyan
  project: '#a855f7',  // purple
  goal: '#10b981',     // green
  event: '#ec4899',    // pink
  note: '#3b82f6',     // blue
  period: '#f97316',   // orange
}

const GraphView = forwardRef(function GraphView({ 
  onNodeSelect, 
  onLinkSelect,
  refreshKey,
  highlightedNodeId,
  highlightedLink, // { sourceId, targetId }
}, ref) {
  const graphRef = useRef()
  const [graphData, setGraphData] = useState({ nodes: [], links: [] })
  const [loading, setLoading] = useState(true)
  const [hoveredNode, setHoveredNode] = useState(null)
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 })
  const containerRef = useRef()
  
  // Settings state
  const [showRelationshipLabels, setShowRelationshipLabels] = useState(false)
  const [visibleTypes, setVisibleTypes] = useState(
    Object.keys(nodeColors).reduce((acc, type) => ({ ...acc, [type]: true }), {})
  )
  const [settingsExpanded, setSettingsExpanded] = useState(true)
  const [linkDistance, setLinkDistance] = useState(80) // Slider: 30-200
  
  // Quick actions menu
  const [quickActionsNode, setQuickActionsNode] = useState(null)
  const [quickActionsPos, setQuickActionsPos] = useState({ x: 0, y: 0 })

  // Filter graph data based on visible types - must be before effects that use it
  // Also aggregate multiple relationships between the same nodes
  const filteredGraphData = useMemo(() => {
    const visibleNodes = graphData.nodes.filter(node => visibleTypes[node.type])
    const visibleNodeIds = new Set(visibleNodes.map(n => n.id))
    const visibleLinks = graphData.links.filter(
      link => visibleNodeIds.has(link.source?.id || link.source) && 
              visibleNodeIds.has(link.target?.id || link.target)
    )
    
    // Group links by source-target pair (ignoring direction)
    const linkGroups = new Map()
    visibleLinks.forEach(link => {
      const sourceId = link.source?.id || link.source
      const targetId = link.target?.id || link.target
      // Normalize the key so A-B and B-A are the same
      const key = [sourceId, targetId].sort().join('|')
      if (!linkGroups.has(key)) {
        linkGroups.set(key, {
          source: sourceId,
          target: targetId,
          links: [],
        })
      }
      linkGroups.get(key).links.push(link)
    })
    
    // Create aggregated links with count
    const aggregatedLinks = Array.from(linkGroups.values()).map(group => ({
      source: group.source,
      target: group.target,
      type: group.links.length === 1 ? group.links[0].type : null,
      label: group.links.length === 1 ? group.links[0].label : `${group.links.length} relationships`,
      count: group.links.length,
      allLinks: group.links,
    }))
    
    return { nodes: visibleNodes, links: aggregatedLinks }
  }, [graphData, visibleTypes])

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    focusNode: (nodeId) => {
      if (!graphRef.current) return
      const node = filteredGraphData.nodes.find(n => n.id === nodeId)
      if (node) {
        graphRef.current.centerAt(node.x, node.y, 500)
        graphRef.current.zoom(2, 500)
      }
    },
    focusLink: (sourceId, targetId) => {
      if (!graphRef.current) return
      const sourceNode = filteredGraphData.nodes.find(n => n.id === sourceId)
      const targetNode = filteredGraphData.nodes.find(n => n.id === targetId)
      if (sourceNode && targetNode) {
        const midX = (sourceNode.x + targetNode.x) / 2
        const midY = (sourceNode.y + targetNode.y) / 2
        graphRef.current.centerAt(midX, midY, 500)
        graphRef.current.zoom(1.8, 500)
      }
    },
  }), [filteredGraphData.nodes])

  // Fetch graph data on mount and when refreshKey changes
  useEffect(() => {
    fetchGraphData()
  }, [refreshKey])

  // Configure force simulation for better node spacing
  useEffect(() => {
    if (!graphRef.current || loading) return
    
    const fg = graphRef.current
    
    // Link distance - controlled by slider
    fg.d3Force('link')
      ?.distance(linkDistance)
      .strength(0.3)
    
    // Charge repulsion - reduced for tighter non-connected nodes
    fg.d3Force('charge')
      ?.strength(-80)      // Lighter repulsion (brings unconnected nodes closer)
      .distanceMax(200)    // Shorter range
    
    // Center force
    fg.d3Force('center')
      ?.strength(0.05)
    
    // Reheat to apply changes
    fg.d3ReheatSimulation()
  }, [loading, filteredGraphData, linkDistance])

  // Use ResizeObserver for reliable dimension tracking
  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect()
        if (rect.width > 0 && rect.height > 0) {
          setDimensions({ width: rect.width, height: rect.height })
        }
      }
      // Fallback if container has no dimensions yet
      if (dimensions.width === 0 || dimensions.height === 0) {
        setDimensions({
          width: window.innerWidth - 280,
          height: window.innerHeight - 64,
        })
      }
    }
    
    const timeoutId = setTimeout(updateDimensions, 50)
    
    let resizeObserver
    if (containerRef.current) {
      resizeObserver = new ResizeObserver(updateDimensions)
      resizeObserver.observe(containerRef.current)
    }
    
    window.addEventListener('resize', updateDimensions)
    
    return () => {
      clearTimeout(timeoutId)
      resizeObserver?.disconnect()
      window.removeEventListener('resize', updateDimensions)
    }
  }, [loading])

  const fetchGraphData = async () => {
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/graph`)
      const data = await res.json()
      
      const nodes = data.nodes.map(node => ({
        ...node,
        color: nodeColors[node.type] || '#64748b',
      }))
      
      const links = data.edges.map(edge => ({
        source: edge.source,
        target: edge.target,
        type: edge.type,
        label: edge.type?.replace(/_/g, ' '),
      }))
      
      setGraphData({ nodes, links })
    } catch (e) {
      console.error('Failed to fetch graph:', e)
    }
    setLoading(false)
  }

  const handleNodeClick = useCallback((node, event) => {
    // Normalize entity to have both name and label
    const entity = {
      ...node,
      name: node.name || node.label,
      label: node.label || node.name,
    }
    
    // Open detail panel
    onNodeSelect(entity)
    
    // Center on node
    if (graphRef.current) {
      graphRef.current.centerAt(node.x, node.y, 500)
      graphRef.current.zoom(2, 500)
    }
    
    // Close quick actions if open
    setQuickActionsNode(null)
  }, [onNodeSelect])

  const hoverTimeoutRef = useRef(null)
  
  const handleNodeHover = useCallback((node, prevNode) => {
    setHoveredNode(node)
    document.body.style.cursor = node ? 'pointer' : 'default'
    
    // Clear any pending hide timeout
    if (hoverTimeoutRef.current) {
      clearTimeout(hoverTimeoutRef.current)
      hoverTimeoutRef.current = null
    }
    
    // Show quick actions near the node
    if (node && graphRef.current) {
      const coords = graphRef.current.graph2ScreenCoords(node.x, node.y)
      setQuickActionsPos({ x: coords.x, y: coords.y })
      setQuickActionsNode(node)
    } else {
      // Delay hiding to allow mouse to reach the menu
      hoverTimeoutRef.current = setTimeout(() => {
        setQuickActionsNode(null)
      }, 200)
    }
  }, [])
  
  // Larger hit area for nodes (invisible, for easier hovering)
  const nodePointerAreaPaint = useCallback((node, color, ctx) => {
    ctx.beginPath()
    ctx.arc(node.x, node.y, 25, 0, 2 * Math.PI, false) // 25px radius hit area
    ctx.fillStyle = color
    ctx.fill()
  }, [])

  const handleNodeRightClick = useCallback((node, event) => {
    event.preventDefault()
    if (graphRef.current) {
      const coords = graphRef.current.graph2ScreenCoords(node.x, node.y)
      setQuickActionsPos({ x: coords.x, y: coords.y })
      setQuickActionsNode(node)
    }
  }, [])

  const toggleEntityType = (type) => {
    setVisibleTypes(prev => ({ ...prev, [type]: !prev[type] }))
  }

  const showAllTypes = () => {
    setVisibleTypes(Object.keys(nodeColors).reduce((acc, type) => ({ ...acc, [type]: true }), {}))
  }

  const hideAllTypes = () => {
    setVisibleTypes(Object.keys(nodeColors).reduce((acc, type) => ({ ...acc, [type]: false }), {}))
  }

  const nodeCanvasObject = useCallback((node, ctx, globalScale) => {
    const label = node.label || node.name || ''
    const fontSize = Math.max(10, 12 / globalScale)
    ctx.font = `${fontSize}px 'Space Grotesk', sans-serif`
    
    const isHovered = hoveredNode?.id === node.id
    const isHighlighted = highlightedNodeId === node.id || 
      (highlightedLink && (highlightedLink.sourceId === node.id || highlightedLink.targetId === node.id))
    const isSelected = isHovered || isHighlighted
    const nodeRadius = isSelected ? 10 : 7
    
    // Draw glow for selected/highlighted nodes
    if (isSelected) {
      ctx.beginPath()
      ctx.arc(node.x, node.y, nodeRadius + 8, 0, 2 * Math.PI, false)
      ctx.fillStyle = isHighlighted ? 'rgba(255, 255, 255, 0.15)' : `${node.color}33`
      ctx.fill()
      
      // Extra glow ring for highlighted
      if (isHighlighted) {
        ctx.beginPath()
        ctx.arc(node.x, node.y, nodeRadius + 4, 0, 2 * Math.PI, false)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.5)'
        ctx.lineWidth = 2
        ctx.stroke()
      }
    }
    
    // Draw node circle
    ctx.beginPath()
    ctx.arc(node.x, node.y, nodeRadius, 0, 2 * Math.PI, false)
    ctx.fillStyle = node.color || '#64748b'
    ctx.fill()
    
    // Draw border
    ctx.strokeStyle = isSelected ? 'white' : `${node.color}aa`
    ctx.lineWidth = isSelected ? 2 : 1
    ctx.stroke()
    
    // Draw label
    if (globalScale > 0.5 || isSelected) {
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = isSelected ? 'white' : 'rgba(255, 255, 255, 0.85)'
      ctx.fillText(label, node.x, node.y + nodeRadius + fontSize + 2)
    }
  }, [hoveredNode, highlightedNodeId, highlightedLink])

  const linkCanvasObject = useCallback((link, ctx, globalScale) => {
    const start = link.source
    const end = link.target
    
    if (typeof start !== 'object' || typeof end !== 'object') return
    
    const isMultiple = link.count > 1
    const midX = (start.x + end.x) / 2
    const midY = (start.y + end.y) / 2
    
    // Check if this link is highlighted
    const isHighlighted = highlightedLink && (
      (highlightedLink.sourceId === start.id && highlightedLink.targetId === end.id) ||
      (highlightedLink.sourceId === end.id && highlightedLink.targetId === start.id)
    )
    
    // Draw line (thicker for multi-relationships or highlighted)
    ctx.beginPath()
    ctx.moveTo(start.x, start.y)
    ctx.lineTo(end.x, end.y)
    
    if (isHighlighted) {
      // Highlighted link - bright with glow effect
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.9)'
      ctx.lineWidth = 3
      ctx.stroke()
      
      // Glow
      ctx.beginPath()
      ctx.moveTo(start.x, start.y)
      ctx.lineTo(end.x, end.y)
      ctx.strokeStyle = 'rgba(168, 85, 247, 0.3)'
      ctx.lineWidth = 8
      ctx.stroke()
    } else {
      ctx.strokeStyle = isMultiple ? 'rgba(168, 85, 247, 0.5)' : 'rgba(168, 85, 247, 0.3)'
      ctx.lineWidth = isMultiple ? 2 : 1
      ctx.stroke()
    }
    
    // Draw multi-relationship badge
    if (isMultiple) {
      const badgeRadius = Math.max(10, 12 / globalScale)
      
      // Badge circle
      ctx.beginPath()
      ctx.arc(midX, midY, badgeRadius, 0, 2 * Math.PI, false)
      ctx.fillStyle = isHighlighted ? '#9333ea' : '#7c3aed' // brighter when highlighted
      ctx.fill()
      ctx.strokeStyle = isHighlighted ? 'white' : 'rgba(255, 255, 255, 0.5)'
      ctx.lineWidth = isHighlighted ? 2 : 1
      ctx.stroke()
      
      // Count text
      const fontSize = Math.max(8, 10 / globalScale)
      ctx.font = `bold ${fontSize}px 'Space Grotesk', sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillStyle = 'white'
      ctx.fillText(link.count.toString(), midX, midY)
    } else if (showRelationshipLabels && link.label && globalScale > 0.8) {
      // Draw single relationship label if enabled
      const fontSize = Math.max(8, 10 / globalScale)
      ctx.font = `${fontSize}px 'Space Grotesk', sans-serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      
      // Background for readability
      const textWidth = ctx.measureText(link.label).width
      ctx.fillStyle = 'rgba(10, 10, 15, 0.8)'
      ctx.fillRect(midX - textWidth/2 - 4, midY - fontSize/2 - 2, textWidth + 8, fontSize + 4)
      
      // Text
      ctx.fillStyle = isHighlighted ? 'rgba(168, 85, 247, 1)' : 'rgba(168, 85, 247, 0.8)'
      ctx.fillText(link.label, midX, midY)
    }
  }, [showRelationshipLabels, highlightedLink])
  
  // Handle link click to open relationship sidebar
  const handleLinkClick = useCallback((link) => {
    if (!link || typeof link.source !== 'object' || typeof link.target !== 'object') return
    
    // Find the node entities
    const sourceNode = graphData.nodes.find(n => n.id === link.source.id) || link.source
    const targetNode = graphData.nodes.find(n => n.id === link.target.id) || link.target
    
    // Normalize entities to have both name and label (graph uses label, components use name)
    const sourceEntity = {
      ...sourceNode,
      name: sourceNode.name || sourceNode.label,
      label: sourceNode.label || sourceNode.name,
    }
    const targetEntity = {
      ...targetNode,
      name: targetNode.name || targetNode.label,
      label: targetNode.label || targetNode.name,
    }
    
    // Call the parent handler to open the sidebar
    onLinkSelect?.(sourceEntity, targetEntity)
  }, [graphData.nodes, onLinkSelect])

  // Quick action handlers
  const handleQuickAction = (action, node) => {
    setQuickActionsNode(null)
    switch (action) {
      case 'view':
        onNodeSelect(node)
        break
      case 'center':
        if (graphRef.current) {
          graphRef.current.centerAt(node.x, node.y, 500)
          graphRef.current.zoom(2.5, 500)
        }
        break
      case 'neighbors':
        // Focus on node's neighborhood
        if (graphRef.current) {
          graphRef.current.centerAt(node.x, node.y, 500)
          graphRef.current.zoom(1.5, 500)
        }
        break
      default:
        break
    }
  }

  // Count visible vs total for each type
  const typeCounts = useMemo(() => {
    const counts = {}
    for (const type of Object.keys(nodeColors)) {
      const total = graphData.nodes.filter(n => n.type === type).length
      const visible = filteredGraphData.nodes.filter(n => n.type === type).length
      counts[type] = { total, visible }
    }
    return counts
  }, [graphData.nodes, filteredGraphData.nodes])

  return (
    <div ref={containerRef} className="absolute inset-0 graph-container">
      {/* Loading overlay */}
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center bg-midnight z-10">
          <div className="text-center">
            <div className="animate-spin w-12 h-12 border-3 border-neon-purple border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-slate-400 font-mono text-sm">Loading knowledge graph...</p>
          </div>
        </div>
      )}
      
      {/* Graph */}
      {!loading && dimensions.width > 0 && dimensions.height > 0 && (
        <ForceGraph2D
          ref={graphRef}
          graphData={filteredGraphData}
          width={dimensions.width}
          height={dimensions.height}
          nodeCanvasObject={nodeCanvasObject}
          nodePointerAreaPaint={nodePointerAreaPaint}
          linkCanvasObject={linkCanvasObject}
          onNodeClick={handleNodeClick}
          onNodeHover={handleNodeHover}
          onNodeRightClick={handleNodeRightClick}
          onLinkClick={handleLinkClick}
          nodeRelSize={6}
          linkWidth={1}
          linkColor={() => 'rgba(168, 85, 247, 0.2)'}
          backgroundColor="#0a0a0f"
          cooldownTicks={200}
          warmupTicks={100}
          d3AlphaDecay={0.02}
          d3VelocityDecay={0.3}
          onEngineStop={() => graphRef.current?.zoomToFit(400, 50)}
          linkPointerAreaPaint={(link, paintColor, ctx) => {
            // Make links easier to click
            const start = link.source
            const end = link.target
            if (typeof start !== 'object' || typeof end !== 'object') return
            
            ctx.beginPath()
            ctx.moveTo(start.x, start.y)
            ctx.lineTo(end.x, end.y)
            ctx.strokeStyle = paintColor
            ctx.lineWidth = 10 // Wide clickable area
            ctx.stroke()
          }}
        />
      )}

      {/* Controls */}
      <div className="absolute bottom-4 right-4 flex flex-col gap-2 z-20">
        <button 
          onClick={() => graphRef.current?.zoom(graphRef.current.zoom() * 1.5, 300)}
          className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="w-5 h-5 text-neon-purple" />
        </button>
        <button 
          onClick={() => graphRef.current?.zoom(graphRef.current.zoom() / 1.5, 300)}
          className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="w-5 h-5 text-neon-purple" />
        </button>
        <button 
          onClick={() => graphRef.current?.zoomToFit(400)}
          className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors"
          title="Fit to Screen"
        >
          <Maximize className="w-5 h-5 text-neon-purple" />
        </button>
        <button 
          onClick={fetchGraphData}
          disabled={loading}
          className="p-2 rounded-lg glass neon-border hover:border-neon-purple transition-colors disabled:opacity-50"
          title="Refresh"
        >
          <RefreshCw className={`w-5 h-5 text-neon-purple ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Legend & Settings Panel */}
      <div className="absolute top-4 left-4 glass neon-border rounded-xl p-4 max-w-xs z-20">
        <div 
          className="flex items-center justify-between cursor-pointer"
          onClick={() => setSettingsExpanded(!settingsExpanded)}
        >
          <div className="flex items-center gap-2">
            <Settings className="w-4 h-4 text-slate-400" />
            <h3 className="text-sm font-semibold text-slate-300">Graph Settings</h3>
          </div>
          {settingsExpanded ? (
            <ChevronUp className="w-4 h-4 text-slate-400" />
          ) : (
            <ChevronDown className="w-4 h-4 text-slate-400" />
          )}
        </div>
        
        {settingsExpanded && (
          <div className="mt-4 space-y-4">
            {/* Link Distance Slider */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">Node Spacing</span>
                <span className="text-xs text-slate-500 font-mono">{linkDistance}</span>
              </div>
              <input
                type="range"
                min="30"
                max="200"
                value={linkDistance}
                onChange={(e) => setLinkDistance(Number(e.target.value))}
                className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-neon-purple"
              />
              <div className="flex justify-between text-xs text-slate-600 mt-1">
                <span>Tight</span>
                <span>Spread</span>
              </div>
            </div>

            {/* Relationship Labels Toggle */}
            <div className="flex items-center justify-between">
              <span className="text-xs text-slate-400">Show Relationship Labels</span>
              <button
                onClick={() => setShowRelationshipLabels(!showRelationshipLabels)}
                className={`p-1.5 rounded-lg transition-colors ${
                  showRelationshipLabels 
                    ? 'bg-neon-purple/20 border border-neon-purple' 
                    : 'bg-slate-700/50 border border-slate-600'
                }`}
              >
                {showRelationshipLabels ? (
                  <Eye className="w-4 h-4 text-neon-purple" />
                ) : (
                  <EyeOff className="w-4 h-4 text-slate-400" />
                )}
              </button>
            </div>
            
            {/* Entity Type Filters */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-400">Entity Types</span>
                <div className="flex gap-1">
                  <button
                    onClick={showAllTypes}
                    className="text-xs text-neon-cyan hover:underline"
                  >
                    All
                  </button>
                  <span className="text-slate-600">|</span>
                  <button
                    onClick={hideAllTypes}
                    className="text-xs text-slate-400 hover:underline"
                  >
                    None
                  </button>
                </div>
              </div>
              <div className="space-y-1.5">
                {Object.entries(nodeColors).map(([type, color]) => (
                  <label 
                    key={type} 
                    className="flex items-center gap-2 cursor-pointer group"
                  >
                    <input
                      type="checkbox"
                      checked={visibleTypes[type]}
                      onChange={() => toggleEntityType(type)}
                      className="sr-only"
                    />
                    <div 
                      className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                        visibleTypes[type] 
                          ? 'border-transparent' 
                          : 'border-slate-600 bg-slate-700/50'
                      }`}
                      style={{ backgroundColor: visibleTypes[type] ? color : undefined }}
                    >
                      {visibleTypes[type] && (
                        <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                    <span className={`text-xs capitalize transition-colors ${
                      visibleTypes[type] ? 'text-slate-300' : 'text-slate-500'
                    }`}>
                      {type}
                    </span>
                    <span className="text-xs text-slate-500 ml-auto">
                      {typeCounts[type]?.visible || 0}/{typeCounts[type]?.total || 0}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Stats */}
      <div className="absolute top-4 right-4 glass neon-border rounded-xl px-4 py-2 z-20">
        <span className="text-sm font-mono text-slate-300">
          {filteredGraphData.nodes.length} nodes · {filteredGraphData.links.length} edges
        </span>
      </div>

      {/* Quick Actions Menu (appears on hover) */}
      {quickActionsNode && (
        <div 
          className="absolute z-30 glass neon-border rounded-lg p-2 shadow-xl"
          style={{
            left: Math.min(quickActionsPos.x + 20, dimensions.width - 180),
            top: Math.max(quickActionsPos.y - 60, 10),
          }}
          onMouseEnter={() => {
            // Cancel any pending hide timeout when entering menu
            if (hoverTimeoutRef.current) {
              clearTimeout(hoverTimeoutRef.current)
              hoverTimeoutRef.current = null
            }
          }}
          onMouseLeave={() => setQuickActionsNode(null)}
        >
          <div className="mb-2 px-2 pb-2 border-b border-slate-700">
            <span className="font-semibold text-sm" style={{ color: quickActionsNode.color }}>
              {quickActionsNode.label || quickActionsNode.name}
            </span>
            <span className="text-xs text-slate-500 ml-2 capitalize">
              ({quickActionsNode.type})
            </span>
          </div>
          <div className="space-y-1">
            <button
              onClick={() => handleQuickAction('view', quickActionsNode)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-700/50 transition-colors text-left"
            >
              <ExternalLink className="w-4 h-4 text-neon-cyan" />
              <span className="text-xs text-slate-300">View Details</span>
            </button>
            <button
              onClick={() => handleQuickAction('center', quickActionsNode)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-700/50 transition-colors text-left"
            >
              <Maximize className="w-4 h-4 text-neon-purple" />
              <span className="text-xs text-slate-300">Focus & Zoom</span>
            </button>
            <button
              onClick={() => handleQuickAction('neighbors', quickActionsNode)}
              className="w-full flex items-center gap-2 px-2 py-1.5 rounded hover:bg-slate-700/50 transition-colors text-left"
            >
              <Link2 className="w-4 h-4 text-neon-green" />
              <span className="text-xs text-slate-300">Show Connections</span>
            </button>
          </div>
        </div>
      )}

      {/* Hovered node tooltip (when quick actions not shown) */}
      {hoveredNode && !quickActionsNode && (
        <div 
          className="absolute pointer-events-none glass neon-border rounded-lg px-3 py-2 text-sm z-20"
          style={{
            left: dimensions.width / 2 - 100,
            top: 80,
          }}
        >
          <span className="font-semibold" style={{ color: hoveredNode.color }}>
            {hoveredNode.label || hoveredNode.name}
          </span>
          <span className="text-slate-400 ml-2">({hoveredNode.type})</span>
          <span className="text-xs text-slate-500 ml-2">Click to view • Right-click for actions</span>
        </div>
      )}
      
    </div>
  )
})

export default GraphView
