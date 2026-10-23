import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../components/DataState'
import { IconShield, IconShieldCheck } from '../components/Icons'
import './Login.css'

const DEMO_ACCOUNTS = [
  ['demo', 'role-analyst', 'Analista de seguridad'],
  ['admin_demo', 'role-admin', 'Administrador'],
  ['coordinador_demo', 'role-it_owner', 'Responsable de TI'],
  ['auditor_demo', 'role-auditor', 'Auditor (solo lectura)'],
]

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/', { replace: true })
    } catch (err) {
      // 400 del login de DRF es casi siempre credenciales inválidas;
      // cualquier otra cosa (backend caído, 500, etc.) sí vale la
      // pena mostrarla tal cual para no hacer perder tiempo buscando
      // un typo que no existe.
      if (err.response?.status === 400) {
        setError('Usuario o contraseña incorrectos.')
      } else {
        setError(extractErrorMessage(err))
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login">
      <div className="login-grid" aria-hidden="true" />
      <div className="login-wrap">
        <aside className="login-side">
          <div className="login-brand">
            <span className="brand-mark"><IconShield size={24} /></span>
            <span>
              <b>CENTINELA<em>SALUD</em></b>
              <small>Protección inteligente</small>
            </span>
          </div>
          <h1>Consola de ciberseguridad asistida por IA</h1>
          <p>
            Vulnerabilidades priorizadas por contexto clínico, controles ISO/IEC 27001 para salud y
            acciones con aprobación de Gerencia, en un solo lugar.
          </p>
          <ul>
            <li><IconShieldCheck size={16} />Prioridad contextual R1-R5 explicada</li>
            <li><IconShieldCheck size={16} />31 controles ISO 27001 para PyMEs de salud</li>
            <li><IconShieldCheck size={16} />Registro de auditoría que no se puede alterar</li>
          </ul>
        </aside>

        <form onSubmit={handleSubmit} className="panel login-card">
          <h2>Iniciar sesión</h2>
          <p className="login-sub">Accede con tu cuenta de la organización</p>

          <label className="field">
            <span>Usuario</span>
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus />
          </label>
          <label className="field">
            <span>Contraseña</span>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          {error && <p className="alert-err" role="alert">{error}</p>}
          <button type="submit" className="btn pri login-btn" disabled={loading}>
            {loading ? 'Ingresando…' : 'Ingresar'}
          </button>

          <div className="login-demo">
            <p>Cuentas de demostración (clave: <span className="mono">demo12345</span>)</p>
            <ul>
              {DEMO_ACCOUNTS.map(([user, cls, label]) => (
                <li key={user}>
                  <button type="button" className="mono" onClick={() => { setUsername(user); setPassword('demo12345') }}>{user}</button>
                  <span className={`role-badge ${cls}`}>{label}</span>
                </li>
              ))}
            </ul>
          </div>
        </form>
      </div>
    </div>
  )
}
