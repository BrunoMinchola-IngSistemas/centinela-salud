/**
 * Antes cada página hacía `.catch(() => ...)` o directamente no tenía
 * `.catch`, así que un 403/500/error de red terminaba mostrando "aún
 * no hay datos" -como si la organización estuviera vacía- en vez de
 * decir que algo falló. Este archivo centraliza cómo se interpreta un
 * error de axios y cómo se muestra, para que sea igual en toda la
 * consola y el motivo real sea visible de un vistazo.
 */

export function extractErrorMessage(error) {
  if (!error) return 'Ocurrió un error inesperado.'

  if (error.response) {
    const { status, data } = error.response
    if (typeof data === 'string' && data.trim()) return data
    if (data && typeof data === 'object') {
      if (typeof data.detail === 'string') return data.detail
      const firstValue = Object.values(data)[0]
      if (Array.isArray(firstValue) && typeof firstValue[0] === 'string') return firstValue[0]
      if (typeof firstValue === 'string') return firstValue
    }
    if (status === 403) return 'No tienes permiso para ver esto (perfil sin organización o rol insuficiente).'
    if (status === 404) return 'No se encontró el recurso solicitado.'
    if (status >= 500) return 'El servidor tuvo un problema al procesar esto. Intenta de nuevo en un momento.'
    return `Error ${status} al comunicarse con el servidor.`
  }

  if (error.request) {
    return import.meta.env.DEV
      ? 'No se pudo conectar con el backend. Verifica que "python manage.py runserver" siga corriendo en el puerto 8000.'
      : 'No se pudo conectar con el servidor. Revisa tu conexión e intenta de nuevo.'
  }

  return error.message || 'Ocurrió un error inesperado.'
}

/** Igual que extractErrorMessage, pero lee el cuerpo cuando la respuesta era un archivo (responseType: 'blob'). */
export async function extractErrorMessageAsync(error) {
  const data = error?.response?.data
  if (data instanceof Blob) {
    try {
      const text = await data.text()
      const json = JSON.parse(text)
      if (typeof json.detail === 'string') return json.detail
      const first = Object.values(json)[0]
      return Array.isArray(first) ? String(first[0]) : String(first ?? text)
    } catch {
      return extractErrorMessage({ response: { status: error.response.status, data: null } })
    }
  }
  return extractErrorMessage(error)
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="empty state-error">
      <div className="state-icon">!</div>
      <p style={{ margin: '0 0 10px' }}>{message}</p>
      {onRetry && (
        <button className="btn sm" onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  )
}

export function LoadingState({ label = 'Cargando…' }) {
  return (
    <div className="empty state-loading">
      <span className="spinner" />
      <span>{label}</span>
    </div>
  )
}

export function EmptyState({ icon = '○', message }) {
  return (
    <div className="empty">
      <div className="state-icon state-icon-mut">{icon}</div>
      <p style={{ margin: 0 }}>{message}</p>
    </div>
  )
}
