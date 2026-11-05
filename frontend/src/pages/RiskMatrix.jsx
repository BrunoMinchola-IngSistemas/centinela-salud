import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { assets, vulnerabilities } from '../api/resources'
import { ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import Select from '../components/Select'

const NIVELES = [
  { value: '', label: 'Todos los niveles' },
  { value: 'critico', label: 'Crítico' },
  { value: 'alto', label: 'Alto' },
  { value: 'medio', label: 'Medio' },
  { value: 'bajo', label: 'Bajo' },
]
const PROB = ['', 'Rara', 'Improbable', 'Posible', 'Probable', 'Casi segura']
const IMP = ['', 'Insignificante', 'Menor', 'Moderado', 'Mayor', 'Catastrófico']

/**
 * HU09: matriz de riesgos 5x5 (probabilidad x impacto) con los
 * hallazgos abiertos. Probabilidad: EPSS / KEV / exposición. Impacto:
 * criticidad del activo y datos clínicos. Se actualiza cada 30 s.
 */
export default function RiskMatrix() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [nivel, setNivel] = useState('')
  const [asset, setAsset] = useState('')
  const [lista, setLista] = useState([])
  const [sel, setSel] = useState(null)

  const load = useCallback(() => {
    vulnerabilities
      .riskMatrix({ nivel: nivel || undefined, asset: asset || undefined })
      .then(({ data }) => { setData(data); setError('') })
      .catch((err) => setError(extractErrorMessage(err)))
  }, [nivel, asset])

  useEffect(() => {
    load()
    const id = setInterval(load, 30000)
    return () => clearInterval(id)
  }, [load])

  useEffect(() => {
    assets.list({ page_size: 200 }).then(({ data }) => setLista(data.results ?? data)).catch(() => {})
  }, [])

  const celdas = useMemo(() => {
    const m = {}
    data?.celdas.forEach((c) => { m[`${c.probabilidad}-${c.impacto}`] = c })
    return m
  }, [data])

  if (error && !data) return <ErrorState message={error} onRetry={load} />
  if (!data) return <LoadingState />
  const elegida = sel ? celdas[sel] : null

  return (
    <div>
      <div className="page-head">
        <h1>Matriz de riesgos</h1>
        <p>Hallazgos abiertos según probabilidad e impacto · actualizada {new Date(data.actualizado_en).toLocaleTimeString('es-PE')}</p>
      </div>

      <div className="row-actions" style={{ marginBottom: 12 }}>
        <Select aria-label="Nivel de riesgo" value={nivel} onChange={(v) => { setNivel(v); setSel(null) }} options={NIVELES} />
        <Select
          aria-label="Activo"
          value={asset}
          onChange={(v) => { setAsset(v); setSel(null) }}
          options={[{ value: '', label: 'Todos los activos' }, ...lista.map((a) => ({ value: a.id, label: a.hostname }))]}
        />
        <span className="muted small">{data.total} hallazgo(s) en la matriz{data.pendientes_asociacion ? ` · ${data.pendientes_asociacion} pendiente(s) de asociación (sin activo, no se ubican)` : ''}</span>
      </div>

      <div className="grid-2">
        <div className="panel pb">
          <div className="matriz">
            {[5, 4, 3, 2, 1].map((p) => (
              <FilaMatriz key={p} p={p} celdas={celdas} sel={sel} onSel={setSel} />
            ))}
            <div />
            {[1, 2, 3, 4, 5].map((i) => <div key={i} className="eje" title={IMP[i]}>{i}</div>)}
          </div>
          <p className="small muted" style={{ margin: '10px 0 0' }}>
            Vertical: probabilidad (1 {PROB[1]} → 5 {PROB[5]}). Horizontal: impacto (1 {IMP[1]} → 5 {IMP[5]}).
          </p>
        </div>

        <div className="panel">
          <div className="ph"><b>{elegida ? `Probabilidad ${elegida.probabilidad} × impacto ${elegida.impacto}` : 'Hallazgos de la celda'}</b>{elegida && <span className="r">Nivel {elegida.nivel}</span>}</div>
          <div className="pb">
            {!elegida && <p className="muted">Toca una celda para ver sus hallazgos.</p>}
            {elegida && elegida.hallazgos.length === 0 && <p className="muted">Sin hallazgos en esta celda.</p>}
            {elegida && elegida.hallazgos.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                {elegida.hallazgos.map((h) => (
                  <li key={h.id}><b style={{ fontWeight: 500 }}>{h.titulo}</b> <span className="muted small">· {h.activo} · {h.cve || 'sin CVE'}</span></li>
                ))}
              </ul>
            )}
            <p style={{ marginTop: 12 }}><Link to="/vulnerabilidades">Ver todas las vulnerabilidades →</Link></p>
          </div>
        </div>
      </div>
    </div>
  )
}

function FilaMatriz({ p, celdas, sel, onSel }) {
  return (
    <>
      <div className="eje" title={PROB[p]}>{p}</div>
      {[1, 2, 3, 4, 5].map((i) => {
        const c = celdas[`${p}-${i}`]
        const clave = `${p}-${i}`
        return (
          <button
            key={i}
            type="button"
            className={`celda ${c?.nivel || ''} ${c?.total ? '' : 'vacia'} ${sel === clave ? 'elegida' : ''}`}
            onClick={() => onSel(clave)}
            title={`Probabilidad ${p} (${PROB[p]}) · impacto ${i} (${IMP[i]}) · nivel ${c?.nivel}`}
          >
            {c?.total || '·'}
          </button>
        )
      })}
    </>
  )
}
