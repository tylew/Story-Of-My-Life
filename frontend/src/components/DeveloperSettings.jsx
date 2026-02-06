import { useState, useEffect } from 'react'
import { Code2, Database, RefreshCw, Trash2, Terminal, Server, Activity, Copy, Check } from 'lucide-react'

const API_BASE = '/api'

export default function DeveloperSettings({ onRefresh }) {
  const [dbInfo, setDbInfo] = useState(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(null)
  const [logs, setLogs] = useState([])

  useEffect(() => {
    fetchDbInfo()
  }, [])

  const fetchDbInfo = async () => {
    try {
      const res = await fetch(`${API_BASE}/status`)
      const data = await res.json()
      setDbInfo(data)
    } catch (e) {
      addLog('error', `Failed to fetch status: ${e.message}`)
    }
  }

  const addLog = (level, message) => {
    setLogs(prev => [{ level, message, time: new Date().toISOString() }, ...prev].slice(0, 50))
  }

  const handleReindex = async () => {
    setLoading(true)
    addLog('info', 'Triggering reindex...')
    try {
      const res = await fetch(`${API_BASE}/reindex`, { method: 'POST' })
      if (res.ok) {
        addLog('success', 'Reindex completed successfully')
        onRefresh?.()
      } else {
        addLog('error', `Reindex failed: ${res.status}`)
      }
    } catch (e) {
      addLog('error', `Reindex error: ${e.message}`)
    }
    setLoading(false)
  }

  const handleClearCache = async () => {
    addLog('info', 'Clearing frontend cache...')
    try {
      localStorage.clear()
      sessionStorage.clear()
      addLog('success', 'Frontend cache cleared')
    } catch (e) {
      addLog('error', `Clear cache error: ${e.message}`)
    }
  }

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text)
    setCopied(key)
    setTimeout(() => setCopied(null), 2000)
  }

  return (
    <div className="h-full overflow-y-auto p-6 animate-fade-in">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-red-500 to-orange-500 flex items-center justify-center">
            <Code2 className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-white">Developer Settings</h1>
            <p className="text-sm text-red-400 font-mono">
              Dev session only — not available in production
            </p>
          </div>
        </div>

        {/* Environment Info */}
        <DevSection icon={Server} title="Environment">
          <InfoRow label="Mode" value="development" valueClass="text-red-400" />
          <InfoRow
            label="API Endpoint"
            value={window.location.origin + '/api'}
            copyable
            onCopy={() => copyToClipboard(window.location.origin + '/api', 'api')}
            copied={copied === 'api'}
          />
          <InfoRow
            label="Frontend URL"
            value={window.location.origin}
            copyable
            onCopy={() => copyToClipboard(window.location.origin, 'frontend')}
            copied={copied === 'frontend'}
          />
          <InfoRow label="Vite HMR" value="active" valueClass="text-neon-green" />
        </DevSection>

        {/* Database Info */}
        <DevSection icon={Database} title="Database">
          {dbInfo ? (
            <>
              <InfoRow label="Total Entities" value={
                Object.values(dbInfo.counts || {}).reduce((a, b) => a + b, 0).toString()
              } />
              {Object.entries(dbInfo.counts || {}).map(([key, val]) => (
                <InfoRow key={key} label={key} value={val.toString()} />
              ))}
            </>
          ) : (
            <p className="py-3 text-sm text-slate-500">Loading database info...</p>
          )}
        </DevSection>

        {/* Actions */}
        <DevSection icon={Activity} title="Actions">
          <div className="py-3 space-y-3">
            <DevButton
              icon={RefreshCw}
              label="Reindex Database"
              description="Trigger a full reindex of the knowledge graph"
              onClick={handleReindex}
              loading={loading}
            />
            <DevButton
              icon={Trash2}
              label="Clear Frontend Cache"
              description="Clear localStorage and sessionStorage"
              onClick={handleClearCache}
              variant="warning"
            />
            <DevButton
              icon={RefreshCw}
              label="Refresh All Data"
              description="Force refresh all dashboard data"
              onClick={() => {
                onRefresh?.()
                addLog('info', 'Forced data refresh')
              }}
            />
          </div>
        </DevSection>

        {/* Console Log */}
        <DevSection icon={Terminal} title="Dev Console">
          <div className="py-3">
            {logs.length === 0 ? (
              <p className="text-xs text-slate-600 font-mono">No log entries yet. Perform an action above.</p>
            ) : (
              <div className="space-y-1 max-h-60 overflow-y-auto">
                {logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs font-mono">
                    <span className="text-slate-600 flex-shrink-0">
                      {new Date(log.time).toLocaleTimeString()}
                    </span>
                    <span className={`flex-shrink-0 ${
                      log.level === 'error' ? 'text-red-400' :
                      log.level === 'success' ? 'text-neon-green' :
                      'text-slate-400'
                    }`}>
                      [{log.level}]
                    </span>
                    <span className="text-slate-300">{log.message}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </DevSection>
      </div>
    </div>
  )
}

function DevSection({ icon: Icon, title, children }) {
  return (
    <div className="mb-6 rounded-xl border border-slate-700/50 bg-obsidian/50 overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-700/50 bg-slate-dark/30">
        <Icon className="w-4 h-4 text-red-400" />
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="px-5 divide-y divide-slate-700/30">
        {children}
      </div>
    </div>
  )
}

function InfoRow({ label, value, valueClass = 'text-slate-300', copyable, onCopy, copied }) {
  return (
    <div className="flex items-center justify-between py-2.5">
      <span className="text-sm text-slate-500">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`text-sm font-mono ${valueClass}`}>{value}</span>
        {copyable && (
          <button onClick={onCopy} className="p-1 hover:bg-slate-700 rounded transition-colors">
            {copied ? (
              <Check className="w-3 h-3 text-neon-green" />
            ) : (
              <Copy className="w-3 h-3 text-slate-500" />
            )}
          </button>
        )}
      </div>
    </div>
  )
}

function DevButton({ icon: Icon, label, description, onClick, loading, variant = 'default' }) {
  return (
    <button
      onClick={onClick}
      disabled={loading}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border transition-colors text-left ${
        variant === 'warning'
          ? 'border-amber-700/50 bg-amber-900/10 hover:bg-amber-900/20 hover:border-amber-600/50'
          : 'border-slate-700 bg-slate-dark/50 hover:bg-slate-dark hover:border-slate-600'
      } ${loading ? 'opacity-50 cursor-wait' : ''}`}
    >
      <Icon className={`w-4 h-4 flex-shrink-0 ${loading ? 'animate-spin' : ''} ${
        variant === 'warning' ? 'text-amber-400' : 'text-slate-400'
      }`} />
      <div>
        <p className="text-sm font-medium text-white">{label}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
    </button>
  )
}

