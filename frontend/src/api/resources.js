import { client } from './client'

/**
 * Una función por endpoint, agrupadas por recurso. Los componentes
 * importan solo lo que usan (p. ej. `import { vulnerabilities } from
 * '../api/resources'`), así queda claro de un vistazo qué parte de
 * la UI habla con qué parte de la API.
 */

export const auth = {
  login: (username, password) => client.post('/api/auth/login/', { username, password }),
  me: () => client.get('/api/auth/me/'),
  updateMe: (payload) => client.patch('/api/auth/me/', payload),
  changePassword: (clave_actual, clave_nueva) => client.post('/api/auth/cambiar-clave/', { clave_actual, clave_nueva }),
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
}

export const integrations = {
  status: () => client.get('/api/integraciones/estado/'),
}

export const dashboard = {
  summary: () => client.get('/api/dashboard/summary/'),
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
  analyze: (id) => client.post(`/api/vulnerabilities/${id}/analyze/`),
  explainSimple: (id) => client.post(`/api/vulnerabilities/${id}/explain_simple/`),
  clinicalImpact: (id) => client.post(`/api/vulnerabilities/${id}/clinical_impact/`),
}

export const controls = {
  list: () => client.get('/api/controls/'),
  byTheme: () => client.get('/api/controls/por-tema/'),
  assess: (id) => client.post(`/api/controls/${id}/assess/`),
}

export const remediationPlans = {
  list: (params) => client.get('/api/remediation-plans/', { params }),
  create: (payload) => client.post('/api/remediation-plans/', payload),
  advance: (id) => client.patch(`/api/remediation-plans/${id}/advance/`),
  verify: (id, payload) => client.post(`/api/remediation-plans/${id}/verify/`, payload),
}

export const evidence = {
  list: (params) => client.get('/api/evidence/', { params }),
}

export const governance = {
  policies: () => client.get('/api/politicas-autonomia/'),
  updatePolicy: (id, nivel) => client.patch(`/api/politicas-autonomia/${id}/`, { nivel }),
  requests: () => client.get('/api/solicitudes-aprobacion/'),
  createRequest: (payload) => client.post('/api/solicitudes-aprobacion/', payload),
  approve: (id, comentario) => client.post(`/api/solicitudes-aprobacion/${id}/aprobar/`, { comentario }),
  reject: (id, comentario) => client.post(`/api/solicitudes-aprobacion/${id}/rechazar/`, { comentario }),
}

export const audit = {
  list: (params) => client.get('/api/registros-auditoria/', { params }),
}

export const incidents = {
  list: () => client.get('/api/incidentes/'),
  create: (payload) => client.post('/api/incidentes/', payload),
}
