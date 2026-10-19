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

export default function AppShell() {
  const { logout } = useAuth()
  const [theme, setTheme] = useState(() => document.documentElement.dataset.theme || 'light')

  function toggleTheme() {
    const next = theme === 'dark' ? 'light' : 'dark'
    document.documentElement.dataset.theme = next
    setTheme(next)
  }

  return (
    <div className="app">
      <header className="top">
        <div className="logo">Centinela Salud</div>
        <div className="org">Clínica San Lucas</div>
        <div className="chips">
          <span className="svc"><i className="dot" />Wazuh</span>
          <span className="svc"><i className="dot" />OpenVAS</span>
        </div>
        <button className="btn sm" onClick={toggleTheme}>{theme === 'dark' ? 'Modo claro' : 'Modo oscuro'}</button>
        <button className="btn sm" onClick={logout}>Salir</button>
      </header>

      <nav className="nav">
        {NAV.map((group) => (
          <div key={group.group}>
            <div className="grp">{group.group}</div>
            {group.items.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end}>
                {item.label}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <main className="work">
        <Outlet />
      </main>
    </div>
  )
}
