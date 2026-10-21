from .rls import desactivar


class ResetRLSMiddleware:
    """
    Al terminar cada petición devuelve la conexión a su rol normal, para
    que una conexión reutilizada nunca "herede" la organización de la
    petición anterior.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        finally:
            desactivar()
