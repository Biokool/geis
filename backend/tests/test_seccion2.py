"""Tests de la Sección 2 — Radar: geografía derivada y reglas R1–R17.

Sin red ni Postgres real: sesiones fake en memoria (patrón de
``test_correccion_profunda.py``) que interpretan el SQL por marcadores y
aplican la semántica documentada (COALESCE en el UPDATE geo, filtros
parametrizados en count/listado, DISTINCT en la cascada).

Cubren:
- ``POST /leads/enrich-geo`` (con geometría / respaldo de texto sobre
  dirección formateada cuando AGEB/DENUE/Marco no cubren / idempotencia),
- ``GET /catalogs/geo-filters`` (cascada entidad→municipio→colonia),
- filtros geo en ``GET /leads/count`` y ``GET /leads/curados``,
- correcciones R5 (regex solar), R10 (gating: 04 requiere 02, motivo
  diferenciado) y R11 (coherencia de providers al definir el par).
"""
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.analytics.scoring_unificado import linea_recomendada
from app.api.v1 import catalogs as catalogs_mod
from app.api.v1 import leads as leads_mod
from app.api.v1 import pipelines as pipelines_mod
from app.api.v1 import providers as providers_mod
from app.db.session import get_db
from app.models.radar import Provider


def _cliente(sesion_fake, *modulos) -> TestClient:
    app = FastAPI()
    for mod in modulos:
        app.include_router(mod.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = lambda: sesion_fake
    return TestClient(app)


# ------------------------------------------------------------ fakes geo
class _Resultado:
    """Resultado fake con all()/first()/scalar() según el contenido."""

    def __init__(self, filas=(), escalar=None):
        self._filas = list(filas)
        self._escalar = escalar
        self.rowcount = 1

    def all(self):
        return list(self._filas)

    def first(self):
        return self._filas[0] if self._filas else None

    def scalar(self):
        return self._escalar


_CAMPOS_GEO = ("entidad", "municipio", "colonia", "cp", "scian")


def _lead_dict(lead_id, **extras):
    datos = {
        "lead_id": lead_id, "source": "gmaps", "nombre": f"Lead {lead_id}",
        "giro": "bodegas", "direccion": "", "telefono": None, "web": None,
        "rating": None, "score": 10, "score_components": {},
        "linea_recomendada": "evaporativa", "etapa": "nuevo",
        "temp_zona": None, "notas": "", "enriquecido_apollo": False,
        "crm_synced_at": None, "created_at": None, "updated_at": None,
        "lat": None, "lon": None,
        "entidad": None, "municipio": None, "colonia": None, "cp": None,
        "scian": None,
    }
    datos.update(extras)
    return datos


def _fila_curado(l: dict) -> tuple:
    """Tupla en el orden exacto de ``leads._COLUMNAS_CURADO``."""
    return (
        l["lead_id"], l["source"], l["nombre"], l["giro"], l["direccion"],
        l["telefono"], l["web"], l["rating"], l["score"],
        l["score_components"], l["linea_recomendada"], l["etapa"],
        l["temp_zona"], l["notas"], l["enriquecido_apollo"],
        l["crm_synced_at"], l["created_at"], l["updated_at"],
        l["lat"], l["lon"],
        l["entidad"], l["municipio"], l["colonia"], l["cp"], l["scian"],
    )


class SesionGeoFake:
    """Sesión en memoria para enrich-geo, count y listado de curados.

    ``agebs``: lead_id → (cve_ent, cve_mun, nom_ent, nom_mun).
    ``denue_cercano``: lead_id → (entidad, municipio, colonia, cp, scian_code).
    El UPDATE aplica semántica COALESCE: nunca pisa un campo ya lleno.
    """

    def __init__(self, leads, agebs=None, denue_cercano=None):
        self.leads = {l["lead_id"]: l for l in leads}
        self.agebs = agebs or {}
        self.denue_cercano = denue_cercano or {}
        self.commits = 0

    def commit(self):
        self.commits += 1

    # -- helpers internos
    def _aplicar_filtros(self, params):
        filas = list(self.leads.values())
        for clave, valor in (params or {}).items():
            if valor is None:
                continue
            if clave == "etapa":
                filas = [l for l in filas if l["etapa"] == valor]
            elif clave == "linea":
                filas = [l for l in filas if l["linea_recomendada"] == valor]
            elif clave == "source":
                filas = [l for l in filas if l["source"] == valor]
            elif clave.startswith("geo_"):
                campo = clave[4:]
                filas = [l for l in filas if l[campo] == valor]
            elif clave == "last":
                filas = [l for l in filas if l["lead_id"] > valor]
        return sorted(filas, key=lambda l: l["lead_id"])

    def _incompletos(self):
        return [
            l for l in self.leads.values()
            if any(l[c] is None for c in _CAMPOS_GEO)
        ]

    def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        if "inegi_agebs" in sql:
            fila = self.agebs.get(params.get("lid"))
            return _Resultado([fila] if fila else [])
        if "ST_DWithin" in sql:
            fila = self.denue_cercano.get(params.get("lid"))
            return _Resultado([fila] if fila else [])
        if sql.startswith("UPDATE prod.leads"):
            lead = self.leads[params["lid"]]
            for campo in _CAMPOS_GEO:
                if lead[campo] is None and params.get(campo) is not None:
                    lead[campo] = params[campo]
            return _Resultado()
        if "SELECT lead_id, direccion" in sql:  # candidatos enrich-geo
            filas = self._incompletos()[: params.get("limite", 500)]
            return _Resultado([
                (l["lead_id"], l["direccion"], l["lat"], l["lon"],
                 l["entidad"], l["municipio"], l["colonia"], l["cp"],
                 l["scian"])
                for l in filas
            ])
        if "COUNT(*)" in sql and "entidad IS NULL" in sql:  # pendientes
            return _Resultado(escalar=len(self._incompletos()))
        if "COUNT(*)" in sql:  # GET /leads/count
            return _Resultado(escalar=len(self._aplicar_filtros(params)))
        if "FROM prod.leads" in sql:  # GET /leads/curados
            filas = self._aplicar_filtros(params)
            limite = params.get("limit")
            if limite:
                filas = filas[:limite]
            return _Resultado([_fila_curado(l) for l in filas])
        raise AssertionError(f"SQL no esperado en la fake: {sql[:120]}")


def _sesion_enrich() -> SesionGeoFake:
    leads = [
        _lead_dict(1, lat=19.6, lon=-99.05,
                   direccion="Nave 4, Parque Industrial Xalostoc"),
        _lead_dict(2, direccion="Av. Juárez 100, Centro, 06000 Ciudad de México"),
        _lead_dict(3, direccion="Carretera libre km 12, sin número"),
    ]
    agebs = {1: ("15", "033", None, "Ecatepec de Morelos")}
    denue = {1: ("México", "Ecatepec de Morelos", "Industrial Xalostoc",
                 "55348", "332710")}
    return SesionGeoFake(leads, agebs=agebs, denue_cercano=denue)


# ------------------------------------------------------------ enrich-geo
def test_enrich_geo_con_geometria_llena_los_cinco_campos():
    sesion = _sesion_enrich()
    cliente = _cliente(sesion, leads_mod)
    res = cliente.post("/api/v1/leads/enrich-geo", json={})
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["actualizados"] == 2
    assert cuerpo["detalle"] == {"con_geometria": 1, "solo_cp": 1, "sin_datos": 1}
    # Lead 1 (con geometría): AGEB da entidad (vía catálogo por cve_ent,
    # porque nom_ent llegó None) y municipio; DENUE da colonia/cp/scian.
    lead1 = sesion.leads[1]
    assert lead1["entidad"] == "México"
    assert lead1["municipio"] == "Ecatepec de Morelos"
    assert lead1["colonia"] == "Industrial Xalostoc"
    assert lead1["cp"] == "55348"
    assert lead1["scian"] == "332710"
    # Quedan pendientes el lead 2 (solo CP) y el 3 (sin datos).
    assert cuerpo["pendientes"] == 2


def test_enrich_geo_sin_geometria_parsea_direccion():
    """"Av. Juárez 100, Centro, 06000 Ciudad de México" → CP + entidad +
    colonia del texto (sin geometría no hay AGEB/DENUE)."""
    sesion = _sesion_enrich()
    cliente = _cliente(sesion, leads_mod)
    res = cliente.post("/api/v1/leads/enrich-geo", json={"limite": 500})
    assert res.status_code == 200
    lead2 = sesion.leads[2]
    assert lead2["cp"] == "06000"
    # "Ciudad de México" es exactamente el nombre de la entidad, no un
    # municipio: la parser lo clasifica como entidad.
    assert lead2["entidad"] == "Ciudad de México"
    assert lead2["municipio"] is None
    # "Centro" es el segmento previo al CP y no es la calle.
    assert lead2["colonia"] == "Centro"
    assert lead2["scian"] is None
    lead3 = sesion.leads[3]
    assert all(lead3[c] is None for c in _CAMPOS_GEO)


def test_enrich_geo_texto_respalda_marco_parcial():
    """Con AGEB y DENUE sin cobertura, la dirección formateada de Google
    llena entidad/municipio/colonia/cp (formato "Calle, Colonia,
    76000 Municipio, Abrev." — los marcos INEGI aún son parciales)."""
    leads = [
        _lead_dict(
            7, lat=20.59, lon=-100.39,
            direccion="Calle Ignacio Zaragoza 150, Centro, "
                      "76000 Santiago de Querétaro, Qro.",
        ),
        _lead_dict(
            8, lat=20.58, lon=-100.40,
            direccion="Fernando de Tapia SN, Centro, "
                      "76000 Santiago de Querétaro, Qro., México",
        ),
        # Sin colonia en la dirección: la calle es el segmento previo al
        # CP y NO debe tomarse como colonia.
        _lead_dict(
            9, lat=20.60, lon=-100.41,
            direccion="José María Arteaga 12, 76000 Santiago de Querétaro, Qro.",
        ),
    ]
    sesion = SesionGeoFake(leads)
    cliente = _cliente(sesion, leads_mod)
    res = cliente.post("/api/v1/leads/enrich-geo", json={})
    assert res.status_code == 200
    for lid in (7, 8):
        lead = sesion.leads[lid]
        assert lead["entidad"] == "Querétaro"
        assert lead["municipio"] == "Santiago de Querétaro"
        assert lead["colonia"] == "Centro"
        assert lead["cp"] == "76000"
    lead9 = sesion.leads[9]
    assert lead9["entidad"] == "Querétaro"
    assert lead9["municipio"] == "Santiago de Querétaro"
    assert lead9["cp"] == "76000"
    assert lead9["colonia"] is None  # la calle nunca es colonia
    assert res.json()["detalle"] == {
        "con_geometria": 3, "solo_cp": 0, "sin_datos": 0,
    }


def test_enrich_geo_es_idempotente_y_no_pisa_campos():
    sesion = _sesion_enrich()
    # Colonia ya capturada a mano: la corrida no debe pisarla.
    sesion.leads[1]["colonia"] = "Col. Previa Manual"
    cliente = _cliente(sesion, leads_mod)
    res1 = cliente.post("/api/v1/leads/enrich-geo", json={})
    assert res1.status_code == 200
    assert sesion.leads[1]["colonia"] == "Col. Previa Manual"
    assert sesion.leads[1]["entidad"] == "México"

    foto = {lid: dict(l) for lid, l in sesion.leads.items()}
    res2 = cliente.post("/api/v1/leads/enrich-geo", json={})
    assert res2.status_code == 200
    assert res2.json()["actualizados"] == 0
    assert sesion.leads == foto


def test_enrich_geo_sin_body_usa_limite_default():
    sesion = _sesion_enrich()
    cliente = _cliente(sesion, leads_mod)
    res = cliente.post("/api/v1/leads/enrich-geo")
    assert res.status_code == 200
    assert res.json()["actualizados"] == 2


# ------------------------------------------------------------ geo-filters
class SesionCatalogosFake:
    """Fake para la cascada: interpreta SELECT DISTINCT por tabla/columna."""

    def __init__(self, leads, denue):
        self._fuentes = {
            "prod.leads": leads,
            "prod.denue_establishments": denue,
        }

    def execute(self, stmt, params=None):
        sql = str(stmt)
        params = params or {}
        tabla = next(t for t in self._fuentes if t in sql)
        filas = self._fuentes[tabla]
        objetivo = sql.split("SELECT DISTINCT")[1].split("FROM")[0].strip()
        campo = "scian" if objetivo in ("scian", "scian_code") else objetivo
        for clave, valor in params.items():
            previo = clave[2:]  # f_entidad → entidad
            filas = [f for f in filas if f.get(previo) == valor]
        valores = {f[campo] for f in filas if f.get(campo)}
        return _Resultado([(v,) for v in valores])


def _sesion_catalogos() -> SesionCatalogosFake:
    leads = [
        {"entidad": "México", "municipio": "Ecatepec de Morelos",
         "colonia": "Industrial Xalostoc", "cp": "55348", "scian": "332710"},
        {"entidad": "Jalisco", "municipio": "Guadalajara",
         "colonia": "Centro", "cp": "44100", "scian": "722515"},
    ]
    denue = [
        {"entidad": "México", "municipio": "Toluca", "colonia": "Centro",
         "cp": "50000", "scian": "468211"},
        {"entidad": "México", "municipio": "Ecatepec de Morelos",
         "colonia": "Jardines", "cp": "55040", "scian": "332710"},
    ]
    return SesionCatalogosFake(leads, denue)


def test_geo_filters_sin_params_union_de_fuentes():
    cliente = _cliente(_sesion_catalogos(), catalogs_mod)
    res = cliente.get("/api/v1/catalogs/geo-filters")
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["entidades"] == ["Jalisco", "México"]
    assert set(cuerpo["municipios"]) == {
        "Ecatepec de Morelos", "Guadalajara", "Toluca"}
    # SCIAN presentes de ambas fuentes (leads.scian y denue.scian_code).
    assert set(cuerpo["scians"]) == {"332710", "468211", "722515"}
    assert set(cuerpo["cps"]) == {"44100", "50000", "55040", "55348"}


def test_geo_filters_cascada_reduce_conjuntos():
    cliente = _cliente(_sesion_catalogos(), catalogs_mod)
    res = cliente.get(
        "/api/v1/catalogs/geo-filters", params={"entidad": "México"})
    assert res.status_code == 200
    cuerpo = res.json()
    assert cuerpo["municipios"] == ["Ecatepec de Morelos", "Toluca"]
    assert "Guadalajara" not in cuerpo["colonias"]

    res2 = cliente.get(
        "/api/v1/catalogs/geo-filters",
        params={"entidad": "México", "municipio": "Ecatepec de Morelos"},
    )
    cuerpo2 = res2.json()
    assert cuerpo2["colonias"] == ["Industrial Xalostoc", "Jardines"]
    assert cuerpo2["cps"] == ["55040", "55348"]
    assert cuerpo2["scians"] == ["332710"]


# ------------------------------------------------------------ filtros geo
def _sesion_filtros() -> SesionGeoFake:
    return SesionGeoFake([
        _lead_dict(1, entidad="México", municipio="Toluca"),
        _lead_dict(2, entidad="México", municipio="Ecatepec de Morelos"),
        _lead_dict(3, entidad="Jalisco", municipio="Guadalajara"),
    ])


def test_count_con_filtro_entidad_reduce():
    cliente = _cliente(_sesion_filtros(), leads_mod)
    sin = cliente.get("/api/v1/leads/count")
    con = cliente.get("/api/v1/leads/count", params={"entidad": "México"})
    assert sin.json() == {"total": 3}
    assert con.json() == {"total": 2}


def test_listado_curados_con_filtro_entidad_reduce():
    cliente = _cliente(_sesion_filtros(), leads_mod)
    sin = cliente.get("/api/v1/leads/curados")
    con = cliente.get(
        "/api/v1/leads/curados", params={"entidad": "Jalisco"})
    assert len(sin.json()["items"]) == 3
    items = con.json()["items"]
    assert len(items) == 1
    assert items[0]["entidad"] == "Jalisco"
    assert items[0]["municipio"] == "Guadalajara"


def test_listado_curados_expone_campos_geo():
    cliente = _cliente(_sesion_filtros(), leads_mod)
    res = cliente.get("/api/v1/leads/curados")
    item = res.json()["items"][0]
    for campo in _CAMPOS_GEO:
        assert campo in item


# ------------------------------------------------------------ R5 (línea)
def test_r5_tienda_en_invierno_es_solar():
    # La regex documentada R5 incluye 'tienda' (el backend no la traía).
    assert linea_recomendada(1, "Tienda de conveniencia") == "solar"
    assert linea_recomendada(11, "Plaza Andares") == "solar"


def test_r5_febrero_gana_koolkat_aunque_el_giro_sea_solar():
    # Sutileza documentada de R5: febrero cae en ambas ramas; gana koolkat.
    assert linea_recomendada(2, "Tienda de conveniencia") == "koolkat"


# ------------------------------------------------------------ R10 (gating)
class SesionRunsFake:
    """Sesión mínima para correr_stage: add/commit/refresh en memoria."""

    def __init__(self):
        self.agregados = []
        self.commits = 0

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        obj.run_id = 7


def _cliente_pipelines(monkeypatch, ultimos: dict) -> TestClient:
    """ultimos: pipeline → SimpleNamespace(estado, detalle) o None."""

    def fake_ultimo_run(db, pipeline):
        return ultimos.get(pipeline)

    monkeypatch.setattr(pipelines_mod, "_ultimo_run", fake_ultimo_run)
    return _cliente(SesionRunsFake(), pipelines_mod)


def test_r10_radar04_requiere_radar02_no_radar03(monkeypatch):
    cliente = _cliente_pipelines(monkeypatch, {
        "radar-02": SimpleNamespace(
            estado="ok", detalle=None, started_at=None),
        "radar-03": None,  # nunca corrió: con la regla vieja bloquearía
    })
    res = cliente.post("/api/v1/pipelines/run/radar-04", json={})
    assert res.status_code == 201
    assert res.json()["pipeline"] == "radar-04"


def test_r10_bloqueo_409_con_motivo_diferenciado_error(monkeypatch):
    cliente = _cliente_pipelines(monkeypatch, {
        "radar-02": SimpleNamespace(
            estado="error", detalle={"error": "boom en n8n"},
            started_at=None),
    })
    res = cliente.post("/api/v1/pipelines/run/radar-04", json={})
    assert res.status_code == 409
    detalle = res.json()["detail"]
    assert detalle["predecesor"] == "radar-02"
    assert detalle["ultimo_estado"] == "error"
    assert "boom en n8n" in detalle["motivo"]


def test_r10_bloqueo_409_con_motivo_nunca(monkeypatch):
    cliente = _cliente_pipelines(monkeypatch, {"radar-01": None})
    res = cliente.post("/api/v1/pipelines/run/radar-02", json={})
    assert res.status_code == 409
    assert "nunca se ha ejecutado" in res.json()["detail"]["motivo"]


# ------------------------------------------------------------ R11 (providers)
class SesionProvidersFake:
    def __init__(self):
        self.providers: dict[str, Provider] = {}
        self.commits = 0

    def get(self, _modelo, name):
        return self.providers.get(name)

    def add(self, obj):
        self.providers[obj.name] = obj

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        # Emula los defaults de BD que Postgres aplica al insertar.
        if obj.enabled is None:
            obj.enabled = True
        if obj.config is None:
            obj.config = {}


def test_r11_par_incoherente_rechazado():
    cliente = _cliente(SesionProvidersFake(), providers_mod)
    res = cliente.put(
        "/api/v1/providers/scraper",
        json={"mode": "cloud", "provider": "local"},
    )
    assert res.status_code == 422
    res2 = cliente.put(
        "/api/v1/providers/scraper",
        json={"mode": "local", "provider": "apify"},
    )
    assert res2.status_code == 422


def test_r11_par_coherente_y_cambio_solo_modo_ok():
    sesion = SesionProvidersFake()
    cliente = _cliente(sesion, providers_mod)
    res = cliente.put(
        "/api/v1/providers/scraper",
        json={"mode": "cloud", "provider": "apify"},
    )
    assert res.status_code == 200
    assert res.json()["mode"] == "cloud"
    assert res.json()["provider"] == "apify"
    # El toggle del frontend envía solo {mode}: no se bloquea.
    res2 = cliente.put("/api/v1/providers/scraper", json={"mode": "local"})
    assert res2.status_code == 200
    assert res2.json()["mode"] == "local"
