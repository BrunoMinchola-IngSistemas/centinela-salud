import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { extractErrorMessage } from '../components/DataState'

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
    <div
      style={{
        height: '100vh',
        display: 'grid',
        placeItems: 'center',
        background: 'radial-gradient(1200px 600px at 20% -10%, var(--brand-soft), transparent), var(--bg)',
      }}
    >
      <form onSubmit={handleSubmit} className="panel" style={{ width: 340, padding: 24 }}>
        <div
          style={{
            width: 34, height: 34, borderRadius: 9, background: 'var(--brand)', color: 'var(--brand-ink)',
            display: 'grid', placeItems: 'center', fontWeight: 700, marginBottom: 10,
          }}
        >
          CS
        </div>
        <h1 style={{ fontSize: 18, fontWeight: 600, margin: '0 0 4px' }}>Centinela Salud</h1>
        <p style={{ color: 'var(--muted)', margin: '0 0 18px' }}>Consola de vulnerabilidades</p>
        <label style={{ display: 'block', marginBottom: 12 }}>
          <span style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Usuario</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ width: '100%', padding: '7px 10px', border: '1px solid var(--line)', borderRadius: 6, background: 'var(--surface2)' }}
            autoFocus
          />
        </label>
        <label style={{ display: 'block', marginBottom: 16 }}>
          <span style={{ display: 'block', marginBottom: 4, fontSize: 13 }}>Contraseña</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: '100%', padding: '7px 10px', border: '1px solid var(--line)', borderRadius: 6, background: 'var(--surface2)' }}
          />
        </label>
        {error && <p style={{ color: 'var(--crit)', fontSize: 13, margin: '0 0 12px' }}>{error}</p>}
        <button type="submit" className="btn pri" disabled={loading} style={{ width: '100%', justifyContent: 'center' }}>
          {loading ? 'Ingresando…' : 'Ingresar'}
        </button>

        <div style={{ marginTop: 18, paddingTop: 14, borderTop: '1px solid var(--line)', fontSize: 12, color: 'var(--muted)' }}>
          <p style={{ margin: '0 0 6px', fontWeight: 500 }}>Cuentas de demostración (clave: demo12345)</p>
          <ul style={{ margin: 0, paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 2 }}>
            <li><span className="mono">demo</span> — Analista de seguridad</li>
            <li><span className="mono">admin_demo</span> — Administrador</li>
            <li><span className="mono">coordinador_demo</span> — Responsable de TI</li>
          </ul>
        </div>
      </form>
    </div>
  )
}
