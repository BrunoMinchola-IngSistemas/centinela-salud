import { useEffect, useState } from 'react'
import { dashboard } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

const SEV_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
const SEV_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low' }

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    setError('')
    dashboard
      .summary()
      .then((res) => setData(res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (loading) return <LoadingState label="Cargando panel general…" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!data) return null

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Panel general</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Estado de riesgo de la organización</p>
      </div>

      <div className="panel" style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 16 }}>
        <Stat label="Vulnerabilidades abiertas" value={data.open_count} detail={`${data.closed_count} cerradas`} />
        <Stat label="Críticas sin corregir" value={data.critical_open} color="var(--crit)" />
        <Stat label="Plazos vencidos" value={data.overdue_count} />
        <Stat label="Cumplimiento de controles" value={`${data.avg_compliance}%`} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 14 }}>
        <section className="panel">
          <div className="ph"><h2 style={{ fontSize: 14, margin: 0 }}>Cola priorizada por IA</h2></div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {data.top_priority.length === 0 && <EmptyState message="Sin hallazgos abiertos." />}
            {data.top_priority.map((v) => (
              <li key={v.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--line)' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b style={{ fontWeight: 500, display: 'block' }}>{v.title}</b>
                  <span style={{ color: 'var(--muted)', fontSize: 12 }}>{v.cve || 'Sin CVE'} · {v.asset__hostname}</span>
                </div>
                <span className={`badge ${SEV_BADGE[v.severity]}`}>{SEV_LABEL[v.severity]}</span>
                <b style={{ width: 28, textAlign: 'right' }}>{v.priority_score}</b>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel">
          <div className="ph"><h2 style={{ fontSize: 14, margin: 0 }}>Controles con mayor brecha</h2></div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {data.control_gaps.length === 0 && <EmptyState message="Sin controles cargados." />}
            {data.control_gaps.map((c) => (
              <li key={c.id} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '10px 14px', borderBottom: '1px solid var(--line)' }}>
                <span style={{ flex: 1 }}>{c.name}</span>
                <b>{c.score}%</b>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}

function Stat({ label, value, detail, color }) {
  return (
    <div style={{ padding: '14px 18px', borderRight: '1px solid var(--line)' }}>
      <div style={{ fontSize: 28, fontWeight: 500, letterSpacing: '-0.02em', color: color || 'inherit' }}>{value}</div>
      <div style={{ color: 'var(--muted)', fontSize: 13 }}>{label}</div>
      {detail && <div style={{ fontSize: 12, marginTop: 4, color: 'var(--muted)' }}>{detail}</div>}
    </div>
  )
}
