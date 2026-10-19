import { useEffect, useState } from 'react'
import { remediationPlans } from '../api/resources'

const COLUMNS = [
  { key: 'pending', label: 'Pendiente' },
  { key: 'in_progress', label: 'En curso' },
  { key: 'in_verification', label: 'En verificación' },
  { key: 'closed', label: 'Cerrado' },
]

export default function RemediationPlan() {
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    remediationPlans.list().then((res) => setPlans(res.data.results ?? res.data)).finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function advance(id) {
    await remediationPlans.advance(id)
    load()
  }

  if (loading) return <div className="empty">Cargando…</div>

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Plan de corrección</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Tareas con responsable y fecha límite</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(220px, 1fr))', gap: 12, overflow: 'auto' }}>
        {COLUMNS.map((col) => {
          const items = plans.filter((p) => p.status === col.key)
          return (
            <div key={col.key} className="panel" style={{ background: 'var(--surface2)', display: 'flex', flexDirection: 'column' }}>
              <div className="ph">
                <h2 style={{ fontSize: 14, margin: 0 }}>{col.label}</h2>
                <span className="r">{items.length}</span>
              </div>
              <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {items.length === 0 && <div className="empty">Sin tareas</div>}
                {items.map((p) => (
                  <div key={p.id} className="panel" style={{ padding: '10px 11px', borderLeft: '3px solid var(--brand)' }}>
                    <span className="mono" style={{ color: 'var(--muted)' }}>PC-{p.id} · {p.vulnerability_detail?.cve || 'sin CVE'}</span>
                    <p style={{ margin: '4px 0 8px', fontWeight: 500 }}>{p.vulnerability_detail?.title}</p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)' }}>
                      <span>{p.owner_name}</span><span>{p.due_date}</span>
                    </div>
                    {(col.key === 'pending' || col.key === 'in_progress') && (
                      <button className="btn sm" style={{ marginTop: 8, width: '100%', justifyContent: 'center' }} onClick={() => advance(p.id)}>
                        {col.key === 'pending' ? 'Iniciar' : 'Enviar a verificación'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
