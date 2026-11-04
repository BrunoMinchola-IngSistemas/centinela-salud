import { useSyncExternalStore } from 'react'

/**
 * Preferencias de la consola (Configuración > General). Son por
 * navegador, no por cuenta: se guardan en localStorage y se aplican
 * como atributos data-* en <html>, que es lo que leen los estilos de
 * global.css. Cualquier componente las lee y cambia con usePrefs().
 */
const KEY = 'centinela_prefs'

export const DEFAULTS = {
  theme: 'system', // system | light | dark
  font: 'default', // default | system | mono
  textSize: 'medium', // small | medium | large
  width: 'full', // full | narrow
  motion: 'system', // system | reduced | full
  notifications: {
    inApp: true, // avisos dentro de la consola
    browser: false, // notificaciones del sistema operativo
    sound: false,
    intervalMin: 5, // cada cuánto se revisa (0 = nunca)
    critical: true, // hallazgos críticos nuevos
    overdue: true, // plazos vencidos nuevos
    approvals: true, // aprobaciones pendientes (Administrador)
  },
}

let state = load()
const listeners = new Set()

function load() {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return migrateOldTheme()
    const saved = JSON.parse(raw)
    return { ...DEFAULTS, ...saved, notifications: { ...DEFAULTS.notifications, ...(saved.notifications || {}) } }
  } catch {
    return { ...DEFAULTS }
  }
}

// Antes el tema se guardaba solo, en 'centinela_theme'.
function migrateOldTheme() {
  try {
    const old = localStorage.getItem('centinela_theme')
    if (old === 'light' || old === 'dark') return { ...DEFAULTS, theme: old }
  } catch {
    // sin localStorage
  }
  return { ...DEFAULTS }
}

const media = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null

export function resolveTheme(theme = state.theme) {
  if (theme === 'system') return media && !media.matches ? 'light' : 'dark'
  return theme
}

export function applyPrefs() {
  const html = document.documentElement
  html.dataset.theme = resolveTheme()
  html.dataset.font = state.font
  html.dataset.text = state.textSize
  html.dataset.width = state.width
  html.dataset.motion = state.motion
}

export function getPrefs() {
  return state
}

export function setPrefs(patch) {
  const next = { ...state, ...patch }
  if (patch.notifications) next.notifications = { ...state.notifications, ...patch.notifications }
  state = next
  try {
    localStorage.setItem(KEY, JSON.stringify(state))
  } catch {
    // Sin localStorage (modo privado) las preferencias duran la sesión.
  }
  applyPrefs()
  listeners.forEach((fn) => fn())
}

export function initPrefs() {
  applyPrefs()
  media?.addEventListener?.('change', () => {
    if (state.theme === 'system') {
      state = { ...state } // objeto nuevo para que los suscriptores re-rendericen
      applyPrefs()
      listeners.forEach((fn) => fn())
    }
  })
}

function subscribe(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

export function usePrefs() {
  const prefs = useSyncExternalStore(subscribe, getPrefs, getPrefs)
  return [prefs, setPrefs]
}
