import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { controls as controlsApi } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

export default function Controls() {
  const { canEdit } = useAuth()
  const [list, setList] = useState([])
  const [themes, setThemes] = useState([])
  const [themeFilter, setThemeFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [assessing, setAssessing] = useState(null)
  const [actionError, setActionError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    controlsApi
      .list()
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
    controlsApi.byTheme().then((res) => setThemes(res.data)).catch(() => setThemes([]))
  }

  // Orden natural del código ISO (5.7 antes que 5.15), no alfabético.
  const isoKey = (code = '') => code.split('.').map((n) => n.padStart(3, '0')).join('.')
  const visible = (themeFilter ? list.filter((c) => c.theme_display === themeFilter) : list)
    .slice()
    .sort((a, b) => isoKey(a.iso_code).localeCompare(isoKey(b.iso_code)))

  useEffect(load, [])

  async function assess(id) {
    setAssessing(id)
    setActionError('')
    try {
      await controlsApi.assess(id)
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setAssessing(null)
    }
  }

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Controles de seguridad</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>
          ISO/IEC 27001:2022 · controles del Anexo A seleccionados para salud (con referencia a ISO 27799). Cumplimiento calculado a partir de los hallazgos.
        </p>
      </div>
      {themes.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${themes.length + 1}, minmax(0, 1fr))`, gap: 10, marginBottom: 14 }}>
          <button className={`panel theme-card ${themeFilter === '' ? 'on' : ''}`} onClick={() => setThemeFilter('')}>
            <span className="tc-label">Todos</span>
            <b className="tc-value">{list.length}</b>
            <span className="tc-sub">controles</span>
          </button>
          {themes.map((t) => (
            <button key={t.tema} className={`panel theme-card ${themeFilter === t.tema ? 'on' : ''}`} onClick={() => setThemeFilter(t.tema)}>
              <span className="tc-label">{t.tema}</span>
              <b className="tc-value" style={{ color: t.cumplimiento >= 85 ? 'var(--ok)' : t.cumplimiento >= 70 ? 'var(--med)' : 'var(--crit)' }}>{t.cumplimiento}%</b>
              <span className="tc-sub">{t.controles} controles</span>
            </button>
          ))}
        </div>
      )}
      {actionError && (
        <div className="panel" style={{ padding: '8px 12px', marginBottom: 10, color: 'var(--crit)', fontSize: 13 }}>
          {actionError}
        </div>
      )}
      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && list.length === 0 && <EmptyState message="Aún no hay controles cargados." />}
        {!loading && !error && visible.length > 0 && (
          <table>
            <thead><tr><th>Código</th><th>Control</th><th>Cumplimiento</th><th>Brechas</th><th></th></tr></thead>
            <tbody>
              {visible.map((c) => (
                <tr key={c.id}>
                  <td className="mono" style={{ whiteSpace: 'nowrap' }}>A.{c.iso_code}</td>
                  <td>
                    <b style={{ fontWeight: 500, display: 'block' }}>{c.name}</b>
                    {c.health_rationale && <span style={{ color: 'var(--muted)', fontSize: 12.5 }}>{c.health_rationale}</span>}
                  </td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <b style={{ width: 38 }}>{c.compliance_score}%</b>
                      <div style={{ flex: 1, minWidth: 90, height: 6, borderRadius: 3, background: 'var(--line)', overflow: 'hidden' }}>
                        <div style={{ width: `${c.compliance_score}%`, height: '100%', background: c.compliance_score >= 85 ? 'var(--ok)' : c.compliance_score >= 70 ? 'var(--med)' : 'var(--crit)' }} />
                      </div>
                    </div>
                  </td>
                  <td>{c.open_findings ? <span className="badge b-high">{c.open_findings}</span> : <span className="badge b-ok">Ninguna</span>}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn sm" disabled={!canEdit || assessing === c.id} title={canEdit ? undefined : "Solo lectura (Auditor)"} onClick={() => assess(c.id)}>
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
