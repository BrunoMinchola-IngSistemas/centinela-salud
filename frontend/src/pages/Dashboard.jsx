import { useEffect, useState } from 'react'
import { dashboard } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import { Donut, Ring, SEV_COLOR, SEV_LABEL, SEV_ORDER, StackedBars } from '../components/Charts'
import {
  IconActivity, IconAlert, IconBook, IconBrain, IconCheckCircle, IconClock, IconCross, IconLayers, IconUserCheck, IconZap,
} from '../components/Icons'
import './Dashboard.css'

const SEV_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low' }

// Capacidades del agente que se muestran bajo el escudo. Son las piezas
// reales del sistema (ver CLAUDE.md), no funciones inventadas.
const CAPABILITIES = [
  { icon: IconBrain, label: 'IA y aprendizaje automático' },
  { icon: IconLayers, label: 'Reglas de contexto R1-R5' },
  { icon: IconBook, label: 'Controles ISO 27001' },
  { icon: IconZap, label: 'Priorización en tiempo real' },
  { icon: IconUserCheck, label: 'Acciones con aprobación' },
]

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  function load() {
    setLoading(true)
    setError('')
    dashboard
      .summary()
      .then((res) => setData(res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  if (loading) return <LoadingState label="Cargando panel general…" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!data) return null

  // Distribución por severidad: el resumen la trae desglosada por tipo
  // de activo, así que aquí se suma para el anillo.
  const bySeverity = SEV_ORDER.reduce((acc, sev) => ({ ...acc, [sev]: 0 }), {})
  for (const row of data.exposure_by_asset_type || []) {
    for (const sev of SEV_ORDER) bySeverity[sev] += row.by_severity?.[sev] || 0
  }
  const segments = SEV_ORDER.map((sev) => ({ key: sev, value: bySeverity[sev], color: SEV_COLOR[sev] }))
  const complianceColor = data.avg_compliance >= 85 ? 'var(--ok)' : data.avg_compliance >= 70 ? 'var(--med)' : 'var(--crit)'
  const complianceLabel = data.avg_compliance >= 85 ? 'Conforme' : data.avg_compliance >= 70 ? 'Parcial' : 'Con brechas'

  return (
    <div className="dash">
      <div className="page-head">
        <h1>Panel general</h1>
        <p>Monitoreo en tiempo real y protección asistida por IA</p>
      </div>

      <div className="dash-grid">
        {/* Columna izquierda ------------------------------------------- */}
        <section className="panel dash-card">
          <div className="ph"><h2>Monitoreo de hallazgos</h2></div>
          <div className="pb">
            <div className="stat-row">
              <div className="stat-big">{data.open_count}</div>
              <div className="stat-side">
                <span className="stat-delta ok"><IconCheckCircle size={14} />{data.closed_count} cerradas</span>
                <span className="stat-sub">vulnerabilidades abiertas</span>
              </div>
            </div>
            <div className="stat-caption">Exposición por tipo de activo</div>
            {data.exposure_by_asset_type?.length ? (
              <StackedBars rows={data.exposure_by_asset_type} />
            ) : (
              <EmptyState message="Sin activos registrados." />
            )}
          </div>
        </section>

        {/* Centro: escudo ----------------------------------------------- */}
        <section className="hero">
          <div className="hero-stage">
            <HeroShield />
            <div className="hero-text">
              <span className="hero-kicker">IA Centinela</span>
              <b>Detección de vulnerabilidades</b>
              <small>Protección en tiempo real</small>
            </div>
          </div>
          <ul className="hero-flags">
            <li className="flag crit">
              <IconAlert size={18} />
              <div><b>{data.critical_open}</b><span>Críticas abiertas</span></div>
            </li>
            <li className="flag high">
              <IconClock size={18} />
              <div><b>{data.overdue_count}</b><span>Plazos vencidos</span></div>
            </li>
            <li className="flag ok">
              <IconCheckCircle size={18} />
              <div><b>{data.closed_count}</b><span>Cerradas</span></div>
            </li>
          </ul>
          <ul className="capabilities">
            {CAPABILITIES.map(({ icon: Ico, label }) => (
              <li key={label}><Ico size={22} /><span>{label}</span></li>
            ))}
          </ul>
        </section>

        {/* Columna derecha ---------------------------------------------- */}
        <section className="panel dash-card">
          <div className="ph"><h2>Distribución de riesgo</h2><span className="r">Hallazgos abiertos</span></div>
          <div className="pb donut-wrap">
            <Donut segments={segments} total={data.open_count} centerValue={data.open_count} centerLabel="abiertos" />
            <ul className="legend">
              {SEV_ORDER.map((sev) => (
                <li key={sev}>
                  <i style={{ background: SEV_COLOR[sev], boxShadow: `0 0 8px ${SEV_COLOR[sev]}` }} />
                  <span>{SEV_LABEL[sev]}</span>
                  <b>{bySeverity[sev]}</b>
                  <small>{data.open_count ? Math.round((bySeverity[sev] / data.open_count) * 100) : 0}%</small>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <section className="panel dash-card">
          <div className="ph"><h2>Cola priorizada por IA</h2><span className="r">Puntaje contextual</span></div>
          <ul className="queue">
            {data.top_priority.length === 0 && <EmptyState message="Sin hallazgos abiertos." />}
            {data.top_priority.map((v) => (
              <li key={v.id} className="queue-item">
                <span className={`queue-icon ${v.severity}`}><IconActivity size={16} /></span>
                <div className="queue-body">
                  <b>{v.title}</b>
                  <span className="mono">{v.cve || 'Sin CVE'} · {v.asset__hostname}</span>
                </div>
                <span className={`badge ${SEV_BADGE[v.severity]}`}>{SEV_LABEL[v.severity]}</span>
                <span className="queue-score">
                  <b>{v.priority_score}</b>
                  <i style={{ width: `${Math.min(100, v.priority_score)}%`, background: SEV_COLOR[v.severity] }} />
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel dash-card">
          <div className="ph"><h2>Cumplimiento de controles</h2><span className="r">ISO/IEC 27001:2022</span></div>
          <div className="pb compliance">
            <div className="compliance-ring">
              <Ring value={data.avg_compliance} color={complianceColor} label="de cumplimiento" />
              <span className="badge" style={{ color: complianceColor, borderColor: complianceColor, background: 'transparent' }}>{complianceLabel}</span>
            </div>
            <div className="gaps">
              <div className="stat-caption">Controles con mayor brecha</div>
              {data.control_gaps.length === 0 && <EmptyState message="Sin controles cargados." />}
              {data.control_gaps.map((c) => (
                <div key={c.id} className="gap">
                  <div className="gap-head"><span>{c.name}</span><b>{c.score}%</b></div>
                  <div className="gap-track"><i style={{ width: `${c.score}%`, background: c.score >= 85 ? 'var(--ok)' : c.score >= 70 ? 'var(--med)' : 'var(--crit)' }} /></div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>

      <section className="panel dash-card">
        <div className="ph"><h2>Marcos normativos</h2><span className="r">Referencias que guían el catálogo de controles</span></div>
        <ul className="frameworks">
          <li>
            <b>ISO/IEC 27001</b>
            <span>Gestión de seguridad de la información (2022)</span>
            <em style={{ color: complianceColor }}><IconCheckCircle size={14} />{data.avg_compliance}% · {complianceLabel}</em>
          </li>
          <li>
            <b>ISO 27799</b>
            <span>Seguridad de la información en salud</span>
            <em className="ref"><IconBook size={14} />Referencia del catálogo</em>
          </li>
          <li>
            <b>HIPAA</b>
            <span>Protección de datos de pacientes</span>
            <em className="ref"><IconCross size={14} />Referencia del catálogo</em>
          </li>
          <li>
            <b>CIS Controls</b>
            <span>Buenas prácticas técnicas</span>
            <em className="ref"><IconLayers size={14} />Referencia del catálogo</em>
          </li>
        </ul>
      </section>
    </div>
  )
}

/** Escudo central con anillos de luz; puramente decorativo. */
function HeroShield() {
  return (
    <svg className="shield" viewBox="0 0 320 320" aria-hidden="true">
      <defs>
        <linearGradient id="shieldFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1e3a8a" stopOpacity="0.9" />
          <stop offset="1" stopColor="#0a1530" stopOpacity="0.95" />
        </linearGradient>
        <linearGradient id="shieldStroke" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#7dd3fc" />
          <stop offset="1" stopColor="#2563eb" />
        </linearGradient>
        <radialGradient id="halo" cx="50%" cy="50%" r="50%">
          <stop offset="0" stopColor="#38bdf8" stopOpacity="0.35" />
          <stop offset="1" stopColor="#38bdf8" stopOpacity="0" />
        </radialGradient>
        <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
          <feGaussianBlur stdDeviation="4" result="b" />
          <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      <circle cx="160" cy="160" r="150" fill="url(#halo)" />
      <g className="rings" stroke="url(#shieldStroke)" fill="none" strokeWidth="1.2" opacity="0.6">
        <circle cx="160" cy="160" r="128" strokeDasharray="6 10" />
        <circle cx="160" cy="160" r="108" strokeDasharray="2 6" opacity="0.6" />
      </g>
      <g className="orbit" stroke="#7dd3fc" fill="none" strokeWidth="2" opacity="0.9">
        <path d="M 160 22 A 138 138 0 0 1 298 160" strokeLinecap="round" />
        <path d="M 160 298 A 138 138 0 0 1 22 160" strokeLinecap="round" />
      </g>
      <ellipse cx="160" cy="268" rx="96" ry="12" fill="none" stroke="#38bdf8" strokeOpacity="0.5" strokeWidth="1.5" />
      <ellipse cx="160" cy="268" rx="70" ry="8" fill="#38bdf8" fillOpacity="0.12" />

      <path
        d="M160 56 L228 82 V150 C228 198 198 236 160 252 C122 236 92 198 92 150 V82 Z"
        fill="url(#shieldFill)" stroke="url(#shieldStroke)" strokeWidth="3" filter="url(#glow)"
      />
      <path d="M160 72 L212 92 V150 C212 188 188 220 160 234 C132 220 108 188 108 150 V92 Z" fill="none" stroke="#38bdf8" strokeOpacity="0.4" strokeWidth="1" />

      {/* Cruz de salud */}
      <path d="M146 112 h28 v22 h22 v28 h-22 v22 h-28 v-22 h-22 v-28 h22 Z" fill="#e6f0ff" fillOpacity="0.95" filter="url(#glow)" />
      <path d="M150 116 h20 v22 h22 v20 h-22 v22 h-20 v-22 h-22 v-20 h22 Z" fill="#38bdf8" fillOpacity="0.25" />
    </svg>
  )
}
