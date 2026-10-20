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
}

export const dashboard = {
  summary: () => client.get('/api/dashboard/summary/'),
}

export const assets = {
  list: (params) => client.get('/api/assets/', { params }),
  retrieve: (id) => client.get(`/api/assets/${id}/`),
}

export const sources = {
  list: () => client.get('/api/sources/'),
  sync: () => client.post('/api/sources/sync/'),
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
