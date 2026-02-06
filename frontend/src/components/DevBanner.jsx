import { AlertTriangle } from 'lucide-react'

const isDevMode = import.meta.env.VITE_DEV_MODE === 'true'

export { isDevMode }

export default function DevBanner() {
  if (!isDevMode) return null

  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 h-7 bg-red-600/90 backdrop-blur-sm flex items-center justify-center gap-2 border-t border-red-500 select-none">
      <AlertTriangle className="w-3.5 h-3.5 text-white" />
      <span className="text-xs font-mono font-bold text-white tracking-widest uppercase">
        Dev Mode
      </span>
      <AlertTriangle className="w-3.5 h-3.5 text-white" />
    </div>
  )
}

