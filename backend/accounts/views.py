from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import MeSerializer


class MeView(APIView):
    """
    GET /api/auth/me/ - quién está conectado. El frontend lo usa para
    mostrar el nombre real de la organización y el rol en la barra
    superior, en vez de un texto fijo ("Clínica San Lucas" a secas
    para cualquier usuario).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response(
                {"detail": "El usuario no tiene un perfil de organización asociado."}, status=403
            )
        return Response(MeSerializer(profile).data)
