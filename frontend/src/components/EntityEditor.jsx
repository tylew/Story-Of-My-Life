import { useState, useEffect } from 'react'
import { Save, X, Plus, Trash2, Calendar, Mail, Phone, Briefcase, Tag, User, Target, Zap, Clock, MapPin, Timer, Hash } from 'lucide-react'

const API_BASE = '/api'

// Field configurations per entity type
const typeFieldConfig = {
  person: {
    fields: [
      { key: 'name', label: 'Name', type: 'text', icon: User, required: true },
      { key: 'disambiguator', label: 'Disambiguator', type: 'text', icon: Tag, placeholder: 'e.g., CEO of Acme Corp' },
      { key: 'email', label: 'Email', type: 'email', icon: Mail },
      { key: 'phone', label: 'Phone', type: 'tel', icon: Phone },
      { key: 'current_employer', label: 'Current Employer', type: 'text', icon: Briefcase },
    ],
    nameField: 'name',
  },
  project: {
    fields: [
      { key: 'name', label: 'Name', type: 'text', icon: Target, required: true },
      { key: 'status', label: 'Status', type: 'select', icon: Tag, options: ['active', 'completed', 'on_hold', 'cancelled'] },
      { key: 'start_date', label: 'Start Date', type: 'date', icon: Calendar },
      { key: 'end_date', label: 'End Date', type: 'date', icon: Calendar },
    ],
    nameField: 'name',
  },
  goal: {
    fields: [
      { key: 'title', label: 'Title', type: 'text', icon: Zap, required: true },
      { key: 'status', label: 'Status', type: 'select', icon: Tag, options: ['active', 'completed', 'abandoned'] },
      { key: 'target_date', label: 'Target Date', type: 'date', icon: Calendar },
      { key: 'progress', label: 'Progress (%)', type: 'range', icon: Target, min: 0, max: 100 },
    ],
    nameField: 'title',
  },
  event: {
    fields: [
      { key: 'title', label: 'Title', type: 'text', icon: Calendar, required: true },
      { key: 'on_date', label: 'Date', type: 'date', icon: Calendar },
      { key: 'start_time', label: 'Start Time', type: 'time', icon: Clock },
      { key: 'end_time', label: 'End Time', type: 'time', icon: Clock },
      { key: 'location', label: 'Location', type: 'text', icon: MapPin },
    ],
    nameField: 'title',
  },
  period: {
    fields: [
      { key: 'name', label: 'Name', type: 'text', icon: Timer, required: true },
      { key: 'start_date', label: 'Start Date', type: 'date', icon: Calendar },
      { key: 'end_date', label: 'End Date', type: 'date', icon: Calendar },
    ],
    nameField: 'name',
  },
}

// System fields that cannot be edited
const systemFields = ['id', 'entity_type', 'type', 'created_at', 'source', 'links', 'confidence']

export default function EntityEditor({ entity, metadata, onSave, onCancel }) {
  const entityType = entity?.type || 'person'
  const config = typeFieldConfig[entityType] || typeFieldConfig.person
  
  const [formData, setFormData] = useState({})
  const [customFields, setCustomFields] = useState({})
  const [tags, setTags] = useState([])
  const [newCustomKey, setNewCustomKey] = useState('')
  const [newCustomValue, setNewCustomValue] = useState('')
  const [newTag, setNewTag] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  
  // Initialize form data from entity/metadata
  useEffect(() => {
    const data = metadata || entity || {}
    const initialData = {}
    
    // Extract configured fields
    config.fields.forEach(field => {
      initialData[field.key] = data[field.key] || ''
    })
    
    setFormData(initialData)
    setCustomFields(data.custom_fields || {})
    setTags(data.tags || [])
  }, [entity, metadata, entityType])
  
  const handleFieldChange = (key, value) => {
    setFormData(prev => ({ ...prev, [key]: value }))
  }
  
  const handleAddCustomField = () => {
    if (!newCustomKey.trim()) return
    setCustomFields(prev => ({
      ...prev,
      [newCustomKey.trim()]: newCustomValue,
    }))
    setNewCustomKey('')
    setNewCustomValue('')
  }
  
  const handleRemoveCustomField = (key) => {
    setCustomFields(prev => {
      const next = { ...prev }
      delete next[key]
      return next
    })
  }
  
  const handleAddTag = () => {
    if (!newTag.trim() || tags.includes(newTag.trim())) return
    setTags(prev => [...prev, newTag.trim()])
    setNewTag('')
  }
  
  const handleRemoveTag = (tag) => {
    setTags(prev => prev.filter(t => t !== tag))
  }
  
  const handleSubmit = async () => {
    setSaving(true)
    setError(null)
    
    try {
      // Build update payload
      const updates = {
        ...formData,
        tags,
        custom_fields: customFields,
      }
      
      // Remove empty strings
      Object.keys(updates).forEach(key => {
        if (updates[key] === '') {
          updates[key] = null
        }
      })
      
      const response = await fetch(`${API_BASE}/entities/${entity.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      })
      
      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to save')
      }
      
      onSave?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }
  
  const renderField = (field) => {
    const value = formData[field.key] || ''
    const Icon = field.icon
    
    return (
      <div key={field.key} className="space-y-1">
        <label className="flex items-center gap-2 text-sm text-slate-400">
          <Icon className="w-4 h-4" />
          {field.label}
          {field.required && <span className="text-red-400">*</span>}
        </label>
        
        {field.type === 'select' ? (
          <select
            value={value}
            onChange={(e) => handleFieldChange(field.key, e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-neon-purple capitalize"
          >
            <option value="">Select...</option>
            {field.options.map(opt => (
              <option key={opt} value={opt} className="capitalize">
                {opt.replace('_', ' ')}
              </option>
            ))}
          </select>
        ) : field.type === 'range' ? (
          <div className="flex items-center gap-3">
            <input
              type="range"
              min={field.min}
              max={field.max}
              value={value || 0}
              onChange={(e) => handleFieldChange(field.key, parseInt(e.target.value))}
              className="flex-1 h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-neon-purple"
            />
            <span className="text-sm text-slate-300 w-12 text-right">{value || 0}%</span>
          </div>
        ) : (
          <input
            type={field.type}
            value={value}
            onChange={(e) => handleFieldChange(field.key, e.target.value)}
            placeholder={field.placeholder}
            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-neon-purple placeholder-slate-500"
          />
        )}
      </div>
    )
  }
  
  return (
    <div className="p-4 space-y-6">
      {error && (
        <div className="bg-red-500/20 border border-red-500/40 rounded-lg p-3">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}
      
      {/* Core Properties */}
      <section>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Core Properties
        </h3>
        <div className="space-y-4 glass neon-border rounded-xl p-4">
          {config.fields.map(renderField)}
        </div>
      </section>
      
      {/* Custom Fields */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
            Custom Fields
          </h3>
        </div>
        <div className="glass neon-border rounded-xl p-4 space-y-3">
          {Object.entries(customFields).length > 0 ? (
            Object.entries(customFields).map(([key, value]) => (
              <div key={key} className="flex items-center gap-2">
                <div className="flex-1 flex items-center gap-2 bg-slate-800 rounded-lg px-3 py-2">
                  <Hash className="w-4 h-4 text-slate-500" />
                  <span className="text-sm text-slate-400 font-mono">{key}</span>
                  <span className="text-slate-600">=</span>
                  <input
                    type="text"
                    value={value}
                    onChange={(e) => setCustomFields(prev => ({ ...prev, [key]: e.target.value }))}
                    className="flex-1 bg-transparent text-sm focus:outline-none"
                  />
                </div>
                <button
                  onClick={() => handleRemoveCustomField(key)}
                  className="p-2 text-slate-500 hover:text-red-400 transition-colors"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500 text-center py-2">No custom fields</p>
          )}
          
          {/* Add new custom field */}
          <div className="flex items-center gap-2 pt-2 border-t border-slate-700">
            <input
              type="text"
              value={newCustomKey}
              onChange={(e) => setNewCustomKey(e.target.value)}
              placeholder="Key"
              className="w-32 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-neon-purple"
            />
            <input
              type="text"
              value={newCustomValue}
              onChange={(e) => setNewCustomValue(e.target.value)}
              placeholder="Value"
              className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-neon-purple"
              onKeyDown={(e) => e.key === 'Enter' && handleAddCustomField()}
            />
            <button
              onClick={handleAddCustomField}
              disabled={!newCustomKey.trim()}
              className="p-2 bg-neon-purple/20 text-neon-purple rounded-lg hover:bg-neon-purple/30 transition-colors disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>
      
      {/* Tags */}
      <section>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          Tags
        </h3>
        <div className="glass neon-border rounded-xl p-4">
          <div className="flex flex-wrap gap-2 mb-3">
            {tags.map(tag => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs bg-neon-purple/20 text-neon-purple border border-neon-purple/30"
              >
                {tag}
                <button
                  onClick={() => handleRemoveTag(tag)}
                  className="hover:text-red-400 transition-colors"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}
            {tags.length === 0 && (
              <p className="text-sm text-slate-500">No tags</p>
            )}
          </div>
          
          <div className="flex items-center gap-2 pt-2 border-t border-slate-700">
            <Tag className="w-4 h-4 text-slate-500" />
            <input
              type="text"
              value={newTag}
              onChange={(e) => setNewTag(e.target.value)}
              placeholder="Add tag..."
              className="flex-1 bg-transparent text-sm focus:outline-none"
              onKeyDown={(e) => e.key === 'Enter' && handleAddTag()}
            />
            <button
              onClick={handleAddTag}
              disabled={!newTag.trim()}
              className="p-1 text-neon-purple hover:bg-neon-purple/20 rounded transition-colors disabled:opacity-50"
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>
      </section>
      
      {/* System Fields (read-only) */}
      <section>
        <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
          System (Read-only)
        </h3>
        <div className="glass neon-border rounded-xl divide-y divide-slate-700/50">
          <SystemField label="ID" value={entity?.id?.slice(0, 12) + '...'} />
          <SystemField label="Created" value={formatDate(metadata?.created_at || entity?.created_at)} />
          <SystemField label="Updated" value={formatDate(metadata?.updated_at || entity?.updated_at)} />
          <SystemField label="Source" value={metadata?.source || entity?.source || 'agent'} />
          <SystemField label="Confidence" value={`${Math.round((metadata?.confidence || entity?.confidence || 0.8) * 100)}%`} />
        </div>
      </section>
      
      {/* Actions */}
      <div className="flex items-center gap-3 pt-4 border-t border-slate-700">
        <button
          onClick={onCancel}
          className="flex-1 py-2 px-4 rounded-lg bg-slate-700 text-slate-300 hover:bg-slate-600 transition-colors flex items-center justify-center gap-2"
        >
          <X className="w-4 h-4" />
          Cancel
        </button>
        <button
          onClick={handleSubmit}
          disabled={saving}
          className="flex-1 py-2 px-4 rounded-lg bg-neon-purple text-white hover:bg-neon-purple/80 transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
        >
          {saving ? (
            <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
          ) : (
            <Save className="w-4 h-4" />
          )}
          Save Changes
        </button>
      </div>
    </div>
  )
}

function SystemField({ label, value }) {
  return (
    <div className="flex items-center justify-between p-3">
      <span className="text-sm text-slate-400">{label}</span>
      <span className="text-sm text-slate-500 font-mono">{value || '-'}</span>
    </div>
  )
}

function formatDate(dateStr) {
  if (!dateStr) return '-'
  try {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return dateStr
  }
}

