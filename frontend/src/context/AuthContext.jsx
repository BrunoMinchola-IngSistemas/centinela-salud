import { createContext, useContext, useMemo, useState } from 'react'
import { auth } from '../api/resources'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('centinela_token'))

  async function login(username, password) {
    const { data } = await auth.login(username, password)
    localStorage.setItem('centinela_token', data.token)
    setToken(data.token)
  }

  function logout() {
    localStorage.removeItem('centinela_token')
    setToken(null)
  }

  const value = useMemo(() => ({ token, isAuthenticated: Boolean(token), login, logout }), [token])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
