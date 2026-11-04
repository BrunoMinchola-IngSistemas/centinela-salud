// Traducción de los códigos internos del registro de auditoría a algo
// legible. Lo usan la página Registro de auditoría y la ventana de
// auditoría de Configuración.
export const MOD_BADGE = { autonomo: 'b-ok', asistido: 'b-br', con_aprobacion: 'b-high' }
export const MOD_LABEL = { autonomo: 'Autónomo', asistido: 'Asistido', con_aprobacion: 'Con aprobación' }

export const ACCION_LABEL = {
  solicitud_creada: 'Pidió aprobación',
  solicitud_aprobada: 'Aprobó una acción',
  solicitud_rechazada: 'Rechazó una acción',
  politica_autonomia_cambiada: 'Cambió un nivel de autonomía',
  incidente_reportado: 'Reportó un incidente',
  verificacion_cerrada: 'Cerró un hallazgo tras verificar',
  verificacion_fallida: 'Reescaneo: el hallazgo sigue presente',
  plan_creado: 'Creó un plan de corrección',
  plan_avanzado: 'Avanzó un plan de corrección',
  analisis_ia: 'Analizó un hallazgo con IA',
  notificacion_enviada: 'Envió una notificación',
  cuenta_actualizada: 'Actualizó su cuenta',
  clave_cambiada: 'Cambió su contraseña',
  organizacion_actualizada: 'Editó los datos de la organización',
  rol_cambiado: 'Cambió el rol de un usuario',
  usuario_creado: 'Creó un usuario',
  usuario_activado: 'Activó una cuenta',
  usuario_desactivado: 'Desactivó una cuenta',
  clave_restablecida: 'Restableció la contraseña de un usuario',
  descubrimiento_ejecutado: 'Ejecutó un descubrimiento de activos',
}
