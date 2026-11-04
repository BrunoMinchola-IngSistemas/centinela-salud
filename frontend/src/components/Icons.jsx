/**
 * Iconos SVG de línea (estilo Lucide) para no depender de emojis ni de
 * una librería externa. Todos son decorativos (aria-hidden): el texto
 * que los acompaña es el que lee el lector de pantalla.
 */
function Icon({ children, size = 18, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

export const IconShield = (p) => (
  <Icon {...p}><path d="M12 3 4.5 6v5.3c0 4.6 3.1 8.6 7.5 9.7 4.4-1.1 7.5-5.1 7.5-9.7V6L12 3Z" /></Icon>
)
export const IconShieldCheck = (p) => (
  <Icon {...p}><path d="M12 3 4.5 6v5.3c0 4.6 3.1 8.6 7.5 9.7 4.4-1.1 7.5-5.1 7.5-9.7V6L12 3Z" /><path d="m9 12 2 2 4-4" /></Icon>
)
export const IconGrid = (p) => (
  <Icon {...p}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></Icon>
)
export const IconBug = (p) => (
  <Icon {...p}><path d="M8 9a4 4 0 0 1 8 0v5a4 4 0 0 1-8 0Z" /><path d="M12 14v6M3 13h5M16 13h5M5 8l3 2M19 8l-3 2M5 19l3-2M19 19l-3-2M9 5l1-2M15 5l-1-2" /></Icon>
)
export const IconKanban = (p) => (
  <Icon {...p}><rect x="3" y="4" width="5" height="16" rx="1.2" /><rect x="10" y="4" width="5" height="10" rx="1.2" /><rect x="17" y="4" width="4" height="7" rx="1.2" /></Icon>
)
export const IconCheckCircle = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="m8.5 12 2.5 2.5 4.5-5" /></Icon>
)
export const IconBook = (p) => (
  <Icon {...p}><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5Z" /><path d="M4 20.5V5.5M8 7h8M8 11h6" /></Icon>
)
export const IconFolder = (p) => (
  <Icon {...p}><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z" /></Icon>
)
export const IconScale = (p) => (
  <Icon {...p}><path d="M12 3v18M5 21h14M3 8h18" /><path d="m6 8-3 7a3 3 0 0 0 6 0l-3-7ZM18 8l-3 7a3 3 0 0 0 6 0l-3-7Z" /></Icon>
)
export const IconList = (p) => (
  <Icon {...p}><path d="M8 6h13M8 12h13M8 18h13" /><circle cx="4" cy="6" r="1" /><circle cx="4" cy="12" r="1" /><circle cx="4" cy="18" r="1" /></Icon>
)
export const IconAlert = (p) => (
  <Icon {...p}><path d="M12 3 2.5 20h19L12 3Z" /><path d="M12 10v4M12 17.5v.5" /></Icon>
)
export const IconServer = (p) => (
  <Icon {...p}><rect x="3" y="4" width="18" height="7" rx="1.5" /><rect x="3" y="13" width="18" height="7" rx="1.5" /><path d="M7 7.5h.01M7 16.5h.01" /></Icon>
)
export const IconBrain = (p) => (
  <Icon {...p}><path d="M9.5 3a3 3 0 0 0-3 3 3 3 0 0 0-2 5 3 3 0 0 0 1 5.5A3 3 0 0 0 9.5 21c1 0 2-.5 2.5-1.5V4.5C11.5 3.5 10.5 3 9.5 3Z" /><path d="M14.5 3a3 3 0 0 1 3 3 3 3 0 0 1 2 5 3 3 0 0 1-1 5.5 3 3 0 0 1-4 4.5c-1 0-2-.5-2.5-1.5V4.5c.5-1 1.5-1.5 2.5-1.5Z" /></Icon>
)
export const IconClock = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Icon>
)
export const IconCalendar = (p) => (
  <Icon {...p}><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4M16 3v4" /></Icon>
)
export const IconLogout = (p) => (
  <Icon {...p}><path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4M15 8l4 4-4 4M19 12H9" /></Icon>
)
export const IconSun = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></Icon>
)
export const IconMoon = (p) => (
  <Icon {...p}><path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" /></Icon>
)
export const IconActivity = (p) => (
  <Icon {...p}><path d="M3 12h4l3-8 4 16 3-8h4" /></Icon>
)
export const IconChip = (p) => (
  <Icon {...p}><rect x="6" y="6" width="12" height="12" rx="2" /><rect x="10" y="10" width="4" height="4" /><path d="M9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4" /></Icon>
)
export const IconDatabase = (p) => (
  <Icon {...p}><ellipse cx="12" cy="5.5" rx="8" ry="3" /><path d="M4 5.5v13c0 1.7 3.6 3 8 3s8-1.3 8-3v-13M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></Icon>
)
export const IconZap = (p) => (
  <Icon {...p}><path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" /></Icon>
)
export const IconExternal = (p) => (
  <Icon {...p}><path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" /></Icon>
)
export const IconCross = (p) => (
  <Icon {...p}><path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6Z" /></Icon>
)
export const IconLayers = (p) => (
  <Icon {...p}><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 13 9 5 9-5M3 17.5l9 5 9-5" /></Icon>
)
export const IconSettings = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" /></Icon>
)
export const IconUsers = (p) => (
  <Icon {...p}><circle cx="9" cy="8" r="4" /><path d="M2 21a7 7 0 0 1 14 0M16 4a4 4 0 0 1 0 8M22 21a7 7 0 0 0-5-6.7" /></Icon>
)
export const IconBuilding = (p) => (
  <Icon {...p}><rect x="4" y="3" width="16" height="18" rx="1.5" /><path d="M9 21v-4h6v4M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2" /></Icon>
)
export const IconKey = (p) => (
  <Icon {...p}><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9M15 8l2 2M18 5l2 2" /></Icon>
)
export const IconPlug = (p) => (
  <Icon {...p}><path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0ZM12 17v5" /></Icon>
)
export const IconPalette = (p) => (
  <Icon {...p}><path d="M12 3a9 9 0 1 0 0 18c1.5 0 2-1 2-2 0-.8-.5-1.2-.5-2 0-1 .8-1.5 2-1.5H17a4 4 0 0 0 4-4c0-5-4-8.5-9-8.5Z" /><circle cx="7.5" cy="12" r="1" /><circle cx="10" cy="8" r="1" /><circle cx="14.5" cy="7.5" r="1" /></Icon>
)
export const IconUser = (p) => (
  <Icon {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Icon>
)
export const IconRefresh = (p) => (
  <Icon {...p}><path d="M21 12a9 9 0 1 1-2.6-6.4M21 3v6h-6" /></Icon>
)
export const IconRadar = (p) => (
  <Icon {...p}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><path d="M12 12 18 6M12 3v2M21 12h-2M12 21v-2M3 12h2" /><circle cx="12" cy="12" r="1" fill="currentColor" /></Icon>
)
export const IconDownload = (p) => (
  <Icon {...p}><path d="M12 3v12M7 10l5 5 5-5M4 19h16" /></Icon>
)
export const IconFileText = (p) => (
  <Icon {...p}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z" /><path d="M14 3v5h5M9 13h6M9 17h6" /></Icon>
)
export const IconUserPlus = (p) => (
  <Icon {...p}><circle cx="9" cy="8" r="4" /><path d="M2 21a7 7 0 0 1 14 0M19 8v6M16 11h6" /></Icon>
)
export const IconMonitor = (p) => (
  <Icon {...p}><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></Icon>
)
export const IconBell = (p) => (
  <Icon {...p}><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4l2-2ZM10 20a2 2 0 0 0 4 0" /></Icon>
)
export const IconUserCheck = (p) => (
  <Icon {...p}><circle cx="9" cy="8" r="4" /><path d="M2 21a7 7 0 0 1 14 0M16 11l2 2 4-4" /></Icon>
)
