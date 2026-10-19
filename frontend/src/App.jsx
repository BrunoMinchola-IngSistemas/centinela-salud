import { Navigate, Route, Routes } from 'react-router-dom'
import AppShell from './layout/AppShell'
import ProtectedRoute from './ProtectedRoute'
import Assets from './pages/Assets'
import Controls from './pages/Controls'
import Dashboard from './pages/Dashboard'
import Evidence from './pages/Evidence'
import Login from './pages/Login'
import RemediationPlan from './pages/RemediationPlan'
import Verification from './pages/Verification'
import Vulnerabilities from './pages/Vulnerabilities'

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
        <Route index element={<Dashboard />} />
        <Route path="vulnerabilidades" element={<Vulnerabilities />} />
        <Route path="plan" element={<RemediationPlan />} />
        <Route path="verificacion" element={<Verification />} />
        <Route path="controles" element={<Controls />} />
        <Route path="evidencias" element={<Evidence />} />
        <Route path="activos" element={<Assets />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
