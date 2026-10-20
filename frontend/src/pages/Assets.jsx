import { useEffect, useState } from 'react'
import { assets as assetsApi } from '../api/resources'
import { EmptyState, ErrorState, LoadingState, extractErrorMessage } from '../components/DataState'

const TYPE_LABEL = { server: 'Servidor', workstation: 'Estación', medical_device: 'Dispositivo médico', application: 'Aplicación', network_device: 'Equipo de red' }

export default function Assets() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  function load() {
    setLoading(true)
    setError('')
    assetsApi
      .list()
      .then((res) => setList(res.data.results ?? res.data))
      .catch((err) => setError(extractErrorMessage(err)))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h1 style={{ fontSize: 20, fontWeight: 600, margin: '0 0 2px' }}>Activos</h1>
        <p style={{ color: 'var(--muted)', margin: 0 }}>Servidores, estaciones, dispositivos médicos y aplicaciones</p>
      </div>
      <div className="panel">
        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} onRetry={load} />}
        {!loading && !error && list.length === 0 && <EmptyState message="Aún no hay activos registrados." />}
        {!loading && !error && list.length > 0 && (
          <table>
            <thead><tr><th>Activo</th><th>Tipo</th><th>Sistema</th><th>Datos sensibles</th><th>Agente</th><th>Vulnerabilidades abiertas</th></tr></thead>
            <tbody>
              {list.map((a) => (
                <tr key={a.id}>
                  <td>
                    <b style={{ fontWeight: 500, display: 'block' }}>{a.hostname}</b>
                    <span className="mono" style={{ color: 'var(--muted)' }}>{a.ip_address}</span>
                  </td>
                  <td>{TYPE_LABEL[a.asset_type]}</td>
                  <td>{a.operating_system}</td>
                  <td>{a.stores_phi ? <span className="badge b-br">Datos de pacientes</span> : '—'}</td>
                  <td>{a.wazuh_agent_online ? <span className="badge b-ok">En línea</span> : <span className="badge b-med">Sin agente</span>}</td>
                  <td>{a.open_vulnerability_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
