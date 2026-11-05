import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../components/DataState'
import { IconShield, IconShieldCheck } from '../components/Icons'
import './Login.css'

// Las cuentas demo se listan solo en desarrollo, o si el build lo pide
// explícitamente (VITE_MOSTRAR_CUENTAS_DEMO=true) para la validación.
const MOSTRAR_DEMO = import.meta.env.DEV || import.meta.env.VITE_MOSTRAR_CUENTAS_DEMO === 'true'
const CLAVE_DEMO = import.meta.env.DEV ? 'demo12345' : ''

const DEMO_ACCOUNTS = [
  ['admin_demo', 'role-admin', 'Gerencia (Administrador)'],
  ['coordinador_demo', 'role-it_owner', 'Responsable de TI'],
  ['cumplimiento_demo', 'role-compliance', 'Oficial de Cumplimiento'],
  ['personal_demo', 'role-staff', 'Personal administrativo'],
  ['demo', 'role-analyst', 'Analista de seguridad'],
  ['auditor_demo', 'role-auditor', 'Auditor (solo lectura)'],
]

export default function Login() {
  const { login, verifyMfa } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [mfaToken, setMfaToken] = useState('')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (mfaToken) {
        await verifyMfa(mfaToken, code)
        navigate('/', { replace: true })
        return
      }
      const r = await login(username, password)
      if (r.mfaToken) {
        setMfaToken(r.mfaToken)
        setCode('')
      } else {
        navigate('/', { replace: true })
      }
    } catch (err) {
      // 423 = cuenta bloqueada por intentos fallidos (HU29); el mensaje
      // del servidor dice cuántos minutos faltan.
      setError(extractErrorMessage(err))
      if (err.response?.status === 400 && mfaToken && /expiró/.test(extractErrorMessage(err))) setMfaToken('')
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
            <li><IconShieldCheck size={16} />Prioridad contextual R1-R5 y clasificación SVM explicadas</li>
            <li><IconShieldCheck size={16} />34 controles ISO 27001 para PyMEs de salud y Ley 29733</li>
            <li><IconShieldCheck size={16} />Segundo factor, bloqueo por intentos y auditoría inalterable</li>
          </ul>
        </aside>

        <form onSubmit={handleSubmit} className="panel login-card">
          {!mfaToken ? (
            <>
              <h2>Iniciar sesión</h2>
              <p className="login-sub">Accede con tu cuenta de la organización</p>
              <label className="field">
                <span>Usuario</span>
                <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
              </label>
              <label className="field">
                <span>Contraseña</span>
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
              </label>
            </>
          ) : (
            <>
              <h2>Verificación en dos pasos</h2>
              <p className="login-sub">Escribe el código de 6 dígitos de tu app autenticadora.</p>
              <label className="field">
                <span>Código</span>
                <input
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  autoFocus
                  required
                  className="mono"
                  style={{ letterSpacing: 6, fontSize: 20, textAlign: 'center' }}
                />
              </label>
            </>
          )}
          {error && <p className="alert-err" role="alert">{error}</p>}
          <button type="submit" className="btn pri login-btn" disabled={loading}>
            {loading ? 'Verificando…' : mfaToken ? 'Verificar' : 'Ingresar'}
          </button>
          {mfaToken && (
            <button type="button" className="btn sm" onClick={() => { setMfaToken(''); setError('') }}>
              Volver
            </button>
          )}

          {MOSTRAR_DEMO && !mfaToken && (
            <div className="login-demo">
              <p>Cuentas de demostración{CLAVE_DEMO && <> (clave: <span className="mono">{CLAVE_DEMO}</span>)</>}</p>
              <ul>
                {DEMO_ACCOUNTS.map(([user, cls, label]) => (
                  <li key={user}>
                    <button type="button" className="mono" onClick={() => { setUsername(user); if (CLAVE_DEMO) setPassword(CLAVE_DEMO) }}>{user}</button>
                    <span className={`role-badge ${cls}`}>{label}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
