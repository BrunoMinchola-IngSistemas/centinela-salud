import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { controls as controlsApi, evidence as evidenceApi, saveBlob } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage, extractErrorMessageAsync } from '../components/DataState'
import { IconUpload } from '../components/Icons'

const TIPOS = [
  ['signed_record', 'Acta firmada'],
  ['configuration', 'Configuración'],
  ['scan_report', 'Informe de escaneo'],
  ['other', 'Otro'],
]
const ROLES_SUBEN = ['admin', 'compliance', 'it_owner', 'analyst']
const ACEPTA = '.pdf,.png,.jpg,.jpeg,.docx,.xlsx,.csv,.txt'

/**
 * Evidencias. HU14: adjuntar un archivo a un control (queda con fecha,
 * responsable y huella SHA-256); formatos no permitidos se rechazan. La
 * descarga pasa por la API (queda en la auditoría) y verifica la huella.
 */
export default function Evidence() {
  const { canEdit, role } = useAuth()
  const [params] = useSearchParams()
  const [list, setList] = useState([])
  const [controles, setControles] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [form, setForm] = useState({ name: '', control: params.get('control') || '', evidence_type: 'signed_record', descripcion: '' })
  const [archivo, setArchivo] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [msg, setMsg] = useState({ ok: '', err: '' })
  const puedeSubir = canEdit && ROLES_SUBEN.includes(role)

  const load = useCallback(() => {
    setLoading(true)
    setError('')
    evidenceApi
      .list()
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }, [])

  useEffect(load, [load])
  useEffect(() => {
    controlsApi.list().then(({ data }) => setControles((data.results ?? data).slice().sort((a, b) => a.iso_code.localeCompare(b.iso_code, undefined, { numeric: true })))).catch(() => {})
  }, [])

  async function subir(e) {
    e.preventDefault()
    setMsg({ ok: '', err: '' })
    if (!archivo) return
    const fd = new FormData()
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v))
    fd.append('archivo', archivo)
    setEnviando(true)
    try {
      const { data } = await evidenceApi.upload(fd)
      setMsg({ ok: `Evidencia registrada. Huella SHA-256: ${data.sha256_hash.slice(0, 16)}…`, err: '' })
      setForm({ ...form, name: '', descripcion: '' })
      setArchivo(null)
      e.target.reset()
      load()
    } catch (err) {
      setMsg({ ok: '', err: extractErrorMessage(err) })
    } finally {
      setEnviando(false)
    }
  }

  async function descargar(ev) {
    try {
      const r = await evidenceApi.download(ev.id)
      if (r.headers['x-integridad-sha256'] !== 'ok') setMsg({ ok: '', err: 'Atención: la huella SHA-256 del archivo no coincide con la registrada.' })
      saveBlob(r, ev.nombre_original || 'evidencia')
    } catch (err) {
      setMsg({ ok: '', err: await extractErrorMessageAsync(err) })
    }
  }

  return (
    <div>
      <div className="page-head">
        <h1>Evidencias</h1>
        <p>Cada registro guarda su huella SHA-256 · los archivos se guardan cifrados y solo se descargan desde la consola</p>
      </div>

      {puedeSubir && (
        <form className="panel pb" onSubmit={subir} style={{ marginBottom: 14, display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, alignItems: 'end' }}>
          <label className="field">Control
            <select required value={form.control} onChange={(e) => setForm({ ...form, control: e.target.value })}>
              <option value="">Elige el control…</option>
              {controles.map((c) => <option key={c.id} value={c.id}>A.{c.iso_code} {c.name} ({c.estado_display})</option>)}
            </select>
          </label>
          <label className="field">Nombre<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Ej.: Política de copias de seguridad" /></label>
          <label className="field">Tipo
            <select value={form.evidence_type} onChange={(e) => setForm({ ...form, evidence_type: e.target.value })}>
              {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label className="field">Archivo (PDF, PNG, JPG, DOCX, XLSX, CSV o TXT · máx. 10 MB)
            <input required type="file" accept={ACEPTA} onChange={(e) => setArchivo(e.target.files[0] || null)} />
          </label>
          <label className="field" style={{ gridColumn: '1 / -1' }}>Descripción (opcional)<input value={form.descripcion} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} /></label>
          <button className="btn pri" disabled={enviando}><IconUpload size={15} /> {enviando ? 'Subiendo…' : 'Adjuntar evidencia'}</button>
        </form>
      )}
      {msg.ok && <div className="alert-ok">{msg.ok}</div>}
      {msg.err && <div className="alert-err">{msg.err}</div>}

      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && list.length === 0 && <EmptyState message="Aún no hay evidencias." />}
        {!loading && !error && list.length > 0 && (
          <table>
            <thead><tr><th>Evidencia</th><th>Vinculada a</th><th>Origen</th><th>Responsable</th><th>Huella SHA-256</th><th>Fecha</th><th /></tr></thead>
            <tbody>
              {list.map((e) => (
                <tr key={e.id}>
                  <td>
                    <b style={{ fontWeight: 500, display: 'block' }}>{e.name}</b>
                    <span className="muted small">{e.evidence_type_display}{e.nombre_original ? ` · ${e.nombre_original}` : ''}</span>
                  </td>
                  <td className="mono">{e.control_codigo ? `A.${e.control_codigo}` : e.vulnerability_cve || '—'}</td>
                  <td>{e.source_system}</td>
                  <td>{e.created_by || '—'}</td>
                  <td className="mono" title={e.sha256_hash}>{e.sha256_hash.slice(0, 10)}…{e.sha256_hash.slice(-4)}</td>
                  <td>{new Date(e.created_at).toLocaleDateString('es-PE')}</td>
                  <td>{e.tiene_archivo && <button className="btn sm" onClick={() => descargar(e)}>Descargar</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
