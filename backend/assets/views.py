from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets
from rest_framework.filters import SearchFilter

from common.mixins import OrganizationScopedMixin

from .models import Asset
from .serializers import AssetSerializer


class AssetViewSet(OrganizationScopedMixin, viewsets.ModelViewSet):
    """
    CRUD de activos. En producción, la mayoría se crean automáticamente
    cuando Wazuh u OpenVAS reportan un host nuevo (ver integrations.sync),
    no a mano desde aquí.
    """

    queryset = Asset.objects.all().order_by("hostname")
    serializer_class = AssetSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["asset_type", "criticality", "stores_phi", "wazuh_agent_online"]
    search_fields = ["hostname", "ip_address", "operating_system"]

