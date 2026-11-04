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


class ConfiguracionTests(APITestCase):
    """
    Endpoints que alimentan la pantalla Configuración: cuenta propia,
    organización, integrantes y estado de integraciones. Lo que importa
    aquí es quién puede cambiar qué según su rol.
    """

    def setUp(self):
        from governance.models import RegistroAuditoria

        self.RegistroAuditoria = RegistroAuditoria
        self.org = Organization.objects.create(name="Clínica Config", ruc="20100000001")
        self.otra_org = Organization.objects.create(name="Otra clínica")

        def crear(username, role, org=None):
            user = DjangoUser.objects.create_user(username, password="clave-vieja-123", email=f"{username}@x.pe")
            User.objects.create(user=user, organization=org or self.org, role=role)
            return user

        self.admin = crear("admin", Role.ADMIN)
        self.analista = crear("analista", Role.ANALYST)
        self.ti = crear("ti", Role.IT_OWNER)
        self.auditor = crear("auditor", Role.AUDITOR)
        self.ajeno = crear("ajeno", Role.ADMIN, self.otra_org)

    # --- Mi cuenta -------------------------------------------------------

    def test_cualquier_rol_incluido_auditor_cambia_su_correo(self):
        self.client.force_authenticate(self.auditor)
        resp = self.client.patch(reverse("auth-me"), {"email": "nuevo@x.pe"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["email"], "nuevo@x.pe")
        self.auditor.refresh_from_db()
        self.assertEqual(self.auditor.email, "nuevo@x.pe")
        self.assertTrue(self.RegistroAuditoria.objects.filter(accion="cuenta_actualizada", actor="auditor").exists())

    def test_cambiar_clave_exige_la_actual(self):
        self.client.force_authenticate(self.analista)
        resp = self.client.post(reverse("auth-cambiar-clave"), {"clave_actual": "mal", "clave_nueva": "clave-nueva-123"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("clave_actual", resp.data)

        resp = self.client.post(
            reverse("auth-cambiar-clave"), {"clave_actual": "clave-vieja-123", "clave_nueva": "clave-nueva-123"}
        )
        self.assertEqual(resp.status_code, 200)
        self.analista.refresh_from_db()
        self.assertTrue(self.analista.check_password("clave-nueva-123"))
        self.assertTrue(self.RegistroAuditoria.objects.filter(accion="clave_cambiada", actor="analista").exists())

    def test_cambiar_clave_rechaza_claves_cortas(self):
        self.client.force_authenticate(self.analista)
        resp = self.client.post(reverse("auth-cambiar-clave"), {"clave_actual": "clave-vieja-123", "clave_nueva": "corta"})
        self.assertEqual(resp.status_code, 400)

    # --- Organización ----------------------------------------------------

    def test_todos_ven_su_organizacion_pero_solo_admin_la_edita(self):
        self.client.force_authenticate(self.analista)
        self.assertEqual(self.client.get(reverse("organizacion")).data["name"], "Clínica Config")
        self.assertEqual(self.client.patch(reverse("organizacion"), {"name": "Hackeada"}).status_code, 403)

        self.client.force_authenticate(self.auditor)
        self.assertEqual(self.client.patch(reverse("organizacion"), {"name": "Hackeada"}).status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.patch(reverse("organizacion"), {"name": "Clínica Renombrada", "ruc": "20100000002"})
        self.assertEqual(resp.status_code, 200)
        self.org.refresh_from_db()
        self.assertEqual(self.org.name, "Clínica Renombrada")
        registro = self.RegistroAuditoria.objects.get(accion="organizacion_actualizada")
        self.assertEqual(registro.detalle["name"], {"de": "Clínica Config", "a": "Clínica Renombrada"})

    # --- Usuarios de la organización -------------------------------------

    def test_lista_de_usuarios_solo_muestra_la_propia_organizacion(self):
        self.client.force_authenticate(self.auditor)
        resp = self.client.get(reverse("miembro-list"))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual({m["username"] for m in resp.data}, {"admin", "analista", "ti", "auditor"})

    def test_solo_admin_cambia_roles_y_nunca_el_suyo(self):
        perfil_analista = User.objects.get(user=self.analista)
        url = reverse("miembro-detail", kwargs={"pk": perfil_analista.pk})

        self.client.force_authenticate(self.ti)
        self.assertEqual(self.client.patch(url, {"role": "admin"}).status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.patch(url, {"role": "it_owner"})
        self.assertEqual(resp.status_code, 200)
        perfil_analista.refresh_from_db()
        self.assertEqual(perfil_analista.role, Role.IT_OWNER)
        self.assertTrue(self.RegistroAuditoria.objects.filter(accion="rol_cambiado", detalle__usuario="analista").exists())

        propio = User.objects.get(user=self.admin)
        resp = self.client.patch(reverse("miembro-detail", kwargs={"pk": propio.pk}), {"role": "analyst"})
        self.assertEqual(resp.status_code, 400)

    def test_admin_crea_usuarios_en_su_organizacion(self):
        self.client.force_authenticate(self.ti)
        resp = self.client.post(reverse("miembro-list"), {"username": "nuevo", "password": "clave-segura-1", "role": "analyst"})
        self.assertEqual(resp.status_code, 403)

        self.client.force_authenticate(self.admin)
        resp = self.client.post(
            reverse("miembro-list"),
            {"username": "nuevo", "email": "nuevo@x.pe", "password": "clave-segura-1", "role": "it_owner"},
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        perfil = User.objects.get(user__username="nuevo")
        self.assertEqual(perfil.organization, self.org)
        self.assertEqual(perfil.role, Role.IT_OWNER)
        self.assertTrue(perfil.user.check_password("clave-segura-1"))
        self.assertTrue(self.RegistroAuditoria.objects.filter(accion="usuario_creado", detalle__usuario="nuevo").exists())

        # Nombre repetido y clave corta se rechazan con 400.
        resp = self.client.post(reverse("miembro-list"), {"username": "NUEVO", "password": "clave-segura-1"})
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(reverse("miembro-list"), {"username": "otro", "password": "corta"})
        self.assertEqual(resp.status_code, 400)

    def test_admin_desactiva_y_restablece_clave_pero_no_a_si_mismo(self):
        perfil_analista = User.objects.get(user=self.analista)
        url = reverse("miembro-detail", kwargs={"pk": perfil_analista.pk})
        self.client.force_authenticate(self.admin)

        resp = self.client.patch(url, {"is_active": False})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.analista.refresh_from_db()
        self.assertFalse(self.analista.is_active)
        self.assertTrue(self.RegistroAuditoria.objects.filter(accion="usuario_desactivado").exists())

        resp = self.client.post(reverse("miembro-restablecer-clave", kwargs={"pk": perfil_analista.pk}), {"clave_nueva": "otra-clave-123"})
        self.assertEqual(resp.status_code, 200)
        self.analista.refresh_from_db()
        self.assertTrue(self.analista.check_password("otra-clave-123"))

        propio = User.objects.get(user=self.admin)
        self.assertEqual(self.client.patch(reverse("miembro-detail", kwargs={"pk": propio.pk}), {"is_active": False}).status_code, 400)
        resp = self.client.post(reverse("miembro-restablecer-clave", kwargs={"pk": propio.pk}), {"clave_nueva": "otra-clave-123"})
        self.assertEqual(resp.status_code, 400)

    def test_auditoria_se_filtra_por_actor_y_accion(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(reverse("organizacion"), {"ruc": "20100000009"})
        self.client.force_authenticate(self.analista)
        self.client.patch(reverse("auth-me"), {"email": "a@x.pe"})

        resp = self.client.get(reverse("registro-auditoria-list"), {"actor": "admin"})
        self.assertEqual({r["accion"] for r in resp.data["results"]}, {"organizacion_actualizada"})
        resp = self.client.get(reverse("registro-auditoria-list"), {"accion": "cuenta_actualizada"})
        self.assertEqual([r["actor"] for r in resp.data["results"]], ["analista"])

    def test_admin_no_alcanza_usuarios_de_otra_organizacion(self):
        perfil_ajeno = User.objects.get(user=self.ajeno)
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(reverse("miembro-detail", kwargs={"pk": perfil_ajeno.pk}), {"role": "analyst"})
        self.assertEqual(resp.status_code, 404)

    # --- Integraciones ---------------------------------------------------

    def test_estado_de_integraciones_no_expone_credenciales(self):
        self.client.force_authenticate(self.ti)
        resp = self.client.get(reverse("integraciones-estado"))
        self.assertEqual(resp.status_code, 200)
        claves = {c["clave"] for c in resp.data["conectores"]}
        self.assertEqual(claves, {"wazuh", "openvas", "qwen", "kaspersky"})
        for conector in resp.data["conectores"]:
            self.assertEqual(set(conector) - {"clave", "nombre", "descripcion", "url", "configurado", "variables"}, set())
