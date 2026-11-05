import { useCallback, useEffect, useState } from 'react'
import { assets, saveBlob, vulnerabilities } from '../api/resources'
import { ErrorState, LoadingState, extractErrorMessage, extractErrorMessageAsync } from '../components/DataState'
import Select from '../components/Select'

const SEV = [
  { value: '', label: 'Todas las severidades' },
  { value: 'critical', label: 'Crítica' },
  { value: 'high', label: 'Alta' },
  { value: 'medium', label: 'Media' },
  { value: 'low', label: 'Baja' },
]
const SEV_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
const ST_LABEL = { open: 'Abierta', in_plan: 'En plan', in_verification: 'En verificación', closed: 'Cerrada' }

function Tendencia({ meses }) {
  const max = Math.max(1, ...meses.flatMap((m) => [m.detectadas, m.cerradas, m.abiertas_al_cierre]))
  const w = 560
  const h = 170
  const paso = (w - 40) / meses.length
  const y = (v) => h - 24 - (v * (h - 40)) / max
  const linea = meses.map((m, i) => `${i ? 'L' : 'M'}${30 + i * paso + paso / 2},${y(m.abiertas_al_cierre)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Tendencia mensual">
      {meses.map((m, i) => {
        const x = 30 + i * paso
        return (
          <g key={m.mes}>
            <rect x={x + paso * 0.15} y={y(m.detectadas)} width={paso * 0.3} height={h - 24 - y(m.detectadas)} fill="var(--high)" rx="3"><title>{m.mes}: {m.detectadas} detectadas</title></rect>
            <rect x={x + paso * 0.5} y={y(m.cerradas)} width={paso * 0.3} height={h - 24 - y(m.cerradas)} fill="var(--ok)" rx="3"><title>{m.mes}: {m.cerradas} cerradas</title></rect>
            <text x={x + paso / 2} y={h - 6} textAnchor="middle" fontSize="11" fill="var(--muted)">{m.mes}</text>
          </g>
        )
      })}
      <path d={linea} fill="none" stroke="var(--brand)" strokeWidth="2.5" />
    </svg>
  )
}

/** HU10: historial filtrable (fecha, severidad, activo) y tendencia de al menos 3 meses. */
export default function History() {
  const [filtros, setFiltros] = useState({ detectado_desde: '', detectado_hasta: '', severity: '', asset: '' })
  const [meses, setMeses] = useState('6')
  const [lista, setLista] = useState([])
  const [count, setCount] = useState(0)
  const [trend, setTrend] = useState(null)
  const [activos, setActivos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const params = useCallback(() => {
    const p = {}
    Object.entries(filtros).forEach(([k, v]) => { if (v) p[k] = v })
    return p
  }, [filtros])

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([vulnerabilities.list(params()), vulnerabilities.trend({ ...params(), meses })])
      .then(([l, t]) => {
        setLista(l.data.results ?? l.data)
        setCount(l.data.count ?? (l.data.results ?? l.data).length)
        setTrend(t.data)
        setError('')
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [params, meses])

  useEffect(load, [load])
  useEffect(() => {
    assets.list().then(({ data }) => setActivos(data.results ?? data)).catch(() => {})
  }, [])

  async function exportar(formato) {
    try {
      saveBlob(await vulnerabilities.exportFile({ ...params(), formato }), `historial.${formato}`)
    } catch (err) {
      setError(await extractErrorMessageAsync(err))
    }
  }

  const set = (k) => (e) => setFiltros({ ...filtros, [k]: e?.target ? e.target.value : e })

  return (
    <div>
      <div className="page-head">
        <h1>Historial y tendencia</h1>
        <p>Vulnerabilidades detectadas en el tiempo · filtra y exporta</p>
      </div>

      <div className="panel pb row-actions" style={{ marginBottom: 14 }}>
        <label className="field">Desde<input type="date" value={filtros.detectado_desde} onChange={set('detectado_desde')} /></label>
        <label className="field">Hasta<input type="date" value={filtros.detectado_hasta} onChange={set('detectado_hasta')} /></label>
        <Select aria-label="Severidad" value={filtros.severity} onChange={set('severity')} options={SEV} />
        <Select aria-label="Activo" value={filtros.asset} onChange={set('asset')} options={[{ value: '', label: 'Todos los activos' }, ...activos.map((a) => ({ value: a.id, label: a.hostname }))]} />
        <Select aria-label="Meses" value={meses} onChange={setMeses} options={['3', '6', '12'].map((m) => ({ value: m, label: `Tendencia: ${m} meses` }))} />
        <span style={{ marginLeft: 'auto' }} className="row-actions">
          <button className="btn sm" onClick={() => exportar('csv')}>CSV</button>
          <button className="btn sm" onClick={() => exportar('xlsx')}>Excel</button>
          <button className="btn sm" onClick={() => exportar('pdf')}>PDF</button>
        </span>
      </div>

      {error && <ErrorState message={error} onRetry={load} />}
      {loading && !trend && <LoadingState />}

      {trend && (
        <div className="panel" style={{ marginBottom: 14 }}>
          <div className="ph">
            <b>Tendencia mensual</b>
            <span className="r"><span style={{ color: 'var(--high)' }}>■</span> detectadas · <span style={{ color: 'var(--ok)' }}>■</span> cerradas · <span style={{ color: 'var(--brand)' }}>━</span> abiertas al cierre del mes</span>
          </div>
          <div className="pb">
            {trend.suficiente ? <Tendencia meses={trend.meses} /> : <p className="note">{trend.mensaje}</p>}
          </div>
        </div>
      )}

      <div className="panel">
        <div className="ph"><b>Hallazgos</b><span className="r">{count} en total (se muestran {lista.length})</span></div>
        <table>
          <thead><tr><th>Detectado</th><th>Hallazgo</th><th>Activo</th><th>Severidad</th><th>Estado</th><th>Cerrado</th></tr></thead>
          <tbody>
            {lista.map((v) => (
              <tr key={v.id}>
                <td className="mono">{new Date(v.first_detected_at).toLocaleDateString('es-PE')}</td>
                <td>{v.title}<div className="muted small mono">{v.cve || 'sin CVE'}</div></td>
                <td>{v.asset_hostname || <span className="badge b-mut">Pendiente de asociación</span>}</td>
                <td>{SEV_LABEL[v.severity]}</td>
                <td>{ST_LABEL[v.status]}</td>
                <td className="mono">{v.closed_at ? new Date(v.closed_at).toLocaleDateString('es-PE') : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
