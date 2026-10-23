import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { auth } from '../api/resources'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('centinela_token'))
  const [profile, setProfile] = useState(null)

  // Quién está conectado (usuario, rol, organización real) se pide
  // aparte del login: el token por sí solo no dice nada de eso, y
  // antes la barra superior mostraba "Clínica San Lucas" fijo para
  // cualquier usuario que entrara.
  useEffect(() => {
    if (!token) {
      setProfile(null)
      return
    }
    auth
      .me()
      .then(({ data }) => setProfile(data))
      .catch(() => setProfile(null))
  }, [token])

  // Configuración cambia correo u organización: se vuelve a pedir el
  // perfil para que la barra superior y el menú muestren lo nuevo.
  async function reloadProfile() {
    const { data } = await auth.me()
    setProfile(data)
    return data
  }

  async function login(username, password) {
    const { data } = await auth.login(username, password)
    localStorage.setItem('centinela_token', data.token)
    setToken(data.token)
  }

  function logout() {
    localStorage.removeItem('centinela_token')
    setToken(null)
    setProfile(null)
  }

  // El Auditor "ve todo pero no hace nada": el backend ya rechaza sus
  // escrituras con 403; aquí se usa para deshabilitar los botones de
  // acción en vez de dejarlo apretar y recibir un error.
  const canEdit = profile?.role !== 'auditor'

  const value = useMemo(
    () => ({ token, isAuthenticated: Boolean(token), profile, canEdit, login, logout, reloadProfile }),
    [token, profile, canEdit],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
