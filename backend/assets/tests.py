from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Organization
from accounts.models import User as Profile

from .models import Asset, AssetType, Criticality


class AssetApiTests(APITestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Clínica de prueba")
        self.user = User.objects.create_user("analista", password="x")
        Profile.objects.create(user=self.user, organization=self.org)
        self.client.force_authenticate(self.user)

    def test_crear_activo_queda_asociado_a_la_organizacion_del_usuario(self):
        resp = self.client.post(
            reverse("asset-list"),
            {
                "hostname": "srv-nuevo",
                "asset_type": AssetType.SERVER,
                "criticality": Criticality.HIGH,
                "stores_phi": True,
            },
        )

        self.assertEqual(resp.status_code, 201, resp.content)
        asset = Asset.objects.get(hostname="srv-nuevo")
        self.assertEqual(asset.organization, self.org)

    def test_no_se_puede_duplicar_el_mismo_hostname_en_la_misma_organizacion(self):
        Asset.objects.create(organization=self.org, hostname="srv-dup", asset_type=AssetType.SERVER)

        resp = self.client.post(reverse("asset-list"), {"hostname": "srv-dup", "asset_type": AssetType.SERVER})

        self.assertEqual(resp.status_code, 400)
