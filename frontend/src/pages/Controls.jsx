import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { controls as controlsApi, saveBlob } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage, extractErrorMessageAsync } from '../components/DataState'

const ESTADOS = [
  ['pendiente', 'Pendiente'],
  ['parcial', 'Parcial'],
  ['implementado', 'Implementado'],
  ['no_aplica', 'No aplica'],
]
const ESTADO_BADGE = { pendiente: 'b-crit', parcial: 'b-med', implementado: 'b-ok', no_aplica: 'b-mut' }
const NIVEL = { alto: 'Alta', medio: 'Media', bajo: 'Baja' }
const COSTO = { alto: 'Alto', medio: 'Medio', bajo: 'Bajo' }
const APLIC = { aplicable: ['Aplicable ahora', 'b-ok'], siguiente_etapa: ['Siguiente etapa', 'b-med'], futuro: ['Más adelante', 'b-mut'] }
const ROLES_EDITAN = ['admin', 'compliance', 'it_owner']

const isoKey = (code = '') => code.split('.').map((n) => n.padStart(3, '0')).join('.')

/**
 * Controles ISO/IEC 27001:2022 para salud.
 * HU11 brecha pendiente · HU12 matriz por madurez · HU13 % por dominio ·
 * HU15 recomendaciones exportables · HU16 Ley 29733.
 */
export default function Controls() {
  const { canEdit, role } = useAuth()
  const [tab, setTab] = useState('controles')
  const [list, setList] = useState([])
  const [temas, setTemas] = useState(null)
  const [filtro, setFiltro] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [assessing, setAssessing] = useState(null)
  const puedeEditar = canEdit && ROLES_EDITAN.includes(role)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    Promise.all([controlsApi.list(), controlsApi.byTheme()])
      .then(([l, t]) => { setList(l.data.results ?? l.data); setTemas(t.data) })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  async function cambiarEstado(control, estado) {
    setAviso('')
    try {
      await controlsApi.setState(control.id, estado)
      load()
    } catch (err) {
      setAviso(extractErrorMessage(err))
    }
  }

  async function assess(id) {
    setAssessing(id)
    try {
      const { data } = await controlsApi.assess(id)
      setAviso(data.recommendation)
    } catch (err) {
      setAviso(extractErrorMessage(err))
    } finally {
      setAssessing(null)
    }
  }

  const visibles = (filtro ? list.filter((c) => c.theme === filtro) : list).slice().sort((a, b) => isoKey(a.iso_code).localeCompare(isoKey(b.iso_code)))

  return (
    <div>
      <div className="page-head">
        <h1>Controles de seguridad</h1>
        <p>ISO/IEC 27001:2022 · Anexo A seleccionado para salud (ISO 27799) y Ley N.° 29733</p>
      </div>

      {temas && (
        <div className="grid-3" style={{ marginBottom: 14 }}>
          <div className="panel pb kpi"><b>{temas.global} %</b><span>Cumplimiento global ISO 27001</span></div>
          <div className="panel pb kpi"><b>{temas.ley_29733} %</b><span>Controles de la Ley 29733</span></div>
          <div className="panel pb kpi"><b>{list.filter((c) => c.brecha_pendiente).length}</b><span>Brechas pendientes (con hallazgos y sin evidencia)</span></div>
        </div>
      )}

      <div className="tabs">
        {[['controles', 'Controles'], ['dominios', 'Cumplimiento por dominio'], ['madurez', 'Matriz por madurez'], ['recomendaciones', 'Recomendaciones']].map(([k, l]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {aviso && <div className="note" style={{ marginBottom: 12 }}>{aviso}</div>}

      {loading && !list.length && <LoadingState />}
      {error && <ErrorState message={error} onRetry={load} />}

      {tab === 'controles' && !error && list.length > 0 && (
        <>
          <div className="row-actions" style={{ marginBottom: 10 }}>
            <button className={`btn sm ${filtro === '' ? 'pri' : ''}`} onClick={() => setFiltro('')}>Todos ({list.length})</button>
            {temas?.dominios.map((d) => (
              <button key={d.dominio} className={`btn sm ${filtro === d.dominio ? 'pri' : ''}`} onClick={() => setFiltro(d.dominio)}>
                {d.tema} · {d.cumplimiento} %
              </button>
            ))}
          </div>
          <div className="panel">
            <table>
              <thead><tr><th>Código</th><th>Control</th><th>Estado</th><th>Hallazgos</th><th>Evidencia</th><th /></tr></thead>
              <tbody>
                {visibles.map((c) => (
                  <tr key={c.id}>
                    <td className="mono" style={{ whiteSpace: 'nowrap' }}>A.{c.iso_code}</td>
                    <td>
                      <b style={{ fontWeight: 500, display: 'block' }}>{c.name}</b>
                      <span className="muted small">{c.health_rationale}</span>
                      <div className="small" style={{ marginTop: 3 }}>
                        {c.mappings.filter((m) => m.framework !== 'iso27001').map((m) => (
                          <span key={m.framework} className="badge b-mut" style={{ marginRight: 4 }}>{m.framework === 'ley29733' ? `Ley 29733 ${m.code}` : `${m.framework.toUpperCase()} ${m.code}`}</span>
                        ))}
                      </div>
                    </td>
                    <td>
                      {puedeEditar ? (
                        <select value={c.estado_implementacion} onChange={(e) => cambiarEstado(c, e.target.value)} aria-label={`Estado de ${c.iso_code}`}>
                          {ESTADOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
                        </select>
                      ) : (
                        <span className={`badge ${ESTADO_BADGE[c.estado_implementacion]}`}>{c.estado_display}</span>
                      )}
                      {c.estado_actualizado_por && <div className="muted small">por {c.estado_actualizado_por}</div>}
                    </td>
                    <td>
                      {c.open_findings ? <span className="badge b-high">{c.open_findings} abiertos</span> : <span className="badge b-ok">Ninguno</span>}
                      <div className="muted small">puntaje técnico {c.compliance_score} %</div>
                    </td>
                    <td>
                      {c.brecha_pendiente
                        ? <span className="badge b-crit" title="Tiene hallazgos vinculados y ninguna evidencia registrada (HU11)">Brecha pendiente</span>
                        : c.tiene_evidencia ? <span className="badge b-ok">Con evidencia</span> : <span className="badge b-mut">—</span>}
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <Link className="btn sm" to={`/evidencias?control=${c.id}`}>Evidencia</Link>{' '}
                      <button className="btn sm" disabled={!canEdit || assessing === c.id} onClick={() => assess(c.id)}>{assessing === c.id ? 'Evaluando…' : 'Evaluar con IA'}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'dominios' && temas && <Dominios temas={temas} />}
      {tab === 'madurez' && <MatrizMadurez />}
      {tab === 'recomendaciones' && <Recomendaciones />}
    </div>
  )
}

function Dominios({ temas }) {
  return (
    <div className="panel">
      <div className="ph"><b>Cumplimiento por dominio del Anexo A</b><span className="r">implementado = 100 % · parcial = 50 % · actualizado {new Date(temas.actualizado_en).toLocaleTimeString('es-PE')}</span></div>
      <div className="pb">
        {temas.dominios.map((d) => (
          <div key={d.dominio} className="hbar" style={{ gridTemplateColumns: '150px 1fr 48px' }}>
            <span>{d.tema}<div className="muted small">{d.implementados} impl. · {d.parciales} parc. · {d.pendientes} pend.</div></span>
            <div className="track"><div className="fill" style={{ width: `${d.cumplimiento}%` }} /></div>
            <span className="val">{d.cumplimiento} %</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MatrizMadurez() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    controlsApi.applicable().then(({ data }) => setData(data)).catch((err) => setError(extractErrorMessage(err)))
  }, [])
  if (error) {
    return (
      <div className="panel pb">
        <p className="alert-err">{error}</p>
        <Link className="btn" to="/configuracion">Registrar el nivel de madurez en Configuración</Link>
      </div>
    )
  }
  if (!data) return <LoadingState />
  return (
    <div className="stack">
      <p className="note">Nivel de madurez registrado: <b>{data.nivel_display}</b>. Los controles se agrupan por dominio y se marcan como aplicables ahora, para la siguiente etapa o más adelante.</p>
      <div className="grid-2">
        {data.dominios.map((d) => (
          <div key={d.dominio} className="panel">
            <div className="ph"><b>{d.tema}</b><span className="r">{d.aplicables} aplicables ahora</span></div>
            <table>
              <tbody>
                {d.controles.map((c) => (
                  <tr key={c.id}>
                    <td className="mono">A.{c.codigo}</td>
                    <td>{c.nombre}<div className="muted small">madurez {c.madurez_minima} · criticidad {NIVEL[c.criticidad]} · costo {COSTO[c.costo]}</div></td>
                    <td><span className={`badge ${APLIC[c.aplicabilidad][1]}`}>{APLIC[c.aplicabilidad][0]}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </div>
  )
}

function Recomendaciones() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    controlsApi.recommendations().then(({ data }) => setData(data)).catch((err) => setError(extractErrorMessage(err)))
  }, [])
  async function exportar(formato) {
    try {
      saveBlob(await controlsApi.recommendationsFile(formato), `plan_accion.${formato}`)
    } catch (err) {
      setError(await extractErrorMessageAsync(err))
    }
  }
  if (error) return <ErrorState message={error} />
  if (!data) return <LoadingState />
  if (!data.recomendaciones.length) return <div className="panel"><EmptyState message={data.mensaje} /></div>
  return (
    <div className="panel">
      <div className="ph">
        <b>Plan de acción recomendado</b>
        <span className="r row-actions">
          ordenado por criticidad y costo ·
          <button className="btn sm" onClick={() => exportar('pdf')}>PDF</button>
          <button className="btn sm" onClick={() => exportar('xlsx')}>Excel</button>
        </span>
      </div>
      <table>
        <thead><tr><th>#</th><th>Acción</th><th>Criticidad</th><th>Costo</th><th>Hallazgos</th><th>Por qué</th></tr></thead>
        <tbody>
          {data.recomendaciones.map((r) => (
            <tr key={r.id}>
              <td className="mono">{r.prioridad}</td>
              <td>{r.accion}<div className="muted small">{r.dominio} · {r.estado}</div></td>
              <td><span className={`badge ${r.criticidad === 'alto' ? 'b-crit' : r.criticidad === 'medio' ? 'b-med' : 'b-low'}`}>{NIVEL[r.criticidad]}</span></td>
              <td>{COSTO[r.costo]}</td>
              <td>{r.hallazgos_abiertos}</td>
              <td className="small muted">{r.motivo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
