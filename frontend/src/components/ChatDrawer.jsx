import { useState, useRef, useEffect } from 'react'
import { Send, Plus, Bot, User, Loader2, MessageSquare, ChevronRight, ChevronLeft, Sparkles } from 'lucide-react'

const API_BASE = '/api'

export default function ChatDrawer({ isOpen, onToggle, onEntityCreated }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I\'m your knowledge assistant. Ask me anything about your notes, or switch to "Add" mode to save new information.',
      timestamp: new Date().toISOString(),
    }
  ])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [mode, setMode] = useState('chat') // 'chat' or 'add'
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [isOpen])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    
    // Add user message
    const userMsg = { 
      role: 'user', 
      content: userMessage,
      timestamp: new Date().toISOString(),
    }
    setMessages(prev => [...prev, userMsg])
    setIsLoading(true)

    try {
      if (mode === 'add') {
        const res = await fetch(`${API_BASE}/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: userMessage }),
        })
        const data = await res.json()
        
        let responseText = ''
        if (data.success) {
          responseText = `✅ **Added to your knowledge graph!**\n\n`
          
          if (data.entities?.length > 0) {
            responseText += `**Entities extracted:**\n${
              data.entities.map(e => {
                const ctx = e.context ? ` — _${e.context}_` : ''
                return `• ${e.name} _(${e.type})_${ctx}`
              }).join('\n')
            }\n\n`
          } else {
            responseText += `**Entities:** None detected\n\n`
          }
          
          if (data.relationships?.length > 0) {
            responseText += `**Relationships:**\n${
              data.relationships.map(r => {
                const pending = r.pending ? ' ⏳' : ' ✓'
                return `• ${r.type} _(${r.category})_${pending}`
              }).join('\n')
            }`
          }
        } else {
          responseText = `❌ **Failed to add:** ${data.message}`
        }
        
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: responseText,
          timestamp: new Date().toISOString(),
          entities: data.entities,
        }])
        
        if (data.success && onEntityCreated) {
          onEntityCreated()
        }
      } else {
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userMessage }),
        })
        const data = await res.json()
        
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer || 'I couldn\'t generate a response.',
          timestamp: new Date().toISOString(),
          sources: data.sources,
        }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `❌ **Error:** ${e.message}`,
        timestamp: new Date().toISOString(),
      }])
    }
    
    setIsLoading(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  const quickActions = [
    { label: 'What happened today?', icon: '📅' },
    { label: 'Show my goals', icon: '🎯' },
    { label: 'Who have I talked to recently?', icon: '👥' },
  ]

  if (!isOpen) {
    return (
      <button
        onClick={onToggle}
        className="fixed right-0 top-1/2 -translate-y-1/2 z-50 px-2 py-4 bg-neon-purple rounded-l-xl shadow-lg hover:bg-neon-purple/80 transition-colors"
      >
        <ChevronLeft className="w-5 h-5 text-white" />
        <MessageSquare className="w-5 h-5 text-white mt-2" />
      </button>
    )
  }

  return (
    <div className="w-96 border-l border-neon-purple/20 flex flex-col bg-obsidian h-full">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold">AI Assistant</span>
        </div>
        <button
          onClick={onToggle}
          className="p-2 rounded-lg hover:bg-slate-dark transition-colors"
        >
          <ChevronRight className="w-5 h-5 text-slate-400" />
        </button>
      </div>

      {/* Mode Toggle */}
      <div className="px-4 py-3 border-b border-slate-700/50">
        <div className="flex rounded-lg bg-slate-dark p-1">
          <button
            onClick={() => setMode('chat')}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
              mode === 'chat' 
                ? 'bg-neon-purple/20 text-neon-purple' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            Ask
          </button>
          <button
            onClick={() => setMode('add')}
            className={`flex-1 py-2 px-3 rounded-md text-sm font-medium transition-all flex items-center justify-center gap-2 ${
              mode === 'add' 
                ? 'bg-neon-green/20 text-neon-green' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Plus className="w-4 h-4" />
            Add
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, idx) => (
          <div 
            key={idx}
            className={`flex gap-3 animate-fade-in ${
              message.role === 'user' ? 'flex-row-reverse' : ''
            }`}
          >
            <div className={`
              flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center
              ${message.role === 'user' 
                ? 'bg-neon-blue/20 text-neon-blue' 
                : 'bg-neon-purple/20 text-neon-purple'
              }
            `}>
              {message.role === 'user' ? (
                <User className="w-4 h-4" />
              ) : (
                <Bot className="w-4 h-4" />
              )}
            </div>
            <div className={`
              max-w-[85%] rounded-xl px-4 py-3 
              ${message.role === 'user' 
                ? 'bg-neon-blue/10 border border-neon-blue/20' 
                : 'bg-slate-dark border border-slate-700'
              }
            `}>
              <div className="text-sm whitespace-pre-wrap leading-relaxed">
                {formatMessage(message.content)}
              </div>
              
              {/* Sources */}
              {message.sources && message.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700">
                  <p className="text-xs text-slate-500 mb-2">
                    📚 Based on {message.sources.length} sources
                  </p>
                  <div className="space-y-1">
                    {message.sources.slice(0, 3).map((source, sidx) => (
                      <p key={sidx} className="text-xs text-slate-400 truncate">
                        • {source.metadata?.name || source.metadata?.title || 'Document'}
                      </p>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Timestamp */}
              <p className="text-[10px] text-slate-500 mt-2 font-mono">
                {new Date(message.timestamp).toLocaleTimeString()}
              </p>
            </div>
          </div>
        ))}
        
        {isLoading && (
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

      {/* Quick Actions */}
      {messages.length <= 1 && mode === 'chat' && (
        <div className="px-4 pb-2">
          <p className="text-xs text-slate-500 mb-2">Quick questions:</p>
          <div className="flex flex-wrap gap-2">
            {quickActions.map((action, idx) => (
              <button
                key={idx}
                onClick={() => setInput(action.label)}
                className="px-3 py-1.5 rounded-full text-xs bg-slate-dark border border-slate-700 hover:border-neon-purple/50 transition-colors"
              >
                {action.icon} {action.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-neon-purple/20">
        <div className="relative">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={mode === 'add' 
              ? "Add a note, event, or observation..." 
              : "Ask about your knowledge..."
            }
            rows={2}
            className="w-full bg-slate-dark border border-slate-700 rounded-xl px-4 py-3 pr-12 text-sm resize-none focus:border-neon-purple transition-colors placeholder-slate-500"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className={`
              absolute right-2 bottom-2 p-2 rounded-lg transition-all
              ${input.trim() && !isLoading
                ? mode === 'add' 
                  ? 'bg-neon-green text-white hover:bg-neon-green/80' 
                  : 'bg-neon-purple text-white hover:bg-neon-purple/80'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }
            `}
          >
            {mode === 'add' ? <Plus className="w-4 h-4" /> : <Send className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[10px] text-slate-500 mt-2 text-center">
          Enter to send • Shift+Enter for new line
        </p>
      </form>
    </div>
  )
}

// Simple markdown-like formatting
function formatMessage(text) {
  if (!text) return text
  
  // Bold
  let formatted = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  // Italic
  formatted = formatted.replace(/_(.+?)_/g, '<em>$1</em>')
  
  return <span dangerouslySetInnerHTML={{ __html: formatted }} />
}

