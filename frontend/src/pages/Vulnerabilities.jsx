import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { assets as assetsApi, remediationPlans, sources, vulnerabilities } from '../api/resources'
import { ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import Select from '../components/Select'

const SEV_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja', none: 'Ninguna' }
const SEV_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low', none: 'b-mut' }
const ST_LABEL = { open: 'Abierta', in_plan: 'En plan', in_verification: 'En verificación', closed: 'Cerrada' }
const ST_BADGE = { open: 'b-mut', in_plan: 'b-br', in_verification: 'b-med', closed: 'b-ok' }
const IMPACTO = { critico: ['Crítico', 'b-crit'], alto: ['Alto', 'b-high'], medio: ['Medio', 'b-med'], bajo: ['Bajo', 'b-low'], pendiente_asociacion: ['Pendiente de asociación', 'b-mut'] }
const CATEGORIAS = [
  ['software_desactualizado', 'Software desactualizado o sin parche'],
  ['config_insegura', 'Configuración insegura / protocolos obsoletos'],
  ['falla_app_web', 'Fallas en aplicaciones web'],
  ['privilegios_excesivos', 'Privilegios excesivos o cuentas inactivas'],
  ['autenticacion_debil', 'Autenticación débil / sin segundo factor'],
  ['activo_no_inventariado', 'Activo no inventariado (shadow IT)'],
  ['sin_registros', 'Ausencia de registros o monitoreo'],
  ['datos_clinicos_expuestos', 'Datos clínicos expuestos o sin cifrar'],
  ['malware', 'Malware o actividad maliciosa'],
  ['nueva_vulnerabilidad', 'Nueva vulnerabilidad que afecta un activo'],
]

export default function Vulnerabilities() {
  const { canEdit } = useAuth()
  const [list, setList] = useState([])
  const [selected, setSelected] = useState(null)
  const [severity, setSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncMsg, setSyncMsg] = useState('')
  const [nuevo, setNuevo] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    vulnerabilities
      .list({ severity: severity || undefined, search: search || undefined })
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [severity, search])

  useEffect(load, [load])

  async function handleSync() {
    setSyncing(true)
    setSyncMsg('')
    try {
      const { data } = await sources.sync()
      const creados = data.results.reduce((a, r) => a + (r.created || 0), 0)
      setSyncMsg(`Sincronización lista: ${creados} hallazgo(s) nuevo(s) de ${data.results.length} fuente(s).`)
      load()
    } catch (err) {
      setSyncMsg(extractErrorMessage(err))
    } finally {
      setSyncing(false)
    }
  }

  async function openDetail(id) {
    try {
      const { data } = await vulnerabilities.retrieve(id)
      setSelected(data)
    } catch (err) {
      setSyncMsg(extractErrorMessage(err))
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: selected ? 'minmax(0, 1fr) 400px' : '1fr', gap: 14 }}>
      <div>
        <div className="page-head" style={{ display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
          <div>
            <h1>Vulnerabilidades</h1>
            <p>Hallazgos de OpenVAS, Wazuh y Kaspersky, priorizados por contexto clínico</p>
          </div>
          <span className="row-actions" style={{ marginLeft: 'auto' }}>
            <button className="btn" onClick={() => setNuevo((v) => !v)} disabled={!canEdit}>Registrar hallazgo</button>
            <button className="btn" onClick={handleSync} disabled={!canEdit || syncing} title={canEdit ? undefined : 'Solo lectura (Auditor)'}>
              {syncing ? 'Sincronizando…' : 'Sincronizar fuentes'}
            </button>
          </span>
        </div>

        {syncMsg && <div className="note" style={{ marginBottom: 10 }}>{syncMsg}</div>}
        {nuevo && <NuevoHallazgo onDone={(v) => { setNuevo(false); load(); if (v) openDetail(v.id) }} />}

        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <Select
            aria-label="Severidad"
            value={severity}
            onChange={setSeverity}
            options={[{ value: '', label: 'Todas las severidades' }, ...['critical', 'high', 'medium', 'low'].map((v) => ({ value: v, label: SEV_LABEL[v] }))]}
          />
          <input
            placeholder="Buscar por CVE, título o activo"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200 }}
          />
        </div>

        <div className="panel">
          {loading && <LoadingState />}
          {!loading && error && <ErrorState message={error} onRetry={load} />}
          {!loading && !error && (
            <table>
              <thead>
                <tr>
                  <th title="Severidad técnica según CVSS">CVSS</th>
                  <th title="Severidad ajustada al contexto del activo (reglas R1-R5)">Prioridad contextual</th>
                  <th>Vulnerabilidad</th><th>Activo</th><th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {list.length === 0 && (
                  <tr><td colSpan={5}><div className="empty">Ningún hallazgo coincide con los filtros.</div></td></tr>
                )}
                {list.map((v) => (
                  <tr key={v.id} className={`row ${selected?.id === v.id ? 'selected' : ''}`} onClick={() => openDetail(v.id)}>
                    <td><span className={`badge ${SEV_BADGE[v.severity]}`}>{SEV_LABEL[v.severity]}</span><div className="mono small muted">{v.cvss_score ?? '—'}</div></td>
                    <td>
                      {v.pendiente_asociacion
                        ? <span className="badge b-mut">Pendiente</span>
                        : <span className={`badge ${SEV_BADGE[v.riesgo_final] || 'b-mut'}`}>{SEV_LABEL[v.riesgo_final] || '—'}</span>}
                      {v.actively_exploited && <span className="badge b-crit" style={{ marginLeft: 4 }} title="Explotación activa reportada (CISA KEV)">KEV</span>}
                      {v.riesgo_corregido && <span className="badge b-br" style={{ marginLeft: 4 }} title="Clasificación corregida por una persona">corregida</span>}
                    </td>
                    <td>
                      <b style={{ fontWeight: 500, display: 'block' }}>{v.title}</b>
                      <span className="mono muted">{v.cve || 'sin CVE'}</span>
                      {v.is_overdue && <span className="badge b-crit" style={{ marginLeft: 6 }}>Vencido</span>}
                    </td>
                    <td>{v.asset_hostname || <span className="badge b-mut">Sin activo</span>}</td>
                    <td><span className={`badge ${ST_BADGE[v.status]}`}>{ST_LABEL[v.status]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selected && (
        <DetailPanel
          vulnerability={selected}
          onClose={() => setSelected(null)}
          onUpdated={(data) => {
            setSelected(data)
            load()
          }}
        />
      )}
    </div>
  )
}

function NuevoHallazgo({ onDone }) {
  const [fuentes, setFuentes] = useState([])
  const [activos, setActivos] = useState([])
  const [f, setF] = useState({ title: '', source: '', asset: '', cve: '', cvss_vector: '', severity: '', category: '', description: '' })
  const [err, setErr] = useState('')
  useEffect(() => {
    sources.list().then(({ data }) => { const xs = data.results ?? data; setFuentes(xs); setF((p) => ({ ...p, source: p.source || xs.find((s) => s.source_type === 'manual')?.id || xs[0]?.id || '' })) }).catch(() => {})
    assetsApi.list().then(({ data }) => setActivos(data.results ?? data)).catch(() => {})
  }, [])
  async function guardar(e) {
    e.preventDefault()
    setErr('')
    const payload = Object.fromEntries(Object.entries(f).filter(([, v]) => v !== ''))
    payload.asset = f.asset || null
    try {
      const { data } = await vulnerabilities.create(payload)
      onDone(data)
    } catch (error) {
      setErr(extractErrorMessage(error))
    }
  }
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  return (
    <form className="panel pb" onSubmit={guardar} style={{ marginBottom: 12, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
      <label className="field" style={{ gridColumn: '1 / -1' }}>Título<input required value={f.title} onChange={set('title')} /></label>
      <label className="field">Fuente<select required value={f.source} onChange={set('source')}>{fuentes.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
      <label className="field">Activo (opcional)<select value={f.asset} onChange={set('asset')}><option value="">— Sin identificar (pendiente de asociación) —</option>{activos.map((a) => <option key={a.id} value={a.id}>{a.hostname}</option>)}</select></label>
      <label className="field">CVE<input value={f.cve} onChange={set('cve')} placeholder="CVE-2024-…" /></label>
      <label className="field">Vector CVSS (calcula el puntaje)<input value={f.cvss_vector} onChange={set('cvss_vector')} placeholder="CVSS:3.1/AV:N/AC:L/…" className="mono" /></label>
      <label className="field">Severidad (si no hay vector)<select value={f.severity} onChange={set('severity')}><option value="">—</option>{Object.entries(SEV_LABEL).filter(([k]) => k !== 'none').map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
      <label className="field">Categoría (vincula controles ISO)<select value={f.category} onChange={set('category')}><option value="">—</option>{CATEGORIAS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
      <label className="field" style={{ gridColumn: '1 / -1' }}>Descripción<textarea value={f.description} onChange={set('description')} /></label>
      {err && <div className="alert-err" style={{ gridColumn: '1 / -1' }}>{err}</div>}
      <div className="row-actions"><button className="btn pri">Guardar hallazgo</button><button type="button" className="btn" onClick={() => onDone(null)}>Cancelar</button></div>
    </form>
  )
}

function DetailPanel({ vulnerability: v, onClose, onUpdated }) {
  const { canEdit } = useAuth()
  const [tab, setTab] = useState('detalle')
  const [busy, setBusy] = useState('')
  const [reply, setReply] = useState('')
  const [actionError, setActionError] = useState('')

  async function run(name, fn) {
    setBusy(name)
    setActionError('')
    try {
      await fn()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setBusy('')
    }
  }

  const refresh = async () => onUpdated((await vulnerabilities.retrieve(v.id)).data)

  return (
    <aside className="panel" style={{ height: 'fit-content', position: 'sticky', top: 0 }}>
      <div className="ph">
        <h2 style={{ fontSize: 15, margin: 0, flex: 1, textTransform: 'none', letterSpacing: 0 }}>{v.title}</h2>
        <button className="btn sm" onClick={onClose}>Cerrar</button>
      </div>
      <div className="tabs" style={{ margin: 0, padding: '0 8px' }}>
        {[['detalle', 'Detalle'], ['clasificacion', 'Clasificación'], ['ia', 'Análisis IA']].map(([k, l]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>

      <div className="pb" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {actionError && <div className="alert-err" style={{ margin: 0 }}>{actionError}</div>}
        {tab === 'detalle' && <Detalle v={v} canEdit={canEdit} onSaved={refresh} />}
        {tab === 'clasificacion' && <Clasificacion v={v} canEdit={canEdit} busy={busy} run={run} refresh={refresh} />}
        {tab === 'ia' && (
          <>
            {v.ai_analyzed_at ? (
              <>
                <div><h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Resumen del riesgo</h3><p style={{ margin: 0 }}>{v.ai_summary}</p></div>
                {v.ai_remediation_steps?.length > 0 && (
                  <div>
                    <h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Pasos recomendados</h3>
                    <ol style={{ margin: 0, paddingLeft: 18 }}>{v.ai_remediation_steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                  </div>
                )}
              </>
            ) : (
              <button className="btn pri" onClick={() => run('analyze', async () => onUpdated((await vulnerabilities.analyze(v.id)).data))} disabled={!canEdit || Boolean(busy)}>
                {busy === 'analyze' ? 'Analizando con Qwen…' : 'Analizar con IA'}
              </button>
            )}
            <div>
              <h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Preguntar al asistente</h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn sm" disabled={!canEdit || Boolean(busy)} onClick={() => run('simple', async () => setReply((await vulnerabilities.explainSimple(v.id)).data.text))}>{busy === 'simple' ? 'Pensando…' : 'Explicar simple'}</button>
                <button className="btn sm" disabled={!canEdit || Boolean(busy)} onClick={() => run('clinical', async () => setReply((await vulnerabilities.clinicalImpact(v.id)).data.text))}>{busy === 'clinical' ? 'Pensando…' : 'Impacto clínico'}</button>
              </div>
              {reply && <div className="note" style={{ marginTop: 8 }}>{reply}</div>}
            </div>
          </>
        )}
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--line)' }}>
        <button
          className="btn pri"
          style={{ width: '100%', justifyContent: 'center' }}
          disabled={!canEdit || v.status !== 'open' || Boolean(busy)}
          onClick={() => run('plan', async () => { await remediationPlans.create({ vulnerability: v.id, owner_name: '' }); await refresh() })}
        >
          {v.status === 'open' ? (busy === 'plan' ? 'Creando…' : 'Crear plan de corrección') : 'Ya tiene plan o está cerrada'}
        </button>
      </div>
    </aside>
  )
}

const EXPOSURE_LABEL = { internet: 'Expuesto a Internet', perimetral: 'Perimetral (DMZ)', interna: 'Solo red interna' }

function Detalle({ v, canEdit, onSaved }) {
  const [vector, setVector] = useState(v.cvss_vector || '')
  const [err, setErr] = useState('')
  const imp = IMPACTO[v.nivel_impacto] || ['—', 'b-mut']
  async function guardarVector(e) {
    e.preventDefault()
    setErr('')
    try {
      await vulnerabilities.update(v.id, { cvss_vector: vector })
      await onSaved()
    } catch (error) {
      setErr(extractErrorMessage(error))
    }
  }
  return (
    <>
      <div>
        <h3 style={{ fontSize: 13, margin: '0 0 6px' }}>Por qué esta decisión</h3>
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {v.explicacion?.map((l, i) => <li key={i}>{l}</li>)}
        </ul>
      </div>
      <dl style={{ display: 'grid', gridTemplateColumns: '120px 1fr', gap: '8px 12px', margin: 0 }}>
        <dt className="muted">Nivel de impacto</dt><dd style={{ margin: 0 }}><span className={`badge ${imp[1]}`}>{imp[0]}</span></dd>
        <dt className="muted">CVE</dt><dd className="mono" style={{ margin: 0 }}>{v.cve || 'Sin CVE'}</dd>
        <dt className="muted">CVSS</dt><dd style={{ margin: 0 }}>{v.cvss_score ?? '—'} <span className="muted small">{v.cvss_vector ? '(calculado del vector)' : ''}</span></dd>
        <dt className="muted">Fuente</dt><dd style={{ margin: 0 }}>{v.source_name}</dd>
        <dt className="muted">Exposición</dt><dd style={{ margin: 0 }}>{EXPOSURE_LABEL[v.asset?.exposure] || '—'}</dd>
        <dt className="muted">Plazo</dt><dd style={{ margin: 0 }}>{v.fecha_limite || '—'} {v.is_overdue && <span className="badge b-crit">Vencido</span>}</dd>
        <dt className="muted">Controles ISO</dt><dd style={{ margin: 0 }}>{v.control_codes?.length ? v.control_codes.join(', ') : '—'}</dd>
      </dl>
      {v.catalogo_cve && (
        <div className="note">
          <b>Base CVE (NVD{v.catalogo_cve.kev ? ' + CISA KEV' : ''}):</b> {v.catalogo_cve.descripcion.slice(0, 240)}{v.catalogo_cve.descripcion.length > 240 ? '…' : ''}
        </div>
      )}
      <div>
        <h3 style={{ fontSize: 13, margin: '0 0 6px' }}>Activos relacionados</h3>
        {v.activos_relacionados?.length ? (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13 }}>
            {v.activos_relacionados.map((a) => (
              <li key={a.id}>{a.hostname} <span className="muted">({a.tipo})</span> {a.critico && <span className="badge b-crit">crítico</span>} {a.datos_clinicos && <span className="badge b-high">datos clínicos</span>} {a.principal && <span className="badge b-br">afectado</span>}</li>
            ))}
          </ul>
        ) : <p className="muted small" style={{ margin: 0 }}>Sin activo asociado: queda pendiente de asociación. Asígnale un activo para calcular su impacto.</p>}
      </div>
      <form onSubmit={guardarVector}>
        <h3 style={{ fontSize: 13, margin: '0 0 6px' }}>Métricas base (vector CVSS)</h3>
        <div className="row-actions">
          <input className="mono" value={vector} onChange={(e) => setVector(e.target.value)} placeholder="CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" style={{ flex: 1, minWidth: 0, fontSize: 12 }} disabled={!canEdit} />
          <button className="btn sm" disabled={!canEdit || vector === (v.cvss_vector || '')}>Recalcular</button>
        </div>
        {err && <div className="alert-err" style={{ marginTop: 6 }}>{err}</div>}
      </form>
    </>
  )
}

function Clasificacion({ v, canEdit, busy, run, refresh }) {
  const [modelo, setModelo] = useState(null)
  const [riesgo, setRiesgo] = useState(v.riesgo_corregido || '')
  const [motivo, setMotivo] = useState('')
  useEffect(() => {
    vulnerabilities.model().then(({ data }) => setModelo(data.modelo)).catch(() => {})
  }, [])
  return (
    <>
      <div className="note small">
        Modelo: {modelo ? <>{modelo.algoritmo} · exactitud <b>{(modelo.accuracy * 100).toFixed(1)} %</b> · F1 macro <b>{(modelo.f1_macro * 100).toFixed(1)} %</b> · {modelo.muestras_reales} casos reales + {modelo.muestras_sinteticas} sintéticos ({modelo.muestras_prueba} de prueba)</> : 'cargando…'}
      </div>
      <dl style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: '8px 12px', margin: 0 }}>
        <dt className="muted">Reglas R1-R5</dt><dd style={{ margin: 0 }}>{v.contextual_priority ? <span className={`badge ${SEV_BADGE[v.contextual_priority]}`}>{SEV_LABEL[v.contextual_priority]}</span> : 'Pendiente'}</dd>
        <dt className="muted">Sugerida por el SVM</dt><dd style={{ margin: 0 }}>{v.riesgo_sugerido ? <span className={`badge ${SEV_BADGE[v.riesgo_sugerido]}`}>{SEV_LABEL[v.riesgo_sugerido]}</span> : '—'}</dd>
        <dt className="muted">Corregida por TI</dt><dd style={{ margin: 0 }}>{v.riesgo_corregido ? <><span className={`badge ${SEV_BADGE[v.riesgo_corregido]}`}>{SEV_LABEL[v.riesgo_corregido]}</span> <span className="muted small">por {v.riesgo_corregido_por}: {v.motivo_correccion}</span></> : '—'}</dd>
      </dl>
      <button className="btn" disabled={!canEdit || Boolean(busy) || v.pendiente_asociacion} onClick={() => run('svm', async () => { await vulnerabilities.classify(v.id); await refresh() })}>
        {busy === 'svm' ? 'Clasificando…' : 'Clasificar con el modelo (SVM)'}
      </button>
      <form onSubmit={(e) => { e.preventDefault(); run('corregir', async () => { await vulnerabilities.correctClassification(v.id, riesgo, motivo); setMotivo(''); await refresh() }) }}>
        <h3 style={{ fontSize: 13, margin: '0 0 6px' }}>Corregir la clasificación</h3>
        <p className="muted small" style={{ margin: '0 0 6px' }}>Se conservan ambas: la sugerida y la corregida (trazabilidad).</p>
        <div className="row-actions">
          <select required value={riesgo} onChange={(e) => setRiesgo(e.target.value)} disabled={!canEdit}>
            <option value="">Nivel correcto…</option>
            {['critical', 'high', 'medium', 'low'].map((k) => <option key={k} value={k}>{SEV_LABEL[k]}</option>)}
          </select>
          <input required value={motivo} onChange={(e) => setMotivo(e.target.value)} placeholder="Motivo" style={{ flex: 1, minWidth: 120 }} disabled={!canEdit} />
          <button className="btn sm pri" disabled={!canEdit || Boolean(busy)}>Guardar</button>
        </div>
      </form>
    </>
  )
}
