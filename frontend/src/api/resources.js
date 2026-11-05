import { client } from './client'

/**
 * Una función por endpoint, agrupadas por recurso. Los componentes
 * importan solo lo que usan (p. ej. `import { vulnerabilities } from
 * '../api/resources'`), así queda claro de un vistazo qué parte de
 * la UI habla con qué parte de la API.
 */

export const auth = {
  login: (username, password) => client.post('/api/auth/login/', { username, password }),
  loginMfa: (mfa_token, codigo) => client.post('/api/auth/login/mfa/', { mfa_token, codigo }),
  logout: () => client.post('/api/auth/logout/'),
  me: () => client.get('/api/auth/me/'),
  updateMe: (payload) => client.patch('/api/auth/me/', payload),
  changePassword: (clave_actual, clave_nueva) => client.post('/api/auth/cambiar-clave/', { clave_actual, clave_nueva }),
  mfaStatus: () => client.get('/api/auth/mfa/'),
  mfaStart: () => client.post('/api/auth/mfa/iniciar/'),
  mfaActivate: (codigo) => client.post('/api/auth/mfa/activar/', { codigo }),
  mfaDeactivate: (codigo) => client.post('/api/auth/mfa/desactivar/', { codigo }),
}

// Configuración: organización, integrantes y estado de conectores.
export const organization = {
  get: () => client.get('/api/organizacion/'),
  update: (payload) => client.patch('/api/organizacion/', payload),
}

export const members = {
  list: () => client.get('/api/usuarios/'),
  create: (payload) => client.post('/api/usuarios/', payload),
  updateRole: (id, role) => client.patch(`/api/usuarios/${id}/`, { role }),
  setActive: (id, is_active) => client.patch(`/api/usuarios/${id}/`, { is_active }),
  resetPassword: (id, clave_nueva) => client.post(`/api/usuarios/${id}/restablecer-clave/`, { clave_nueva }),
  resetSecurity: (id, quitar_mfa) => client.post(`/api/usuarios/${id}/restablecer-seguridad/`, { quitar_mfa }),
}

export const integrations = {
  status: () => client.get('/api/integraciones/estado/'),
  failures: () => client.get('/api/integraciones/fallas/'),
  incomplete: (params) => client.get('/api/registros-incompletos/', { params }),
  fixIncomplete: (id, payload) => client.post(`/api/registros-incompletos/${id}/corregir/`, payload),
}

export const cve = {
  list: (params) => client.get('/api/cve/', { params }),
  syncs: () => client.get('/api/cve/sincronizaciones/'),
  sync: () => client.post('/api/cve/sincronizar/'),
}

export const dashboard = {
  summary: () => client.get('/api/dashboard/summary/'),
}

export const executive = {
  summary: () => client.get('/api/ejecutivo/resumen/'),
}

export const assets = {
  list: (params) => client.get('/api/assets/', { params }),
  retrieve: (id) => client.get(`/api/assets/${id}/`),
  discover: (fuente, objetivo) => client.post('/api/assets/descubrir/', { fuente, objetivo }),
  report: () => client.get('/api/assets/informe/'),
  reportCsv: () => client.get('/api/assets/informe/', { params: { formato: 'csv' }, responseType: 'blob' }),
}

export const discoveries = {
  list: () => client.get('/api/descubrimientos/'),
}

export const sources = {
  list: () => client.get('/api/sources/'),
  sync: () => client.post('/api/sources/sync/'),
  update: (id, payload) => client.patch(`/api/sources/${id}/`, payload),
}

export const vulnerabilities = {
  list: (params) => client.get('/api/vulnerabilities/', { params }),
  retrieve: (id) => client.get(`/api/vulnerabilities/${id}/`),
  create: (payload) => client.post('/api/vulnerabilities/', payload),
  update: (id, payload) => client.patch(`/api/vulnerabilities/${id}/`, payload),
  analyze: (id) => client.post(`/api/vulnerabilities/${id}/analyze/`),
  explainSimple: (id) => client.post(`/api/vulnerabilities/${id}/explain_simple/`),
  clinicalImpact: (id) => client.post(`/api/vulnerabilities/${id}/clinical_impact/`),
  classify: (id) => client.post(`/api/vulnerabilities/${id}/clasificar/`),
  correctClassification: (id, riesgo, motivo) =>
    client.post(`/api/vulnerabilities/${id}/corregir-clasificacion/`, { riesgo, motivo }),
  model: () => client.get('/api/vulnerabilities/modelo/'),
  retrain: () => client.post('/api/vulnerabilities/modelo/'),
  riskMatrix: (params) => client.get('/api/vulnerabilities/matriz-riesgos/', { params }),
  trend: (params) => client.get('/api/vulnerabilities/tendencia/', { params }),
  exportFile: (params) => client.get('/api/vulnerabilities/exportar/', { params, responseType: 'blob' }),
}

export const controls = {
  list: () => client.get('/api/controls/'),
  byTheme: () => client.get('/api/controls/por-tema/'),
  assess: (id) => client.post(`/api/controls/${id}/assess/`),
  setState: (id, estado_implementacion) => client.patch(`/api/controls/${id}/`, { estado_implementacion }),
  applicable: () => client.get('/api/controls/matriz-aplicables/'),
  recommendations: () => client.get('/api/controls/recomendaciones/'),
  recommendationsFile: (formato) =>
    client.get('/api/controls/recomendaciones/', { params: { formato }, responseType: 'blob' }),
}

export const remediationPlans = {
  list: (params) => client.get('/api/remediation-plans/', { params }),
  create: (payload) => client.post('/api/remediation-plans/', payload),
  update: (id, payload) => client.patch(`/api/remediation-plans/${id}/`, payload),
  advance: (id) => client.patch(`/api/remediation-plans/${id}/advance/`),
  verify: (id, payload) => client.post(`/api/remediation-plans/${id}/verify/`, payload),
  generate: (prioridad_minima) => client.post('/api/remediation-plans/generar/', { prioridad_minima }),
  exportFile: (formato) => client.get('/api/remediation-plans/exportar/', { params: { formato }, responseType: 'blob' }),
}

export const evidence = {
  list: (params) => client.get('/api/evidence/', { params }),
  upload: (formData) => client.post('/api/evidence/', formData),
  download: (id) => client.get(`/api/evidence/${id}/descargar/`, { responseType: 'blob' }),
}

export const governance = {
  policies: () => client.get('/api/politicas-autonomia/'),
  updatePolicy: (id, nivel) => client.patch(`/api/politicas-autonomia/${id}/`, { nivel }),
  requests: () => client.get('/api/solicitudes-aprobacion/'),
  createRequest: (payload) => client.post('/api/solicitudes-aprobacion/', payload),
  approve: (id, comentario) => client.post(`/api/solicitudes-aprobacion/${id}/aprobar/`, { comentario }),
  reject: (id, comentario) => client.post(`/api/solicitudes-aprobacion/${id}/rechazar/`, { comentario }),
  actions: (params) => client.get('/api/acciones-agente/', { params }),
  proposeAction: (plan, tipo_accion, detalle) => client.post('/api/acciones-agente/', { plan, tipo_accion, detalle }),
  runAction: (id) => client.post(`/api/acciones-agente/${id}/ejecutar/`),
  discardAction: (id, comentario) => client.post(`/api/acciones-agente/${id}/descartar/`, { comentario }),
}

export const audit = {
  list: (params) => client.get('/api/registros-auditoria/', { params }),
}

export const incidents = {
  list: () => client.get('/api/incidentes/'),
  create: (payload) => client.post('/api/incidentes/', payload),
  setState: (id, estado) => client.post(`/api/incidentes/${id}/cambiar-estado/`, { estado }),
}

export const notifications = {
  summary: () => client.get('/api/notificaciones/resumen/'),
  list: (params) => client.get('/api/notificaciones/', { params }),
  read: (id) => client.post(`/api/notificaciones/${id}/leer/`),
  readAll: () => client.post('/api/notificaciones/leer-todas/'),
}

export const reports = {
  list: () => client.get('/api/reportes/'),
  generate: (formato) => client.post('/api/reportes/generar/', { formato }),
  download: (id) => client.get(`/api/reportes/${id}/descargar/`, { responseType: 'blob' }),
}

export const assistant = {
  ask: (pregunta) => client.post('/api/asistente/preguntar/', { pregunta }),
}

/** Descarga un blob de axios como archivo, usando el nombre que manda el servidor. */
export function saveBlob(response, fallback) {
  const header = response.headers?.['content-disposition'] || ''
  const match = /filename="?([^";]+)"?/i.exec(header)
  const name = match ? decodeURIComponent(match[1]) : fallback
  const url = URL.createObjectURL(response.data)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
