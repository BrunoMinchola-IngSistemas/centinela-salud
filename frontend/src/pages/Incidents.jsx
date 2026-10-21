import { useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { incidents } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

const ESTADO_BADGE = { reportado: 'b-med', en_revision: 'b-br', cerrado: 'b-ok' }

function nowLocal() {
  const d = new Date()
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset())
  return d.toISOString().slice(0, 16)
}

/**
 * HU30: reportar un incidente con máximo 3 campos (qué, dónde, cuándo).
 * Pensado para personal clínico sin entrenamiento técnico.
 */
export default function Incidents() {
  const { canEdit } = useAuth()
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ descripcion: '', lugar: '', ocurrido_en: nowLocal() })
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [sent, setSent] = useState(false)

  function load() {
    setLoading(true)
    setError('')
    incidents
      .list()
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function submit(e) {
    e.preventDefault()
    setSaving(true)
    setFormError('')
    setSent(false)
    try {
      await incidents.create({ ...form, ocurrido_en: new Date(form.ocurrido_en).toISOString() })
      setForm({ descripcion: '', lugar: '', ocurrido_en: nowLocal() })
      setSent(true)
      load()
    } catch (err) {
      setFormError(extractErrorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  return (
    <div>
      <div className="page-head">
        <h1>Reportar un incidente</h1>
        <p>¿Viste algo raro? Cuéntanos en 3 datos. No necesitas saber de informática.</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) minmax(0, 1.4fr)', gap: 14, alignItems: 'start' }}>
        <form className="panel pb" onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {sent && <div className="alert-ok" style={{ margin: 0 }}>Gracias, tu reporte quedó registrado. TI lo revisará.</div>}
          {formError && <div className="alert-err" style={{ margin: 0 }}>{formError}</div>}
          <label className="field">
            1. ¿Qué pasó?
            <textarea
              required
              placeholder="Ej.: me llegó un correo pidiendo mi clave del sistema de historias"
              value={form.descripcion}
              onChange={set('descripcion')}
              disabled={!canEdit}
            />
          </label>
          <label className="field">
            2. ¿Dónde?
            <input required placeholder="Ej.: Admisión, consultorio 3, laptop de laboratorio" value={form.lugar} onChange={set('lugar')} disabled={!canEdit} />
          </label>
          <label className="field">
            3. ¿Cuándo?
            <input required type="datetime-local" value={form.ocurrido_en} onChange={set('ocurrido_en')} disabled={!canEdit} />
          </label>
          <button className="btn pri" disabled={!canEdit || saving} style={{ justifyContent: 'center' }} title={canEdit ? undefined : 'Solo lectura (Auditor)'}>
            {saving ? 'Enviando…' : 'Enviar reporte'}
          </button>
        </form>

        <div className="panel">
          <div className="ph"><b>Incidentes reportados</b><span className="r">{list.length}</span></div>
          {loading && <LoadingState />}
          {!loading && error && <ErrorState message={error} onRetry={load} />}
          {!loading && !error && list.length === 0 && <EmptyState message="Nadie ha reportado incidentes todavía." />}
          {!loading && !error && list.length > 0 && (
            <table>
              <thead><tr><th>Cuándo</th><th>Dónde</th><th>Qué pasó</th><th>Estado</th></tr></thead>
              <tbody>
                {list.map((i) => (
                  <tr key={i.id}>
                    <td className="mono" style={{ whiteSpace: 'nowrap' }}>{new Date(i.ocurrido_en).toLocaleString('es-PE')}</td>
                    <td>{i.lugar}</td>
                    <td>
                      {i.descripcion}
                      <div style={{ color: 'var(--muted)', fontSize: 12 }}>Reportó: {i.reportado_por || 'anónimo'}</div>
                    </td>
                    <td><span className={`badge ${ESTADO_BADGE[i.estado]}`}>{i.estado_display}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
