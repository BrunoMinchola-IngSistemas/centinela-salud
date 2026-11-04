import { useEffect, useSyncExternalStore } from 'react'
import { dismiss, dismissLast, getToasts, subscribe } from '../toasts'
import { IconAlert, IconCheckCircle, IconClock, IconScale } from './Icons'
import './Toasts.css'

const ICONS = { critical: IconAlert, overdue: IconClock, approval: IconScale, info: IconCheckCircle }
const EMPTY = []

/** Avisos en la esquina inferior derecha (Configuración > General > Notificaciones). Escape cierra el último. */
export function Toaster() {
  const list = useSyncExternalStore(subscribe, getToasts, () => EMPTY)
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') dismissLast()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
  if (list.length === 0) return null
  return (
    <div className="toasts" role="region" aria-label="Avisos">
      {list.map((t) => {
        const Ico = ICONS[t.kind] || ICONS.info
        return (
          <div key={t.id} className={`toast ${t.kind}`} role="status">
            <Ico size={18} />
            <div className="toast-body">
              <b>{t.title}</b>
              {t.body && <span>{t.body}</span>}
            </div>
            <button type="button" className="toast-x" onClick={() => dismiss(t.id)} aria-label="Cerrar aviso">×</button>
          </div>
        )
      })}
    </div>
  )
}
