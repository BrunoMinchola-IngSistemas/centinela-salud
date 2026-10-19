import { useEffect, useState } from 'react'
import { controls as controlsApi } from '../api/resources'

export default function Controls() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [assessing, setAssessing] = useState(null)

  function load() {
    setLoading(true)
    controlsApi.list().then((res) => setList(res.data.results ?? res.data)).finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function assess(id) {
    setAssessing(id)
    try {
      await controlsApi.assess(id)
      load()
    } finally {
      setAssessing(null)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Controles de seguridad</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Cumplimiento calculado a partir de los hallazgos</p>
      </div>
      <div className="panel">
        {loading && <div className="empty">Cargando…</div>}
        {!loading && list.length === 0 && <div className="empty">Aún no hay controles cargados.</div>}
        {!loading && list.length > 0 && (
          <table>
            <thead><tr><th>Control</th><th>Cumplimiento</th><th>Brechas</th><th></th></tr></thead>
            <tbody>
              {list.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <b style={{ width: 38 }}>{c.compliance_score}%</b>
                      <div style={{ flex: 1, height: 6, borderRadius: 3, background: 'var(--line)', overflow: 'hidden' }}>
                        <div style={{ width: `${c.compliance_score}%`, height: '100%', background: c.compliance_score >= 85 ? 'var(--ok)' : c.compliance_score >= 70 ? 'var(--med)' : 'var(--crit)' }} />
                      </div>
                    </div>
                  </td>
                  <td>{c.open_findings || 'Ninguna'}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn sm" disabled={assessing === c.id} onClick={() => assess(c.id)}>
                      {assessing === c.id ? 'Evaluando…' : 'Evaluar con IA'}
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
