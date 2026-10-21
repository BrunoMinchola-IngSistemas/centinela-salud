"""Calcula la prioridad contextual (R1-R5) de los hallazgos que ya existían."""

from django.db import migrations


def recalcular(apps, schema_editor):
    from vulnerabilities.priority import calcular_prioridad

    Vulnerability = apps.get_model("vulnerabilities", "Vulnerability")
    for v in Vulnerability.objects.select_related("asset"):
        r = calcular_prioridad(
            cvss=v.cvss_score,
            severidad_declarada=v.severity,
            exposicion=v.asset.exposure,
            criticidad=v.asset.criticality,
            explotacion_activa=v.actively_exploited,
            datos_clinicos=v.asset.stores_phi,
        )
        v.contextual_priority = r.nivel_final
        v.priority_rules = r.as_dict()
        v.save(update_fields=["contextual_priority", "priority_rules"])


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0002_asset_exposure"),
        ("vulnerabilities", "0002_vulnerability_actively_exploited_and_more"),
    ]

    operations = [migrations.RunPython(recalcular, migrations.RunPython.noop)]
