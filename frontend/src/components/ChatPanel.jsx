import { useState, useRef, useEffect } from 'react'
import { Send, Plus, Bot, User, Loader2 } from 'lucide-react'

const API_BASE = '/api'

export default function ChatPanel({ onEntityCreated }) {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: 'Hello! I\'m your personal knowledge assistant. Ask me anything about your notes, or add new information to your knowledge graph.',
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

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)

    try {
      if (mode === 'add') {
        // Add new content
        const res = await fetch(`${API_BASE}/add`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content: userMessage }),
        })
        const data = await res.json()
        
        let responseText = data.success 
          ? `✅ Added to your knowledge graph!\n\n**Entities extracted:**\n${
              data.entities?.map(e => `- ${e.name} (${e.type})`).join('\n') || 'None'
            }`
          : `❌ Failed to add: ${data.message}`
        
        setMessages(prev => [...prev, { role: 'assistant', content: responseText }])
        
        if (data.success && onEntityCreated) {
          onEntityCreated()
        }
      } else {
        // Chat/query
        const res = await fetch(`${API_BASE}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: userMessage }),
        })
        const data = await res.json()
        
        setMessages(prev => [...prev, { 
          role: 'assistant', 
          content: data.answer || 'I couldn\'t generate a response.',
          sources: data.sources,
        }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `❌ Error: ${e.message}` 
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

  return (
    <div className="flex flex-col h-full bg-obsidian">
      {/* Header */}
      <div className="p-4 border-b border-neon-purple/20">
        <div className="flex items-center gap-4">
          <button
            onClick={() => setMode('chat')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
              mode === 'chat' 
                ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/40' 
                : 'text-slate-400 hover:text-white border border-transparent'
            }`}
          >
            💬 Ask
          </button>
          <button
            onClick={() => setMode('add')}
            className={`flex-1 py-2 px-4 rounded-lg text-sm font-medium transition-all ${
              mode === 'add' 
                ? 'bg-neon-green/20 text-neon-green border border-neon-green/40' 
                : 'text-slate-400 hover:text-white border border-transparent'
            }`}
          >
            ➕ Add
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
                {message.content}
              </div>
              {message.sources && message.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-700">
                  <p className="text-xs text-slate-500 mb-2">
                    Based on {message.sources.length} sources
                  </p>
                </div>
              )}
            </div>
          </div>
        ))}
        
        {isLoading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-neon-purple/20 flex items-center justify-center">
              <Bot className="w-4 h-4 text-neon-purple" />
            </div>
            <div className="bg-slate-dark border border-slate-700 rounded-xl px-4 py-3">
              <Loader2 className="w-5 h-5 text-neon-purple animate-spin" />
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
                ? 'bg-neon-purple text-white hover:bg-neon-purple/80' 
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }
            `}
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-slate-500 mt-2 text-center">
          Press Enter to send, Shift+Enter for new line
        </p>
      </form>
    </div>
  )
}

