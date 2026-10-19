import { useEffect, useState } from 'react'
import { evidence as evidenceApi } from '../api/resources'

export default function Evidence() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    evidenceApi.list().then((res) => setList(res.data.results ?? res.data)).finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Evidencias</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Cada registro guarda su huella SHA-256</p>
      </div>
      <div className="panel">
        {loading && <div className="empty">Cargando…</div>}
        {!loading && list.length === 0 && <div className="empty">Aún no hay evidencias generadas.</div>}
        {!loading && list.length > 0 && (
          <table>
            <thead><tr><th>Evidencia</th><th>Vinculada a</th><th>Origen</th><th>Huella SHA-256</th><th>Fecha</th></tr></thead>
            <tbody>
              {list.map((e) => (
                <tr key={e.id}>
                  <td>
                    <b style={{ fontWeight: 500, display: 'block' }}>{e.name}</b>
                    <span style={{ color: 'var(--muted)', fontSize: 12 }}>{e.evidence_type}</span>
                  </td>
                  <td className="mono">{e.vulnerability_cve || '—'}</td>
                  <td>{e.source_system}</td>
                  <td className="mono" title={e.sha256_hash}>{e.sha256_hash.slice(0, 10)}…{e.sha256_hash.slice(-4)}</td>
                  <td>{new Date(e.created_at).toLocaleDateString('es-PE')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
