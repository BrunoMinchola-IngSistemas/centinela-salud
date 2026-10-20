import { useEffect, useState } from 'react'
import { remediationPlans } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

export default function Verification() {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(null)
  const [actionError, setActionError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    remediationPlans
      .list({ status: 'in_verification' })
      .then((res) => setPlans(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function verify(id, stillPresent) {
    setBusy(id)
    setActionError('')
    try {
      await remediationPlans.verify(id, { vulnerability_still_present: stillPresent, requested_by: 'Analista' })
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Verificación</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Confirma si el reescaneo encontró la vulnerabilidad otra vez</p>
      </div>

      {actionError && (
        <div className="panel" style={{ padding: '8px 12px', marginBottom: 10, color: 'var(--crit)', fontSize: 13 }}>
          {actionError}
        </div>
      )}

      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && plans.length === 0 && (
          <EmptyState message="No hay tareas en verificación. Envía una tarea desde el plan de corrección." />
        )}
        {!loading && !error && plans.length > 0 && (
          <table>
            <thead>
              <tr><th>Plan</th><th>Vulnerabilidad</th><th>Activo</th><th></th></tr>
            </thead>
            <tbody>
              {plans.map((p) => (
                <tr key={p.id}>
                  <td className="mono">PC-{p.id}</td>
                  <td>
                    <b style={{ fontWeight: 500, display: 'block' }}>{p.vulnerability_detail?.title}</b>
                    <span className="mono" style={{ color: 'var(--muted)' }}>{p.vulnerability_detail?.cve || 'sin CVE'}</span>
                  </td>
                  <td>{p.vulnerability_detail?.asset_hostname}</td>
                  <td style={{ textAlign: 'right', display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    <button className="btn sm" disabled={busy === p.id} onClick={() => verify(p.id, true)}>
                      Sigue presente
                    </button>
                    <button className="btn sm pri" disabled={busy === p.id} onClick={() => verify(p.id, false)}>
                      Confirmar corregida
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
