import { useState, useRef, useEffect, useCallback } from 'react'
import { 
  Send, Bot, User, Loader2, Sparkles, Check, X, Edit3, 
  Plus, ChevronDown, ChevronUp, Users, Target, Zap, Calendar, 
  Link2, RefreshCw, MessageSquare, FileText, Clock, ExternalLink
} from 'lucide-react'
import ChangeSummary from './ChangeSummary'
import RelationshipDetail from './RelationshipDetail'

const API_BASE = '/api'

const entityIcons = {
  person: Users,
  project: Target,
  goal: Zap,
  event: Calendar,
  document: FileText,
  period: Clock,
}

const entityColors = {
  person: { bg: 'bg-neon-cyan/20', text: 'text-neon-cyan', border: 'border-neon-cyan' },
  project: { bg: 'bg-neon-purple/20', text: 'text-neon-purple', border: 'border-neon-purple' },
  goal: { bg: 'bg-neon-green/20', text: 'text-neon-green', border: 'border-neon-green' },
  event: { bg: 'bg-neon-pink/20', text: 'text-neon-pink', border: 'border-neon-pink' },
  document: { bg: 'bg-neon-blue/20', text: 'text-neon-blue', border: 'border-neon-blue' },
  period: { bg: 'bg-amber-500/20', text: 'text-amber-400', border: 'border-amber-500' },
}

const WELCOME_MESSAGE = {
  id: 'welcome',
  role: 'assistant',
  content: "Hi! I'm your knowledge assistant. You can ask me questions about your data, add new information, or both at once. I'll propose any changes for your review before saving.",
  timestamp: new Date().toISOString(),
}

export default function ConversationalChat({ 
  conversationId: propConversationId,
  onEntityCreated, 
  onEntitySelect, 
  onConversationUpdate,
  fullPage = false 
}) {
  const [messages, setMessages] = useState([WELCOME_MESSAGE])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [conversationId, setConversationId] = useState(propConversationId || null)
  const [pendingProposal, setPendingProposal] = useState(null)
  const [loadingHistory, setLoadingHistory] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const hasLoadedHistory = useRef(false)

  // Load conversation history when conversationId changes
  useEffect(() => {
    if (propConversationId && propConversationId !== conversationId) {
      setConversationId(propConversationId)
      hasLoadedHistory.current = false
    }
  }, [propConversationId])

  // Load messages from backend
  useEffect(() => {
    if (conversationId && !hasLoadedHistory.current) {
      loadConversationHistory()
    }
  }, [conversationId])

  const loadConversationHistory = async () => {
    if (!conversationId || hasLoadedHistory.current) return
    
    setLoadingHistory(true)
    try {
      const res = await fetch(`${API_BASE}/conversations/${conversationId}?include_messages=true`)
      if (res.ok) {
        const data = await res.json()
        hasLoadedHistory.current = true
        
        if (data.messages && data.messages.length > 0) {
          // Convert backend messages to our format
          const loadedMessages = data.messages.map(msg => ({
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: msg.created_at,
            // Parse entities if stored
            entities_mentioned: msg.entities_mentioned,
          }))
          
          // Add welcome message at the start if first message is from user
          if (loadedMessages[0]?.role === 'user') {
            setMessages([WELCOME_MESSAGE, ...loadedMessages])
          } else {
            setMessages(loadedMessages.length > 0 ? loadedMessages : [WELCOME_MESSAGE])
          }
        } else {
          // No messages yet, show welcome
          setMessages([WELCOME_MESSAGE])
        }
      }
    } catch (e) {
      console.error('Failed to load conversation history:', e)
      setMessages([WELCOME_MESSAGE])
    } finally {
      setLoadingHistory(false)
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, pendingProposal])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  // Auto-name conversation based on first user message
  const autoNameConversation = async (convId, firstMessage) => {
    if (!convId || !firstMessage || !onConversationUpdate) return
    
    // Create a short name from the first message
    let name = firstMessage.slice(0, 50)
    if (firstMessage.length > 50) {
      name = name.slice(0, name.lastIndexOf(' ')) + '...'
    }
    
    try {
      await fetch(`${API_BASE}/conversations/${convId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      
      onConversationUpdate({ name, preview: firstMessage.slice(0, 100) })
    } catch (e) {
      console.error('Failed to auto-name conversation:', e)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    const isFirstUserMessage = messages.filter(m => m.role === 'user').length === 0
    setInput('')
    
    // Add user message
    const userMsg = { 
      id: Date.now().toString(),
      role: 'user', 
      content: userMessage,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    try {
      // Send to unified conversation endpoint
      const res = await fetch(`${API_BASE}/conversation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          message: userMessage,
          conversation_id: conversationId,
          context: messages.slice(-10).map(m => ({ role: m.role, content: m.content })),
        }),
      })
      const data = await res.json()
      
      // Update conversation ID
      if (data.conversation_id) {
        const newConvId = data.conversation_id
        setConversationId(newConvId)
        
        // Auto-name if this was the first message
        if (isFirstUserMessage) {
          autoNameConversation(newConvId, userMessage)
        }
        
        // Update message count
        if (onConversationUpdate) {
          onConversationUpdate({ 
            updated_at: new Date().toISOString(),
            message_count: messages.length + 1,
          })
        }
      }
      
      // Handle response based on type
      if (data.requires_confirmation && data.proposal_set) {
        // Show proposal for user to review
        setPendingProposal({
          ...data.proposal_set,
          originalMessage: userMessage,
        })
        
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: data.message || "I've identified some information to add. Please review and edit if needed:",
          timestamp: new Date().toISOString(),
          hasProposal: true,
        }])
      } else {
        // Regular response (answer to question)
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: data.answer || data.message || "I couldn't process that request.",
          timestamp: new Date().toISOString(),
          sources: data.sources,
        }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { 
        id: Date.now().toString(),
        role: 'assistant', 
        content: `❌ Error: ${e.message}`,
        timestamp: new Date().toISOString(),
      }])
    }
    
    setIsLoading(false)
  }

  const handleConfirmProposal = async () => {
    if (!pendingProposal) return
    
    setIsLoading(true)
    
    try {
      // Build entity selections from proposal
      const entitySelections = {}
      const entityDescriptions = {}
      const relationshipApprovals = {}
      
      for (const ep of pendingProposal.entity_proposals || []) {
        // Use selected candidate or "new" if user chose to create new
        if (ep.userSelection === 'new' || !ep.selected_candidate_id) {
          entitySelections[ep.proposal_id] = 'new'
          if (ep.userDescription) {
            entityDescriptions[ep.proposal_id] = ep.userDescription
          }
        } else {
          entitySelections[ep.proposal_id] = ep.selected_candidate_id || ep.userSelection
        }
      }
      
      for (const rp of pendingProposal.relationship_proposals || []) {
        relationshipApprovals[rp.proposal_id] = rp.approved !== false
      }
      
      const documentApprovals = {}
      for (const dp of pendingProposal.document_proposals || []) {
        documentApprovals[dp.proposal_id] = dp.approved !== false
      }
      
      const res = await fetch(`${API_BASE}/conversation/confirm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId,
          proposal_set_id: pendingProposal.proposal_set_id,
          entity_selections: entitySelections,
          entity_descriptions: entityDescriptions,
          relationship_approvals: relationshipApprovals,
          document_approvals: documentApprovals,
        }),
      })
      const data = await res.json()
      
      // Build result message
      const errors = data.errors?.length || 0
      
      let resultMsg = data.message || "✅ Changes saved!"
      
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: resultMsg,
        timestamp: new Date().toISOString(),
        savedEntities: data.created_entities,
        linkedEntities: data.linked_entities,
        savedRelationships: data.relationships_created || data.relationships || [],
        updatedDocuments: data.documents_updated || [],
        errors: data.errors || [],
        hasChangeSummary: true,
      }])
      
      setPendingProposal(null)
      onEntityCreated?.()
    } catch (e) {
      setMessages(prev => [...prev, {
        id: Date.now().toString(),
        role: 'assistant',
        content: `❌ Failed to save: ${e.message}`,
        timestamp: new Date().toISOString(),
      }])
    }
    
    setIsLoading(false)
  }

  const handleRejectProposal = () => {
    setMessages(prev => [...prev, {
      id: Date.now().toString(),
      role: 'assistant',
      content: "No problem! I've discarded those changes. Is there anything else you'd like to add or modify?",
      timestamp: new Date().toISOString(),
    }])
    setPendingProposal(null)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  // Full page layout with centered chat
  if (fullPage) {
    return (
      <div className="h-full flex flex-col bg-midnight overflow-hidden">
        {/* Full Page Header - Only shown when not in ChatManager */}
        {!propConversationId && (
          <div className="flex-shrink-0 p-6 border-b border-neon-purple/20">
            <div className="max-w-4xl mx-auto flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-neon-purple via-neon-blue to-neon-cyan flex items-center justify-center shadow-lg shadow-neon-purple/20">
                  <Sparkles className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-display font-bold neon-text">Knowledge Assistant</h1>
                  <p className="text-sm text-slate-400">Ask questions, add information, or manage your knowledge graph</p>
                </div>
              </div>
              <button
                onClick={() => {
                  setMessages([WELCOME_MESSAGE])
                  setConversationId(null)
                  setPendingProposal(null)
                  hasLoadedHistory.current = false
                }}
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-slate-dark border border-slate-700 hover:border-neon-purple/50 transition-colors"
              >
                <RefreshCw className="w-4 h-4 text-slate-400" />
                <span className="text-sm text-slate-400">New Chat</span>
              </button>
            </div>
          </div>
        )}

        {/* Messages Area - Centered */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto p-6 space-y-6">
            {loadingHistory ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-6 h-6 text-neon-purple animate-spin" />
                <span className="ml-3 text-slate-400">Loading conversation...</span>
              </div>
            ) : messages.map((message) => (
              <MessageBubble key={message.id} message={message} fullPage onEntitySelect={onEntitySelect} />
            ))}
            
            {/* Pending Proposal */}
            {pendingProposal && (
              <div className="ml-12">
                <ProposalCard 
                  proposal={pendingProposal}
                  onUpdate={setPendingProposal}
                  onConfirm={handleConfirmProposal}
                  onReject={handleRejectProposal}
                  isLoading={isLoading}
                  fullPage
                />
              </div>
            )}
            
            {isLoading && !pendingProposal && (
              <div className="flex gap-4">
                <div className="w-10 h-10 rounded-xl bg-neon-purple/20 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-neon-purple" />
                </div>
                <div className="bg-slate-dark border border-slate-700 rounded-2xl px-6 py-4">
                  <div className="flex items-center gap-3">
                    <Loader2 className="w-5 h-5 text-neon-purple animate-spin" />
                    <span className="text-slate-400">Thinking...</span>
                  </div>
                </div>
              </div>
            )}
            
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Input Area - Fixed at bottom, centered */}
        <div className="flex-shrink-0 border-t border-neon-purple/20 bg-obsidian/80 backdrop-blur-sm">
          <form onSubmit={handleSubmit} className="max-w-4xl mx-auto p-6">
            <div className="relative">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask me anything about your knowledge graph, or add new information..."
                rows={3}
                disabled={isLoading || !!pendingProposal}
                className="w-full bg-slate-dark border border-slate-700 rounded-2xl px-6 py-4 pr-16 text-base resize-none focus:border-neon-purple focus:ring-2 focus:ring-neon-purple/20 transition-all placeholder-slate-500 disabled:opacity-50"
              />
              <button
                type="submit"
                disabled={!input.trim() || isLoading || !!pendingProposal}
                className={`
                  absolute right-3 bottom-3 p-3 rounded-xl transition-all
                  ${input.trim() && !isLoading && !pendingProposal
                    ? 'bg-gradient-to-r from-neon-purple to-neon-blue text-white hover:shadow-lg hover:shadow-neon-purple/30' 
                    : 'bg-slate-700 text-slate-500 cursor-not-allowed'
                  }
                `}
              >
                <Send className="w-5 h-5" />
              </button>
            </div>
            <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
              <span>Enter to send • Shift+Enter for new line</span>
              <span>Powered by CrewAI</span>
            </div>
          </form>
        </div>
      </div>
    )
  }

  // Sidebar layout (original)
  return (
    <div className="flex flex-col h-full bg-obsidian">
      {/* Header - Only show if not managed by ChatManager */}
      {!propConversationId && (
        <div className="p-4 border-b border-neon-purple/20 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center">
              <Sparkles className="w-4 h-4 text-white" />
            </div>
            <div>
              <span className="font-semibold">Knowledge Assistant</span>
              <p className="text-xs text-slate-500">Ask questions or add information</p>
            </div>
          </div>
          <button
            onClick={() => {
              setMessages([WELCOME_MESSAGE])
              setConversationId(null)
              setPendingProposal(null)
              hasLoadedHistory.current = false
            }}
            className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
            title="New conversation"
          >
            <RefreshCw className="w-4 h-4 text-slate-400" />
          </button>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {loadingHistory ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-5 h-5 text-neon-purple animate-spin" />
            <span className="ml-2 text-sm text-slate-400">Loading...</span>
          </div>
        ) : messages.map((message) => (
          <MessageBubble key={message.id} message={message} onEntitySelect={onEntitySelect} />
        ))}
        
        {/* Pending Proposal */}
        {pendingProposal && (
          <ProposalCard 
            proposal={pendingProposal}
            onUpdate={setPendingProposal}
            onConfirm={handleConfirmProposal}
            onReject={handleRejectProposal}
            isLoading={isLoading}
          />
        )}
        
        {isLoading && !pendingProposal && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-neon-purple/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-neon-purple" />
            </div>
            <div className="bg-slate-dark border border-slate-700 rounded-xl px-4 py-3">
              <div className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-neon-purple animate-spin" />
                <span className="text-sm text-slate-400">Thinking...</span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-neon-purple/20">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a question or add information..."
            rows={2}
            disabled={isLoading || !!pendingProposal}
            className="w-full bg-slate-dark border border-slate-700 rounded-xl px-4 py-3 pr-12 text-sm resize-none focus:border-neon-purple transition-colors placeholder-slate-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading || !!pendingProposal}
            className={`
              absolute right-2 bottom-2 p-2 rounded-lg transition-all
              ${input.trim() && !isLoading && !pendingProposal
                ? 'bg-neon-purple text-white hover:bg-neon-purple/80' 
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }
            `}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-[10px] text-slate-500 mt-2 text-center">
          Enter to send • Shift+Enter for new line
        </p>
      </form>
    </div>
  )
}

function MessageBubble({ message, fullPage = false, onEntitySelect, onRelationshipSelect }) {
  const isUser = message.role === 'user'
  const [selectedRelationship, setSelectedRelationship] = useState(null)
  
  // Simple markdown formatting
  const formatContent = (text) => {
    if (!text) return text
    // Bold
    let formatted = text.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-white">$1</strong>')
    // Italic
    formatted = formatted.replace(/_(.+?)_/g, '<em>$1</em>')
    // Newlines
    formatted = formatted.replace(/\n/g, '<br/>')
    return <span dangerouslySetInnerHTML={{ __html: formatted }} />
  }
  
  const iconSize = fullPage ? 'w-10 h-10 rounded-xl' : 'w-8 h-8 rounded-lg'
  const iconInnerSize = fullPage ? 'w-5 h-5' : 'w-4 h-4'
  const bubbleMaxWidth = fullPage ? 'max-w-[90%]' : 'max-w-[85%]'
  const bubblePadding = fullPage ? 'px-6 py-4 rounded-2xl' : 'px-4 py-3 rounded-xl'
  const textSize = fullPage ? 'text-base' : 'text-sm'
  
  const handleSourceClick = (source) => {
    if (onEntitySelect && source.id) {
      // For documents, we might want to open the parent entity or the document itself
      // The type will determine how to handle this
      onEntitySelect({ 
        id: source.id, 
        name: source.name, 
        type: source.type 
      })
    }
  }
  
  const handleRelationshipClick = (rel) => {
    // For now, open the source entity. Could add a relationship detail modal later.
    setSelectedRelationship(rel)
  }
  
  return (
    <div className={`flex ${fullPage ? 'gap-4' : 'gap-3'} animate-fade-in ${isUser ? 'flex-row-reverse' : ''}`}>
      <div className={`
        flex-shrink-0 ${iconSize} flex items-center justify-center
        ${isUser ? 'bg-neon-blue/20 text-neon-blue' : 'bg-neon-purple/20 text-neon-purple'}
      `}>
        {isUser ? <User className={iconInnerSize} /> : <Bot className={iconInnerSize} />}
      </div>
      <div className={`
        ${bubbleMaxWidth} ${bubblePadding}
        ${isUser ? 'bg-neon-blue/10 border border-neon-blue/20' : 'bg-slate-dark border border-slate-700'}
      `}>
        <div className={`${textSize} leading-relaxed`}>
          {formatContent(message.content)}
        </div>
        
        {/* New Change Summary Component - replaces old entity/relationship display */}
        {message.hasChangeSummary && (
          <ChangeSummary
            createdEntities={message.savedEntities || []}
            linkedEntities={message.linkedEntities || []}
            createdRelationships={message.savedRelationships || []}
            updatedDocuments={message.updatedDocuments || []}
            errors={message.errors || []}
            onEntitySelect={onEntitySelect}
            onRelationshipSelect={handleRelationshipClick}
          />
        )}
        
        {/* Legacy: Saved entities indicator - clickable (for old messages without hasChangeSummary) */}
        {!message.hasChangeSummary && message.savedEntities && message.savedEntities.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <p className="text-xs text-neon-green mb-2">✓ Created:</p>
            <div className="flex flex-wrap gap-1">
              {message.savedEntities.map((e, i) => {
                const Icon = entityIcons[e.type] || MessageSquare
                const colors = entityColors[e.type] || entityColors.event
                return (
                  <button
                    key={i}
                    onClick={() => handleSourceClick(e)}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs ${colors.bg} ${colors.text} hover:opacity-80 transition-opacity cursor-pointer`}
                  >
                    <Icon className="w-3 h-3" />
                    <span>{e.name}</span>
                    <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                  </button>
                )
              })}
            </div>
          </div>
        )}
        
        {/* Legacy: Linked entities - clickable */}
        {!message.hasChangeSummary && message.linkedEntities && message.linkedEntities.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <p className="text-xs text-neon-blue mb-2">🔗 Linked:</p>
            <div className="flex flex-wrap gap-1">
              {message.linkedEntities.map((e, i) => {
                const Icon = entityIcons[e.type] || Link2
                const colors = entityColors[e.type] || entityColors.person
                return (
                  <button
                    key={i}
                    onClick={() => handleSourceClick({ id: e.entity_id, name: e.mention, type: e.type })}
                    className={`flex items-center gap-1.5 px-2 py-1 rounded-lg text-xs ${colors.bg} ${colors.text} hover:opacity-80 transition-opacity cursor-pointer`}
                  >
                    <Icon className="w-3 h-3" />
                    <span>{e.mention}</span>
                    <ExternalLink className="w-2.5 h-2.5 opacity-60" />
                  </button>
                )
              })}
            </div>
          </div>
        )}
        
        {/* Sources - clickable entity/document chips */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <p className="text-xs text-slate-400 mb-2 flex items-center gap-1">
              <FileText className="w-3 h-3" />
              Sources:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {message.sources.map((source, i) => {
                const Icon = entityIcons[source.type] || MessageSquare
                const colors = entityColors[source.type] || entityColors.person
                return (
                  <button
                    key={i}
                    onClick={() => handleSourceClick(source)}
                    className={`group flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs border transition-all cursor-pointer ${colors.bg} ${colors.border}/40 hover:${colors.border} hover:shadow-sm`}
                  >
                    <Icon className={`w-3.5 h-3.5 ${colors.text}`} />
                    <span className={`font-medium ${colors.text}`}>{source.name}</span>
                    <span className="text-[10px] text-slate-500 capitalize">({source.type})</span>
                    <ExternalLink className={`w-3 h-3 ${colors.text} opacity-0 group-hover:opacity-70 transition-opacity`} />
                  </button>
                )
              })}
            </div>
          </div>
        )}
        
        <p className="text-[10px] text-slate-500 mt-2 font-mono">
          {new Date(message.timestamp).toLocaleTimeString()}
        </p>
        
        {/* Relationship detail modal */}
        {selectedRelationship && (
          <div className="mt-3 pt-3 border-t border-slate-700">
            <RelationshipDetail
              relationship={selectedRelationship}
              sourceEntity={{ id: selectedRelationship.source_id, name: selectedRelationship.source_name }}
              targetEntity={{ id: selectedRelationship.target_id, name: selectedRelationship.target_name }}
              onClose={() => setSelectedRelationship(null)}
              onEntitySelect={onEntitySelect}
            />
          </div>
        )}
      </div>
    </div>
  )
}

function ProposalCard({ proposal, onUpdate, onConfirm, onReject, isLoading, fullPage = false }) {
  const [expanded, setExpanded] = useState(true)
  const [editingEntity, setEditingEntity] = useState(null)
  
  const entityProposals = proposal.entity_proposals || []
  const relationshipProposals = proposal.relationship_proposals || []
  
  const updateEntityProposal = (index, updates) => {
    const newEntities = [...entityProposals]
    newEntities[index] = { ...newEntities[index], ...updates }
    onUpdate({ ...proposal, entity_proposals: newEntities })
  }
  
  const removeEntityProposal = (index) => {
    const newEntities = entityProposals.filter((_, i) => i !== index)
    onUpdate({ ...proposal, entity_proposals: newEntities })
  }
  
  const updateRelationshipProposal = (index, updates) => {
    const newRels = [...relationshipProposals]
    newRels[index] = { ...newRels[index], ...updates }
    onUpdate({ ...proposal, relationship_proposals: newRels })
  }
  
  const removeRelationshipProposal = (index) => {
    const newRels = relationshipProposals.filter((_, i) => i !== index)
    onUpdate({ ...proposal, relationship_proposals: newRels })
  }

  return (
    <div className="ml-11 glass neon-border rounded-xl overflow-hidden animate-fade-in">
      {/* Header */}
      <div 
        className="px-4 py-3 bg-neon-purple/10 flex items-center justify-between cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-2">
          <Edit3 className="w-4 h-4 text-neon-purple" />
          <span className="font-medium text-sm">Review Changes</span>
          <span className="px-2 py-0.5 rounded-full text-xs bg-neon-purple/20 text-neon-purple">
            {entityProposals.length} entities
          </span>
          {relationshipProposals.length > 0 && (
            <span className="px-2 py-0.5 rounded-full text-xs bg-neon-blue/20 text-neon-blue">
              {relationshipProposals.length} relationships
            </span>
          )}
        </div>
        {expanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
      </div>
      
      {expanded && (
        <div className="p-4 space-y-4">
          {/* Entity Proposals */}
          {entityProposals.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Entities</h4>
              <div className="space-y-2">
                {entityProposals.map((ep, idx) => (
                  <EntityProposalEditor
                    key={ep.proposal_id}
                    entityProposal={ep}
                    isEditing={editingEntity === idx}
                    onEdit={() => setEditingEntity(editingEntity === idx ? null : idx)}
                    onUpdate={(updates) => updateEntityProposal(idx, updates)}
                    onRemove={() => removeEntityProposal(idx)}
                  />
                ))}
              </div>
            </div>
          )}
          
          {/* Relationship Proposals */}
          {relationshipProposals.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Relationships</h4>
              <div className="space-y-2">
                {relationshipProposals.map((rp, idx) => (
                  <RelationshipProposalEditor
                    key={rp.proposal_id}
                    relationshipProposal={rp}
                    entityProposals={entityProposals}
                    onUpdate={(updates) => updateRelationshipProposal(idx, updates)}
                    onRemove={() => removeRelationshipProposal(idx)}
                  />
                ))}
              </div>
            </div>
          )}
          
          {/* Document Proposals */}
          {(proposal.document_proposals || []).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Document Updates</h4>
              <div className="space-y-2">
                {proposal.document_proposals.map((dp) => (
                  <DocumentProposalEditor
                    key={dp.proposal_id}
                    documentProposal={dp}
                    onUpdate={(updates) => {
                      const newDocs = proposal.document_proposals.map(d =>
                        d.proposal_id === dp.proposal_id ? { ...d, ...updates } : d
                      )
                      onUpdate({ ...proposal, document_proposals: newDocs })
                    }}
                    onRemove={() => {
                      const newDocs = proposal.document_proposals.filter(d => d.proposal_id !== dp.proposal_id)
                      onUpdate({ ...proposal, document_proposals: newDocs })
                    }}
                  />
                ))}
              </div>
            </div>
          )}
          
          {/* Actions */}
          <div className="flex gap-2 pt-2 border-t border-slate-700">
            <button
              onClick={onConfirm}
              disabled={isLoading || entityProposals.length === 0}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-neon-green/20 text-neon-green hover:bg-neon-green/30 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Check className="w-4 h-4" />
              )}
              <span className="text-sm font-medium">Save Changes</span>
            </button>
            <button
              onClick={onReject}
              disabled={isLoading}
              className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-slate-dark border border-slate-700 text-slate-400 hover:text-white hover:border-slate-600 transition-colors"
            >
              <X className="w-4 h-4" />
              <span className="text-sm">Discard</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function EntityProposalEditor({ entityProposal, isEditing, onEdit, onUpdate, onRemove }) {
  const Icon = entityIcons[entityProposal.inferred_type] || MessageSquare
  const colors = entityColors[entityProposal.inferred_type] || entityColors.event
  const [showCandidates, setShowCandidates] = useState(false)
  
  const candidates = entityProposal.candidates || []
  const selectedCandidate = candidates.find(c => c.id === entityProposal.selected_candidate_id)
  const nonCreateCandidates = candidates.filter(c => !c.is_create_new)
  const isExisting = selectedCandidate && !selectedCandidate.is_create_new
  const needsSelection = !entityProposal.selected_candidate_id && nonCreateCandidates.length > 0
  
  if (isEditing) {
    return (
      <div className={`p-3 rounded-lg border ${colors.border}/40 bg-slate-dark/50`}>
        <div className="space-y-2">
          <div>
            <label className="text-xs text-slate-500">Name</label>
            <input
              type="text"
              value={entityProposal.mention}
              readOnly
              className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm"
            />
          </div>
          <div>
            <label className="text-xs text-slate-500">Description (for new entity)</label>
            <input
              type="text"
              value={entityProposal.userDescription || ''}
              onChange={(e) => onUpdate({ userDescription: e.target.value })}
              placeholder="Add a note about this entity..."
              className="w-full mt-1 px-3 py-2 rounded-lg bg-slate-dark border border-slate-700 text-sm focus:border-neon-purple"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <button
              onClick={onEdit}
              className="flex-1 px-3 py-1.5 rounded-lg bg-neon-purple/20 text-neon-purple text-sm"
            >
              Done
            </button>
            <button
              onClick={onRemove}
              className="px-3 py-1.5 rounded-lg bg-red-500/20 text-red-400 text-sm"
            >
              Remove
            </button>
          </div>
        </div>
      </div>
    )
  }
  
  return (
    <div className={`rounded-lg border ${needsSelection ? 'border-yellow-500/40 bg-yellow-500/5' : isExisting ? 'border-neon-green/40 bg-neon-green/5' : `${colors.border}/20`} transition-colors`}>
      <div className="flex items-center gap-3 p-3">
        <div className={`w-8 h-8 rounded-lg ${colors.bg} flex items-center justify-center`}>
          <Icon className={`w-4 h-4 ${colors.text}`} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="font-medium text-sm truncate">{entityProposal.mention}</p>
            {isExisting && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-neon-green/20 text-neon-green">
                LINKED
              </span>
            )}
            {needsSelection && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-yellow-500/20 text-yellow-400">
                SELECT
              </span>
            )}
            {!isExisting && !needsSelection && (
              <span className="px-1.5 py-0.5 rounded text-[10px] bg-neon-blue/20 text-neon-blue">
                NEW
              </span>
            )}
          </div>
          {isExisting && selectedCandidate && (
            <p className="text-xs text-neon-green/70 truncate">
              → {selectedCandidate.name} {selectedCandidate.context && `(${selectedCandidate.context})`}
            </p>
          )}
          {entityProposal.inferred_context && (
            <p className="text-xs text-slate-500 truncate">{entityProposal.inferred_context}</p>
          )}
        </div>
        <span className={`px-2 py-0.5 rounded-full text-xs ${colors.bg} ${colors.text} capitalize`}>
          {entityProposal.inferred_type}
        </span>
        {candidates.length > 1 && (
          <button 
            onClick={() => setShowCandidates(!showCandidates)} 
            className={`p-1 rounded hover:bg-slate-dark ${needsSelection ? 'text-yellow-400' : 'text-slate-400'}`}
            title="View candidates"
          >
            <Link2 className="w-3 h-3" />
          </button>
        )}
        <button onClick={onEdit} className="p-1 rounded hover:bg-slate-dark">
          <Edit3 className="w-3 h-3 text-slate-400" />
        </button>
        <button onClick={onRemove} className="p-1 rounded hover:bg-slate-dark">
          <X className="w-3 h-3 text-slate-400" />
        </button>
      </div>
      
      {/* Candidates dropdown */}
      {showCandidates && (
        <div className="px-3 pb-3 border-t border-slate-700/50 mt-1 pt-2">
          <p className="text-xs text-slate-400 mb-2">Select entity or create new:</p>
          <div className="space-y-1">
            {candidates.map((candidate, idx) => (
              <button
                key={idx}
                onClick={() => {
                  if (candidate.is_create_new) {
                    onUpdate({ 
                      selected_candidate_id: null, 
                      userSelection: 'new' 
                    })
                  } else {
                    onUpdate({ 
                      selected_candidate_id: candidate.id,
                      userSelection: candidate.id 
                    })
                  }
                  setShowCandidates(false)
                }}
                className={`w-full flex items-center gap-2 p-2 rounded-lg text-left text-sm transition-colors ${
                  (candidate.is_create_new && !isExisting && !entityProposal.selected_candidate_id) ||
                  (candidate.id === entityProposal.selected_candidate_id)
                    ? 'bg-neon-purple/20 border border-neon-purple/40'
                    : 'bg-slate-dark/50 hover:bg-slate-dark'
                }`}
              >
                {candidate.is_create_new ? (
                  <>
                    <Plus className="w-3 h-3 text-neon-blue" />
                    <span className="flex-1">Create as new entity</span>
                  </>
                ) : (
                  <>
                    <span className="flex-1 truncate">{candidate.name}</span>
                    {candidate.context && (
                      <span className="text-xs text-slate-500 truncate max-w-[120px]">{candidate.context}</span>
                    )}
                    <span className="text-xs text-neon-green">
                      {Math.round((candidate.match_score || 0) * 100)}%
                    </span>
                  </>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

function RelationshipProposalEditor({ relationshipProposal, entityProposals, onUpdate, onRemove }) {
  const isApproved = relationshipProposal.approved !== false
  
  return (
    <div className={`flex items-center gap-2 p-3 rounded-lg border transition-colors ${
      isApproved ? 'border-neon-blue/20 hover:border-neon-blue/40' : 'border-slate-700/50 opacity-50'
    }`}>
      <button 
        onClick={() => onUpdate({ approved: !isApproved })}
        className={`p-1 rounded ${isApproved ? 'text-neon-green' : 'text-slate-500'}`}
      >
        <Check className="w-4 h-4" />
      </button>
      <span className="text-sm font-medium truncate max-w-[80px]">
        {relationshipProposal.source_mention}
      </span>
      <span className="text-xs px-2 py-0.5 rounded-full bg-neon-blue/20 text-neon-blue">
        {relationshipProposal.relationship_type}
      </span>
      <span className="text-sm font-medium truncate max-w-[80px]">
        {relationshipProposal.target_mention}
      </span>
      {relationshipProposal.action === 'replace' && (
        <span className="text-[10px] text-yellow-400">(replaces {relationshipProposal.old_type})</span>
      )}
      <div className="flex-1" />
      <button onClick={onRemove} className="p-1 rounded hover:bg-slate-dark">
        <X className="w-3 h-3 text-slate-400" />
      </button>
    </div>
  )
}

function DocumentProposalEditor({ documentProposal, onUpdate, onRemove }) {
  const isApproved = documentProposal.approved !== false
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className={`rounded-lg border transition-colors ${
      isApproved ? 'border-neon-green/20 bg-neon-green/5' : 'border-slate-700/50 opacity-50'
    }`}>
      <div className="flex items-center gap-2 p-3">
        <button 
          onClick={() => onUpdate({ approved: !isApproved })}
          className={`p-1 rounded ${isApproved ? 'text-neon-green' : 'text-slate-500'}`}
        >
          <Check className="w-4 h-4" />
        </button>
        <span className="text-xs px-2 py-0.5 rounded-full bg-neon-green/20 text-neon-green">
          {documentProposal.action === 'append' ? '📝 Update' : '📄 Create'}
        </span>
        <span className="text-sm font-medium truncate flex-1">
          {documentProposal.entity_mention}
        </span>
        <button 
          onClick={() => setExpanded(!expanded)}
          className="p-1 rounded hover:bg-slate-dark text-slate-400"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>
        <button onClick={onRemove} className="p-1 rounded hover:bg-slate-dark">
          <X className="w-3 h-3 text-slate-400" />
        </button>
      </div>
      {expanded && (
        <div className="px-3 pb-3 border-t border-slate-700/50">
          <p className="text-xs text-slate-400 mt-2 mb-1">Content to add:</p>
          <div className="p-2 rounded bg-slate-dark/50 text-xs text-slate-300 whitespace-pre-wrap">
            {documentProposal.content}
          </div>
        </div>
      )}
    </div>
  )
}

