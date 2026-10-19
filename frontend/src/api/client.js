import axios from 'axios'

// En desarrollo esto queda vacío y usamos el proxy de Vite (ver
// vite.config.js). En producción, VITE_API_URL apunta a la URL real
// de la API (p. ej. https://api.centinela-salud.clinica.pe).
const baseURL = import.meta.env.VITE_API_URL || ''

export const client = axios.create({ baseURL })

client.interceptors.request.use((config) => {
  const token = localStorage.getItem('centinela_token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('centinela_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  },
)
