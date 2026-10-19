import { useEffect, useState } from 'react'
import { remediationPlans, sources, vulnerabilities } from '../api/resources'

const SEV_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
const SEV_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low' }
const ST_LABEL = { open: 'Abierta', in_plan: 'En plan', in_verification: 'En verificación', closed: 'Cerrada' }
const ST_BADGE = { open: 'b-mut', in_plan: 'b-br', in_verification: 'b-med', closed: 'b-ok' }

export default function Vulnerabilities() {
  const [list, setList] = useState([])
  const [selected, setSelected] = useState(null)
  const [severity, setSeverity] = useState('')
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)

  function load() {
    setLoading(true)
    vulnerabilities
      .list({ severity: severity || undefined, search: search || undefined })
      .then((res) => setList(res.data.results ?? res.data))
      .finally(() => setLoading(false))
  }

  useEffect(load, [severity, search])

  async function handleSync() {
    setSyncing(true)
    try {
      await sources.sync()
      load()
    } finally {
      setSyncing(false)
    }
  }

  async function openDetail(id) {
    const { data } = await vulnerabilities.retrieve(id)
    setSelected(data)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 380px' : '1fr', gap: 14 }}>
      <div>
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 12, marginBottom: 16 }}>
          <div>
            <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Vulnerabilidades</h1>
            <p style={{ color: 'var(--muted)', margin: 0 }}>Hallazgos de OpenVAS y Wazuh</p>
          </div>
          <button className="btn" style={{ marginLeft: 'auto' }} onClick={handleSync} disabled={syncing}>
            {syncing ? 'Sincronizando…' : 'Sincronizar fuentes'}
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} style={{ border: '1px solid var(--line)', borderRadius: 6, padding: '5px 9px', background: 'var(--surface)' }}>
            <option value="">Todas las severidades</option>
            <option value="critical">Crítica</option>
            <option value="high">Alta</option>
            <option value="medium">Media</option>
            <option value="low">Baja</option>
          </select>
          <input
            placeholder="Buscar por CVE, título o activo"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ flex: 1, minWidth: 200, border: '1px solid var(--line)', borderRadius: 6, padding: '5px 9px', background: 'var(--surface)' }}
          />
        </div>

        <div className="panel">
          <table>
            <thead>
              <tr>
                <th>Severidad</th><th>Vulnerabilidad</th><th>Activo</th><th>Prioridad IA</th><th>Estado</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr><td colSpan={5}><div className="empty">Cargando…</div></td></tr>
              )}
              {!loading && list.length === 0 && (
                <tr><td colSpan={5}><div className="empty">Ningún hallazgo coincide con los filtros.</div></td></tr>
              )}
              {!loading && list.map((v) => (
                <tr key={v.id} className={`row ${selected?.id === v.id ? 'sel' : ''}`} onClick={() => openDetail(v.id)}>
                  <td><span className={`badge ${SEV_BADGE[v.severity]}`}>{SEV_LABEL[v.severity]}</span></td>
                  <td>
                    <b style={{ fontWeight: 500, display: 'block' }}>{v.title}</b>
                    <span className="mono" style={{ color: 'var(--muted)' }}>{v.id.slice(0, 8)} · {v.cve || 'sin CVE'}</span>
                  </td>
                  <td>{v.asset_hostname}</td>
                  <td>{v.priority_score}</td>
                  <td><span className={`badge ${ST_BADGE[v.status]}`}>{ST_LABEL[v.status]}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
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
  const [tab, setTab] = useState('ia')
  const [analyzing, setAnalyzing] = useState(false)
  const [reply, setReply] = useState('')
  const [creatingPlan, setCreatingPlan] = useState(false)

  async function handleAnalyze() {
    setAnalyzing(true)
    try {
      const { data } = await vulnerabilities.analyze(vulnerability.id)
      onUpdated(data)
    } finally {
      setAnalyzing(false)
    }
  }

  async function handleCreatePlan() {
    setCreatingPlan(true)
    try {
      await remediationPlans.create({ vulnerability: vulnerability.id, owner_name: 'Por asignar' })
      const { data } = await vulnerabilities.retrieve(vulnerability.id)
      onUpdated(data)
    } finally {
      setCreatingPlan(false)
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
              <button className="btn pri" onClick={handleAnalyze} disabled={analyzing}>
                {analyzing ? 'Analizando con Qwen…' : 'Analizar con IA'}
              </button>
            )}
            <div>
              <h3 style={{ fontSize: 13, margin: '0 0 5px' }}>Preguntar al asistente</h3>
              <div style={{ display: 'flex', gap: 6 }}>
                <button className="btn sm" onClick={async () => setReply((await vulnerabilities.explainSimple(vulnerability.id)).data.text)}>
                  Explicar simple
                </button>
                <button className="btn sm" onClick={async () => setReply((await vulnerabilities.clinicalImpact(vulnerability.id)).data.text)}>
                  Impacto clínico
                </button>
              </div>
              {reply && <div style={{ marginTop: 8, background: 'var(--surface2)', border: '1px solid var(--line)', borderRadius: 6, padding: 10 }}>{reply}</div>}
            </div>
          </>
        ) : (
          <dl style={{ display: 'grid', gridTemplateColumns: '110px 1fr', gap: '8px 12px', margin: 0 }}>
            <dt style={{ color: 'var(--muted)' }}>CVE</dt><dd className="mono" style={{ margin: 0 }}>{vulnerability.cve || 'Sin CVE'}</dd>
            <dt style={{ color: 'var(--muted)' }}>Activo</dt><dd style={{ margin: 0 }}>{vulnerability.asset_hostname}</dd>
            <dt style={{ color: 'var(--muted)' }}>CVSS</dt><dd style={{ margin: 0 }}>{vulnerability.cvss_score ?? '—'}</dd>
            <dt style={{ color: 'var(--muted)' }}>Fuente</dt><dd style={{ margin: 0 }}>{vulnerability.source_name}</dd>
          </dl>
        )}
      </div>

      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--line)' }}>
        <button
          className="btn pri"
          style={{ width: '100%', justifyContent: 'center' }}
          disabled={vulnerability.status !== 'open' || creatingPlan}
          onClick={handleCreatePlan}
        >
          {vulnerability.status === 'open' ? (creatingPlan ? 'Creando…' : 'Crear plan de corrección') : 'Ya tiene plan o está cerrada'}
        </button>
      </div>
    </aside>
  )
}
