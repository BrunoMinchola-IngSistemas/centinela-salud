import { useCallback, useEffect, useState } from 'react'
import { executive } from '../api/resources'
import { ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

const REFRESCO_MS = 30000
const NIVEL_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low' }

function Barra({ etiqueta, valor }) {
  return (
    <div className="hbar">
      <span>{etiqueta}</span>
      <div className="track"><div className="fill" style={{ width: `${valor}%` }} /></div>
      <span className="val">{valor} %</span>
    </div>
  )
}

/** Mini gráfico de línea del Risk Score diario (línea base = primer punto). */
function Evolucion({ puntos }) {
  if (puntos.length < 2) {
    return <p className="note">La línea base se tomó hoy. La evolución aparece a partir del segundo día de operación (el agente toma una foto diaria).</p>
  }
  const w = 520
  const h = 120
  const x = (i) => 10 + (i * (w - 20)) / (puntos.length - 1)
  const y = (v) => h - 10 - (v * (h - 20)) / 100
  const d = puntos.map((p, i) => `${i ? 'L' : 'M'}${x(i)},${y(p.risk_score)}`).join(' ')
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width="100%" role="img" aria-label="Evolución del Risk Score">
      <line x1="10" x2={w - 10} y1={y(35)} y2={y(35)} stroke="var(--low)" strokeDasharray="4 4" />
      <line x1="10" x2={w - 10} y1={y(65)} y2={y(65)} stroke="var(--crit)" strokeDasharray="4 4" />
      <path d={d} fill="none" stroke="var(--brand)" strokeWidth="2.5" />
      {puntos.map((p, i) => <circle key={p.fecha} cx={x(i)} cy={y(p.risk_score)} r="3" fill="var(--brand)"><title>{p.fecha}: {p.risk_score}</title></circle>)}
    </svg>
  )
}

/**
 * HU16 + HU20: Cuadro de mando de la Gerencia. Lenguaje no técnico,
 * semáforo, % de cumplimiento ISO y Ley 29733, y variación del riesgo
 * respecto de la línea base (OE3). Se actualiza solo cada 30 s.
 */
export default function Executive() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    executive
      .summary()
      .then(({ data }) => { setData(data); setError('') })
      .catch((err) => setError(extractErrorMessage(err)))
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, REFRESCO_MS)
    return () => clearInterval(id)
  }, [load])

  if (error && !data) return <ErrorState message={error} onRetry={load} />
  if (!data) return <LoadingState />
  const r = data.riesgo
  const variacion = data.variacion_vs_linea_base

  return (
    <div>
      <div className="page-head">
        <h1>Cuadro de mando ejecutivo</h1>
        <p>{data.organizacion} · se actualiza solo · última lectura {new Date(data.actualizado_en).toLocaleTimeString('es-PE')}</p>
      </div>

      <div className={`semaforo ${r.semaforo}`} style={{ marginBottom: 14 }}>
        <div className="luz">{r.score}</div>
        <div>
          <div style={{ fontFamily: 'var(--font-display)', fontSize: 20, textTransform: 'uppercase', letterSpacing: '.06em' }}>
            Nivel de riesgo {r.nivel}
          </div>
          <p style={{ margin: '4px 0 0' }}>{r.mensaje}</p>
        </div>
      </div>

      <div className="grid-3" style={{ marginBottom: 14 }}>
        <div className="panel pb kpi"><b>{data.cumplimiento_global} %</b><span>Cumplimiento ISO/IEC 27001</span></div>
        <div className="panel pb kpi"><b>{data.cumplimiento_ley_29733} %</b><span>Cumplimiento Ley N.° 29733 (datos personales)</span></div>
        <div className="panel pb kpi"><b>{r.graves}</b><span>Problemas graves sin resolver</span></div>
        <div className="panel pb kpi"><b>{data.vencidos}</b><span>Correcciones fuera de plazo</span></div>
        <div className="panel pb kpi"><b>{data.aprobaciones_pendientes}</b><span>Decisiones esperando su aprobación</span></div>
        <div className="panel pb kpi"><b>{data.incidentes_30_dias}</b><span>Incidentes reportados (30 días)</span></div>
      </div>

      <div className="grid-2">
        <div className="panel">
          <div className="ph"><b>Lo más importante ahora</b></div>
          <div className="pb">
            {data.principales_riesgos.length === 0 && <p className="muted">No hay problemas abiertos.</p>}
            <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 8 }}>
              {data.principales_riesgos.map((x) => (
                <li key={x.id}><span className={`badge ${NIVEL_BADGE[x.nivel] || 'b-mut'}`} style={{ marginRight: 6 }}>{x.nivel === 'critical' ? 'Urgente' : x.nivel === 'high' ? 'Importante' : 'Moderado'}</span>{x.texto}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="panel">
          <div className="ph"><b>Cumplimiento por dominio</b><span className="r">ISO/IEC 27001:2022 Anexo A</span></div>
          <div className="pb">
            {data.por_dominio.map((d) => <Barra key={d.dominio} etiqueta={d.tema} valor={d.cumplimiento} />)}
          </div>
        </div>

        <div className="panel" style={{ gridColumn: '1 / -1' }}>
          <div className="ph">
            <b>Evolución del riesgo</b>
            <span className="r">
              {data.linea_base
                ? <>Línea base {data.linea_base.fecha}: {data.linea_base.risk_score} · variación {variacion > 0 ? '+' : ''}{variacion} puntos</>
                : 'Sin línea base aún'}
            </span>
          </div>
          <div className="pb"><Evolucion puntos={data.historial} /></div>
        </div>
      </div>
    </div>
  )
}
