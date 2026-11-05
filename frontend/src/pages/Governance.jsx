import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { governance, organization, remediationPlans } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import Select from '../components/Select'

const NIVEL_BADGE = { autonomo: 'b-ok', asistido: 'b-br', con_aprobacion: 'b-high' }
const NIVEL_LABEL = { autonomo: 'Autónomo', asistido: 'Asistido', con_aprobacion: 'Con aprobación' }
const ESTADO_BADGE = { pendiente: 'b-med', aprobada: 'b-ok', rechazada: 'b-crit', escalada: 'b-high' }
const ACC_BADGE = { ejecutada: 'b-ok', pendiente_manual: 'b-med', pendiente_aprobacion: 'b-high', rechazada: 'b-crit', descartada: 'b-mut' }
const TIPOS_TODOS = [
  ['notificar', 'Notificar'],
  ['abrir_ticket', 'Abrir ticket'],
  ['desactivar_cuenta', 'Desactivar cuenta inactiva'],
  ['aplicar_parche', 'Aplicar parche'],
  ['modificar_config', 'Modificar configuración'],
  ['aislar_servidor', 'Aislar servidor de producción'],
]
const TIPOS = [
  ['aislar_servidor', 'Aislar servidor de producción'],
  ['aplicar_parche', 'Aplicar parche'],
  ['modificar_config', 'Modificar configuración'],
  ['desactivar_cuenta', 'Desactivar cuenta inactiva'],
  ['otro', 'Otro'],
]

/**
 * HU23 (niveles de autonomía) y HU24 (aprobación humana de acciones de
 * alto impacto). Cualquiera puede ver; el Analista y TI pueden pedir
 * aprobación; solo el Administrador (Gerencia) decide y cambia políticas.
 */
export default function Governance() {
  const { profile, canEdit } = useAuth()
  const isAdmin = profile?.role === 'admin'
  const puedeEjecutar = canEdit && ['admin', 'it_owner'].includes(profile?.role)
  const [acciones, setAcciones] = useState([])
  const [org, setOrg] = useState(null)

  const [policies, setPolicies] = useState([])
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [actionError, setActionError] = useState('')
  const [busy, setBusy] = useState(null)
  const [comments, setComments] = useState({})
  const [showForm, setShowForm] = useState(false)

  function load() {
    setLoading(true)
    setError('')
    Promise.all([governance.policies(), governance.requests(), governance.actions(), organization.get()])
      .then(([p, r, a, o]) => {
        setPolicies(p.data.results ?? p.data)
        setRequests(r.data.results ?? r.data)
        setAcciones(a.data.results ?? a.data)
        setOrg(o.data)
      })
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function changeLevel(id, nivel) {
    setActionError('')
    try {
      await governance.updatePolicy(id, nivel)
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    }
  }

  async function decide(id, approve) {
    setBusy(id)
    setActionError('')
    try {
      const fn = approve ? governance.approve : governance.reject
      await fn(id, comments[id] || '')
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  async function toggleAutonomia() {
    setActionError('')
    try {
      await organization.update({ ejecucion_autonoma_activa: !org.ejecucion_autonoma_activa })
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    }
  }

  async function accion(id, ejecutar) {
    setBusy(id)
    setActionError('')
    try {
      if (ejecutar) await governance.runAction(id)
      else await governance.discardAction(id, '')
      load()
    } catch (err) {
      setActionError(extractErrorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const pending = requests.filter((r) => r.estado === 'pendiente' || r.estado === 'escalada')
  const decided = requests.filter((r) => r.estado !== 'pendiente' && r.estado !== 'escalada')
  const puedeDecidir = (r) => isAdmin || (r.estado === 'escalada' && r.escalado_a === profile?.username)

  return (
    <div>
      <div className="page-head" style={{ display: 'flex', alignItems: 'flex-end', gap: 12 }}>
        <div>
          <h1>Gobernanza y aprobaciones</h1>
          <p>Qué puede hacer el agente solo, qué solo recomienda y qué necesita aprobación de Gerencia.</p>
        </div>
        {canEdit && (
          <button className="btn pri" style={{ marginLeft: 'auto' }} onClick={() => setShowForm((v) => !v)}>
            {showForm ? 'Cancelar' : 'Pedir aprobación'}
          </button>
        )}
      </div>

      {actionError && <div className="alert-err">{actionError}</div>}
      {showForm && <RequestForm onDone={() => { setShowForm(false); load() }} />}

      {loading && <div className="panel"><LoadingState /></div>}
      {!loading && error && <div className="panel"><ErrorState message={error} onRetry={load} /></div>}

      {!loading && !error && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.3fr)', gap: 14, alignItems: 'start' }}>
          <div className="panel">
            <div className="ph"><b>Niveles de autonomía</b><span className="r">{isAdmin ? 'Puedes cambiarlos' : 'Solo el Administrador los cambia'}</span></div>
            <table>
              <thead><tr><th>Acción</th><th>Nivel</th></tr></thead>
              <tbody>
                {policies.map((p) => (
                  <tr key={p.id}>
                    <td>{p.tipo_accion_display}</td>
                    <td>
                      {isAdmin ? (
                        <Select size="sm" aria-label={`Nivel para ${p.tipo_accion_display}`} value={p.nivel} onChange={(nivel) => changeLevel(p.id, nivel)} options={Object.entries(NIVEL_LABEL).map(([value, label]) => ({ value, label }))} />
                      ) : (
                        <span className={`badge ${NIVEL_BADGE[p.nivel]}`}>{NIVEL_LABEL[p.nivel]}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pb" style={{ fontSize: 12.5, color: 'var(--muted)', borderTop: '1px solid var(--line)' }}>
              <b>Autónomo:</b> el agente lo hace y lo registra (solo la lista blanca de bajo riesgo). <b>Asistido:</b> el agente recomienda, TI ejecuta.{' '}
              <b>Con aprobación:</b> no se hace nada sin el visto bueno de Gerencia.
            </div>
            {org && (
              <div className="pb" style={{ borderTop: '1px solid var(--line)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ flex: 1 }}>
                  <b>Ejecución autónoma</b>{' '}
                  <span className={`badge ${org.ejecucion_autonoma_activa ? 'b-ok' : 'b-crit'}`}>{org.ejecucion_autonoma_activa ? 'Activada' : 'Desactivada'}</span>
                  <div className="muted small">Si se desactiva, el agente no ejecuta nada solo: todo queda pendiente de TI.</div>
                </span>
                {puedeEjecutar && <button className="btn sm" onClick={toggleAutonomia}>{org.ejecucion_autonoma_activa ? 'Desactivar' : 'Activar'}</button>}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div className="panel">
              <div className="ph"><b>Pendientes de aprobación</b><span className="r">{pending.length}</span></div>
              {pending.length === 0 && <EmptyState icon="✓" message="No hay acciones esperando aprobación." />}
              {pending.map((r) => (
                <div key={r.id} className="pb" style={{ borderBottom: '1px solid var(--line)', display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <b>{r.tipo_accion_display}</b>
                    <span className="badge b-mut">{r.vulnerability_title}</span>
                    {r.estado === 'escalada' && <span className="badge b-high">Escalada a {r.escalado_a}</span>}
                    <span style={{ marginLeft: 'auto', color: 'var(--muted)', fontSize: 12 }}>
                      Plazo: {new Date(r.plazo).toLocaleString('es-PE')}
                    </span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, fontSize: 13 }}>
                    <div style={{ background: 'var(--crit-soft)', borderRadius: 6, padding: 8 }}>
                      <div style={{ color: 'var(--crit)', fontWeight: 500, marginBottom: 2 }}>Si NO se actúa</div>
                      {r.riesgo_de_no_actuar}
                    </div>
                    <div style={{ background: 'var(--ok-soft)', borderRadius: 6, padding: 8 }}>
                      <div style={{ color: 'var(--ok)', fontWeight: 500, marginBottom: 2 }}>Si SÍ se actúa</div>
                      {r.efecto_esperado}
                    </div>
                  </div>
                  {puedeDecidir(r) && canEdit ? (
                    <div style={{ display: 'flex', gap: 6 }}>
                      <input
                        placeholder="Comentario (opcional)"
                        value={comments[r.id] || ''}
                        onChange={(e) => setComments({ ...comments, [r.id]: e.target.value })}
                        style={{ flex: 1, border: '1px solid var(--line)', borderRadius: 6, padding: '5px 9px', background: 'var(--surface2)' }}
                      />
                      <button className="btn sm" disabled={busy === r.id} onClick={() => decide(r.id, false)}>Rechazar</button>
                      <button className="btn sm pri" disabled={busy === r.id} onClick={() => decide(r.id, true)}>Aprobar</button>
                    </div>
                  ) : (
                    <span style={{ fontSize: 12.5, color: 'var(--muted)' }}>Esperando decisión del Administrador (Gerencia).</span>
                  )}
                </div>
              ))}
            </div>

            <div className="panel" style={{ overflowX: 'auto' }}>
              <div className="ph"><b>Acciones del agente</b><span className="r">según la política de autonomía</span></div>
              {acciones.length === 0 ? <EmptyState message="El agente aún no propuso acciones." /> : (
                <table>
                  <thead><tr><th>Acción</th><th>Hallazgo</th><th>Estado</th><th>Resultado</th><th /></tr></thead>
                  <tbody>
                    {acciones.map((a) => (
                      <tr key={a.id}>
                        <td>{a.tipo_accion_display}<div className="muted small">{a.nivel_display}</div></td>
                        <td className="small">{a.vulnerability_title}</td>
                        <td><span className={`badge ${ACC_BADGE[a.estado]}`}>{a.estado_display}</span><div className="muted small">{a.motivo}</div></td>
                        <td className="small">{a.resultado || '—'}{a.ejecutada_por && <div className="muted">por {a.ejecutada_por}{a.ejecutado_en ? ` · ${new Date(a.ejecutado_en).toLocaleString('es-PE')}` : ''}</div>}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          {a.estado === 'pendiente_manual' && puedeEjecutar && (
                            <>
                              <button className="btn sm pri" disabled={busy === a.id} onClick={() => accion(a.id, true)}>Ejecutar</button>{' '}
                              <button className="btn sm" disabled={busy === a.id} onClick={() => accion(a.id, false)}>Descartar</button>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {canEdit && <ProponerAccion onDone={load} />}
            </div>

            <div className="panel">
              <div className="ph"><b>Historial de decisiones</b><span className="r">{decided.length}</span></div>
              {decided.length === 0 ? (
                <EmptyState message="Todavía no se ha decidido ninguna solicitud." />
              ) : (
                <table>
                  <thead><tr><th>Acción</th><th>Hallazgo</th><th>Estado</th><th>Decidió</th></tr></thead>
                  <tbody>
                    {decided.map((r) => (
                      <tr key={r.id}>
                        <td>{r.tipo_accion_display}</td>
                        <td>{r.vulnerability_title}</td>
                        <td><span className={`badge ${ESTADO_BADGE[r.estado]}`}>{r.estado_display}</span></td>
                        <td>
                          {r.decidido_por}
                          {r.comentario_decision && <div style={{ color: 'var(--muted)', fontSize: 12 }}>{r.comentario_decision}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function RequestForm({ onDone }) {
  const [plans, setPlans] = useState([])
  const [form, setForm] = useState({ plan: '', tipo_accion: 'aislar_servidor', riesgo_de_no_actuar: '', efecto_esperado: '', horas: 24 })
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    remediationPlans
      .list()
      .then((res) => setPlans((res.data.results ?? res.data).filter((p) => p.status !== 'closed')))
      .catch((err) => setError(extractErrorMessage(err)))
  }, [])

  async function submit(e) {
    e.preventDefault()
    if (!form.plan) {
      setError('Elige el plan de corrección que necesita aprobación.')
      return
    }
    setSaving(true)
    setError('')
    try {
      const plazo = new Date(Date.now() + Number(form.horas) * 3600 * 1000).toISOString()
      await governance.createRequest({
        plan: form.plan,
        tipo_accion: form.tipo_accion,
        riesgo_de_no_actuar: form.riesgo_de_no_actuar,
        efecto_esperado: form.efecto_esperado,
        plazo,
      })
      onDone()
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <form className="panel pb" onSubmit={submit} style={{ marginBottom: 14, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
      {error && <div className="alert-err" style={{ gridColumn: '1 / -1', margin: 0 }}>{error}</div>}
      <div className="field">
        Plan de corrección
        <Select
          aria-label="Plan de corrección"
          placeholder="Elige un plan…"
          value={form.plan}
          onChange={(plan) => setForm({ ...form, plan })}
          options={plans.map((p) => ({ value: p.id, label: `${p.vulnerability_detail?.title || `Plan ${p.id}`} · ${p.vulnerability_detail?.asset_hostname}` }))}
        />
      </div>
      <div className="field">
        Acción que necesita aprobación
        <Select aria-label="Acción que necesita aprobación" value={form.tipo_accion} onChange={(tipo_accion) => setForm({ ...form, tipo_accion })} options={TIPOS.map(([value, label]) => ({ value, label }))} />
      </div>
      <label className="field">
        ¿Qué pasa si NO se actúa?
        <textarea required value={form.riesgo_de_no_actuar} onChange={set('riesgo_de_no_actuar')} />
      </label>
      <label className="field">
        ¿Qué cambia si SÍ se actúa?
        <textarea required value={form.efecto_esperado} onChange={set('efecto_esperado')} />
      </label>
      <label className="field">
        Plazo para decidir (horas)
        <input type="number" min="1" max="168" value={form.horas} onChange={set('horas')} />
      </label>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'flex-end' }}>
        <button className="btn pri" disabled={saving}>{saving ? 'Enviando…' : 'Enviar a Gerencia'}</button>
      </div>
    </form>
  )
}

function ProponerAccion({ onDone }) {
  const [plans, setPlans] = useState([])
  const [plan, setPlan] = useState('')
  const [tipo, setTipo] = useState('notificar')
  const [msg, setMsg] = useState('')
  useEffect(() => {
    remediationPlans.list().then((res) => setPlans((res.data.results ?? res.data).filter((p) => p.status !== 'closed'))).catch(() => {})
  }, [])
  async function proponer(e) {
    e.preventDefault()
    setMsg('')
    try {
      const { data } = await governance.proposeAction(plan, tipo, '')
      setMsg(`${data.tipo_accion_display}: ${data.estado_display}. ${data.motivo}`)
      onDone()
    } catch (err) {
      setMsg(extractErrorMessage(err))
    }
  }
  return (
    <form className="pb row-actions" onSubmit={proponer} style={{ borderTop: '1px solid var(--line)' }}>
      <select required value={plan} onChange={(e) => setPlan(e.target.value)} style={{ flex: 1, minWidth: 180 }}>
        <option value="">Plan de corrección…</option>
        {plans.map((p) => <option key={p.id} value={p.id}>{p.vulnerability_detail?.title}</option>)}
      </select>
      <select value={tipo} onChange={(e) => setTipo(e.target.value)}>
        {TIPOS_TODOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
      <button className="btn sm">Proponer acción al agente</button>
      {msg && <div className="note" style={{ width: '100%' }}>{msg}</div>}
    </form>
  )
}
