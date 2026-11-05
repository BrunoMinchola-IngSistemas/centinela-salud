import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { organization, reports, saveBlob } from '../api/resources'
import { useAuth } from '../context/AuthContext'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage, extractErrorMessageAsync } from '../components/DataState'

/**
 * HU21: reportes automáticos (PDF y Excel) según la periodicidad
 * configurada, con un resumen ejecutivo de una página. También se
 * pueden generar a pedido.
 */
export default function Reports() {
  const { canEdit } = useAuth()
  const [list, setList] = useState([])
  const [org, setOrg] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [generando, setGenerando] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([reports.list(), organization.get()])
      .then(([r, o]) => { setList(r.data.results ?? r.data); setOrg(o.data); setError('') })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  async function generar(formato) {
    setGenerando(formato)
    setAviso('')
    try {
      await reports.generate(formato)
      load()
    } catch (err) {
      setAviso(extractErrorMessage(err))
    } finally {
      setGenerando('')
    }
  }

  async function descargar(r) {
    try {
      saveBlob(await reports.download(r.id), `reporte.${r.formato}`)
    } catch (err) {
      setAviso(await extractErrorMessageAsync(err))
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Reportes</h1>
        <p>Resumen de vulnerabilidades, cumplimiento y remediación, con resumen ejecutivo de una página</p>
      </div>

      <div className="panel pb row-actions" style={{ marginBottom: 14 }}>
        <span>
          Periodicidad: <b>{org?.periodicidad_reporte_display || 'no configurada'}</b>
          {org?.ultimo_reporte_en && <span className="muted"> · último automático {new Date(org.ultimo_reporte_en).toLocaleString('es-PE')}</span>}
        </span>
        <span style={{ marginLeft: 'auto' }} className="row-actions">
          <button className="btn pri" disabled={!canEdit || Boolean(generando)} onClick={() => generar('pdf')}>{generando === 'pdf' ? 'Generando…' : 'Generar PDF ahora'}</button>
          <button className="btn" disabled={!canEdit || Boolean(generando)} onClick={() => generar('xlsx')}>{generando === 'xlsx' ? 'Generando…' : 'Generar Excel ahora'}</button>
        </span>
      </div>
      {aviso && (
        <div className="alert-err">
          {aviso} {/periodicidad/i.test(aviso) && <Link to="/configuracion">Ir a Configuración → Organización</Link>}
        </div>
      )}

      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && list.length === 0 && <EmptyState message="Aún no se generó ningún reporte." />}
        {!loading && !error && list.length > 0 && (
          <table>
            <thead><tr><th>Generado</th><th>Periodo</th><th>Formato</th><th>Origen</th><th>Risk Score</th><th>Huella SHA-256</th><th /></tr></thead>
            <tbody>
              {list.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{new Date(r.generado_en).toLocaleString('es-PE')}</td>
                  <td>{r.periodo_desde} → {r.periodo_hasta}</td>
                  <td>{r.formato_display}</td>
                  <td>{r.automatico ? <span className="badge b-br">Automático</span> : <span className="badge b-mut">{r.generado_por}</span>}</td>
                  <td>{r.resumen?.risk_score ?? '—'} {r.resumen?.nivel && <span className="muted small">({r.resumen.nivel})</span>}</td>
                  <td className="mono small" title={r.sha256_hash}>{r.sha256_hash.slice(0, 12)}…</td>
                  <td><button className="btn sm" onClick={() => descargar(r)}>Descargar</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
