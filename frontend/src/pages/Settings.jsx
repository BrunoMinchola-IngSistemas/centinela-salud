import { Fragment, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { audit, auth, governance, integrations, members, organization, sources } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import {
  IconBell, IconBuilding, IconKey, IconList, IconMonitor, IconMoon, IconPlug, IconRefresh, IconScale, IconSettings, IconShieldCheck,
  IconSun, IconUser, IconUserPlus, IconUsers,
} from '../components/Icons'
import Select from '../components/Select'
import { ACCION_LABEL, MOD_BADGE, MOD_LABEL } from '../auditLabels'
import { notify } from '../toasts'
import { pedirPermisoNavegador } from '../alerts'
import { usePrefs } from '../prefs'
import './Settings.css'

const ALL = ['admin', 'analyst', 'it_owner', 'compliance', 'staff', 'auditor']

/**
 * Qué secciones ve cada rol y cuáles puede editar. El Auditor ve las
 * mismas secciones que el Administrador pero en solo lectura ("ve
 * todo, no cambia nada"); el Analista solo gestiona su propia cuenta;
 * TI además administra las fuentes e integraciones.
 */
const SECTIONS = [
  { key: 'general', label: 'General', desc: 'Apariencia y notificaciones', icon: IconSettings, roles: ALL, editors: ALL },
  { key: 'cuenta', label: 'Mi cuenta', desc: 'Correo, contraseña y segundo factor', icon: IconUser, roles: ALL, editors: ALL },
  { key: 'organizacion', label: 'Organización', desc: 'Datos, red, madurez, reportes y escalamiento', icon: IconBuilding, roles: ['admin', 'it_owner', 'compliance', 'auditor'], editors: ['admin', 'it_owner', 'compliance'] },
  { key: 'usuarios', label: 'Usuarios y roles', desc: 'Quién accede y con qué permisos', icon: IconUsers, roles: ['admin', 'auditor'], editors: ['admin'] },
  { key: 'integraciones', label: 'Integraciones', desc: 'Wazuh, OpenVAS, Qwen y fuentes', icon: IconPlug, roles: ['admin', 'it_owner', 'auditor'], editors: ['admin', 'it_owner'] },
  { key: 'autonomia', label: 'Autonomía del agente', desc: 'Qué hace solo y qué requiere aprobación', icon: IconScale, roles: ['admin', 'auditor'], editors: ['admin'] },
  { key: 'auditoria', label: 'Auditoría', desc: 'Quién hizo qué, con filtros', icon: IconList, roles: ['admin', 'auditor'], editors: ['admin', 'auditor'] },
]

const ROLE_LABEL = {
  admin: 'Administrador (Gerencia)',
  it_owner: 'Responsable de TI',
  compliance: 'Oficial de Cumplimiento',
  staff: 'Personal administrativo / clínico',
  analyst: 'Analista de seguridad',
  auditor: 'Auditor',
}
const ROLE_OPTIONS = Object.entries(ROLE_LABEL).map(([value, label]) => ({ value, label }))

export default function Settings() {
  const { profile } = useAuth()
  const role = profile?.role
  const visible = SECTIONS.filter((s) => s.roles.includes(role))
  const [active, setActive] = useState('general')

  if (!profile) return <LoadingState label="Cargando configuración…" />
  const section = visible.find((s) => s.key === active) || visible[0]
  const canEdit = section.editors.includes(role)

  return (
    <div>
      <div className="page-head">
        <h1>Configuración</h1>
        <p>
          Opciones disponibles para tu rol: <span className={`role-badge role-${role}`}>{profile.role_display}</span>
          {role === 'auditor' && <span className="muted"> · solo lectura</span>}
        </p>
      </div>

      <div className="settings">
        <nav className="settings-nav" aria-label="Secciones de configuración">
          {visible.map((s) => {
            const Ico = s.icon
            return (
              <button key={s.key} type="button" className={`settings-tab ${s.key === active ? 'on' : ''}`} onClick={() => setActive(s.key)}>
                <Ico size={18} />
                <span><b>{s.label}</b><small>{s.desc}</small></span>
                {!s.editors.includes(role) && <em className="badge b-mut">Lectura</em>}
              </button>
            )
          })}
        </nav>

        <div className="settings-body">
          {section.key === 'general' && <GeneralSection />}
          {section.key === 'cuenta' && <AccountSection />}
          {section.key === 'organizacion' && <OrganizationSection canEdit={canEdit} />}
          {section.key === 'usuarios' && <MembersSection canEdit={canEdit} />}
          {section.key === 'integraciones' && <IntegrationsSection canEdit={canEdit} />}
          {section.key === 'autonomia' && <AutonomySection canEdit={canEdit} />}
          {section.key === 'auditoria' && <AuditSection />}
        </div>
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- Mi cuenta */
function AccountSection() {
  const { profile, reloadProfile } = useAuth()
  const [email, setEmail] = useState(profile.email || '')
  const [emailMsg, setEmailMsg] = useState(null)
  const [pw, setPw] = useState({ actual: '', nueva: '', repetir: '' })
  const [pwMsg, setPwMsg] = useState(null)
  const [busy, setBusy] = useState('')

  async function saveEmail(e) {
    e.preventDefault()
    setBusy('email')
    setEmailMsg(null)
    try {
      await auth.updateMe({ email })
      await reloadProfile()
      setEmailMsg({ ok: true, text: 'Correo actualizado.' })
    } catch (err) {
      setEmailMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy('')
    }
  }

  async function savePassword(e) {
    e.preventDefault()
    setPwMsg(null)
    if (pw.nueva !== pw.repetir) {
      setPwMsg({ ok: false, text: 'La contraseña nueva y su repetición no coinciden.' })
      return
    }
    setBusy('pw')
    try {
      await auth.changePassword(pw.actual, pw.nueva)
      setPw({ actual: '', nueva: '', repetir: '' })
      setPwMsg({ ok: true, text: 'Contraseña actualizada. Úsala la próxima vez que ingreses.' })
    } catch (err) {
      setPwMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy('')
    }
  }

  const set = (k) => (e) => setPw({ ...pw, [k]: e.target.value })

  return (
    <>
      <section className="panel">
        <div className="ph"><h2>Datos de la cuenta</h2></div>
        <form className="pb settings-form" onSubmit={saveEmail}>
          <div className="settings-grid">
            <label className="field"><span>Usuario</span><input value={profile.username} disabled /></label>
            <label className="field"><span>Rol</span><input value={profile.role_display} disabled /></label>
            <label className="field"><span>Organización</span><input value={profile.organization?.name || ''} disabled /></label>
            <label className="field"><span>Correo</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@clinica.pe" /></label>
          </div>
          <Msg msg={emailMsg} />
          <div className="settings-actions">
            <button className="btn pri" disabled={busy === 'email' || email === (profile.email || '')}>{busy === 'email' ? 'Guardando…' : 'Guardar correo'}</button>
          </div>
        </form>
      </section>

      <section className="panel">
        <div className="ph"><h2>Contraseña</h2><span className="r">Mínimo 10 caracteres, que no sea común ni solo números</span></div>
        <form className="pb settings-form" onSubmit={savePassword}>
          <div className="settings-grid">
            <label className="field"><span>Contraseña actual</span><input type="password" autoComplete="current-password" required value={pw.actual} onChange={set('actual')} /></label>
            <span />
            <label className="field"><span>Contraseña nueva</span><input type="password" autoComplete="new-password" required minLength={8} value={pw.nueva} onChange={set('nueva')} /></label>
            <label className="field"><span>Repetir contraseña nueva</span><input type="password" autoComplete="new-password" required minLength={8} value={pw.repetir} onChange={set('repetir')} /></label>
          </div>
          <Msg msg={pwMsg} />
          <div className="settings-actions">
            <button className="btn pri" disabled={busy === 'pw'}><IconKey size={15} />{busy === 'pw' ? 'Cambiando…' : 'Cambiar contraseña'}</button>
          </div>
        </form>
      </section>

      <MfaSection />
    </>
  )
}

/* --------------------------------------------------------- Segundo factor (HU29) */
function MfaSection() {
  const { profile, reloadProfile } = useAuth()
  const [setup, setSetup] = useState(null)
  const [code, setCode] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  async function iniciar() {
    setMsg(null)
    setBusy(true)
    try {
      setSetup((await auth.mfaStart()).data)
    } catch (err) {
      setMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  async function confirmar(e, activar) {
    e.preventDefault()
    setMsg(null)
    setBusy(true)
    try {
      if (activar) await auth.mfaActivate(code)
      else await auth.mfaDeactivate(code)
      setSetup(null)
      setCode('')
      await reloadProfile()
      setMsg({ ok: true, text: activar ? 'Segundo factor activado. Desde ahora te pedirá el código al ingresar.' : 'Segundo factor desactivado.' })
    } catch (err) {
      setMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy(false)
    }
  }

  const activo = profile.mfa_enabled
  return (
    <section className="panel">
      <div className="ph"><h2>Segundo factor (MFA)</h2><span className="r">App autenticadora (Google/Microsoft Authenticator, Authy)</span></div>
      <div className="pb settings-form">
        <div className="settings-row">
          <IconShieldCheck size={22} style={{ color: activo ? 'var(--ok)' : 'var(--muted)' }} />
          <div>
            <b>{activo ? 'Activado' : 'No activado'}</b>
            <p className="muted">Además de la contraseña, se pide un código de 6 dígitos que cambia cada 30 segundos. Tras 5 intentos fallidos la cuenta se bloquea 15 minutos.</p>
          </div>
        </div>
        {!activo && !setup && <div className="settings-actions"><button className="btn pri" onClick={iniciar} disabled={busy}>Configurar segundo factor</button></div>}
        {!activo && setup && (
          <form onSubmit={(e) => confirmar(e, true)} style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <span className="qr-box"><img src={setup.qr} alt="Código QR para la app autenticadora" width="180" height="180" /></span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, minWidth: 220 }}>
              <span className="small">1. Escanea el QR con tu app. ¿No puedes? Ingresa esta clave: <span className="mono">{setup.secreto}</span></span>
              <label className="field">2. Escribe el código que muestra la app
                <input className="mono" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} required />
              </label>
              <button className="btn pri" disabled={busy || code.length !== 6}>Activar</button>
            </div>
          </form>
        )}
        {activo && (
          <form onSubmit={(e) => confirmar(e, false)} className="row-actions">
            <input className="mono" inputMode="numeric" placeholder="Código actual" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} required />
            <button className="btn" disabled={busy || code.length !== 6}>Desactivar segundo factor</button>
          </form>
        )}
        <Msg msg={msg} />
      </div>
    </section>
  )
}

/* ------------------------------------------------------------------ General */
const THEME_OPTIONS = [
  ['system', 'Sistema', IconMonitor],
  ['light', 'Claro', IconSun],
  ['dark', 'Oscuro', IconMoon],
]
const INTERVALOS = [[0, 'Desactivado'], [1, 'Cada minuto'], [5, 'Cada 5 minutos'], [15, 'Cada 15 minutos'], [60, 'Cada hora']]

function PrefRow({ label, hint, children }) {
  return (
    <div className="pref-row">
      <div className="pref-label"><b>{label}</b>{hint && <small>{hint}</small>}</div>
      <div className="pref-control">{children}</div>
    </div>
  )
}

function Toggle({ on, onChange, label, disabled }) {
  return (
    <button type="button" className={`switch ${on ? 'on' : ''}`} role="switch" aria-checked={on} aria-label={label} disabled={disabled} onClick={() => onChange(!on)}>
      <i />
    </button>
  )
}

function GeneralSection() {
  const { profile } = useAuth()
  const [prefs, setPrefs] = usePrefs()
  const n = prefs.notifications
  const setN = (patch) => setPrefs({ notifications: patch })
  const permisoNavegador = typeof Notification !== 'undefined' ? Notification.permission : 'unsupported'

  async function toggleBrowser(on) {
    if (!on) return setN({ browser: false })
    const ok = await pedirPermisoNavegador()
    setN({ browser: ok })
    if (!ok) notify({ kind: 'info', title: 'Sin permiso del navegador', body: 'Permite las notificaciones para este sitio en la configuración del navegador.' })
  }

  return (
    <>
      <section className="panel">
        <div className="ph"><h2>Apariencia</h2><span className="r">Se guarda en este navegador</span></div>
        <div className="pref-list">
          <PrefRow label="Tema">
            <div className="segmented" role="radiogroup" aria-label="Tema">
              {THEME_OPTIONS.map(([v, l, Ico]) => (
                <button key={v} type="button" role="radio" aria-checked={prefs.theme === v} className={prefs.theme === v ? 'on' : ''} title={l} onClick={() => setPrefs({ theme: v })}>
                  <Ico size={15} />
                </button>
              ))}
            </div>
          </PrefRow>
          <PrefRow label="Fuente de la interfaz">
            <Select align="right" aria-label="Fuente de la interfaz" value={prefs.font} onChange={(font) => setPrefs({ font })} options={[
              { value: 'default', label: 'Predeterminada · Inter' }, { value: 'system', label: 'Sistema' }, { value: 'mono', label: 'Monoespaciada' },
            ]} />
          </PrefRow>
          <PrefRow label="Tamaño del texto">
            <Select align="right" aria-label="Tamaño del texto" value={prefs.textSize} onChange={(textSize) => setPrefs({ textSize })} options={[
              { value: 'small', label: 'Pequeño' }, { value: 'medium', label: 'Medio' }, { value: 'large', label: 'Grande' },
            ]} />
          </PrefRow>
          <PrefRow label="Ancho del contenido" hint="En pantallas anchas, centra el contenido o lo extiende a todo el ancho.">
            <Select align="right" aria-label="Ancho del contenido" value={prefs.width} onChange={(width) => setPrefs({ width })} options={[
              { value: 'full', label: 'Completo' }, { value: 'narrow', label: 'Estrecho' },
            ]} />
          </PrefRow>
          <PrefRow label="Movimiento" hint="Animaciones del escudo, brillos y transiciones.">
            <Select align="right" aria-label="Movimiento" value={prefs.motion} onChange={(motion) => setPrefs({ motion })} options={[
              { value: 'system', label: 'Sistema' }, { value: 'full', label: 'Completo' }, { value: 'reduced', label: 'Reducido' },
            ]} />
          </PrefRow>
        </div>
      </section>

      <section className="panel">
        <div className="ph"><h2>Notificaciones</h2><IconBell size={16} style={{ color: 'var(--brand)' }} /></div>
        <div className="pref-list">
          <PrefRow label="Avisos en la consola" hint="Mensajes emergentes en la esquina inferior mientras la consola está abierta.">
            <Toggle on={n.inApp} onChange={(v) => setN({ inApp: v })} label="Avisos en la consola" />
          </PrefRow>
          <PrefRow label="Notificaciones del navegador" hint={permisoNavegador === 'denied' ? 'Bloqueadas por el navegador para este sitio.' : 'Aviso del sistema cuando la pestaña está en segundo plano.'}>
            <Toggle on={n.browser} onChange={toggleBrowser} label="Notificaciones del navegador" disabled={permisoNavegador === 'unsupported' || permisoNavegador === 'denied'} />
          </PrefRow>
          <PrefRow label="Sonido" hint="Un tono corto al llegar un aviso.">
            <Toggle on={n.sound} onChange={(v) => setN({ sound: v })} label="Sonido" />
          </PrefRow>
          <PrefRow label="Frecuencia de revisión" hint="Cada cuánto se consulta el estado de la organización.">
            <Select align="right" aria-label="Frecuencia de revisión" value={n.intervalMin} onChange={(v) => setN({ intervalMin: Number(v) })} options={INTERVALOS.map(([value, label]) => ({ value, label }))} />
          </PrefRow>
          <PrefRow label="Hallazgos críticos nuevos">
            <Toggle on={n.critical} onChange={(v) => setN({ critical: v })} label="Avisar de hallazgos críticos nuevos" />
          </PrefRow>
          <PrefRow label="Plazos vencidos">
            <Toggle on={n.overdue} onChange={(v) => setN({ overdue: v })} label="Avisar de plazos vencidos" />
          </PrefRow>
          {profile.role === 'admin' && (
            <PrefRow label="Aprobaciones pendientes" hint="Solicitudes de alto impacto que esperan decisión de Gerencia.">
              <Toggle on={n.approvals} onChange={(v) => setN({ approvals: v })} label="Avisar de aprobaciones pendientes" />
            </PrefRow>
          )}
        </div>
        <div className="pref-note" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
          <span>Los avisos comparan cada revisión con la anterior: solo avisan de lo que cambió.</span>
          <button type="button" className="btn sm" onClick={() => notify({ kind: 'critical', title: 'Aviso de prueba', body: 'Así se verá un aviso en la consola.' })}>Probar aviso</button>
        </div>
      </section>
    </>
  )
}

/* ------------------------------------------------------------- Organización */
const CAMPOS_POR_ROL = {
  admin: null,
  it_owner: ['rango_red', 'ejecucion_autonoma_activa'],
  compliance: ['nivel_madurez', 'periodicidad_reporte'],
}
const MADUREZ = [['', 'Sin registrar'], ['1', '1 · Inicial'], ['2', '2 · Gestionado'], ['3', '3 · Definido'], ['4', '4 · Medido'], ['5', '5 · Optimizado']]

function OrganizationSection({ canEdit }) {
  const { reloadProfile, profile } = useAuth()
  const permitidos = CAMPOS_POR_ROL[profile.role]
  const puede = (campo) => canEdit && (permitidos === null || (permitidos || []).includes(campo))
  const [miembros, setMiembros] = useState([])
  const [form, setForm] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState(null)
  const [saving, setSaving] = useState(false)

  function load() {
    setError('')
    organization
      .get()
      .then((r) => setForm({
        name: r.data.name,
        ruc: r.data.ruc || '',
        rango_red: r.data.rango_red || '',
        nivel_madurez: r.data.nivel_madurez ? String(r.data.nivel_madurez) : '',
        periodicidad_reporte: r.data.periodicidad_reporte || '',
        responsable_escalamiento: r.data.responsable_escalamiento ? String(r.data.responsable_escalamiento) : '',
        ejecucion_autonoma_activa: r.data.ejecucion_autonoma_activa,
      }))
      .catch((err) => setError(extractErrorMessage(err)))
    members.list().then((r) => setMiembros(r.data.results ?? r.data)).catch(() => {})
  }
  useEffect(load, [])

  async function save(e) {
    e.preventDefault()
    setSaving(true)
    setMsg(null)
    try {
      const payload = {}
      Object.entries(form).forEach(([k, v]) => {
        if (!puede(k)) return
        if (k === 'nivel_madurez' || k === 'responsable_escalamiento') payload[k] = v ? Number(v) : null
        else payload[k] = v
      })
      await organization.update(payload)
      await reloadProfile()
      setMsg({ ok: true, text: 'Datos de la organización guardados.' })
    } catch (err) {
      setMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setSaving(false)
    }
  }

  if (error) return <div className="panel"><ErrorState message={error} onRetry={load} /></div>
  if (!form) return <div className="panel"><LoadingState /></div>

  return (
    <section className="panel">
      <div className="ph"><h2>Datos y ajustes de la organización</h2><span className="r">Cada rol edita lo suyo: Gerencia todo; TI red y autonomía; Cumplimiento madurez y reportes</span></div>
      <form className="pb settings-form" onSubmit={save}>
        <div className="settings-grid">
          <label className="field"><span>Nombre</span><input required maxLength={150} value={form.name} disabled={!puede('name')} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
          <label className="field"><span>RUC / identificador fiscal</span><input maxLength={20} value={form.ruc} disabled={!puede('ruc')} onChange={(e) => setForm({ ...form, ruc: e.target.value })} /></label>
          <label className="field"><span>Rango de red para descubrimiento (HU01)</span><input className="mono" placeholder="10.10.1.0/24" value={form.rango_red} disabled={!puede('rango_red')} onChange={(e) => setForm({ ...form, rango_red: e.target.value })} /></label>
          <label className="field"><span>Nivel de madurez de seguridad (HU12)</span>
            <select value={form.nivel_madurez} disabled={!puede('nivel_madurez')} onChange={(e) => setForm({ ...form, nivel_madurez: e.target.value })}>
              {MADUREZ.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field"><span>Periodicidad del reporte automático (HU21)</span>
            <select value={form.periodicidad_reporte} disabled={!puede('periodicidad_reporte')} onChange={(e) => setForm({ ...form, periodicidad_reporte: e.target.value })}>
              <option value="">Sin configurar</option><option value="semanal">Semanal</option><option value="mensual">Mensual</option>
            </select>
          </label>
          <label className="field"><span>Segundo responsable para escalar aprobaciones (HU24)</span>
            <select value={form.responsable_escalamiento} disabled={!puede('responsable_escalamiento')} onChange={(e) => setForm({ ...form, responsable_escalamiento: e.target.value })}>
              <option value="">Automático (primer Responsable de TI)</option>
              {miembros.map((m) => <option key={m.id} value={m.user_id ?? ''} disabled={!m.user_id}>{m.username} · {m.role_display}</option>)}
            </select>
          </label>
          <label className="field" style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <input type="checkbox" checked={form.ejecucion_autonoma_activa} disabled={!puede('ejecucion_autonoma_activa')} onChange={(e) => setForm({ ...form, ejecucion_autonoma_activa: e.target.checked })} style={{ width: 'auto' }} />
            <span>Ejecución autónoma de acciones de bajo riesgo (HU18)</span>
          </label>
        </div>
        <Msg msg={msg} />
        {canEdit && (
          <div className="settings-actions">
            <button className="btn pri" disabled={saving}>{saving ? 'Guardando…' : 'Guardar cambios'}</button>
          </div>
        )}
      </form>
    </section>
  )
}

/* ------------------------------------------------------------------ Usuarios */
const NUEVO_USUARIO = { username: '', email: '', password: '', role: 'analyst' }

function MembersSection({ canEdit }) {
  const { profile } = useAuth()
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState(NUEVO_USUARIO)
  const [resetFor, setResetFor] = useState(null)
  const [resetPw, setResetPw] = useState('')

  function load() {
    setLoading(true)
    setError('')
    members.list().then((r) => setList(r.data.results ?? r.data)).catch((err) => setError(extractErrorMessage(err))).finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function run(id, fn, okText) {
    setBusy(id)
    setMsg(null)
    try {
      await fn()
      if (okText) setMsg({ ok: true, text: okText })
      load()
    } catch (err) {
      setMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy(null)
    }
  }

  async function create(e) {
    e.preventDefault()
    await run('create', () => members.create(form), `Usuario ${form.username} creado.`)
    setForm(NUEVO_USUARIO)
    setShowForm(false)
  }

  async function reset(e) {
    e.preventDefault()
    const m = resetFor
    await run(m.id, () => members.resetPassword(m.id, resetPw), `Contraseña de ${m.username} restablecida.`)
    setResetFor(null)
    setResetPw('')
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <>
      {canEdit && showForm && (
        <section className="panel">
          <div className="ph"><h2>Nuevo usuario</h2></div>
          <form className="pb settings-form" onSubmit={create}>
            <div className="settings-grid">
              <label className="field"><span>Usuario</span><input required minLength={3} maxLength={150} pattern="[\w.@+\-]+" value={form.username} onChange={set('username')} placeholder="ej. jperez" /></label>
              <label className="field"><span>Correo</span><input type="email" value={form.email} onChange={set('email')} placeholder="nombre@clinica.pe" /></label>
              <label className="field"><span>Contraseña inicial</span><input type="password" required minLength={8} autoComplete="new-password" value={form.password} onChange={set('password')} /></label>
              <div className="field">
                <span>Rol</span>
                <Select aria-label="Rol" value={form.role} onChange={(role) => setForm({ ...form, role })} options={ROLE_OPTIONS} />
              </div>
            </div>
            <p className="muted" style={{ margin: 0, fontSize: 12.5 }}>La cuenta queda en tu organización. Entrega la contraseña inicial por un canal seguro; la persona puede cambiarla desde Mi cuenta.</p>
            <div className="settings-actions">
              <button type="button" className="btn" onClick={() => { setShowForm(false); setForm(NUEVO_USUARIO) }}>Cancelar</button>
              <button className="btn pri" disabled={busy === 'create'}><IconUserPlus size={15} />{busy === 'create' ? 'Creando…' : 'Crear usuario'}</button>
            </div>
          </form>
        </section>
      )}

      <section className="panel">
        <div className="ph">
          <h2>Usuarios de la organización</h2>
          <span className="r">{list.length} cuentas</span>
          {canEdit && !showForm && (
            <button className="btn sm pri" onClick={() => setShowForm(true)}><IconUserPlus size={14} />Nuevo usuario</button>
          )}
        </div>
        {msg && <div style={{ padding: '10px 14px 0' }}><Msg msg={msg} /></div>}
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && (
          <table>
            <thead><tr><th>Usuario</th><th>Correo</th><th>Rol</th><th>Último acceso</th><th>Estado</th>{canEdit && <th></th>}</tr></thead>
            <tbody>
              {list.map((m) => {
                const esYo = m.username === profile.username
                const editable = canEdit && !esYo
                return (
                  <Fragment key={m.id}>
                    <tr style={{ opacity: m.is_active ? 1 : 0.6 }}>
                      <td><b style={{ fontWeight: 500 }}>{m.username}</b>{esYo && <span className="badge b-br" style={{ marginLeft: 6 }}>Tú</span>}</td>
                      <td className="muted">{m.email || '—'}</td>
                      <td>
                        {editable ? (
                          <Select size="sm" aria-label={`Rol de ${m.username}`} value={m.role} disabled={busy === m.id} onChange={(role) => run(m.id, () => members.updateRole(m.id, role))} options={ROLE_OPTIONS} />
                        ) : (
                          <span className={`role-badge role-${m.role}`}>{m.role_display}</span>
                        )}
                      </td>
                      <td className="muted">
                        {m.last_login ? new Date(m.last_login).toLocaleString('es-PE') : 'Nunca'}
                        <div>
                          {m.mfa_enabled && <span className="badge b-ok" style={{ marginRight: 4 }}>MFA</span>}
                          {m.bloqueado && <span className="badge b-crit">Bloqueada</span>}
                        </div>
                      </td>
                      <td>
                        {editable ? (
                          <button type="button" className={`switch ${m.is_active ? 'on' : ''}`} role="switch" aria-checked={m.is_active} disabled={busy === m.id} title={m.is_active ? 'Desactivar cuenta' : 'Activar cuenta'} aria-label={`${m.is_active ? 'Desactivar' : 'Activar'} ${m.username}`} onClick={() => run(m.id, () => members.setActive(m.id, !m.is_active))}><i /></button>
                        ) : (
                          m.is_active ? <span className="badge b-ok">Activa</span> : <span className="badge b-crit">Inactiva</span>
                        )}
                      </td>
                      {canEdit && (
                        <td style={{ textAlign: 'right' }}>
                          {editable && (m.bloqueado || m.mfa_enabled) && (
                            <button className="btn sm" disabled={busy === m.id} title="Desbloquea la cuenta y, si se confirma, quita el segundo factor (p. ej. celular perdido)"
                              onClick={() => run(m.id, () => members.resetSecurity(m.id, m.mfa_enabled && window.confirm(`¿Quitar también el segundo factor de ${m.username}?`)))}>
                              Desbloquear
                            </button>
                          )}{' '}
                          {editable && (
                            <button className="btn sm" disabled={busy === m.id} onClick={() => { setResetFor(resetFor?.id === m.id ? null : m); setResetPw('') }}>
                              <IconKey size={13} />Clave
                            </button>
                          )}
                        </td>
                      )}
                    </tr>
                    {resetFor?.id === m.id && (
                      <tr>
                        <td colSpan={6} style={{ background: 'var(--surface2)' }}>
                          <form onSubmit={reset} style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <span style={{ fontSize: 13 }}>Nueva contraseña para <b>{m.username}</b>:</span>
                            <input type="password" required minLength={8} autoComplete="new-password" value={resetPw} onChange={(e) => setResetPw(e.target.value)} style={{ minWidth: 220 }} />
                            <button className="btn sm pri" disabled={busy === m.id}>Restablecer</button>
                            <button type="button" className="btn sm" onClick={() => setResetFor(null)}>Cancelar</button>
                          </form>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}

/* ----------------------------------------------------------------- Auditoría */
function AuditSection() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filtro, setFiltro] = useState({ actor: '', accion: '', modalidad: '' })
  const [open, setOpen] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    const params = Object.fromEntries(Object.entries(filtro).filter(([, v]) => v))
    audit.list(params).then((r) => setList(r.data.results ?? r.data)).catch((err) => setError(extractErrorMessage(err))).finally(() => setLoading(false))
  }
  useEffect(load, [filtro])

  const set = (k) => (e) => setFiltro({ ...filtro, [k]: e.target.value })
  const actores = [...new Set(list.map((r) => r.actor))].sort()

  return (
    <section className="panel">
      <div className="ph">
        <h2>Ventana de auditoría</h2>
        <Link to="/auditoria" className="r">Registro completo →</Link>
      </div>
      <div className="pb audit-filters">
        <label className="field"><span>Quién</span>
          <input list="audit-actores" value={filtro.actor} onChange={set('actor')} placeholder="usuario o «agente»" />
          <datalist id="audit-actores">{actores.map((a) => <option key={a} value={a} />)}</datalist>
        </label>
        <div className="field"><span>Acción</span>
          <Select aria-label="Acción" value={filtro.accion} onChange={(accion) => setFiltro({ ...filtro, accion })} options={[{ value: '', label: 'Todas' }, ...Object.entries(ACCION_LABEL).map(([value, label]) => ({ value, label }))]} />
        </div>
        <div className="field"><span>Modalidad</span>
          <Select aria-label="Modalidad" value={filtro.modalidad} onChange={(modalidad) => setFiltro({ ...filtro, modalidad })} options={[{ value: '', label: 'Todas' }, ...Object.entries(MOD_LABEL).map(([value, label]) => ({ value, label }))]} />
        </div>
        <button type="button" className="btn sm" onClick={() => setFiltro({ actor: '', accion: '', modalidad: '' })}>Limpiar</button>
      </div>
      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && list.length === 0 && <EmptyState message="Ningún registro coincide con los filtros." />}
      {!loading && !error && list.length > 0 && (
        <table>
          <thead><tr><th>Fecha</th><th>Quién</th><th>Qué hizo</th><th>Modalidad</th><th>Sobre</th></tr></thead>
          <tbody>
            {list.map((r) => (
              <Fragment key={r.id}>
                <tr className="row" onClick={() => setOpen(open === r.id ? null : r.id)}>
                  <td className="mono" style={{ whiteSpace: 'nowrap' }}>{new Date(r.creado_en).toLocaleString('es-PE')}</td>
                  <td>{r.actor === 'agente' ? <span className="badge b-br">Agente</span> : r.actor}</td>
                  <td>{ACCION_LABEL[r.accion] || r.accion}</td>
                  <td><span className={`badge ${MOD_BADGE[r.modalidad] || 'b-mut'}`}>{MOD_LABEL[r.modalidad] || r.modalidad}</span></td>
                  <td className="mono muted">{r.objeto_tipo} · {String(r.objeto_id).slice(0, 12)}</td>
                </tr>
                {open === r.id && (
                  <tr><td colSpan={5} style={{ background: 'var(--surface2)' }}><pre className="mono" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(r.detalle, null, 2)}</pre></td></tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
      <div className="pb muted" style={{ fontSize: 12.5, borderTop: '1px solid var(--line)' }}>
        Se muestran los 25 registros más recientes que coinciden. El registro no se puede editar ni borrar.
      </div>
    </section>
  )
}

/* ------------------------------------------------------------ Integraciones */
function IntegrationsSection({ canEdit }) {
  const [status, setStatus] = useState(null)
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionMsg, setActionMsg] = useState(null)
  const [busy, setBusy] = useState('')

  function load() {
    setLoading(true)
    setError('')
    Promise.all([integrations.status(), sources.list()])
      .then(([s, f]) => {
        setStatus(s.data)
        setList(f.data.results ?? f.data)
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function toggle(src) {
    setBusy(src.id)
    setActionMsg(null)
    try {
      await sources.update(src.id, { is_active: !src.is_active })
      load()
    } catch (err) {
      setActionMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy('')
    }
  }

  async function sync() {
    setBusy('sync')
    setActionMsg(null)
    try {
      const { data } = await sources.sync()
      const total = (data.results || []).reduce((a, r) => a + (r.created || 0) + (r.updated || 0), 0)
      setActionMsg({ ok: true, text: `Sincronización terminada: ${total} hallazgos procesados en ${data.results?.length || 0} fuentes.` })
      load()
    } catch (err) {
      setActionMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setBusy('')
    }
  }

  if (loading) return <div className="panel"><LoadingState /></div>
  if (error) return <div className="panel"><ErrorState message={error} onRetry={load} /></div>

  return (
    <>
      <section className="panel">
        <div className="ph">
          <h2>Conectores</h2>
          <span className="r">{status.modo_demo ? 'Modo demo: datos de ejemplo hasta conectar Wazuh u OpenVAS' : 'Credenciales en el entorno del servidor'}</span>
        </div>
        <ul className="connectors">
          {status.conectores.map((c) => (
            <li key={c.clave}>
              <span className={`conn-dot ${c.configurado ? 'ok' : ''}`} />
              <div className="conn-body">
                <b>{c.nombre}</b>
                <small>{c.descripcion}</small>
                <span className="mono muted">{c.url || `Sin configurar · variables ${c.variables.join(', ')}`}</span>
              </div>
              <span className={`badge ${c.configurado ? 'b-ok' : 'b-mut'}`}>{c.configurado ? 'Configurado' : 'Pendiente'}</span>
            </li>
          ))}
        </ul>
        <div className="pb muted" style={{ borderTop: '1px solid var(--line)', fontSize: 12.5 }}>
          Las credenciales se definen en el archivo <span className="mono">.env</span> del backend y nunca se muestran aquí.
        </div>
      </section>

      <section className="panel">
        <div className="ph">
          <h2>Fuentes de hallazgos</h2>
          {canEdit && (
            <button className="btn sm" style={{ marginLeft: 'auto' }} disabled={busy === 'sync'} onClick={sync}>
              <IconRefresh size={14} />{busy === 'sync' ? 'Sincronizando…' : 'Sincronizar ahora'}
            </button>
          )}
        </div>
        {actionMsg && <div style={{ padding: '10px 14px 0' }}><Msg msg={actionMsg} /></div>}
        {list.length === 0 ? (
          <EmptyState message="Sin fuentes registradas." />
        ) : (
          <table>
            <thead><tr><th>Fuente</th><th>Tipo</th><th>Última sincronización</th><th>Resultado</th><th>Activa</th></tr></thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.id}>
                  <td><b style={{ fontWeight: 500 }}>{s.name}</b></td>
                  <td className="muted">{s.source_type}</td>
                  <td className="muted">{s.last_sync_at ? new Date(s.last_sync_at).toLocaleString('es-PE') : 'Nunca'}</td>
                  <td>{s.last_sync_ok == null ? <span className="badge b-mut">—</span> : s.last_sync_ok ? <span className="badge b-ok">OK</span> : <span className="badge b-crit">Falló</span>}</td>
                  <td>
                    {canEdit ? (
                      <button type="button" className={`switch ${s.is_active ? 'on' : ''}`} role="switch" aria-checked={s.is_active} disabled={busy === s.id} onClick={() => toggle(s)} aria-label={`${s.is_active ? 'Desactivar' : 'Activar'} ${s.name}`}>
                        <i />
                      </button>
                    ) : (
                      <span className={`badge ${s.is_active ? 'b-ok' : 'b-mut'}`}>{s.is_active ? 'Sí' : 'No'}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}

/* ----------------------------------------------------------------- Autonomía */
const NIVEL_BADGE = { autonomo: 'b-ok', asistido: 'b-br', con_aprobacion: 'b-high' }
const NIVEL_LABEL = { autonomo: 'Autónomo', asistido: 'Asistido', con_aprobacion: 'Con aprobación' }

function AutonomySection({ canEdit }) {
  const [policies, setPolicies] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    governance.policies().then((r) => setPolicies(r.data.results ?? r.data)).catch((err) => setError(extractErrorMessage(err))).finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function change(id, nivel) {
    setActionError('')
    try {
      await governance.updatePolicy(id, nivel)
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    }
  }

  return (
    <section className="panel">
      <div className="ph">
        <h2>Niveles de autonomía</h2>
        <Link to="/gobernanza" className="r">Ver aprobaciones pendientes →</Link>
      </div>
      {actionError && <div className="alert-err" style={{ margin: 12 }}>{actionError}</div>}
      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && (
        <table>
          <thead><tr><th>Acción del agente</th><th>Nivel</th></tr></thead>
          <tbody>
            {policies.map((p) => (
              <tr key={p.id}>
                <td>{p.tipo_accion_display}</td>
                <td>
                  {canEdit ? (
                    <Select size="sm" aria-label={`Nivel para ${p.tipo_accion_display}`} value={p.nivel} onChange={(nivel) => change(p.id, nivel)} options={Object.entries(NIVEL_LABEL).map(([value, label]) => ({ value, label }))} />
                  ) : (
                    <span className={`badge ${NIVEL_BADGE[p.nivel]}`}>{NIVEL_LABEL[p.nivel]}</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <div className="pb muted" style={{ fontSize: 12.5, borderTop: '1px solid var(--line)' }}>
        <b>Autónomo:</b> el agente lo hace y lo registra. <b>Asistido:</b> el agente recomienda, TI ejecuta.{' '}
        <b>Con aprobación:</b> no se hace nada sin el visto bueno de Gerencia.
      </div>
    </section>
  )
}

function Msg({ msg }) {
  if (!msg) return null
  return <div className={msg.ok ? 'alert-ok' : 'alert-err'} role={msg.ok ? 'status' : 'alert'}>{msg.text}</div>
}
