from django.contrib.auth.models import User as DjangoUser
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Organization, Role, User


class MeEndpointTests(APITestCase):
    """
    /api/auth/me/ es lo que usa la barra superior del frontend para
    mostrar el nombre real de la organización y el rol de quien inició
    sesión, en vez de un texto fijo igual para cualquier usuario.
    """

    def test_usuario_con_perfil_ve_su_organizacion_y_rol(self):
        org = Organization.objects.create(name="Clínica San Lucas (demo)", ruc="20123456789")
        django_user = DjangoUser.objects.create_user("demo", password="demo12345")
        User.objects.create(user=django_user, organization=org, role=Role.ANALYST)

        self.client.force_authenticate(django_user)
        resp = self.client.get(reverse("auth-me"))

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["username"], "demo")
        self.assertEqual(resp.data["role"], "analyst")
        self.assertEqual(resp.data["organization"]["name"], "Clínica San Lucas (demo)")

    def test_usuario_sin_perfil_recibe_403_no_un_crash(self):
        huerfano = DjangoUser.objects.create_user("huerfano", password="x")
        self.client.force_authenticate(huerfano)

        resp = self.client.get(reverse("auth-me"))

        self.assertEqual(resp.status_code, 403)
