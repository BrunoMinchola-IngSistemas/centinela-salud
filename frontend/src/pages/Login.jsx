import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

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
    } catch {
      setError('Usuario o contraseña incorrectos.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ height: '100vh', display: 'grid', placeItems: 'center', background: 'var(--bg)' }}>
      <form onSubmit={handleSubmit} className="panel" style={{ width: 320, padding: 24 }}>
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
      </form>
    </div>
  )
}
