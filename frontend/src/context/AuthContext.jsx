import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { auth } from '../api/resources'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('centinela_token'))
  const [profile, setProfile] = useState(null)

  // Quién está conectado (usuario, rol, organización real y módulos a
  // los que tiene acceso, HU28) se pide aparte del login.
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

  async function reloadProfile() {
    const { data } = await auth.me()
    setProfile(data)
    return data
  }

  function saveToken(key) {
    localStorage.setItem('centinela_token', key)
    setToken(key)
  }

  /**
   * HU29: si la cuenta tiene segundo factor, el primer paso no entrega
   * el token sino un `mfa_token`; la pantalla de login pide el código y
   * llama a verifyMfa. Devuelve { mfaToken } en ese caso.
   */
  async function login(username, password) {
    const { data } = await auth.login(username, password)
    if (data.mfa_requerido) return { mfaToken: data.mfa_token }
    saveToken(data.token)
    return {}
  }

  async function verifyMfa(mfaToken, codigo) {
    const { data } = await auth.loginMfa(mfaToken, codigo)
    saveToken(data.token)
  }

  function logout() {
    // Se invalida también en el servidor (el token deja de servir).
    auth.logout().catch(() => {})
    localStorage.removeItem('centinela_token')
    setToken(null)
    setProfile(null)
  }

  // El Auditor "ve todo pero no hace nada": el backend ya rechaza sus
  // escrituras con 403; aquí se usa para deshabilitar los botones.
  const canEdit = profile?.role !== 'auditor'
  const modules = profile?.modulos

  const value = useMemo(
    () => ({
      token,
      isAuthenticated: Boolean(token),
      profile,
      canEdit,
      can: (modulo) => (modules ? modules.includes(modulo) : true),
      role: profile?.role,
      login,
      verifyMfa,
      logout,
      reloadProfile,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [token, profile, canEdit, modules],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth debe usarse dentro de AuthProvider')
  return ctx
}
