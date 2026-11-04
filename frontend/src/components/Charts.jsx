/**
 * Gráficos SVG pequeños y sin dependencias para el Panel general. Cada
 * uno recibe datos ya calculados por el componente que lo usa; aquí
 * solo se dibuja.
 */

const SEV_COLOR = { critical: 'var(--crit)', high: 'var(--high)', medium: 'var(--med)', low: 'var(--low)' }
const GLOW_PAD = 6
export const SEV_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
export const SEV_ORDER = ['critical', 'high', 'medium', 'low']

/** Anillo con segmentos (distribución por severidad). */
export function Donut({ segments, total, size = 150, stroke = 16, centerValue, centerLabel }) {
  // GLOW_PAD deja sitio al resplandor (drop-shadow) dentro del SVG; sin
  // ese margen el brillo se corta en el borde y el anillo parece una
  // imagen cuadrada recortada.
  const r = (size - stroke) / 2 - GLOW_PAD
  const c = 2 * Math.PI * r
  let offset = 0
  const sum = segments.reduce((a, s) => a + s.value, 0) || 1

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }} role="img" aria-label={`${centerValue} ${centerLabel}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
      {segments.map((s) => {
        const len = (s.value / sum) * c
        const el = (
          <circle
            key={s.key}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={s.color}
            strokeWidth={stroke}
            strokeDasharray={`${len} ${c - len}`}
            strokeDashoffset={-offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ filter: `drop-shadow(0 0 6px ${s.color})` }}
          />
        )
        offset += len
        return el
      })}
      <text x="50%" y="47%" textAnchor="middle" fill="var(--ink)" fontSize={size * 0.2} fontWeight="700" fontFamily="var(--font-display)">
        {centerValue}
      </text>
      <text x="50%" y="62%" textAnchor="middle" fill="var(--muted)" fontSize={size * 0.075}>
        {centerLabel}
      </text>
      {total === 0 && null}
    </svg>
  )
}

/** Barras horizontales apiladas por severidad (exposición por tipo de activo). */
export function StackedBars({ rows }) {
  const max = Math.max(1, ...rows.map((r) => r.total))
  return (
    <div className="sbars">
      {rows.map((row) => (
        <div key={row.type} className="sbar">
          <div className="sbar-head">
            <span>{row.type}</span>
            <b>{row.total}</b>
          </div>
          <div className="sbar-track" role="img" aria-label={`${row.type}: ${row.total} hallazgos abiertos`}>
            {SEV_ORDER.map((sev) => {
              const n = row.by_severity?.[sev] || 0
              if (!n) return null
              return <span key={sev} className="sbar-seg" style={{ width: `${(n / max) * 100}%`, background: SEV_COLOR[sev] }} title={`${SEV_LABEL[sev]}: ${n}`} />
            })}
          </div>
        </div>
      ))}
    </div>
  )
}

/** Anillo de progreso simple (porcentaje). */
export function Ring({ value, size = 88, stroke = 9, color = 'var(--brand)', label }) {
  const r = (size - stroke) / 2 - GLOW_PAD
  const c = 2 * Math.PI * r
  const len = (Math.max(0, Math.min(100, value)) / 100) * c
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ overflow: 'visible' }} role="img" aria-label={`${value}% ${label || ''}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
        strokeDasharray={`${len} ${c - len}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ filter: `drop-shadow(0 0 6px ${color})` }}
      />
      <text x="50%" y="54%" textAnchor="middle" fill="var(--ink)" fontSize={size * 0.24} fontWeight="700" fontFamily="var(--font-display)">
        {value}%
      </text>
    </svg>
  )
}

export { SEV_COLOR }
