import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  IconAlert, IconBook, IconBrain, IconBug, IconCalendar, IconChat, IconCheckCircle, IconClock, IconExternal,
  IconFileText, IconFolder, IconGauge, IconGrid, IconHistory, IconKanban, IconList, IconMatrix, IconPlug,
  IconScale, IconServer, IconSettings, IconShield,
} from '../components/Icons'
import NotificationBell from '../components/NotificationBell'
import UserMenu from '../components/UserMenu'
import { Toaster } from '../components/Toasts'
import { useAlertPolling } from '../alerts'
import { useTheme } from '../theme'
import './AppShell.css'

// HU28: cada opción pertenece a un módulo; el menú muestra solo los
// módulos del rol (lista que manda el backend en /api/auth/me/).
const NAV = [
  {
    group: 'Gerencia',
    items: [{ to: '/ejecutivo', label: 'Cuadro ejecutivo', icon: IconGauge, modulo: 'ejecutivo' }],
  },
  {
    group: 'Operación',
    items: [
      { to: '/', label: 'Panel general', end: true, icon: IconGrid, modulo: 'panel' },
      { to: '/vulnerabilidades', label: 'Vulnerabilidades', icon: IconBug, modulo: 'vulnerabilidades' },
      { to: '/riesgos', label: 'Matriz de riesgos', icon: IconMatrix, modulo: 'riesgos' },
      { to: '/historial', label: 'Historial y tendencia', icon: IconHistory, modulo: 'vulnerabilidades' },
      { to: '/plan', label: 'Plan de corrección', icon: IconKanban, modulo: 'remediacion' },
      { to: '/verificacion', label: 'Verificación', icon: IconCheckCircle, modulo: 'remediacion' },
      { to: '/asistente', label: 'Asistente', icon: IconChat, modulo: 'asistente' },
    ],
  },
  {
    group: 'Cumplimiento',
    items: [
      { to: '/controles', label: 'Controles ISO 27001', icon: IconBook, modulo: 'controles' },
      { to: '/evidencias', label: 'Evidencias', icon: IconFolder, modulo: 'evidencias' },
      { to: '/reportes', label: 'Reportes', icon: IconFileText, modulo: 'informes' },
    ],
  },
  {
    group: 'Gobernanza',
    items: [
      { to: '/gobernanza', label: 'Aprobaciones y autonomía', icon: IconScale, modulo: 'gobernanza' },
      { to: '/auditoria', label: 'Registro de auditoría', icon: IconList, modulo: 'auditoria' },
    ],
  },
  {
    group: 'Personal',
    items: [{ to: '/incidentes', label: 'Reportar incidente', icon: IconAlert, modulo: 'incidentes' }],
  },
  {
    group: 'Inventario y datos',
    items: [
      { to: '/activos', label: 'Activos', icon: IconServer, modulo: 'activos' },
      { to: '/fuentes', label: 'Fuentes y CVE', icon: IconPlug, modulo: 'integraciones' },
    ],
  },
  {
    group: 'Sistema',
    items: [{ to: '/configuracion', label: 'Configuración', icon: IconSettings, modulo: 'configuracion' }],
  },
]

// El admin de Django: en desarrollo vive en el puerto 8000; en la nube,
// si está habilitado, en el mismo dominio (Caddy reenvía /admin/).
const DJANGO_ADMIN_URL = import.meta.env.DEV ? 'http://localhost:8000/admin/' : `${import.meta.env.VITE_API_URL || ''}/admin/`

// Reloj de la barra superior: se actualiza cada segundo mientras la
// consola esté abierta, como en un centro de operaciones.
function useClock() {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

export default function AppShell() {
  const { logout, profile, can } = useAuth()
  const [theme, setTheme] = useTheme()
  const now = useClock()
  useAlertPolling(profile)

  function toggleTheme() {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const orgName = profile?.organization?.name || 'Cargando organización…'
  const isAdmin = Boolean(profile?.admin_django)
  const grupos = NAV.map((g) => ({ ...g, items: g.items.filter((i) => can(i.modulo)) })).filter((g) => g.items.length)

  const time = now.toLocaleTimeString('es-PE', { hour12: false })
  const date = now.toLocaleDateString('es-PE', { day: '2-digit', month: 'short', year: 'numeric' })

  return (
    <div className="app">
      <aside className="nav">
        <div className="brand">
          <span className="brand-mark"><IconShield size={22} /></span>
          <span className="brand-text">
            <b>CENTINELA<span>SALUD</span></b>
            <small>Protección inteligente</small>
          </span>
        </div>

        <div className="nav-groups">
          {grupos.map((group) => (
            <div key={group.group} className="nav-group">
              <div className="grp">{group.group}</div>
              {group.items.map((item) => {
                const Ico = item.icon
                return (
                  <NavLink key={item.to} to={item.to} end={item.end}>
                    <Ico />
                    <span>{item.label}</span>
                  </NavLink>
                )
              })}
            </div>
          ))}
          {isAdmin && (
            <div className="nav-group">
              <div className="grp">Administración</div>
              <a href={DJANGO_ADMIN_URL} target="_blank" rel="noreferrer">
                <IconExternal />
                <span>Panel de Django (admin)</span>
              </a>
            </div>
          )}
        </div>

        <div className="engine">
          <div className="engine-head">
            <span>Motor IA</span>
            <i className="dot" />
          </div>
          <div className="engine-icon"><IconBrain size={30} /></div>
          <b>ACTIVO</b>
          <small>Reglas R1-R5 · SVM · Qwen</small>
        </div>
      </aside>

      <header className="top">
        <div className="org-badge">
          <span className="org-label">Organización</span>
          <span className="org">{orgName}</span>
        </div>

        <div className="top-right">
          <span className="meta"><IconClock size={15} /><span className="mono">{time}</span></span>
          <span className="meta"><IconCalendar size={15} />{date}</span>
          <div className="chips">
            <span className="svc"><i className="dot" />Wazuh</span>
            <span className="svc"><i className="dot" />OpenVAS</span>
          </div>
          <NotificationBell />
          <UserMenu profile={profile} theme={theme} onToggleTheme={toggleTheme} onLogout={logout} />
        </div>
      </header>

      <main className="work">
        {profile?.role === 'auditor' && (
          <div className="readonly-banner">
            Modo auditor: puedes ver toda la información de la organización, pero no modificar nada.
          </div>
        )}
        <Outlet />
      </main>
      <Toaster />
    </div>
  )
}
