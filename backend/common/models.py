"""
Además de enviar la señal post_migrate que aplica RLS (ver apps.py),
esta app guarda el estado de las tareas programadas del agente.
"""

from django.db import models


class EjecucionTarea(models.Model):
    """Última ejecución de cada tarea del programador (común a todas las organizaciones)."""

    nombre = models.CharField(max_length=60, unique=True)
    ultima_ejecucion = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    detalle = models.TextField(blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre
