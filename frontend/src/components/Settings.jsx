import { useState } from 'react'
import { Settings as SettingsIcon, Monitor, Bell, Database, Palette, Save } from 'lucide-react'

export default function Settings() {
  const [settings, setSettings] = useState({
    theme: 'dark',
    graphAnimation: true,
    showNodeLabels: true,
    notificationsEnabled: true,
    openLoopReminders: true,
    autoRefreshInterval: 30,
    sidebarDefaultOpen: true,
  })

  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }))
  }

  return (
    <div className="h-full overflow-y-auto p-6 animate-fade-in">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-neon-purple to-neon-blue flex items-center justify-center">
            <SettingsIcon className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-display font-bold text-white">Settings</h1>
            <p className="text-sm text-slate-400">Configure your SOML experience</p>
          </div>
        </div>

        {/* Display Settings */}
        <SettingsSection icon={Monitor} title="Display">
          <ToggleSetting
            label="Graph Animations"
            description="Smooth animations in the knowledge graph view"
            value={settings.graphAnimation}
            onChange={(v) => updateSetting('graphAnimation', v)}
          />
          <ToggleSetting
            label="Show Node Labels"
            description="Display labels on graph nodes"
            value={settings.showNodeLabels}
            onChange={(v) => updateSetting('showNodeLabels', v)}
          />
          <ToggleSetting
            label="Sidebar Default Open"
            description="Open sidebar on launch"
            value={settings.sidebarDefaultOpen}
            onChange={(v) => updateSetting('sidebarDefaultOpen', v)}
          />
        </SettingsSection>

        {/* Notification Settings */}
        <SettingsSection icon={Bell} title="Notifications">
          <ToggleSetting
            label="Notifications"
            description="Enable in-app notifications"
            value={settings.notificationsEnabled}
            onChange={(v) => updateSetting('notificationsEnabled', v)}
          />
          <ToggleSetting
            label="Open Loop Reminders"
            description="Remind about unresolved open loops"
            value={settings.openLoopReminders}
            onChange={(v) => updateSetting('openLoopReminders', v)}
          />
        </SettingsSection>

        {/* Data Settings */}
        <SettingsSection icon={Database} title="Data">
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm text-white font-medium">Auto-Refresh Interval</p>
              <p className="text-xs text-slate-500">How often to refresh data (seconds)</p>
            </div>
            <select
              value={settings.autoRefreshInterval}
              onChange={(e) => updateSetting('autoRefreshInterval', parseInt(e.target.value))}
              className="bg-slate-dark border border-slate-700 rounded-lg px-3 py-1.5 text-sm text-white focus:border-neon-purple"
            >
              <option value={10}>10s</option>
              <option value={30}>30s</option>
              <option value={60}>1 min</option>
              <option value={300}>5 min</option>
              <option value={0}>Off</option>
            </select>
          </div>
        </SettingsSection>

        {/* Appearance */}
        <SettingsSection icon={Palette} title="Appearance">
          <div className="flex items-center justify-between py-3">
            <div>
              <p className="text-sm text-white font-medium">Theme</p>
              <p className="text-xs text-slate-500">Application color theme</p>
            </div>
            <div className="flex gap-2">
              {['dark'].map((theme) => (
                <button
                  key={theme}
                  onClick={() => updateSetting('theme', theme)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors ${
                    settings.theme === theme
                      ? 'bg-neon-purple/20 text-neon-purple border border-neon-purple/50'
                      : 'bg-slate-dark text-slate-400 border border-slate-700 hover:border-slate-600'
                  }`}
                >
                  {theme}
                </button>
              ))}
              <button
                disabled
                className="px-3 py-1.5 rounded-lg text-xs font-medium capitalize bg-slate-dark text-slate-600 border border-slate-700 cursor-not-allowed"
              >
                light (soon)
              </button>
            </div>
          </div>
        </SettingsSection>

        <div className="mt-8 flex justify-end">
          <button className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-gradient-to-r from-neon-purple to-neon-blue text-white text-sm font-medium hover:opacity-90 transition-opacity">
            <Save className="w-4 h-4" />
            Save Settings
          </button>
        </div>
      </div>
    </div>
  )
}

function SettingsSection({ icon: Icon, title, children }) {
  return (
    <div className="mb-6 rounded-xl border border-slate-700/50 bg-obsidian/50 overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-slate-700/50 bg-slate-dark/30">
        <Icon className="w-4 h-4 text-neon-purple" />
        <h2 className="text-sm font-semibold text-white">{title}</h2>
      </div>
      <div className="px-5 divide-y divide-slate-700/30">
        {children}
      </div>
    </div>
  )
}

function ToggleSetting({ label, description, value, onChange }) {
  return (
    <div className="flex items-center justify-between py-3">
      <div>
        <p className="text-sm text-white font-medium">{label}</p>
        <p className="text-xs text-slate-500">{description}</p>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative w-10 h-5 rounded-full transition-colors ${
          value ? 'bg-neon-purple' : 'bg-slate-700'
        }`}
      >
        <span
          className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
            value ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
    </div>
  )
}

