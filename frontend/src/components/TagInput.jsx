import { useState, useEffect, useRef } from 'react'
import { Tag, X, Plus, Loader2 } from 'lucide-react'

const API_BASE = '/api'

/**
 * TagInput - Autocomplete tag input component
 * 
 * Features:
 * - Autocomplete from existing tags
 * - Create new tags on-the-fly
 * - Color coding for tags
 * - Remove tags
 */
export default function TagInput({
  value = [],
  onChange,
  placeholder = 'Add tags...',
  disabled = false,
  className = '',
}) {
  const [allTags, setAllTags] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const [loading, setLoading] = useState(false)
  const [highlightedIndex, setHighlightedIndex] = useState(0)
  const inputRef = useRef(null)
  const containerRef = useRef(null)

  // Fetch all available tags
  useEffect(() => {
    fetchTags()
  }, [])

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setShowSuggestions(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchTags = async () => {
    try {
      setLoading(true)
      const res = await fetch(`${API_BASE}/tags`)
      const data = await res.json()
      setAllTags(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('Failed to fetch tags:', e)
    } finally {
      setLoading(false)
    }
  }

  // Filter suggestions based on input
  const suggestions = allTags
    .filter(tag => 
      tag.name.toLowerCase().includes(inputValue.toLowerCase()) &&
      !value.includes(tag.name)
    )
    .slice(0, 8)

  // Check if we should show "create new tag" option
  const showCreateOption = inputValue.trim() && 
    !allTags.some(t => t.name.toLowerCase() === inputValue.toLowerCase()) &&
    !value.includes(inputValue.trim())

  const addTag = (tagName) => {
    const trimmed = tagName.trim()
    if (!trimmed || value.includes(trimmed)) return
    
    onChange([...value, trimmed])
    setInputValue('')
    setShowSuggestions(false)
    setHighlightedIndex(0)
    inputRef.current?.focus()
  }

  const removeTag = (tagName) => {
    onChange(value.filter(t => t !== tagName))
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      if (suggestions.length > 0 && highlightedIndex < suggestions.length) {
        addTag(suggestions[highlightedIndex].name)
      } else if (showCreateOption) {
        addTag(inputValue)
      }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      const maxIndex = suggestions.length + (showCreateOption ? 1 : 0) - 1
      setHighlightedIndex(Math.min(highlightedIndex + 1, maxIndex))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlightedIndex(Math.max(highlightedIndex - 1, 0))
    } else if (e.key === 'Escape') {
      setShowSuggestions(false)
    } else if (e.key === 'Backspace' && !inputValue && value.length > 0) {
      removeTag(value[value.length - 1])
    }
  }

  const getTagColor = (tagName) => {
    const tag = allTags.find(t => t.name === tagName)
    return tag?.color || null
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      {/* Tags container */}
      <div
        className={`
          flex flex-wrap items-center gap-1.5 p-2 rounded-lg
          bg-slate-dark border border-slate-700
          focus-within:border-neon-purple transition-colors
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
        `}
        onClick={() => !disabled && inputRef.current?.focus()}
      >
        {/* Existing tags */}
        {value.map(tag => (
          <TagPill
            key={tag}
            name={tag}
            color={getTagColor(tag)}
            onRemove={() => !disabled && removeTag(tag)}
            disabled={disabled}
          />
        ))}
        
        {/* Input */}
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={(e) => {
            setInputValue(e.target.value)
            setShowSuggestions(true)
            setHighlightedIndex(0)
          }}
          onFocus={() => setShowSuggestions(true)}
          onKeyDown={handleKeyDown}
          placeholder={value.length === 0 ? placeholder : ''}
          disabled={disabled}
          className="flex-1 min-w-[100px] bg-transparent text-sm focus:outline-none"
        />
        
        {loading && (
          <Loader2 className="w-4 h-4 text-slate-400 animate-spin" />
        )}
      </div>

      {/* Suggestions dropdown */}
      {showSuggestions && (suggestions.length > 0 || showCreateOption) && (
        <div className="absolute z-20 mt-1 w-full bg-slate-dark border border-slate-700 rounded-lg shadow-xl max-h-60 overflow-y-auto">
          {suggestions.map((tag, idx) => (
            <button
              key={tag.name}
              onClick={() => addTag(tag.name)}
              className={`
                w-full flex items-center gap-2 px-3 py-2 text-sm text-left
                transition-colors
                ${idx === highlightedIndex ? 'bg-neon-purple/20 text-neon-purple' : 'hover:bg-slate-700'}
              `}
            >
              <Tag className="w-3 h-3" />
              <span className="flex-1">{tag.name}</span>
              {tag.color && (
                <span
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: tag.color }}
                />
              )}
              <span className="text-xs text-slate-500">
                {tag.total_count || 0} items
              </span>
            </button>
          ))}
          
          {showCreateOption && (
            <button
              onClick={() => addTag(inputValue)}
              className={`
                w-full flex items-center gap-2 px-3 py-2 text-sm text-left
                transition-colors border-t border-slate-700
                ${highlightedIndex === suggestions.length ? 'bg-neon-purple/20 text-neon-purple' : 'hover:bg-slate-700'}
              `}
            >
              <Plus className="w-3 h-3" />
              <span>Create "{inputValue.trim()}"</span>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

/**
 * TagPill - Single tag display with remove button
 */
function TagPill({ name, color, onRemove, disabled }) {
  return (
    <span
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-neon-purple/20 text-neon-purple"
      style={color ? { backgroundColor: `${color}20`, color: color } : undefined}
    >
      <Tag className="w-2.5 h-2.5" />
      {name}
      {!disabled && (
        <button
          onClick={(e) => {
            e.stopPropagation()
            onRemove()
          }}
          className="ml-0.5 hover:text-white transition-colors"
        >
          <X className="w-3 h-3" />
        </button>
      )}
    </span>
  )
}

/**
 * TagDisplay - Read-only tag display
 */
export function TagDisplay({ tags = [], className = '' }) {
  if (!tags.length) return null
  
  return (
    <div className={`flex flex-wrap gap-1.5 ${className}`}>
      {tags.map(tag => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-neon-purple/20 text-neon-purple"
        >
          <Tag className="w-2.5 h-2.5" />
          {tag}
        </span>
      ))}
    </div>
  )
}

