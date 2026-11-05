import { useCallback, useEffect, useState } from 'react'
import { cve, integrations, sources } from '../api/resources'
import { useAuth } from '../context/AuthContext'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

/**
 * HU02 (recolección automática de 3+ fuentes y log de fallas), HU03
 * (base CVE de NVD + CISA KEV) y HU04 (registros incompletos que no
 * entran al análisis hasta corregirlos).
 */
export default function Sources() {
  const { canEdit, role } = useAuth()
  const [estado, setEstado] = useState(null)
  const [fuentes, setFuentes] = useState([])
  const [fallas, setFallas] = useState([])
  const [incompletos, setIncompletos] = useState([])
  const [cveInfo, setCveInfo] = useState(null)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [ocupado, setOcupado] = useState('')

  const load = useCallback(() => {
    Promise.all([integrations.status(), sources.list(), integrations.failures(), integrations.incomplete({ corregido: false }), cve.syncs()])
      .then(([e, s, f, i, c]) => {
        setEstado(e.data)
        setFuentes(s.data.results ?? s.data)
        setFallas(f.data.results ?? f.data)
        setIncompletos(i.data.results ?? i.data)
        setCveInfo(c.data)
        setError('')
      })
      .catch((err) => setError(extractErrorMessage(err)))
  }, [])

  useEffect(load, [load])

  async function sincronizar() {
    setOcupado('sync')
    setMsg('')
    try {
      const { data } = await sources.sync()
      const t = data.results.map((r) => `${r.source}: ${r.error ? `error (${r.error})` : `${r.created} nuevos, ${r.updated} actualizados, ${r.incompletos ?? 0} incompletos`}`)
      setMsg(t.join(' · '))
      load()
    } catch (err) {
      setMsg(extractErrorMessage(err))
    } finally {
      setOcupado('')
    }
  }

  async function sincronizarCve() {
    setOcupado('cve')
    setMsg('')
    try {
      const { data } = await cve.sync()
      setMsg(`Base CVE actualizada: ${data.nuevos} nuevas, ${data.actualizados} actualizadas, ${data.kev_marcados} marcadas KEV, ${data.hallazgos_enriquecidos} hallazgos enriquecidos.`)
    } catch (err) {
      setMsg(`La sincronización no se completó: ${err.response?.data?.error || extractErrorMessage(err)}. Se conserva la última versión.`)
    } finally {
      setOcupado('')
      load()
    }
  }

  if (error && !estado) return <ErrorState message={error} onRetry={load} />
  if (!estado) return <LoadingState />
  const puedeSync = canEdit && ['admin', 'it_owner'].includes(role)

  return (
    <div>
      <div className="page-head">
        <h1>Fuentes de datos y base CVE</h1>
        <p>Recolección automática (cada 6 h), base de conocimiento de vulnerabilidades y registros por corregir</p>
      </div>
      {estado.modo_demo && (
        <div className="note" style={{ marginBottom: 12 }}>
          Modo demostración: Wazuh, OpenVAS y Kaspersky no tienen credenciales en este servidor, así que cada fuente devuelve un lote fijo de hallazgos de ejemplo. Con credenciales reales se usan los datos de la clínica.
        </div>
      )}
      {msg && <div className="alert-ok">{msg}</div>}

      <div className="grid-2">
        <div className="panel">
          <div className="ph">
            <b>Fuentes internas</b>
            <span className="r"><button className="btn sm" onClick={sincronizar} disabled={!canEdit || Boolean(ocupado)}>{ocupado === 'sync' ? 'Sincronizando…' : 'Sincronizar ahora'}</button></span>
          </div>
          <table>
            <thead><tr><th>Fuente</th><th>Tipo</th><th>Última sincronización</th><th>Estado</th></tr></thead>
            <tbody>
              {fuentes.map((f) => (
                <tr key={f.id}>
                  <td>{f.name}</td>
                  <td>{f.source_type_display}</td>
                  <td className="mono small">{f.last_sync_at ? new Date(f.last_sync_at).toLocaleString('es-PE') : '—'}</td>
                  <td>{f.last_sync_ok === null ? <span className="badge b-mut">Sin datos</span> : f.last_sync_ok ? <span className="badge b-ok">OK</span> : <span className="badge b-crit">Falló</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="panel">
          <div className="ph">
            <b>Base de conocimiento CVE</b>
            <span className="r"><button className="btn sm" onClick={sincronizarCve} disabled={!puedeSync || Boolean(ocupado)} title={puedeSync ? 'NVD (últimas 24 h) + CISA KEV' : 'Solo Gerencia o TI'}>{ocupado === 'cve' ? 'Sincronizando…' : 'Sincronizar CVE'}</button></span>
          </div>
          <div className="pb">
            <div className="grid-3">
              <div className="kpi"><b>{cveInfo?.total_cve ?? 0}</b><span>CVE en la base</span></div>
              <div className="kpi"><b>{cveInfo?.total_kev ?? 0}</b><span>Explotadas activamente (KEV)</span></div>
            </div>
            <p className="small muted">
              Última sincronización completa: {cveInfo?.ultima_ok ? new Date(cveInfo.ultima_ok.terminado_en).toLocaleString('es-PE') : 'ninguna todavía'}.
              Fuentes: NVD (NIST) y CISA KEV. El programador la corre cada 6 h.
            </p>
            {cveInfo?.historial?.slice(0, 5).map((s) => (
              <div key={s.id} className="small" style={{ display: 'flex', gap: 8, padding: '3px 0' }}>
                <span className={`badge ${s.ok ? 'b-ok' : 'b-crit'}`}>{s.ok ? 'OK' : 'Falló'}</span>
                <span className="mono">{new Date(s.iniciado_en).toLocaleString('es-PE')}</span>
                <span className="muted">{s.ok ? `${s.nuevos} nuevas · ${s.kev_marcados} KEV` : s.error.slice(0, 80)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="ph"><b>Registros incompletos</b><span className="r">fuera del análisis hasta corregirlos</span></div>
          {incompletos.length === 0 ? <EmptyState message="No hay registros incompletos." /> : (
            <div className="pb stack">
              {incompletos.map((r) => <Incompleto key={r.id} registro={r} onDone={load} canEdit={canEdit && role !== 'compliance'} />)}
            </div>
          )}
        </div>

        <div className="panel">
          <div className="ph"><b>Log de fallas de integración</b></div>
          {fallas.length === 0 ? <EmptyState message="Sin fallas registradas." /> : (
            <table>
              <thead><tr><th>Cuándo</th><th>Fuente</th><th>Error</th></tr></thead>
              <tbody>
                {fallas.map((f) => (
                  <tr key={f.id}><td className="mono small">{new Date(f.ocurrido_en).toLocaleString('es-PE')}</td><td>{f.fuente_nombre}</td><td className="small">{f.error}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}

const CAMPO_INPUT = { title: 'Título del hallazgo', severity: 'Severidad', external_id: 'Identificador', activo: 'Hostname del activo' }

function Incompleto({ registro, onDone, canEdit }) {
  const [datos, setDatos] = useState({})
  const [err, setErr] = useState('')
  async function corregir(e) {
    e.preventDefault()
    setErr('')
    const payload = { ...datos }
    if (payload.activo) { payload.asset_hostname = payload.activo; delete payload.activo }
    try {
      await integrations.fixIncomplete(registro.id, payload)
      onDone()
    } catch (error) {
      setErr(extractErrorMessage(error))
    }
  }
  return (
    <form onSubmit={corregir} style={{ borderBottom: '1px solid var(--line)', paddingBottom: 10 }}>
      <div className="small"><b>{registro.fuente_nombre}</b> · <span className="mono">{registro.external_id || 'sin id'}</span> · faltan: {registro.campos_faltantes_display.join(', ')}</div>
      <div className="muted small">{registro.datos.description}</div>
      <div className="row-actions" style={{ marginTop: 6 }}>
        {registro.campos_faltantes.map((c) => (
          c === 'severity'
            ? <select key={c} value={datos[c] || ''} onChange={(e) => setDatos({ ...datos, [c]: e.target.value })} required disabled={!canEdit}>
                <option value="">Severidad…</option><option value="critical">Crítica</option><option value="high">Alta</option><option value="medium">Media</option><option value="low">Baja</option>
              </select>
            : <input key={c} placeholder={CAMPO_INPUT[c] || c} value={datos[c] || ''} onChange={(e) => setDatos({ ...datos, [c]: e.target.value })} required disabled={!canEdit} />
        ))}
        <button className="btn sm pri" disabled={!canEdit}>Corregir e incluir</button>
      </div>
      {err && <div className="alert-err" style={{ marginTop: 6 }}>{err}</div>}
    </form>
  )
}
