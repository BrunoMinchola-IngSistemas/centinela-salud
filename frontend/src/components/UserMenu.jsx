import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { IconLogout, IconMoon, IconSettings, IconShieldCheck, IconSun } from './Icons'
import './UserMenu.css'

/**
 * Círculo con las iniciales del usuario en la barra superior. Al hacer
 * clic despliega un menú con sus datos (rol, organización, correo),
 * el cambio de tema y la salida. Se cierra con Escape o clic afuera.
 */
export default function UserMenu({ profile, theme, onToggleTheme, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function onClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    function onKey(e) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const username = profile?.username || '…'
  const initials = username
    .split(/[._\-\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join('') || '?'
  const role = profile?.role || 'analyst'

  return (
    <div className="umenu" ref={ref}>
      <button
        type="button"
        className={`avatar role-${role} ${open ? 'open' : ''}`}
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Menú de ${username}`}
        title={username}
      >
        {initials}
      </button>

      {open && (
        <div className="umenu-pop" role="menu">
          <div className="umenu-head">
            <span className={`avatar lg role-${role}`} aria-hidden="true">{initials}</span>
            <div className="umenu-id">
              <b>{username}</b>
              <span className={`role-badge role-${role}`}>{profile?.role_display || 'Sin rol'}</span>
            </div>
          </div>

          <dl className="umenu-info">
            <dt>Organización</dt>
            <dd>{profile?.organization?.name || '—'}</dd>
            <dt>Correo</dt>
            <dd>{profile?.email || 'Sin correo registrado'}</dd>
            <dt>Segundo factor</dt>
            <dd className={profile?.mfa_enabled ? 'on' : ''}>
              <IconShieldCheck size={14} />
              {profile?.mfa_enabled ? 'Activado' : 'No configurado'}
            </dd>
          </dl>

          <div className="umenu-sep" />

          <Link to="/configuracion" className="umenu-item" role="menuitem" onClick={() => setOpen(false)}>
            <IconSettings size={16} />
            <span>Configuración</span>
          </Link>
          <button type="button" className="umenu-item" role="menuitem" onClick={onToggleTheme}>
            {theme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
            <span>{theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}</span>
            <small>{theme === 'dark' ? 'Oscuro' : 'Claro'}</small>
          </button>
          <button type="button" className="umenu-item danger" role="menuitem" onClick={onLogout}>
            <IconLogout size={16} />
            <span>Cerrar sesión</span>
          </button>
        </div>
      )}
    </div>
  )
}
