from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Notificacion


class NotificacionSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = Notificacion
        fields = [
            "id", "tipo", "tipo_display", "nivel", "titulo", "mensaje", "enlace",
            "objeto_tipo", "objeto_id", "leida", "creada_en",
        ]
        read_only_fields = fields


class NotificacionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    /api/notificaciones/ - las notificaciones de quien inició sesión
    (nunca las de otra persona). Cualquier rol las puede marcar como
    leídas, también el Auditor: es su bandeja, no datos de la clínica.
    """

    serializer_class = NotificacionSerializer
    modulo = "notificaciones"
    escritura_propia = True  # ver common.permissions: el Auditor puede marcar las suyas

    def get_queryset(self):
        qs = Notificacion.objects.filter(destinatario=self.request.user)
        if self.request.query_params.get("no_leidas") in ("1", "true"):
            qs = qs.filter(leida=False)
        return qs

    @action(detail=False, methods=["get"], url_path="resumen")
    def resumen(self, request):
        qs = Notificacion.objects.filter(destinatario=request.user, leida=False)
        ultimas = NotificacionSerializer(qs[:5], many=True).data
        return Response({"no_leidas": qs.count(), "ultimas": ultimas})

    @action(detail=True, methods=["post"], url_path="leer")
    def leer(self, request, pk=None):
        n = self.get_object()
        n.leida = True
        n.save(update_fields=["leida"])
        return Response(NotificacionSerializer(n).data)

    @action(detail=False, methods=["post"], url_path="leer-todas")
    def leer_todas(self, request):
        total = Notificacion.objects.filter(destinatario=request.user, leida=False).update(leida=True)
        return Response({"marcadas": total})
