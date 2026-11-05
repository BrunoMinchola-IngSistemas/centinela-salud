import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { notifications } from '../api/resources'
import { IconBell } from './Icons'
import { notify } from '../toasts'

const INTERVALO_MS = 20000

/**
 * Campana de la barra superior: avisos del agente para quien inició
 * sesión (activo nuevo HU05, vencidos HU22, aprobaciones y escalamientos
 * HU24, incidentes HU30, CVE HU03...). Se consulta cada 20 s, así TI
 * recibe la evaluación de un incidente prácticamente en tiempo real;
 * los avisos nuevos además aparecen como toast.
 */
export default function NotificationBell() {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [count, setCount] = useState(0)
  const [items, setItems] = useState([])
  const vistos = useRef(null)
  const caja = useRef(null)

  const refresh = useCallback(async () => {
    try {
      const { data } = await notifications.summary()
      setCount(data.no_leidas)
      const ids = new Set(data.ultimas.map((n) => n.id))
      if (vistos.current) {
        data.ultimas
          .filter((n) => !vistos.current.has(n.id))
          .forEach((n) => notify({ kind: n.nivel === 'critica' ? 'critical' : 'info', title: n.titulo, body: n.mensaje.slice(0, 140) }))
      }
      vistos.current = ids
    } catch {
      // sin conexión: se reintenta en la próxima vuelta
    }
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, INTERVALO_MS)
    return () => clearInterval(id)
  }, [refresh])

  useEffect(() => {
    function fuera(e) {
      if (caja.current && !caja.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', fuera)
    return () => document.removeEventListener('mousedown', fuera)
  }, [])

  async function toggle() {
    const next = !open
    setOpen(next)
    if (next) {
      const { data } = await notifications.list()
      setItems(data.results ?? data)
    }
  }

  async function abrir(n) {
    if (!n.leida) await notifications.read(n.id).catch(() => {})
    setOpen(false)
    refresh()
    if (n.enlace) navigate(n.enlace)
  }

  async function leerTodas() {
    await notifications.readAll()
    setItems((xs) => xs.map((x) => ({ ...x, leida: true })))
    refresh()
  }

  return (
    <div className="bell" ref={caja}>
      <button type="button" onClick={toggle} aria-label={`Notificaciones: ${count} sin leer`} title="Notificaciones">
        <IconBell size={17} />
        {count > 0 && <span className="count">{count > 99 ? '99+' : count}</span>}
      </button>
      {open && (
        <div className="menu" role="menu">
          <div className="ph" style={{ display: 'flex', alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--line)' }}>
            <b style={{ flex: 1 }}>Notificaciones</b>
            {count > 0 && <button className="btn sm" onClick={leerTodas}>Marcar todas como leídas</button>}
          </div>
          {items.length === 0 && <div className="empty">No tienes notificaciones.</div>}
          {items.map((n) => (
            <button key={n.id} className={`item ${n.leida ? '' : 'unread'} ${n.nivel}`} onClick={() => abrir(n)}>
              <b style={{ fontWeight: n.leida ? 400 : 600 }}>{n.titulo}</b>
              <small>{n.mensaje}</small>
              <small>{n.tipo_display} · {new Date(n.creada_en).toLocaleString('es-PE')}</small>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
