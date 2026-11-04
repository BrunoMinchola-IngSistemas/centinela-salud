import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { remediationPlans, sources, vulnerabilities } from '../api/resources'
import { ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import Select from '../components/Select'

const SEV_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja', none: 'Ninguna' }
const SEV_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low', none: 'b-mut' }
const ST_LABEL = { open: 'Abierta', in_plan: 'En plan', in_verification: 'En verificación', closed: 'Cerrada' }
const ST_BADGE = { open: 'b-mut', in_plan: 'b-br', in_verification: 'b-med', closed: 'b-ok' }

export default function Vulnerabilities() {
  const { canEdit } = useAuth()
  const [list, setList] = useState([])
  const [selected, setSelected] = useState(null)
  const [severity, setSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [syncError, setSyncError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    vulnerabilities
      .list({ severity: severity || undefined, search: search || undefined })
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [severity, search])

  async function handleSync() {
    setSyncing(true)
    setSyncError('')
    try {
      await sources.sync()
      load()
    } catch (err) {
      setSyncError(extractErrorMessage(err))
    } finally {
      setSyncing(false)
    }
  }

  async function openDetail(id) {
    try {
      const { data } = await vulnerabilities.retrieve(id)
      setSelected(data)
    } catch (err) {
      setSyncError(extractErrorMessage(err))
    }
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 380px' : '1fr', gap: 14 }}>
      <div>
        <div className="page-head" style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
          <div>
            <h1>Vulnerabilidades</h1>
            <p>Hallazgos de OpenVAS y Wazuh</p>
          </div>
          <button className="btn" style={{ marginLeft: 'auto' }} onClick={handleSync} disabled={!canEdit || syncing} title={canEdit ? undefined : "Solo lectura (Auditor)"}>
            {syncing ? 'Sincronizando…' : 'Sincronizar fuentes'}
          </button>
        </div>

        {syncError && (
          <div className="panel" style={{ padding: '8px 12px', marginBottom: 10, color: 'var(--crit)', fontSize: 13 }}>
            {syncError}
          </div>
        )}

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
            style={{ flex: 1, minWidth: 200, border: '1px solid var(--line)', borderRadius: 6, padding: '5px 9px', background: 'var(--surface)' }}
          />
        </div>

        <div className="panel">
          {loading && <LoadingState />}
          {!loading && error && <ErrorState message={error} onRetry={load} />}
          {!loading && !error && (
            <table>
              <thead>
                <tr>
                  <th title="Severidad técnica según CVSS">CVSS</th><th title="Severidad ajustada al contexto del activo (reglas R1-R5)">Prioridad contextual</th><th>Vulnerabilidad</th><th>Activo</th><th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {list.length === 0 && (
                  <tr><td colSpan={5}><div className="empty">Ningún hallazgo coincide con los filtros.</div></td></tr>
                )}
                {list.map((v) => (
                  <tr key={v.id} className={`row ${selected?.id === v.id ? 'sel' : ''}`} onClick={() => openDetail(v.id)}>
                    <td><span className={`badge ${SEV_BADGE[v.severity]}`}>{SEV_LABEL[v.severity]}</span></td>
                    <td>
                      <span className={`badge ${SEV_BADGE[v.contextual_priority] || 'b-mut'}`}>{SEV_LABEL[v.contextual_priority] || '—'}</span>
                      {v.actively_exploited && <span className="badge b-crit" style={{ marginLeft: 4 }} title="Explotación activa reportada (CISA KEV)">KEV</span>}
                    </td>
                    <td>
                      <b style={{ fontWeight: 500, display: 'block' }}>{v.title}</b>
                      <span className="mono" style={{ color: 'var(--muted)' }}>{v.id.slice(0, 8)} · {v.cve || 'sin CVE'}</span>
                    </td>
                    <td>{v.asset_hostname}</td>
                    <td><span className={`badge ${ST_BADGE[v.status]}`}>{ST_LABEL[v.status]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {selected && (
        <AiPanel
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

function AiPanel({ vulnerability, onClose, onUpdated }) {
  const { canEdit } = useAuth()
  const [tab, setTab] = useState('ia')
  const [analyzing, setAnalyzing] = useState(false)
  const [asking, setAsking] = useState('')
  const [reply, setReply] = useState('')
  const [creatingPlan, setCreatingPlan] = useState(false)
  const [actionError, setActionError] = useState('')

  async function handleAnalyze() {
    setAnalyzing(true)
    setActionError('')
    try {
      const { data } = await vulnerabilities.analyze(vulnerability.id)
      onUpdated(data)
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleCreatePlan() {
    setCreatingPlan(true)
    setActionError('')
    try {
      await remediationPlans.create({ vulnerability: vulnerability.id, owner_name: 'Por asignar' })
      const { data } = await vulnerabilities.retrieve(vulnerability.id)
      onUpdated(data)
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setCreatingPlan(false)
    }
  }

  async function ask(kind) {
    setAsking(kind)
    setActionError('')
    try {
      const fn = kind === 'simple' ? vulnerabilities.explainSimple : vulnerabilities.clinicalImpact
      const { data } = await fn(vulnerability.id)
      setReply(data.text)
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setAsking('')
    }
  }

  return (
    <aside className="panel" style={{ height: 'fit-content', position: 'sticky', top: 0 }}>
      <div className="ph">
        <h2 style={{ fontSize: 15, margin: 0, flex: 1 }}>{vulnerability.title}</h2>
        <button className="btn sm" onClick={onClose}>Cerrar</button>
      </div>
      <div style={{ display: 'flex', borderBottom: '1px solid var(--line)' }}>
        {['ia', 'detalle'].map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className="btn sm"
            style={{ border: 0, borderRadius: 0, borderBottom: tab === t ? '2px solid var(--brand)' : '2px solid transparent', color: tab === t ? 'var(--brand)' : 'inherit' }}
          >
            {t === 'ia' ? 'Análisis IA' : 'Detalle'}
          </button>
        ))}
      </div>

      <div className="pb" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {actionError && (
          <div style={{ color: 'var(--crit)', fontSize: 13, background: 'var(--crit-soft)', border: '1px solid var(--crit)', borderRadius: 6, padding: '8px 10px' }}>
            {actionError}
          </div>
        )}
        {tab === 'ia' ? (
          <>
            {vulnerability.ai_analyzed_at ? (
              <>
                <div>
                  <h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Resumen del riesgo</h3>
                  <p style={{ margin: 0 }}>{vulnerability.ai_summary}</p>
                </div>
                {vulnerability.ai_remediation_steps?.length > 0 && (
                  <div>
                    <h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Pasos recomendados</h3>
                    <ol style={{ margin: 0, paddingLeft: 18 }}>
                      {vulnerability.ai_remediation_steps.map((s, i) => <li key={i}>{s}</li>)}
                    </ol>
                  </div>
                )}
              </>
            ) : (
              <button className="btn pri" onClick={handleAnalyze} disabled={!canEdit || analyzing} title={canEdit ? undefined : "Solo lectura (Auditor)"}>
                {analyzing ? 'Analizando con Qwen…' : 'Analizar con IA'}
              </button>
            )}
            <div>
              <h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Preguntar al asistente</h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn sm" disabled={!canEdit || Boolean(asking)} title={canEdit ? undefined : "Solo lectura (Auditor)"} onClick={() => ask('simple')}>
                  {asking === 'simple' ? 'Pensando…' : 'Explicar simple'}
                </button>
                <button className="btn sm" disabled={!canEdit || Boolean(asking)} title={canEdit ? undefined : "Solo lectura (Auditor)"} onClick={() => ask('clinical')}>
                  {asking === 'clinical' ? 'Pensando…' : 'Impacto clínico'}
                </button>
              </div>
              {reply && <div style={{ marginTop: 8, background: 'var(--surface2)', border: '1px solid var(--line)', borderRadius: 6, padding: 10 }}>{reply}</div>}
            </div>
          </>
        ) : (
          <>
          <dl style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '8px 12px', margin: 0 }}>
            <dt style={{ color: 'var(--muted)' }}>CVE</dt><dd className="mono" style={{ margin: 0 }}>{vulnerability.cve || 'Sin CVE'}</dd>
            <dt style={{ color: 'var(--muted)' }}>Activo</dt><dd style={{ margin: 0 }}>{vulnerability.asset_hostname}</dd>
            <dt style={{ color: 'var(--muted)' }}>CVSS</dt><dd style={{ margin: 0 }}>{vulnerability.cvss_score ?? '—'}</dd>
            <dt style={{ color: 'var(--muted)' }}>Fuente</dt><dd style={{ margin: 0 }}>{vulnerability.source_name}</dd>
            <dt style={{ color: 'var(--muted)' }}>Exposición</dt><dd style={{ margin: 0 }}>{EXPOSURE_LABEL[vulnerability.asset?.exposure] || '—'}</dd>
            <dt style={{ color: 'var(--muted)' }}>Controles ISO</dt>
            <dd style={{ margin: 0 }}>{vulnerability.control_codes?.length ? vulnerability.control_codes.join(', ') : '—'}</dd>
          </dl>
          <PriorityExplanation vulnerability={vulnerability} />
          </>
        )}
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--line)' }}>
        <button
          className="btn pri"
          style={{ width: '100%', justifyContent: 'center' }}
          disabled={!canEdit || vulnerability.status !== 'open' || creatingPlan} title={canEdit ? undefined : "Solo lectura (Auditor)"}
          onClick={handleCreatePlan}
        >
          {vulnerability.status === 'open' ? (creatingPlan ? 'Creando…' : 'Crear plan de corrección') : 'Ya tiene plan o está cerrada'}
        </button>
      </div>
    </aside>
  )
}

const EXPOSURE_LABEL = { internet: 'Expuesto a Internet', perimetral: 'Perimetral (DMZ)', interna: 'Solo red interna' }

// Explica en lenguaje llano por qué el hallazgo quedó con esa prioridad
// (el documento pide que cada decisión del agente sea explicable).
function PriorityExplanation({ vulnerability }) {
  const info = vulnerability.priority_rules
  if (!info?.nivel_base) return null
  return (
    <div style={{ borderTop: '1px solid var(--line)', paddingTop: 12 }}>
      <h3 style={{ fontSize: 13, margin: '0 0 6px' }}>Por qué esta prioridad</h3>
      <p style={{ margin: '0 0 6px', fontSize: 13 }}>
        CVSS la clasifica como <b>{SEV_LABEL[info.nivel_base]}</b>; con el contexto del activo queda en{' '}
        <span className={`badge ${SEV_BADGE[info.nivel_final]}`}>{SEV_LABEL[info.nivel_final]}</span>.
      </p>
      {info.reglas.length === 0 ? (
        <p style={{ margin: 0, color: 'var(--muted)', fontSize: 13 }}>Ninguna regla de contexto aplicó.</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, display: 'flex', flexDirection: 'column', gap: 3 }}>
          {info.reglas.map((r, i) => (
            <li key={i}><b className="mono">{r.regla}</b> — {r.explicacion}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
