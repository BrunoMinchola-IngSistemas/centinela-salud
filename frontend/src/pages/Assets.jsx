import { Fragment, useEffect, useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { assets as assetsApi, discoveries } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'
import { IconDownload, IconFileText, IconRadar, IconServer } from '../components/Icons'
import Select from '../components/Select'
import './Assets.css'

const TYPE_LABEL = { server: 'Servidor', workstation: 'Estación', medical_device: 'Dispositivo médico', application: 'Aplicación', network_device: 'Equipo de red' }
const ESTADO = {
  en_linea: { label: 'En línea', badge: 'b-ok' },
  sin_senal: { label: 'Sin señal', badge: 'b-crit' },
  desconocido: { label: 'Sin verificar', badge: 'b-mut' },
}
const CRIT_BADGE = { critical: 'b-crit', high: 'b-high', medium: 'b-med', low: 'b-low' }
const CRIT_LABEL = { critical: 'Crítica', high: 'Alta', medium: 'Media', low: 'Baja' }
const TABS = [
  { key: 'inventario', label: 'Inventario', icon: IconServer },
  { key: 'descubrimiento', label: 'Descubrimiento', icon: IconRadar },
  { key: 'informes', label: 'Informes', icon: IconFileText },
]

/**
 * Inventario de activos tecnológicos con su estado, descubrimiento
 * automático (barrido de red o agentes Wazuh, solo Administrador y
 * TI) e informes del parque con exportación a CSV.
 */
export default function Assets() {
  const { profile } = useAuth()
  const puedeDescubrir = ['admin', 'it_owner'].includes(profile?.role)
  const [tab, setTab] = useState('inventario')

  return (
    <div>
      <div className="page-head">
        <h1>Activos</h1>
        <p>Servidores, estaciones, dispositivos médicos y aplicaciones: qué hay, cómo está y qué riesgo concentra.</p>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(({ key, label, icon: Ico }) => (
          <button key={key} type="button" role="tab" aria-selected={tab === key} className={`tab ${tab === key ? 'on' : ''}`} onClick={() => setTab(key)}>
            <Ico size={16} />{label}
          </button>
        ))}
      </div>

      {tab === 'inventario' && <Inventory />}
      {tab === 'descubrimiento' && <Discovery canRun={puedeDescubrir} />}
      {tab === 'informes' && <Reports />}
    </div>
  )
}

/* ---------------------------------------------------------------- Inventario */
function Inventory() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filtro, setFiltro] = useState({ tipo: '', estado: '', q: '' })

  function load() {
    setLoading(true)
    setError('')
    assetsApi.list({ asset_type: filtro.tipo || undefined, search: filtro.q || undefined })
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }
  useEffect(load, [filtro.tipo, filtro.q])

  const visible = filtro.estado ? list.filter((a) => a.estado === filtro.estado) : list
  const set = (k) => (e) => setFiltro({ ...filtro, [k]: e.target.value })

  return (
    <div className="panel">
      <div className="ph asset-filters">
        <Select aria-label="Tipo de activo" value={filtro.tipo} onChange={(tipo) => setFiltro({ ...filtro, tipo })} options={[{ value: '', label: 'Todos los tipos' }, ...Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label }))]} />
        <Select aria-label="Estado" value={filtro.estado} onChange={(estado) => setFiltro({ ...filtro, estado })} options={[{ value: '', label: 'Todos los estados' }, ...Object.entries(ESTADO).map(([value, e]) => ({ value, label: e.label }))]} />
        <input placeholder="Buscar por nombre, IP, MAC o sistema" value={filtro.q} onChange={set('q')} />
        <span className="r">{visible.length} activos</span>
      </div>
      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} onRetry={load} />}
      {!loading && !error && visible.length === 0 && <EmptyState message="Ningún activo coincide. Lanza un descubrimiento para poblar el inventario." />}
      {!loading && !error && visible.length > 0 && (
        <table>
          <thead><tr><th>Activo</th><th>Tipo</th><th>Sistema</th><th>Estado</th><th>Criticidad</th><th>Datos sensibles</th><th>Agente</th><th>Origen</th><th>Vuln. abiertas</th></tr></thead>
          <tbody>
            {visible.map((a) => (
              <tr key={a.id}>
                <td>
                  <b style={{ fontWeight: 500, display: 'block' }}>{a.hostname}</b>
                  <span className="mono muted">{a.ip_address || 'sin IP'}{a.mac_address && ` · ${a.mac_address}`}</span>
                </td>
                <td>{TYPE_LABEL[a.asset_type]}</td>
                <td>{a.operating_system || '—'}</td>
                <td>
                  <span className={`badge ${ESTADO[a.estado].badge}`}><i className="st-dot" />{ESTADO[a.estado].label}</span>
                  {a.last_discovered_at && <div className="muted" style={{ fontSize: 11 }}>{new Date(a.last_discovered_at).toLocaleString('es-PE')}</div>}
                </td>
                <td><span className={`badge ${CRIT_BADGE[a.criticality]}`}>{CRIT_LABEL[a.criticality]}</span></td>
                <td>{a.stores_phi ? <span className="badge b-br">Datos de pacientes</span> : '—'}</td>
                <td>{a.wazuh_agent_online ? <span className="badge b-ok">En línea</span> : a.wazuh_agent_id ? <span className="badge b-med">Registrado</span> : <span className="badge b-mut">Sin agente</span>}</td>
                <td className="muted">{a.discovery_source_display}</td>
                <td>{a.open_vulnerability_count ? <b style={{ color: 'var(--crit)' }}>{a.open_vulnerability_count}</b> : 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

/* ------------------------------------------------------------ Descubrimiento */
function Discovery({ canRun }) {
  const [runs, setRuns] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [fuente, setFuente] = useState('red_local')
  const [objetivo, setObjetivo] = useState('192.168.1.0/24')
  const [running, setRunning] = useState(false)
  const [msg, setMsg] = useState(null)
  const [open, setOpen] = useState(null)

  function load() {
    setLoading(true)
    setError('')
    discoveries.list().then((r) => setRuns(r.data.results ?? r.data)).catch((err) => setError(extractErrorMessage(err))).finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function run(e) {
    e.preventDefault()
    setRunning(true)
    setMsg(null)
    try {
      const { data } = await assetsApi.discover(fuente, fuente === 'red_local' ? objetivo : '')
      if (data.status === 'error') {
        setMsg({ ok: false, text: data.error })
      } else {
        setMsg({ ok: true, text: `Listo: ${data.found_count} equipos respondieron, ${data.new_count} nuevos en el inventario, ${data.unreachable_count} conocidos sin señal.` })
      }
      setOpen(data.id)
      load()
    } catch (err) {
      setMsg({ ok: false, text: extractErrorMessage(err) })
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="disc-layout">
      <section className="panel">
        <div className="ph"><h2>Nuevo descubrimiento</h2></div>
        {canRun ? (
          <form className="pb disc-form" onSubmit={run}>
            <div className="disc-sources">
              <label className={`disc-source ${fuente === 'red_local' ? 'on' : ''}`}>
                <input type="radio" name="fuente" value="red_local" checked={fuente === 'red_local'} onChange={() => setFuente('red_local')} />
                <b>Barrido de red local</b>
                <small>Ping a cada dirección del rango desde el servidor, MAC por ARP y nombre por DNS inverso. Máximo /24.</small>
              </label>
              <label className={`disc-source ${fuente === 'wazuh' ? 'on' : ''}`}>
                <input type="radio" name="fuente" value="wazuh" checked={fuente === 'wazuh'} onChange={() => setFuente('wazuh')} />
                <b>Agentes Wazuh</b>
                <small>Inventario de agentes del manager, con su sistema y si están en línea. Requiere Wazuh configurado.</small>
              </label>
            </div>
            {fuente === 'red_local' && (
              <label className="field">
                <span>Rango de red (CIDR)</span>
                <input required value={objetivo} onChange={(e) => setObjetivo(e.target.value)} placeholder="192.168.1.0/24" className="mono" />
              </label>
            )}
            {msg && <div className={msg.ok ? 'alert-ok' : 'alert-err'} style={{ margin: 0 }}>{msg.text}</div>}
            <button className="btn pri" disabled={running} style={{ justifyContent: 'center' }}>
              <IconRadar size={16} />{running ? 'Explorando la red…' : 'Iniciar descubrimiento'}
            </button>
            <p className="muted" style={{ margin: 0, fontSize: 12 }}>Un barrido de /24 tarda entre 10 y 20 segundos. Cada ejecución queda en el registro de auditoría.</p>
          </form>
        ) : (
          <div className="pb muted" style={{ fontSize: 13 }}>Solo el Administrador y el Responsable de TI pueden lanzar un descubrimiento. Aquí puedes revisar el historial.</div>
        )}
      </section>

      <section className="panel">
        <div className="ph"><h2>Historial de descubrimientos</h2><span className="r">{runs.length} ejecuciones</span></div>
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && runs.length === 0 && <EmptyState message="Todavía no se ha ejecutado ningún descubrimiento." />}
        {!loading && !error && runs.length > 0 && (
          <table>
            <thead><tr><th>Fecha</th><th>Fuente</th><th>Objetivo</th><th>Por</th><th>Encontrados</th><th>Nuevos</th><th>Sin señal</th><th>Estado</th></tr></thead>
            <tbody>
              {runs.map((r) => (
                <Fragment key={r.id}>
                  <tr className={`row ${open === r.id ? 'sel' : ''}`} onClick={() => setOpen(open === r.id ? null : r.id)}>
                    <td className="mono" style={{ whiteSpace: 'nowrap' }}>{new Date(r.started_at).toLocaleString('es-PE')}</td>
                    <td>{r.source_display}</td>
                    <td className="mono">{r.target || '—'}</td>
                    <td>{r.started_by}</td>
                    <td>{r.found_count}</td>
                    <td>{r.new_count ? <b style={{ color: 'var(--brand)' }}>{r.new_count}</b> : 0}</td>
                    <td>{r.unreachable_count ? <b style={{ color: 'var(--crit)' }}>{r.unreachable_count}</b> : 0}</td>
                    <td>{r.status === 'ok' ? <span className="badge b-ok">Completado</span> : <span className="badge b-crit" title={r.error}>Con error</span>}</td>
                  </tr>
                  {open === r.id && (
                    <tr>
                      <td colSpan={8} style={{ background: 'var(--surface2)', padding: 0 }}>
                        {r.error && <div className="alert-err" style={{ margin: 12 }}>{r.error}</div>}
                        {r.hosts.length === 0 ? (
                          <div className="pb muted">Ningún equipo respondió.</div>
                        ) : (
                          <table className="sub">
                            <thead><tr><th>IP</th><th>Nombre</th><th>MAC</th><th>Sistema</th><th>Activo en inventario</th></tr></thead>
                            <tbody>
                              {r.hosts.map((h) => (
                                <tr key={h.ip || h.hostname}>
                                  <td className="mono">{h.ip || '—'}</td>
                                  <td>{h.hostname || <span className="muted">sin nombre</span>}</td>
                                  <td className="mono muted">{h.mac || '—'}</td>
                                  <td className="muted">{h.os_name || '—'}</td>
                                  <td>{h.activo}{h.nuevo && <span className="badge b-br" style={{ marginLeft: 6 }}>Nuevo</span>}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </div>
  )
}

/* ----------------------------------------------------------------- Informes */
function Reports() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState(false)

  function load() {
    setLoading(true)
    setError('')
    assetsApi.report().then((r) => setData(r.data)).catch((err) => setError(extractErrorMessage(err))).finally(() => setLoading(false))
  }
  useEffect(load, [])

  async function download() {
    setDownloading(true)
    try {
      const { data: blob } = await assetsApi.reportCsv()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `inventario-activos-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      setError(extractErrorMessage(err))
    } finally {
      setDownloading(false)
    }
  }

  if (loading) return <div className="panel"><LoadingState /></div>
  if (error) return <div className="panel"><ErrorState message={error} onRetry={load} /></div>

  const pct = (n) => (data.total ? Math.round((n / data.total) * 100) : 0)
  const estadoColor = { en_linea: 'var(--ok)', sin_senal: 'var(--crit)', desconocido: 'var(--muted)' }
  const critColor = { critical: 'var(--crit)', high: 'var(--high)', medium: 'var(--med)', low: 'var(--low)' }

  return (
    <div className="reports">
      <div className="report-head">
        <span className="muted">Generado {new Date(data.generado_en).toLocaleString('es-PE')}</span>
        <button className="btn" onClick={download} disabled={downloading}><IconDownload size={15} />{downloading ? 'Preparando…' : 'Descargar inventario (CSV)'}</button>
      </div>

      <div className="kpis">
        <Kpi label="Activos" value={data.total} />
        <Kpi label="En línea" value={data.por_estado.find((e) => e.clave === 'en_linea')?.total ?? 0} color="var(--ok)" sub={`${pct(data.por_estado.find((e) => e.clave === 'en_linea')?.total ?? 0)}%`} />
        <Kpi label="Sin verificar" value={data.sin_verificar} color="var(--muted)" />
        <Kpi label="Con agente Wazuh" value={data.con_agente} sub={`${data.agente_en_linea} en línea`} />
        <Kpi label="Con datos de pacientes" value={data.con_datos_pacientes} color="var(--brand)" />
        <Kpi label="Con vulnerabilidades" value={data.con_vulnerabilidades_abiertas} color="var(--crit)" />
      </div>

      <div className="report-grid">
        <Breakdown title="Por tipo" rows={data.por_tipo} total={data.total} color={() => 'var(--brand)'} />
        <Breakdown title="Por estado" rows={data.por_estado} total={data.total} color={(r) => estadoColor[r.clave]} />
        <Breakdown title="Por criticidad" rows={data.por_criticidad} total={data.total} color={(r) => critColor[r.clave]} />
      </div>

      <section className="panel">
        <div className="ph"><h2>Activos con mayor riesgo</h2><span className="r">Ordenados por vulnerabilidades abiertas</span></div>
        {data.mayor_riesgo.length === 0 ? <EmptyState message="Sin activos." /> : (
          <table>
            <thead><tr><th>Activo</th><th>Tipo</th><th>Criticidad</th><th>Estado</th><th>Datos sensibles</th><th>Vuln. abiertas</th></tr></thead>
            <tbody>
              {data.mayor_riesgo.map((a) => (
                <tr key={a.id}>
                  <td><b style={{ fontWeight: 500 }}>{a.hostname}</b></td>
                  <td>{TYPE_LABEL[a.asset_type]}</td>
                  <td><span className={`badge ${CRIT_BADGE[a.criticality]}`}>{CRIT_LABEL[a.criticality]}</span></td>
                  <td><span className={`badge ${ESTADO[a.estado].badge}`}>{ESTADO[a.estado].label}</span></td>
                  <td>{a.stores_phi ? <span className="badge b-br">Sí</span> : '—'}</td>
                  <td>{a.abiertas ? <b style={{ color: 'var(--crit)' }}>{a.abiertas}</b> : 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="panel">
        <div className="ph"><h2>Último descubrimiento</h2></div>
        {data.ultimo_descubrimiento ? (
          <div className="pb last-run">
            <span><b>{data.ultimo_descubrimiento.source_display}</b> {data.ultimo_descubrimiento.target}</span>
            <span className="muted">{new Date(data.ultimo_descubrimiento.started_at).toLocaleString('es-PE')} · por {data.ultimo_descubrimiento.started_by}</span>
            <span>{data.ultimo_descubrimiento.found_count} encontrados · {data.ultimo_descubrimiento.new_count} nuevos · {data.ultimo_descubrimiento.unreachable_count} sin señal</span>
          </div>
        ) : (
          <div className="pb muted">Aún no se ha ejecutado ningún descubrimiento. El estado de los activos quedará como "Sin verificar" hasta entonces.</div>
        )}
      </section>
    </div>
  )
}

function Kpi({ label, value, sub, color }) {
  return (
    <div className="panel kpi">
      <b style={{ color: color || 'inherit' }}>{value}</b>
      <span>{label}</span>
      {sub && <small>{sub}</small>}
    </div>
  )
}

function Breakdown({ title, rows, total, color }) {
  return (
    <section className="panel">
      <div className="ph"><h2>{title}</h2></div>
      <div className="pb breakdown">
        {rows.map((r) => (
          <div key={r.clave} className="bd-row">
            <div className="bd-head"><span>{r.etiqueta}</span><b>{r.total}</b></div>
            <div className="bd-track"><i style={{ width: `${total ? (r.total / total) * 100 : 0}%`, background: color(r) }} /></div>
          </div>
        ))}
      </div>
    </section>
  )
}
