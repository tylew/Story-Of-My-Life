import { useState, useEffect, useCallback } from 'react'
import { 
  Plus, MessageSquare, Trash2, Edit3, Check, X, 
  ChevronLeft, ChevronRight, MoreVertical, Clock,
  Sparkles
} from 'lucide-react'
import ConversationalChat from './ConversationalChat'

const API_BASE = '/api'

export default function ChatManager({ onEntityCreated, onEntitySelect, fullPage = false }) {
  // Conversations state
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [openTabs, setOpenTabs] = useState([]) // Array of conversation IDs that are open as tabs
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [loading, setLoading] = useState(true)
  
  // Editing state
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [menuOpenId, setMenuOpenId] = useState(null)

  // Load conversations on mount
  useEffect(() => {
    loadConversations()
    
    // Load last active conversation from localStorage
    const lastActive = localStorage.getItem('soml_active_conversation')
    const lastOpenTabs = localStorage.getItem('soml_open_tabs')
    
    if (lastOpenTabs) {
      try {
        const tabs = JSON.parse(lastOpenTabs)
        setOpenTabs(tabs)
      } catch (e) {
        console.error('Failed to parse open tabs:', e)
      }
    }
    
    if (lastActive) {
      setActiveConversationId(lastActive)
    }
  }, [])

  // Persist state to localStorage
  useEffect(() => {
    if (activeConversationId) {
      localStorage.setItem('soml_active_conversation', activeConversationId)
    }
  }, [activeConversationId])
  
  useEffect(() => {
    if (openTabs.length > 0) {
      localStorage.setItem('soml_open_tabs', JSON.stringify(openTabs))
    }
  }, [openTabs])

  const loadConversations = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/conversations?limit=100`)
      const data = await res.json()
      setConversations(data.conversations || [])
      
      // If we don't have an active conversation, check if we should set one
      if (!activeConversationId && data.conversations?.length > 0) {
        // Check localStorage first
        const lastActive = localStorage.getItem('soml_active_conversation')
        const exists = data.conversations.find(c => c.id === lastActive)
        
        if (exists) {
          setActiveConversationId(lastActive)
          if (!openTabs.includes(lastActive)) {
            setOpenTabs([lastActive])
          }
        }
      }
    } catch (e) {
      console.error('Failed to load conversations:', e)
    } finally {
      setLoading(false)
    }
  }

  const createNewChat = async () => {
    try {
      const res = await fetch(`${API_BASE}/conversations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'New Chat' }),
      })
      const data = await res.json()
      
      if (data.success) {
        const newConv = {
          id: data.conversation_id,
          name: data.name,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          message_count: 0,
          preview: null,
        }
        
        setConversations(prev => [newConv, ...prev])
        setActiveConversationId(data.conversation_id)
        setOpenTabs(prev => [...prev.filter(id => id !== data.conversation_id), data.conversation_id])
      }
    } catch (e) {
      console.error('Failed to create conversation:', e)
    }
  }

  const selectConversation = useCallback((convId) => {
    setActiveConversationId(convId)
    // Add to open tabs if not already there
    if (!openTabs.includes(convId)) {
      setOpenTabs(prev => [...prev, convId])
    }
    setMenuOpenId(null)
  }, [openTabs])

  const closeTab = useCallback((convId, e) => {
    e?.stopPropagation()
    setOpenTabs(prev => prev.filter(id => id !== convId))
    
    // If closing active tab, switch to another
    if (activeConversationId === convId) {
      const remaining = openTabs.filter(id => id !== convId)
      if (remaining.length > 0) {
        setActiveConversationId(remaining[remaining.length - 1])
      } else {
        setActiveConversationId(null)
      }
    }
  }, [activeConversationId, openTabs])

  const renameConversation = async (convId) => {
    if (!editName.trim()) {
      setEditingId(null)
      return
    }
    
    try {
      const res = await fetch(`${API_BASE}/conversations/${convId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: editName.trim() }),
      })
      
      if (res.ok) {
        setConversations(prev => 
          prev.map(c => c.id === convId ? { ...c, name: editName.trim() } : c)
        )
      }
    } catch (e) {
      console.error('Failed to rename conversation:', e)
    }
    
    setEditingId(null)
    setEditName('')
  }

  const deleteConversation = async (convId) => {
    if (!confirm('Delete this conversation? This cannot be undone.')) return
    
    try {
      const res = await fetch(`${API_BASE}/conversations/${convId}`, {
        method: 'DELETE',
      })
      
      if (res.ok) {
        setConversations(prev => prev.filter(c => c.id !== convId))
        closeTab(convId)
      }
    } catch (e) {
      console.error('Failed to delete conversation:', e)
    }
    
    setMenuOpenId(null)
  }

  const startEditing = (conv) => {
    setEditingId(conv.id)
    setEditName(conv.name || 'New Chat')
    setMenuOpenId(null)
  }

  // Handle conversation update from chat (e.g., auto-naming)
  const handleConversationUpdate = useCallback((convId, updates) => {
    setConversations(prev =>
      prev.map(c => c.id === convId ? { ...c, ...updates } : c)
    )
  }, [])

  // Format relative time
  const formatTime = (dateStr) => {
    if (!dateStr) return ''
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now - date
    
    if (diff < 60000) return 'Just now'
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    if (diff < 604800000) return `${Math.floor(diff / 86400000)}d ago`
    return date.toLocaleDateString()
  }

  // Get active conversation
  const activeConversation = conversations.find(c => c.id === activeConversationId)

  return (
    <div className="h-full flex bg-midnight overflow-hidden">
      {/* Sidebar - Conversation List */}
      <div className={`
        ${sidebarOpen ? 'w-72' : 'w-0'} 
        flex-shrink-0 border-r border-neon-purple/20 flex flex-col 
        transition-all duration-300 overflow-hidden bg-obsidian
      `}>
        {/* Sidebar Header */}
        <div className="p-4 border-b border-neon-purple/20 flex items-center justify-between">
          <h2 className="font-semibold text-sm">Conversations</h2>
          <button
            onClick={createNewChat}
            className="p-2 rounded-lg bg-neon-purple/20 text-neon-purple hover:bg-neon-purple/30 transition-colors"
            title="New Chat"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="p-4 text-center text-slate-500 text-sm">Loading...</div>
          ) : conversations.length === 0 ? (
            <div className="p-4 text-center">
              <p className="text-slate-500 text-sm mb-3">No conversations yet</p>
              <button
                onClick={createNewChat}
                className="px-4 py-2 rounded-lg bg-neon-purple/20 text-neon-purple text-sm hover:bg-neon-purple/30 transition-colors"
              >
                Start a Chat
              </button>
            </div>
          ) : (
            <div className="p-2 space-y-1">
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  className={`
                    group relative rounded-lg cursor-pointer transition-colors
                    ${activeConversationId === conv.id 
                      ? 'bg-neon-purple/20 border border-neon-purple/40' 
                      : 'hover:bg-slate-dark border border-transparent'
                    }
                  `}
                  onClick={() => selectConversation(conv.id)}
                >
                  <div className="p-3">
                    {editingId === conv.id ? (
                      <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') renameConversation(conv.id)
                            if (e.key === 'Escape') setEditingId(null)
                          }}
                          autoFocus
                          className="flex-1 bg-slate-dark border border-slate-700 rounded px-2 py-1 text-sm focus:border-neon-purple"
                        />
                        <button
                          onClick={() => renameConversation(conv.id)}
                          className="p-1 text-neon-green hover:bg-neon-green/20 rounded"
                        >
                          <Check className="w-3 h-3" />
                        </button>
                        <button
                          onClick={() => setEditingId(null)}
                          className="p-1 text-slate-400 hover:bg-slate-dark rounded"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-start gap-2">
                          <MessageSquare className="w-4 h-4 text-slate-400 mt-0.5 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm truncate">
                              {conv.name || 'New Chat'}
                            </p>
                            {conv.preview && (
                              <p className="text-xs text-slate-500 truncate mt-0.5">
                                {conv.preview}
                              </p>
                            )}
                          </div>
                          
                          {/* Menu Button */}
                          <div className="relative">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                setMenuOpenId(menuOpenId === conv.id ? null : conv.id)
                              }}
                              className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-slate-dark transition-opacity"
                            >
                              <MoreVertical className="w-3 h-3 text-slate-400" />
                            </button>
                            
                            {/* Dropdown Menu */}
                            {menuOpenId === conv.id && (
                              <div 
                                className="absolute right-0 top-6 z-50 w-32 py-1 bg-slate-dark border border-slate-700 rounded-lg shadow-lg"
                                onClick={e => e.stopPropagation()}
                              >
                                <button
                                  onClick={() => startEditing(conv)}
                                  className="w-full px-3 py-1.5 text-left text-sm text-slate-300 hover:bg-slate-700 flex items-center gap-2"
                                >
                                  <Edit3 className="w-3 h-3" />
                                  Rename
                                </button>
                                <button
                                  onClick={() => deleteConversation(conv.id)}
                                  className="w-full px-3 py-1.5 text-left text-sm text-red-400 hover:bg-slate-700 flex items-center gap-2"
                                >
                                  <Trash2 className="w-3 h-3" />
                                  Delete
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                        
                        {/* Meta info */}
                        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-slate-500">
                          <Clock className="w-3 h-3" />
                          <span>{formatTime(conv.updated_at)}</span>
                          {conv.message_count > 0 && (
                            <span className="ml-auto">{conv.message_count} messages</span>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Tabs Bar */}
        {openTabs.length > 0 && (
          <div className="flex-shrink-0 border-b border-neon-purple/20 bg-obsidian/50 flex items-center">
            {/* Sidebar Toggle */}
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-3 hover:bg-slate-dark transition-colors border-r border-slate-700"
            >
              {sidebarOpen ? (
                <ChevronLeft className="w-4 h-4 text-slate-400" />
              ) : (
                <ChevronRight className="w-4 h-4 text-slate-400" />
              )}
            </button>

            {/* Tabs */}
            <div className="flex-1 flex items-center overflow-x-auto">
              {openTabs.map(tabId => {
                const conv = conversations.find(c => c.id === tabId)
                const isActive = tabId === activeConversationId
                
                return (
                  <div
                    key={tabId}
                    onClick={() => setActiveConversationId(tabId)}
                    className={`
                      flex items-center gap-2 px-4 py-2 cursor-pointer border-r border-slate-700/50
                      transition-colors min-w-0 max-w-[200px]
                      ${isActive 
                        ? 'bg-neon-purple/10 text-white border-b-2 border-b-neon-purple' 
                        : 'text-slate-400 hover:bg-slate-dark hover:text-white'
                      }
                    `}
                  >
                    <MessageSquare className="w-3 h-3 flex-shrink-0" />
                    <span className="text-sm truncate">
                      {conv?.name || 'New Chat'}
                    </span>
                    <button
                      onClick={(e) => closeTab(tabId, e)}
                      className="p-0.5 rounded hover:bg-slate-700 flex-shrink-0"
                    >
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                )
              })}
            </div>

            {/* New Tab Button */}
            <button
              onClick={createNewChat}
              className="p-3 hover:bg-slate-dark transition-colors"
              title="New Chat"
            >
              <Plus className="w-4 h-4 text-slate-400" />
            </button>
          </div>
        )}

        {/* Chat Content */}
        <div className="flex-1 overflow-hidden">
          {activeConversationId ? (
            <ConversationalChat
              key={activeConversationId}
              conversationId={activeConversationId}
              onEntityCreated={onEntityCreated}
              onEntitySelect={onEntitySelect}
              onConversationUpdate={(updates) => handleConversationUpdate(activeConversationId, updates)}
              fullPage={fullPage && !sidebarOpen}
            />
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-neon-purple via-neon-blue to-neon-cyan flex items-center justify-center mb-6 shadow-lg shadow-neon-purple/20">
                <Sparkles className="w-10 h-10 text-white" />
              </div>
              <h2 className="text-2xl font-display font-bold mb-2">Knowledge Assistant</h2>
              <p className="text-slate-400 text-center mb-6 max-w-md">
                Ask questions about your knowledge graph, add new information, or manage your data through natural conversation.
              </p>
              <button
                onClick={createNewChat}
                className="flex items-center gap-2 px-6 py-3 rounded-xl bg-gradient-to-r from-neon-purple to-neon-blue text-white font-medium hover:shadow-lg hover:shadow-neon-purple/30 transition-all"
              >
                <Plus className="w-5 h-5" />
                Start a New Chat
              </button>
              
              {conversations.length > 0 && (
                <p className="mt-4 text-sm text-slate-500">
                  or select a conversation from the sidebar
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Click outside to close menu */}
      {menuOpenId && (
        <div 
          className="fixed inset-0 z-40" 
          onClick={() => setMenuOpenId(null)}
        />
      )}
    </div>
  )
}

