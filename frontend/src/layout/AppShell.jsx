import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import {
  IconAlert, IconBook, IconBrain, IconBug, IconCalendar, IconCheckCircle, IconClock, IconExternal,
  IconFolder, IconGrid, IconKanban, IconList, IconScale, IconServer, IconSettings, IconShield,
} from '../components/Icons'
import UserMenu from '../components/UserMenu'
import { Toaster } from '../components/Toasts'
import { useAlertPolling } from '../alerts'
import { useTheme } from '../theme'
import './AppShell.css'

const NAV = [
  {
    group: 'Operación',
    items: [
      { to: '/', label: 'Panel general', end: true, icon: IconGrid },
      { to: '/vulnerabilidades', label: 'Vulnerabilidades', icon: IconBug },
      { to: '/plan', label: 'Plan de corrección', icon: IconKanban },
      { to: '/verificacion', label: 'Verificación', icon: IconCheckCircle },
    ],
  },
  {
    group: 'Cumplimiento',
    items: [
      { to: '/controles', label: 'Controles ISO 27001', icon: IconBook },
      { to: '/evidencias', label: 'Evidencias', icon: IconFolder },
    ],
  },
  {
    group: 'Gobernanza',
    items: [
      { to: '/gobernanza', label: 'Aprobaciones y autonomía', icon: IconScale },
      { to: '/auditoria', label: 'Registro de auditoría', icon: IconList },
    ],
  },
  {
    group: 'Personal',
    items: [{ to: '/incidentes', label: 'Reportar incidente', icon: IconAlert }],
  },
  {
    group: 'Inventario',
    items: [{ to: '/activos', label: 'Activos', icon: IconServer }],
  },
  {
    group: 'Sistema',
    items: [{ to: '/configuracion', label: 'Configuración', icon: IconSettings }],
  },
]

// API_BASE: en desarrollo el frontend habla con el backend a través
// del proxy de Vite (rutas relativas /api/...), pero el admin de
// Django vive aparte en el puerto 8000, así que ese enlace sí necesita
// la URL completa.
const DJANGO_ADMIN_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/admin/'

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
  const { logout, profile } = useAuth()
  const [theme, setTheme] = useTheme()
  const now = useClock()
  useAlertPolling(profile)

  function toggleTheme() {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }

  const orgName = profile?.organization?.name || 'Cargando organización…'
  const isAdmin = profile?.role === 'admin'

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
          {NAV.map((group) => (
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
          <small>Qwen local · datos de ejemplo</small>
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
