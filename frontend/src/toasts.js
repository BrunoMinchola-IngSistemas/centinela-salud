/**
 * Almacén de avisos de la consola. `notify()` encola uno desde
 * cualquier parte (sondeo de alertas, botón "Probar aviso"); el
 * componente <Toaster/> (components/Toasts.jsx) los pinta.
 */
let toasts = []
const listeners = new Set()
let seq = 0

function emit() {
  listeners.forEach((fn) => fn())
}

export function notify({ title, body = '', kind = 'info', ttl = 8000 }) {
  const id = ++seq
  toasts = [...toasts, { id, title, body, kind }]
  emit()
  if (ttl > 0) setTimeout(() => dismiss(id), ttl)
  return id
}

export function dismiss(id) {
  toasts = toasts.filter((t) => t.id !== id)
  emit()
}

export function dismissLast() {
  if (toasts.length) dismiss(toasts[toasts.length - 1].id)
}

export function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function getToasts() {
  return toasts
}
