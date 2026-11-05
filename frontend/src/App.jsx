import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './layout/AppShell'
import ProtectedRoute from './ProtectedRoute'
import { useAuth } from './context/AuthContext'
import { IconLock } from './components/Icons'
import Assets from './pages/Assets'
import Assistant from './pages/Assistant'
import AuditLog from './pages/AuditLog'
import Controls from './pages/Controls'
import Dashboard from './pages/Dashboard'
import Evidence from './pages/Evidence'
import Executive from './pages/Executive'
import Governance from './pages/Governance'
import History from './pages/History'
import Incidents from './pages/Incidents'
import Login from './pages/Login'
import RemediationPlan from './pages/RemediationPlan'
import Reports from './pages/Reports'
import RiskMatrix from './pages/RiskMatrix'
import Settings from './pages/Settings'
import Sources from './pages/Sources'
import Verification from './pages/Verification'
import Vulnerabilities from './pages/Vulnerabilities'

/** HU28 esc. 2: si el rol no tiene el módulo, se muestra "permisos insuficientes" en vez de la página. */
function RequireModulo({ modulo, children }) {
  const { profile, can } = useAuth()
  if (!profile) return null
  if (!can(modulo)) {
    return (
      <div className="panel pb" style={{ maxWidth: 560 }}>
        <div className="empty">
          <IconLock size={34} />
          <b>Permisos insuficientes</b>
          <span>Tu rol ({profile.role_display}) no tiene acceso a este módulo. Si lo necesitas, pídeselo a la Gerencia.</span>
        </div>
      </div>
    )
  }
  return children
}

/** La página de inicio depende del rol: el personal administrativo va directo a reportar un incidente. */
function Inicio() {
  const { profile, can } = useAuth()
  if (!profile) return null
  if (can('panel')) return <Dashboard />
  if (can('ejecutivo')) return <Navigate to="/ejecutivo" replace />
  return <Navigate to="/incidentes" replace />
}

const RUTAS = [
  ['ejecutivo', 'ejecutivo', Executive],
  ['vulnerabilidades', 'vulnerabilidades', Vulnerabilities],
  ['riesgos', 'riesgos', RiskMatrix],
  ['historial', 'vulnerabilidades', History],
  ['plan', 'remediacion', RemediationPlan],
  ['verificacion', 'remediacion', Verification],
  ['asistente', 'asistente', Assistant],
  ['controles', 'controles', Controls],
  ['evidencias', 'evidencias', Evidence],
  ['reportes', 'informes', Reports],
  ['activos', 'activos', Assets],
  ['fuentes', 'integraciones', Sources],
  ['gobernanza', 'gobernanza', Governance],
  ['auditoria', 'auditoria', AuditLog],
  ['incidentes', 'incidentes', Incidents],
  ['configuracion', 'configuracion', Settings],
]

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<Inicio />} />
        {RUTAS.map(([path, modulo, Page]) => (
          <Route key={path} path={path} element={<RequireModulo modulo={modulo}><Page /></RequireModulo>} />
        ))}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
