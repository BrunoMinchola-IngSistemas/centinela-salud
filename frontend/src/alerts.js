import { useEffect, useRef } from 'react'
import { dashboard, governance } from './api/resources'
import { notify } from './toasts'
import { usePrefs } from './prefs'

/**
 * Sondeo de alertas según Configuración > General > Notificaciones:
 * cada N minutos pide el resumen del panel (y, para el Administrador,
 * las solicitudes de aprobación) y avisa si aparecieron hallazgos
 * críticos, plazos vencidos o aprobaciones pendientes nuevas. La
 * primera lectura solo fija la línea base para no avisar de lo que ya
 * se veía al entrar.
 */
export function useAlertPolling(profile) {
  const [prefs] = usePrefs()
  const n = prefs.notifications
  const baseline = useRef(null)

  useEffect(() => {
    if (!profile || !n.intervalMin || (!n.inApp && !n.browser)) return undefined
    let cancelled = false

    async function check() {
      try {
        const { data } = await dashboard.summary()
        let pending = null
        if (n.approvals && profile.role === 'admin') {
          const r = await governance.requests()
          pending = (r.data.results ?? r.data).filter((s) => s.estado === 'pendiente').length
        }
        if (cancelled) return
        const now = { critical: data.critical_open, overdue: data.overdue_count, pending }
        const before = baseline.current
        baseline.current = now
        if (!before) return

        const avisos = []
        if (n.critical && now.critical > before.critical) {
          avisos.push({ kind: 'critical', title: 'Nuevos hallazgos críticos', body: `${now.critical - before.critical} crítico(s) más sin corregir.` })
        }
        if (n.overdue && now.overdue > before.overdue) {
          avisos.push({ kind: 'overdue', title: 'Plazos vencidos', body: `${now.overdue} plan(es) de corrección fuera de plazo.` })
        }
        if (pending != null && before.pending != null && pending > before.pending) {
          avisos.push({ kind: 'approval', title: 'Aprobación pendiente', body: `${pending} solicitud(es) esperando decisión de Gerencia.` })
        }
        avisos.forEach((a) => emitir(a, n))
      } catch {
        // Sin conexión con el backend: se reintenta en el próximo ciclo.
      }
    }

    check()
    const id = setInterval(check, n.intervalMin * 60 * 1000)
    return () => {
      cancelled = true
      clearInterval(id)
    }
  }, [profile, n])
}

function emitir(aviso, n) {
  if (n.inApp) notify(aviso)
  if (n.browser && typeof Notification !== 'undefined' && Notification.permission === 'granted' && document.hidden) {
    try {
      new Notification(`Centinela Salud · ${aviso.title}`, { body: aviso.body })
    } catch {
      // Algunos navegadores exigen un service worker; se ignora.
    }
  }
  if (n.sound) beep()
}

function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.value = 0.05
    osc.connect(gain).connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.18)
  } catch {
    // Sin audio disponible.
  }
}

/** Pide permiso para notificaciones del navegador; devuelve si quedó concedido. */
export async function pedirPermisoNavegador() {
  if (typeof Notification === 'undefined') return false
  if (Notification.permission === 'granted') return true
  if (Notification.permission === 'denied') return false
  const r = await Notification.requestPermission()
  return r === 'granted'
}
