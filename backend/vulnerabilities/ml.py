"""
HU08: clasificación de riesgo con aprendizaje supervisado (SVM).

Qué hace
--------
Entrena un SVM (scikit-learn, kernel RBF) que sugiere el nivel de
riesgo (baja / media / alta / crítica) de un hallazgo a partir de:
CVSS, EPSS, explotación activa (KEV), exposición del activo (Internet /
perimetral / interna), criticidad del activo y si guarda datos
clínicos. Reporta su exactitud (accuracy) y F1 macro sobre un 25 % de
datos apartados para prueba, y guarda cada entrenamiento en
EntrenamientoModelo para documentarlo en la tesis (OE3).

De dónde sale el historial
--------------------------
1. Los hallazgos ya clasificados de la organización (con activo). Si
   alguien corrigió la clasificación (HU08 esc. 2), manda la corrección.
2. Mientras SaludMedica no entregue su historial real, se completa con
   un HISTORIAL SINTÉTICO reproducible (semilla fija): casos generados
   al azar y etiquetados con las reglas R1-R5 más un 10 % de ruido que
   simula desacuerdos entre analistas. Se informa por separado
   (`muestras_reales` vs `muestras_sinteticas`) para no presentarlo
   como dato real; reemplazarlo es solo cargar el historial real.

El modelo vive en memoria (se reentrena en milisegundos con estos
volúmenes); no se guarda en disco ningún objeto serializado.
"""

import random

from django.utils import timezone

from .priority import calcular_prioridad

NIVELES = ["low", "medium", "high", "critical"]
EXPOSICIONES = ["internet", "perimetral", "interna"]
CRITICIDADES = ["low", "medium", "high", "critical"]
SEMILLA = 2026
N_SINTETICAS = 600
RUIDO = 0.10
ALGORITMO = "SVM (RBF, C=10, gamma=scale) · scikit-learn"

_CACHE = {}


def caracteristicas(cvss, epss, kev, exposicion, criticidad, phi):
    return [
        float(cvss or 0),
        float(epss or 0),
        1.0 if kev else 0.0,
        *[1.0 if exposicion == e else 0.0 for e in EXPOSICIONES],
        float(CRITICIDADES.index(criticidad) if criticidad in CRITICIDADES else 1),
        1.0 if phi else 0.0,
    ]


def caracteristicas_de(vuln):
    a = vuln.asset
    return caracteristicas(vuln.cvss_score, vuln.epss_score, vuln.actively_exploited, a.exposure, a.criticality, a.stores_phi)


def historial_sintetico(n=N_SINTETICAS, semilla=SEMILLA):
    rnd = random.Random(semilla)
    X, y = [], []
    for _ in range(n):
        cvss = round(rnd.uniform(1.0, 10.0), 1)
        epss = round(rnd.random() ** 2, 3)
        kev = rnd.random() < 0.12
        exposicion = rnd.choice(EXPOSICIONES)
        criticidad = rnd.choice(CRITICIDADES)
        phi = rnd.random() < 0.4
        etiqueta = calcular_prioridad(
            cvss=cvss, severidad_declarada=None, exposicion=exposicion, criticidad=criticidad,
            explotacion_activa=kev, datos_clinicos=phi,
        ).nivel_final
        etiqueta = "low" if etiqueta == "none" else etiqueta
        if rnd.random() < RUIDO:
            i = NIVELES.index(etiqueta) + rnd.choice([-1, 1])
            etiqueta = NIVELES[min(max(i, 0), len(NIVELES) - 1)]
        X.append(caracteristicas(cvss, epss, kev, exposicion, criticidad, phi))
        y.append(etiqueta)
    return X, y


def historial_real(organization):
    from .models import Vulnerability

    X, y = [], []
    for v in Vulnerability.objects.filter(organization=organization, asset__isnull=False).select_related("asset"):
        etiqueta = v.riesgo_corregido or v.contextual_priority
        if etiqueta == "none":
            etiqueta = "low"
        if etiqueta in NIVELES:
            X.append(caracteristicas_de(v))
            y.append(etiqueta)
    return X, y


def _clave_cache(organization):
    from .models import Vulnerability

    from django.db.models import Max

    # Se reentrena si cambia el historial: hallazgos nuevos o una
    # corrección humana. Guardar la sugerencia no cuenta (si no, cada
    # clasificación forzaría un reentrenamiento).
    qs = Vulnerability.objects.filter(organization=organization)
    agg = qs.aggregate(ultimo=Max("first_detected_at"), correccion=Max("riesgo_corregido_en"))
    return (str(organization.id), qs.count(), str(agg["ultimo"]), str(agg["correccion"]))


def entrenar(organization, forzar=False):
    """Entrena (o reutiliza de la caché) y devuelve (modelo, EntrenamientoModelo)."""
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.svm import SVC

    from .models import EntrenamientoModelo

    clave = _clave_cache(organization)
    if not forzar and clave in _CACHE:
        return _CACHE[clave]

    Xr, yr = historial_real(organization)
    Xs, ys = historial_sintetico()
    X, y = Xr + Xs, yr + ys
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, random_state=SEMILLA, stratify=y)
    modelo = make_pipeline(StandardScaler(), SVC(kernel="rbf", C=10, gamma="scale", random_state=SEMILLA))
    modelo.fit(X_tr, y_tr)
    pred = modelo.predict(X_te)
    registro = EntrenamientoModelo.objects.create(
        organization=organization,
        algoritmo=ALGORITMO,
        muestras_reales=len(Xr),
        muestras_sinteticas=len(Xs),
        muestras_prueba=len(X_te),
        accuracy=round(float(accuracy_score(y_te, pred)), 4),
        f1_macro=round(float(f1_score(y_te, pred, average="macro")), 4),
        parametros={"kernel": "rbf", "C": 10, "gamma": "scale", "test_size": 0.25, "semilla": SEMILLA, "ruido": RUIDO},
    )
    _CACHE.clear()
    _CACHE[clave] = (modelo, registro)
    return modelo, registro


def sugerir(vuln):
    """Devuelve (nivel_sugerido, EntrenamientoModelo) o (None, None) si el hallazgo no tiene activo."""
    if vuln.asset_id is None:
        return None, None
    modelo, registro = entrenar(vuln.organization)
    return str(modelo.predict([caracteristicas_de(vuln)])[0]), registro


def clasificar(vuln):
    nivel, registro = sugerir(vuln)
    if nivel:
        vuln.riesgo_sugerido = nivel
        vuln.riesgo_sugerido_en = timezone.now()
        vuln.save(update_fields=["riesgo_sugerido", "riesgo_sugerido_en"])
    return nivel, registro
