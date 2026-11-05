import { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { remediationPlans, saveBlob } from '../api/resources'
import { ErrorState, LoadingState, extractErrorMessage, extractErrorMessageAsync } from '../components/DataState'

const COLUMNS = [
  { key: 'pending', label: 'Pendiente' },
  { key: 'in_progress', label: 'En curso' },
  { key: 'in_verification', label: 'En verificación' },
  { key: 'closed', label: 'Cerrado' },
]
const ROLES_GENERAN = ['admin', 'compliance', 'it_owner', 'analyst']

/**
 * Plan de corrección (tablero). HU17: el agente genera las acciones
 * (responsable, plazo, estado) y se exportan en PDF o Excel. HU19:
 * cada cambio de estado queda con fecha y usuario. HU22: tarjetas
 * vencidas marcadas.
 */
export default function RemediationPlan() {
  const { canEdit, role } = useAuth()
  const [plans, setPlans] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState({ ok: '', err: '' })
  const [generando, setGenerando] = useState(false)

  const load = useCallback(() => {
    setError('')
    remediationPlans
      .list()
      .then((res) => setPlans(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])

  async function advance(id) {
    setMsg({ ok: '', err: '' })
    try {
      await remediationPlans.advance(id)
      load()
    } catch (err) {
      setMsg({ ok: '', err: extractErrorMessage(err) })
    }
  }

  async function generar() {
    setGenerando(true)
    setMsg({ ok: '', err: '' })
    try {
      const { data } = await remediationPlans.generate('low')
      setMsg({
        ok: data.creados
          ? `El agente generó ${data.creados} acción(es) de corrección${data.responsable_disponible ? '' : ' (sin Responsable de TI disponible: quedan con responsable pendiente de asignación)'} y notificó a TI.`
          : 'No había hallazgos priorizados sin plan.',
        err: '',
      })
      load()
    } catch (err) {
      setMsg({ ok: '', err: extractErrorMessage(err) })
    } finally {
      setGenerando(false)
    }
  }

  async function asignar(p) {
    const nombre = window.prompt('Responsable de esta acción:', p.owner_name)
    if (nombre === null) return
    try {
      await remediationPlans.update(p.id, { owner_name: nombre.trim() })
      load()
    } catch (err) {
      setMsg({ ok: '', err: extractErrorMessage(err) })
    }
  }

  async function exportar(formato) {
    try {
      saveBlob(await remediationPlans.exportFile(formato), `plan_remediacion.${formato}`)
    } catch (err) {
      setMsg({ ok: '', err: await extractErrorMessageAsync(err) })
    }
  }

  if (loading) return <LoadingState />
  if (error) return <ErrorState message={error} onRetry={load} />

  return (
    <div>
      <div className="page-head" style={{ display: 'flex', alignItems: 'flex-end', gap: 12, flexWrap: 'wrap' }}>
        <div>
          <h1>Plan de corrección</h1>
          <p>Acciones con responsable, plazo y estado</p>
        </div>
        <span className="row-actions" style={{ marginLeft: 'auto' }}>
          <button className="btn pri" onClick={generar} disabled={!canEdit || !ROLES_GENERAN.includes(role) || generando}>
            {generando ? 'Generando…' : 'Generar plan con el agente'}
          </button>
          <button className="btn" onClick={() => exportar('pdf')}>Exportar PDF</button>
          <button className="btn" onClick={() => exportar('xlsx')}>Exportar Excel</button>
        </span>
      </div>

      {msg.ok && <div className="alert-ok">{msg.ok}</div>}
      {msg.err && <div className="alert-err">{msg.err}</div>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(220px, 1fr))', gap: 12, overflow: 'auto' }}>
        {COLUMNS.map((col) => {
          const items = plans.filter((p) => p.status === col.key)
          return (
            <div key={col.key} className="panel" style={{ background: 'var(--surface2)', display: 'flex', flexDirection: 'column' }}>
              <div className="ph">
                <h2 style={{ fontSize: 14, margin: 0 }}>{col.label}</h2>
                <span className="r">{items.length}</span>
              </div>
              <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
                {items.length === 0 && <div className="empty">Sin tareas</div>}
                {items.map((p) => (
                  <div key={p.id} className="panel" style={{ padding: '10px 11px', borderLeft: `3px solid ${p.vencido ? 'var(--crit)' : 'var(--brand)'}` }}>
                    <span className="mono muted">PC-{p.id} · {p.vulnerability_detail?.cve || 'sin CVE'}</span>
                    {p.generado_por_agente && <span className="badge b-br" style={{ marginLeft: 6 }}>Agente</span>}
                    {p.vencido && <span className="badge b-crit" style={{ marginLeft: 6 }}>Vencido</span>}
                    <p style={{ margin: '4px 0 8px', fontWeight: 500 }}>{p.vulnerability_detail?.title}</p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--muted)', gap: 8 }}>
                      {p.responsable_pendiente
                        ? <button className="btn sm" onClick={() => asignar(p)} disabled={!canEdit} style={{ color: 'var(--high)' }}>Responsable pendiente de asignación</button>
                        : <span onDoubleClick={() => canEdit && asignar(p)} title="Doble clic para cambiar">{p.owner_name}</span>}
                      <span className="mono">{p.due_date}</span>
                    </div>
                    {(col.key === 'pending' || col.key === 'in_progress') && (
                      <button className="btn sm" style={{ marginTop: 8, width: '100%', justifyContent: 'center' }} disabled={!canEdit} title={canEdit ? undefined : 'Solo lectura (Auditor)'} onClick={() => advance(p.id)}>
                        {col.key === 'pending' ? 'Iniciar' : 'Enviar a verificación'}
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
