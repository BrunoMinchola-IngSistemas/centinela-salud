import { useEffect, useState } from 'react'
import { remediationPlans } from '../api/resources'

export default function Verification() {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)

  function load() {
    setLoading(true)
    remediationPlans
      .list({ status: 'in_verification' })
      .then((res) => setPlans(res.data.results ?? res.data))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function verify(id, stillPresent) {
    setBusy(id)
    try {
      await remediationPlans.verify(id, { vulnerability_still_present: stillPresent, requested_by: 'Analista' })
      load()
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

      <div className="panel">
        {loading && <div className="empty">Cargando…</div>}
        {!loading && plans.length === 0 && (
          <div className="empty">No hay tareas en verificación. Envía una tarea desde el plan de corrección.</div>
        )}
        {!loading && plans.length > 0 && (
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
