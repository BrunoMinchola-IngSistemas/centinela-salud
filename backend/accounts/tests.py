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


class AuditorSoloLecturaTests(APITestCase):
    """El Auditor ve todo lo de su organización, pero no puede modificar nada."""

    def setUp(self):
        from assets.models import Asset, AssetType, Criticality

        self.org = Organization.objects.create(name="Clínica auditada")
        self.auditor = DjangoUser.objects.create_user("auditor", password="x")
        User.objects.create(user=self.auditor, organization=self.org, role=Role.AUDITOR)
        self.analista = DjangoUser.objects.create_user("analista", password="x")
        User.objects.create(user=self.analista, organization=self.org, role=Role.ANALYST)
        self.asset = Asset.objects.create(
            organization=self.org, hostname="srv-1", asset_type=AssetType.SERVER, criticality=Criticality.HIGH
        )

    def test_auditor_puede_leer(self):
        self.client.force_authenticate(self.auditor)
        self.assertEqual(self.client.get(reverse("asset-list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("registro-auditoria-list")).status_code, 200)

    def test_auditor_no_puede_crear_ni_editar_ni_borrar(self):
        self.client.force_authenticate(self.auditor)
        resp = self.client.post(reverse("asset-list"), {"hostname": "nuevo", "asset_type": "server"})
        self.assertEqual(resp.status_code, 403)
        resp = self.client.patch(reverse("asset-detail", kwargs={"pk": self.asset.id}), {"hostname": "x"})
        self.assertEqual(resp.status_code, 403)
        resp = self.client.delete(reverse("asset-detail", kwargs={"pk": self.asset.id}))
        self.assertEqual(resp.status_code, 403)

    def test_analista_si_puede_crear(self):
        self.client.force_authenticate(self.analista)
        resp = self.client.post(reverse("asset-list"), {"hostname": "nuevo", "asset_type": "server"})
        self.assertEqual(resp.status_code, 201)
