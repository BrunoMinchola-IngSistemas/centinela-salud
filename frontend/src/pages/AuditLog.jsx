import { Fragment, useEffect, useState } from 'react'
import { audit } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import { ACCION_LABEL, MOD_BADGE, MOD_LABEL } from '../auditLabels'

/**
 * HU27: registro de auditoría. Es de solo lectura para todos los roles
 * (la API no permite editar ni borrar entradas), y es la pantalla
 * principal del Auditor.
 */
export default function AuditLog() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    audit
      .list()
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div>
      <div className="page-head">
        <h1>Registro de auditoría</h1>
        <p>Cada decisión del agente y de las personas, con quién, cuándo y bajo qué nivel de autonomía. No se puede editar ni borrar.</p>
      </div>
      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && list.length === 0 && <EmptyState message="Aún no hay registros." />}
        {!loading && !error && list.length > 0 && (
          <table>
            <thead><tr><th>Fecha</th><th>Quién</th><th>Qué hizo</th><th>Modalidad</th><th>Sobre</th></tr></thead>
            <tbody>
              {list.map((r) => (
                <Fragment key={r.id}>
                  <tr className="row" onClick={() => setOpen(open === r.id ? null : r.id)}>
                    <td className="mono" style={{ whiteSpace: 'nowrap' }}>{new Date(r.creado_en).toLocaleString('es-PE')}</td>
                    <td>{r.actor === 'agente' ? <span className="badge b-br">Agente</span> : r.actor}</td>
                    <td>{ACCION_LABEL[r.accion] || r.accion}</td>
                    <td><span className={`badge ${MOD_BADGE[r.modalidad] || 'b-mut'}`}>{MOD_LABEL[r.modalidad] || r.modalidad}</span></td>
                    <td className="mono" style={{ color: 'var(--muted)' }}>{r.objeto_tipo} · {String(r.objeto_id).slice(0, 12)}</td>
                  </tr>
                  {open === r.id && (
                    <tr>
                      <td colSpan={5} style={{ background: 'var(--surface2)' }}>
                        <pre className="mono" style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{JSON.stringify(r.detalle, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
