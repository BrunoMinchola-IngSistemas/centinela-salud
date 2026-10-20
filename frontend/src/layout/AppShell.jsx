import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import './AppShell.css'

const NAV = [
  {
    group: 'Operación',
    items: [
      { to: '/', label: 'Panel general', end: true },
      { to: '/vulnerabilidades', label: 'Vulnerabilidades' },
      { to: '/plan', label: 'Plan de corrección' },
      { to: '/verificacion', label: 'Verificación' },
    ],
  },
  {
    group: 'Cumplimiento',
    items: [
      { to: '/controles', label: 'Controles' },
      { to: '/evidencias', label: 'Evidencias' },
    ],
  },
  {
    group: 'Inventario',
    items: [{ to: '/activos', label: 'Activos' }],
  },
]

// API_BASE: en desarrollo el frontend habla con el backend a través
// del proxy de Vite (rutas relativas /api/...), pero el admin de
// Django vive aparte en el puerto 8000, así que ese enlace sí necesita
// la URL completa.
const DJANGO_ADMIN_URL = (import.meta.env.VITE_API_URL || 'http://localhost:8000') + '/admin/'

export default function AppShell() {
  const { logout, profile } = useAuth()
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    setTheme(next)
  }

  const orgName = profile?.organization?.name || 'Cargando organización…'
  const isAdmin = profile?.role === 'admin'

  const nav = isAdmin
    ? [...NAV, { group: 'Administración', items: [], external: { label: 'Panel de Django (admin)', href: DJANGO_ADMIN_URL } }]
    : NAV

  return (
    <div className="app">
      <header className="top">
        <div className="logo">Centinela Salud</div>
        <div className="org-badge">
          <span className="org">{orgName}</span>
        </div>
        <div className="chips">
          <span className="svc"><i className="dot" />Wazuh</span>
          <span className="svc"><i className="dot" />OpenVAS</span>
        </div>
        {profile && (
          <div className="user-chip">
            <span className="uname">{profile.username}</span>
            <span className="urole">
              <span className="role-badge">{profile.role_display}</span>
            </span>
          </div>
        )}
        <button className="btn sm" onClick={toggleTheme}>{theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}</button>
        <button className="btn sm" onClick={logout}>Salir</button>
      </header>

      <nav className="nav">
        {nav.map((group) => (
          <div key={group.group}>
            <div className="grp">{group.group}</div>
            {group.items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {item.label}
              </NavLink>
            ))}
            {group.external && (
              <a href={group.external.href} target="_blank" rel="noreferrer">
                {group.external.label} ↗
              </a>
            )}
          </div>
        ))}
      </nav>

      <main className="work">
        <Outlet />
      </main>
    </div>
  )
}
