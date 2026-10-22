"""Tests del módulo de configuración inicial + IA interna (sin red: httpx mockeado)."""
import math
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.ai import knowledge, operator, providers
from app.analytics.scoring_unificado import PESOS_BIOKOOL, linea_recomendada
from app.company import derive as derive_mod
from app.company import profile as profile_mod
from app.company import store as store_mod
from app.models.company import AiUsageLog, CompanyProfile, KnowledgeFact

DOCS = Path(__file__).resolve().parents[2] / "docs"
PLANTILLA = DOCS / "PERFIL-EMPRESA.md"
EJEMPLO = DOCS / "PERFIL-EMPRESA.ejemplo-gimnasios.md"


@pytest.fixture
def perfil_gyms():
    return profile_mod.parse_archivo(str(EJEMPLO))["profile"]


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    for tabla in (
        CompanyProfile.__table__,
        KnowledgeFact.__table__,
        AiUsageLog.__table__,
    ):
        tabla.create(bind=eng)
    sesion = sessionmaker(bind=eng)()
    yield sesion
    sesion.close()


# ------------------------------------------------- 1. plantilla: faltantes
def test_parsea_plantilla_detecta_faltantes_criticos():
    res = profile_mod.parse_archivo(str(PLANTILLA))
    assert res["profile"]["empresa"]["nombre"] == "[Tu respuesta aquí]"
    for campo in (
        "empresa.nombre",
        "vertical.id",
        "cliente_ideal.descripcion",
    ):
        assert campo in res["faltantes"]
    assert any(f.startswith("productos") for f in res["faltantes"])
    assert any(f.startswith("territorio") for f in res["faltantes"])


# ------------------------------------------------- 2. ejemplo: 0 faltantes
def test_parsea_ejemplo_gimnasios_sin_faltantes():
    res = profile_mod.parse_archivo(str(EJEMPLO))
    assert res["faltantes"] == []
    assert res["profile"]["empresa"]["nombre"] == "FitLife Gimnasios"


# ------------------------------------------------- 3. derive: pesos + scian
def test_derive_gimnasios_pesos_y_scian(perfil_gyms):
    cfg = derive_mod.derive_config(perfil_gyms)
    assert math.isclose(sum(cfg.scoring_weights.values()), 1.0)
    assert "713940" in cfg.scian_targets
    assert cfg.demand_intensity["713940"] == 0.8


# ------------------------------------------------- 4. derive: tam_defaults
def test_derive_tam_defaults_tickets_promedio(perfil_gyms):
    cfg = derive_mod.derive_config(perfil_gyms)
    assert len(cfg.tam_defaults) == 3
    tickets = {t.producto: t.ticket_mxn for t in cfg.tam_defaults}
    assert tickets["Membresía mensual"] == 799
    assert tickets["Plan anual"] == 7990
    assert tickets["Entrenamiento personal (paquete 12 sesiones)"] == 4800


# ------------------------------------------------- 5. derive: icp_keywords
def test_derive_icp_keywords_desde_dolores(perfil_gyms):
    cfg = derive_mod.derive_config(perfil_gyms)
    assert cfg.icp_keywords, "icp_keywords no debe estar vacío"
    assert all(k == k.lower() for k in cfg.icp_keywords)
    assert len(set(cfg.icp_keywords)) == len(cfg.icp_keywords)
    assert any("tiempo" in k for k in cfg.icp_keywords)


# ------------------------------------------------- 6. knowledge: save/get/upsert
def test_knowledge_save_get_upsert(db):
    assert knowledge.get_fact(db, "gimnasios", "k1") is None
    knowledge.save_fact(db, "gimnasios", "k1", {"a": 1}, source="manual")
    hecho = knowledge.get_fact(db, "gimnasios", "k1")
    assert hecho["value"] == {"a": 1}
    assert hecho["source"] == "manual"
    # upsert: actualiza valor y fuente, no duplica
    knowledge.save_fact(db, "gimnasios", "k1", {"a": 2}, source="system")
    hecho2 = knowledge.get_fact(db, "gimnasios", "k1")
    assert hecho2["value"] == {"a": 2}
    assert hecho2["source"] == "system"
    assert len(knowledge.list_facts(db, "gimnasios")) == 1


# ------------------------------------------------- 7. providers sin keys
def test_providers_sin_keys_no_configurados(monkeypatch):
    for p in providers.PROVIDERS:
        monkeypatch.delenv(f"{p.upper()}_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    assert all(not providers.configured(p) for p in providers.PROVIDERS)
    with pytest.raises(providers.AIProviderError, match="ningún proveedor"):
        providers.chat("sys", [{"role": "user", "content": "hola"}])


# ------------------------------------------------- 8. providers: fallback a groq
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_providers_fallback_openai_caido_usa_groq(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GROQ_API_KEY", "y")
    for p in ("anthropic", "gemini", "deepseek"):
        monkeypatch.delenv(f"{p.upper()}_API_KEY", raising=False)

    def fake_post(url, *, headers=None, payload):
        if "api.openai.com" in url:
            import httpx

            raise httpx.ConnectError("caído")
        assert "api.groq.com" in url
        return _FakeResp(
            {"choices": [{"message": {"content": "respuesta groq"}}]}
        )

    monkeypatch.setattr(providers, "_post", fake_post)
    nombre, texto = providers.chat_with_provider("sys", [{"role": "user", "content": "h"}])
    assert nombre == "groq"
    assert texto == "respuesta groq"


# ------------------------------------------------- 9. operador híbrido: IA → guarda fact
def test_operador_get_knowledge_sin_dato_llama_ia_y_guarda(db, monkeypatch):
    def fake_chat(system, messages, purpose=""):
        return "mock", "respuesta generada por IA"

    monkeypatch.setattr(
        operator.providers, "chat_with_provider", fake_chat
    )
    res = operator.run_tool(
        "get_knowledge",
        {"key": "ticket_promedio_zona", "pregunta": "¿cuál es el ticket?"},
        db, "gimnasios",
    )
    assert res["origen"] == "ia"
    hecho = knowledge.get_fact(db, "gimnasios", "ticket_promedio_zona")
    assert hecho is not None
    assert hecho["source"] == "ai:mock"
    assert float(hecho["confidence"]) == pytest.approx(0.7)


# ------------------------------------------------- 10. operador: dato local, sin IA
def test_operador_get_knowledge_con_dato_local_no_llama_ia(db, monkeypatch):
    knowledge.save_fact(db, "gimnasios", "k-local", {"v": 1}, source="manual")

    def fake_chat(system, messages, purpose=""):
        raise AssertionError("la IA no debió llamarse")

    monkeypatch.setattr(
        operator.providers, "chat_with_provider", fake_chat
    )
    res = operator.run_tool("get_knowledge", {"key": "k-local"}, db, "gimnasios")
    assert res["origen"] == "local"
    assert res["hecho"]["value"] == {"v": 1}


# ------------------------------------------------- 11. chat registra ai_usage_log
def test_chat_registra_uso_en_ai_usage_log(db, monkeypatch):
    def fake_chat(system, messages, purpose=""):
        return "mock", "respuesta final sin herramientas"

    monkeypatch.setattr(
        operator.providers, "chat_with_provider", fake_chat
    )
    res = operator.chat("hola", [], "gimnasios", db)
    assert res["reply"] == "respuesta final sin herramientas"
    assert res["tools_used"] == []
    filas = db.query(AiUsageLog).all()
    assert len(filas) == 1
    assert filas[0].provider == "mock"
    assert filas[0].purpose == "operator_chat"
    assert filas[0].ok is True


# ------------------------------------------------- 12. linea_recomendada: producto del perfil
def test_linea_recomendada_acepta_producto_del_perfil():
    productos = ["Membresía mensual", "Plan anual"]
    assert (
        linea_recomendada(8, giro="Gimnasio con Membresía mensual", productos_perfil=productos)
        == "Membresía mensual"
    )
    # Sin match con productos: comportamiento clásico intacto.
    assert linea_recomendada(8, giro="hotel", productos_perfil=productos) == "evaporativa"


def test_linea_recomendada_usa_perfil_activo(monkeypatch):
    monkeypatch.setattr(
        store_mod, "get_active_config",
        lambda db=None, vertical_id=None: {
            "tam_defaults": [
                {"producto": "Plan anual", "ticket_mxn": 7990, "ciclo_dias": 7}
            ],
        },
    )
    assert linea_recomendada(3, giro="quiero el Plan anual") == "Plan anual"


# ------------------------------------------------- extra: pesos climatización
def test_derive_climatizacion_usa_pesos_biokool():
    cfg = derive_mod.derive_config(
        {"empresa": {"nombre": "X"}, "vertical": {"id": "climatizacion"},
         "productos": [], "cliente_ideal": {}, "territorio": {}}
    )
    assert cfg.scoring_weights == PESOS_BIOKOOL


# ------------------------------------------------- 15. cloudflare: requiere token + account id
def test_cloudflare_configured_requiere_token_y_account(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    assert not providers.configured("cloudflare")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    assert not providers.configured("cloudflare")  # falta account id
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    assert providers.configured("cloudflare")


# ------------------------------------------------- 16. openrouter / nvidia / cloudflare: URL, headers y modelo
def _responder_openai_compatible(texto):
    def fake_post(url, *, headers=None, payload):
        assert payload["messages"][0]["role"] == "system"
        assert "Bearer " in (headers or {}).get("Authorization", "")
        return _FakeResp({"choices": [{"message": {"content": texto}}]})
    return fake_post


def test_openrouter_llamada_ok(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-x")
    vistos = {}

    def fake_post(url, *, headers=None, payload):
        vistos["url"] = url
        vistos["headers"] = headers
        vistos["payload"] = payload
        return _FakeResp({"choices": [{"message": {"content": "hola or"}}]})

    monkeypatch.setattr(providers, "_post", fake_post)
    assert providers._openrouter("sys", []) == "hola or"
    assert vistos["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert vistos["headers"]["HTTP-Referer"] == "https://geis.local"
    assert vistos["payload"]["model"] == "openai/gpt-4o-mini"


def test_nvidia_llamada_ok_y_modelo_por_env(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nv-x")
    monkeypatch.setenv("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
    vistos = {}

    def fake_post(url, *, headers=None, payload):
        vistos["url"] = url
        vistos["payload"] = payload
        return _FakeResp({"choices": [{"message": {"content": "hola nv"}}]})

    monkeypatch.setattr(providers, "_post", fake_post)
    assert providers._nvidia("sys", []) == "hola nv"
    assert vistos["url"] == "https://integrate.api.nvidia.com/v1/chat/completions"
    assert vistos["payload"]["model"] == "meta/llama-3.1-8b-instruct"


def test_cloudflare_llamada_ok_con_account_id(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "cf-tok")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc123")
    vistos = {}

    def fake_post(url, *, headers=None, payload):
        vistos["url"] = url
        vistos["headers"] = headers
        return _FakeResp({"choices": [{"message": {"content": "hola cf"}}]})

    monkeypatch.setattr(providers, "_post", fake_post)
    assert providers._cloudflare("sys", []) == "hola cf"
    assert vistos["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/acc123"
        "/ai/v1/chat/completions"
    )
    assert vistos["headers"]["Authorization"] == "Bearer cf-tok"


# ------------------------------------------------- 17. orden por defecto incluye los 3 nuevos al final
def test_provider_order_default_incluye_nuevos(monkeypatch):
    monkeypatch.delenv("AI_DEFAULT_ORDER", raising=False)
    orden = providers.provider_order()
    assert orden == [
        "openai", "anthropic", "gemini", "groq", "deepseek",
        "openrouter", "nvidia", "cloudflare",
    ]


# ------------------------------------------------- 18. fallback llega hasta openrouter si los 5 primeros caen
def test_fallback_hasta_openrouter(monkeypatch):
    for p in ("openai", "anthropic", "gemini", "groq", "deepseek", "openrouter"):
        monkeypatch.setenv(f"{p.upper()}_API_KEY", "x")
    for p in ("nvidia", "cloudflare"):
        monkeypatch.delenv(f"{p.upper()}_API_KEY", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

    def fake_post(url, *, headers=None, payload):
        import httpx

        if "openrouter.ai" in url:
            return _FakeResp({"choices": [{"message": {"content": "vía openrouter"}}]})
        raise httpx.ConnectError("caído")

    monkeypatch.setattr(providers, "_post", fake_post)
    nombre, texto = providers.chat_with_provider("sys", [])
    assert nombre == "openrouter"
    assert texto == "vía openrouter"
