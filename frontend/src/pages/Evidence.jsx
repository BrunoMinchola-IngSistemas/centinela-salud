import { useEffect, useState } from 'react'
import { evidence as evidenceApi } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

export default function Evidence() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    evidenceApi
      .list()
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div>
      <div className="page-head">
        <h1>Evidencias</h1>
        <p>Cada registro guarda su huella SHA-256</p>
      </div>
      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && list.length === 0 && <EmptyState message="Aún no hay evidencias generadas." />}
        {!loading && !error && list.length > 0 && (
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
