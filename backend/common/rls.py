"""
Row-Level Security (RLS) de PostgreSQL — la razón principal por la que
el Benchmarking de la tesis (sección 3.4, criterio con 30 % de peso)
eligió PostgreSQL.

Idea en una frase
-----------------
Además del filtro por organización que ya hace Django
(OrganizationScopedMixin), el propio motor de base de datos se niega a
devolver o modificar filas de otra clínica. Si algún día una vista se
olvida del filtro, PostgreSQL igual no deja pasar los datos.

Cómo funciona
-------------
- Hay un rol de base de datos "dueño" (el usuario con el que Django se
  conecta, p. ej. `centinela`). Es dueño de las tablas, corre las
  migraciones y los comandos de mantenimiento (seed, catálogo ISO), y
  por ser dueño no está sujeto a RLS.
- Hay un rol sin login, `centinela_app`. En cada petición a la API, una
  vez que se sabe quién es el usuario, la conexión hace
  `SET ROLE centinela_app` y guarda la organización del usuario en la
  variable de sesión `app.current_org`. Desde ese momento, todas las
  consultas de esa petición pasan por las políticas RLS.
- Las políticas dicen: "solo filas cuya organización = app.current_org".
  Las tablas que no tienen organización directa (planes, solicitudes,
  M2M hallazgo-control, etc.) se filtran a través de su tabla "padre".
- El registro de auditoría (HU27/RNF-05) queda además sin permisos de
  UPDATE ni DELETE para `centinela_app`: ni siquiera un error en el
  código podría editarlo o borrarlo.

Todo esto se aplica solo, después de cada `python manage.py migrate`
(ver CommonConfig.ready). En SQLite no hace nada.
"""

from django.db import connection

APP_ROLE = "centinela_app"

# Tablas con columna organization_id propia.
TABLAS_CON_ORGANIZACION = [
    "accounts_user",
    "assets_asset",
    "assets_discoveryrun",
    "controls_control",
    "vulnerabilities_vulnerabilitysource",
    "vulnerabilities_vulnerability",
    "evidence_evidence",
    "governance_politicaautonomia",
    "governance_registroauditoria",
    "incidents_incidentereportado",
]

# Tablas sin organización directa: (tabla, condición que la liga a una
# tabla que sí tiene RLS). Como la subconsulta también pasa por RLS, si
# la fila "padre" no es visible, la hija tampoco.
TABLAS_HIJAS = [
    ("accounts_organization", "id = {org}"),
    ("remediation_remediationplan",
     "EXISTS (SELECT 1 FROM vulnerabilities_vulnerability v WHERE v.id = vulnerability_id)"),
    ("remediation_verificationattempt",
     "EXISTS (SELECT 1 FROM remediation_remediationplan p WHERE p.id = plan_id)"),
    ("governance_solicitudaprobacion",
     "EXISTS (SELECT 1 FROM remediation_remediationplan p WHERE p.id = plan_id)"),
    ("controls_controlmapping",
     "EXISTS (SELECT 1 FROM controls_control c WHERE c.id = control_id)"),
    ("controls_complianceassessment",
     "EXISTS (SELECT 1 FROM controls_control c WHERE c.id = control_id)"),
    ("vulnerabilities_vulnerability_controls",
     "EXISTS (SELECT 1 FROM vulnerabilities_vulnerability v WHERE v.id = vulnerability_id)"),
]

TABLAS_SOLO_INSERCION = ["governance_registroauditoria"]

# NULLIF para que, si no hay organización en sesión, el resultado sea
# NULL (no ve nada) en vez de un error de conversión.
ORG_ACTUAL = "NULLIF(current_setting('app.current_org', true), '')::uuid"


def es_postgres():
    return connection.vendor == "postgresql"


def sentencias_rls():
    """Lista de sentencias SQL idempotentes que dejan RLS configurado."""
    sql = [
        # El rol lo crea el script de instalación (docs/postgres_setup.sql);
        # aquí solo se verifica para dar un error claro si falta.
        f"""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
            RAISE EXCEPTION 'Falta el rol {APP_ROLE}. Corre primero docs/postgres_setup.sql como usuario postgres.';
          END IF;
        END $$;
        """,
        f"GRANT USAGE ON SCHEMA public TO {APP_ROLE};",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE};",
        f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};",
    ]

    for tabla in TABLAS_CON_ORGANIZACION:
        sql += _politica(tabla, f"organization_id = {ORG_ACTUAL}")
    for tabla, condicion in TABLAS_HIJAS:
        sql += _politica(tabla, condicion.format(org=ORG_ACTUAL))

    for tabla in TABLAS_SOLO_INSERCION:
        sql.append(f"REVOKE UPDATE, DELETE, TRUNCATE ON {tabla} FROM {APP_ROLE};")
    return sql


def _politica(tabla, condicion):
    nombre = "aislamiento_por_organizacion"
    return [
        f"ALTER TABLE {tabla} ENABLE ROW LEVEL SECURITY;",
        f"DROP POLICY IF EXISTS {nombre} ON {tabla};",
        f"CREATE POLICY {nombre} ON {tabla} TO {APP_ROLE} USING ({condicion}) WITH CHECK ({condicion});",
    ]


def aplicar_rls(using="default", verbose=False):
    from django.db import connections

    conn = connections[using]
    if conn.vendor != "postgresql":
        return False
    with conn.cursor() as cur:
        for sentencia in sentencias_rls():
            if verbose:
                print(sentencia.strip().splitlines()[0][:110])
            cur.execute(sentencia)
    return True


def activar_para_usuario(user):
    """
    Llamado por la autenticación (ver common/authentication.py) apenas se
    sabe quién hace la petición: cambia la conexión al rol restringido y
    fija la organización. Un usuario sin perfil queda con organización
    vacía y, por lo tanto, no ve ninguna fila.
    """
    if not es_postgres():
        return
    profile = getattr(user, "profile", None)  # se lee ANTES de restringir
    org_id = str(profile.organization_id) if profile else ""
    with connection.cursor() as cur:
        cur.execute(f"SET ROLE {APP_ROLE}")
        cur.execute("SELECT set_config('app.current_org', %s, false)", [org_id])


def desactivar():
    if not es_postgres() or connection.connection is None:
        return
    with connection.cursor() as cur:
        cur.execute("RESET ROLE")
        cur.execute("RESET app.current_org")
