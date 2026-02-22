import { createContext, useCallback, useState, type ReactNode } from 'react'

type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  message: string
  type: ToastType
}

export interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void
}

// Exported for use by hooks/useToast.ts only
// eslint-disable-next-line react-refresh/only-export-components
export const ToastContext = createContext<ToastContextValue | null>(null)

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = nextId++
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, 5000)
  }, [])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const typeStyles: Record<ToastType, string> = {
    success: 'bg-green-600',
    error: 'bg-red-600',
    info: 'bg-blue-600',
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`${typeStyles[t.type]} text-white px-4 py-3 rounded-lg shadow-lg max-w-sm flex items-center justify-between gap-3`}
          >
            <span className="text-sm">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="text-white/80 hover:text-white text-lg leading-none"
            >
              &times;
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
