import { resolveTheme, setPrefs, usePrefs } from './prefs'

/**
 * Atajo sobre las preferencias para quien solo necesita el tema
 * efectivo (claro u oscuro) y cambiarlo, como el menú de usuario.
 * La elección "sistema" vive en prefs.js.
 */
export function applyTheme(theme) {
  setPrefs({ theme })
}

export function useTheme() {
  const [prefs] = usePrefs()
  return [resolveTheme(prefs.theme), applyTheme]
}
