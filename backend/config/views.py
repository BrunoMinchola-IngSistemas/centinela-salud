from datetime import timedelta

from django.db.models import Count
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from assets.models import Asset
from controls.models import Control
from vulnerabilities.models import Severity, Vulnerability, VulnerabilityStatus


class DashboardSummaryView(APIView):
    """
    Agrega en una sola llamada lo que pinta el Panel general de la
    consola: cifras de riesgo, exposición por tipo de activo y los
    controles con mayor brecha. Pensado para una sola organización
    por request (ver TODO de autenticación/tenant más abajo).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = getattr(request.user, "profile", None)
        if profile is None:
            return Response(
                {"detail": "El usuario no tiene un perfil de organización asociado."}, status=403
            )
        organization = profile.organization

        open_qs = Vulnerability.objects.filter(organization=organization).exclude(status=VulnerabilityStatus.CLOSED)
        today = timezone.now().date()

        by_severity = dict(open_qs.values_list("severity").annotate(n=Count("id")).values_list("severity", "n"))
        overdue_count = open_qs.filter(due_date__lt=today).count()

        exposure = []
        for asset_type, label in Asset._meta.get_field("asset_type").choices:
            assets_of_type = Asset.objects.filter(organization=organization, asset_type=asset_type)
            counts = {
                sev: open_qs.filter(asset__in=assets_of_type, severity=sev).count() for sev, _ in Severity.choices
            }
            total = sum(counts.values())
            if total or assets_of_type.exists():
                exposure.append({"type": label, "total": total, "by_severity": counts})

        controls_with_gaps = []
        for control in Control.objects.filter(organization=organization).prefetch_related("vulnerabilities"):
            linked = control.vulnerabilities.all()
            open_count = linked.exclude(status=VulnerabilityStatus.CLOSED).count()
            closed_count = linked.filter(status=VulnerabilityStatus.CLOSED).count()
            score = max(20, min(99, control.baseline_score - open_count * 3 + closed_count * 3))
            controls_with_gaps.append({"id": control.id, "name": control.name, "score": score})
        controls_with_gaps.sort(key=lambda c: c["score"])

        top_priority = (
            open_qs.select_related("asset")
            .order_by("-priority_score")[:5]
            .values("id", "title", "cve", "asset__hostname", "severity", "priority_score")
        )

        avg_compliance = (
            round(sum(c["score"] for c in controls_with_gaps) / len(controls_with_gaps))
            if controls_with_gaps
            else 0
        )

        return Response(
            {
                "open_count": open_qs.count(),
                "closed_count": Vulnerability.objects.filter(
                    organization=organization, status=VulnerabilityStatus.CLOSED
                ).count(),
                "critical_open": by_severity.get("critical", 0),
                "overdue_count": overdue_count,
                "avg_compliance": avg_compliance,
                "exposure_by_asset_type": exposure,
                "control_gaps": controls_with_gaps[:4],
                "top_priority": list(top_priority),
            }
        )
