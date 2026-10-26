"""Constructor del reporte de ubicación — SRS §6.5.

Compone el JSON del informe de decisión con las 13 secciones del SRS más
la §14 "plan de contacto sugerido" (fusión GEIS × Biokool, §7 del
blueprint), además del veredicto explícito (sección 0). Es una función
pura: recibe el contexto ya calculado (análisis, ISM, TAM, Huff, demanda)
y devuelve el payload listo para persistir.

Regla de honestidad: ningún valor se inventa. Si un dato no existe, la
sección declara "dato no disponible".
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.analytics.scoring_unificado import sugerir_plan_contacto

VEREDICTOS = ("AVANZAR", "NEGOCIAR", "EXPLORAR_OTRA_ZONA")


def _perfil_empresa_activo() -> dict | None:
    """Nombre y productos del perfil de empresa activo.

    Silencioso: devuelve None si no hay perfil o no hay base de datos,
    para no alterar el comportamiento cuando no hay configuración inicial.
    """
    try:
        from app.company.store import get_active_config

        cfg = get_active_config()
        if not cfg:
            return None
        return {
            "nombre": cfg.get("nombre_empresa"),
            "vertical_id": cfg.get("vertical_id"),
            "productos": [t["producto"] for t in cfg.get("tam_defaults", [])],
        }
    except Exception:
        return None


def decidir_veredicto(anillos: list[dict], ism_promedio: float | None = None) -> tuple[str, str, list[str]]:
    """Regla de veredicto a partir de las bandas ISM por anillo.

    Devuelve (veredicto, confianza, factores).
    """
    bandas = [a.get("ism_banda") for a in anillos]
    if not bandas:
        return ("NEGOCIAR", "Baja", ["Sin datos de competencia para evaluar"])

    if all(b == "oceano_azul" for b in bandas):
        return ("AVANZAR", "Alta", [
            "ISM en océano azul en todos los anillos: demanda muy superior a la oferta",
            "Territorio desatendido para el giro",
        ])
    if "oceano_azul" in bandas or bandas.count("equilibrado") >= len(bandas) / 2:
        return ("AVANZAR", "Media", [
            "ISM en océano azul o equilibrado en la mayoría de los anillos",
            "Entrada viable; validar diferenciación frente a competidores cercanos",
        ])
    if "equilibrado" in bandas:
        return ("NEGOCIAR", "Media", [
            "Mercado equilibrado: la entrada requiere diferenciación clara",
            "Negociar condiciones (renta, ubicación exacta) antes de avanzar",
        ])
    return ("EXPLORAR_OTRA_ZONA", "Alta", [
        "ISM en océano rojo/competido: territorio saturado para el giro",
        "Se recomienda explorar otra zona salvo estrategia disruptiva",
    ])


def build_location_report(ctx: dict) -> dict:
    """Compone el reporte de ubicación completo.

    ``ctx`` (contexto ya calculado) admite las claves:
    titulo, giro, scian, lat, lon, etiqueta_ubicacion, radios, fecha,
    anillos (lista de dicts con radio_m/competencia/ism/ism_banda/...),
    tam_mxn, tam_rango, huff (dict), demanda (dict), hogares (dict),
    competencia_lista (list), atractores (list), entorno (dict),
    isocronas (list), supuestos (list), ediciones (list), model_version,
    perfil_editorial (str | None), veredicto_forzado (opcional), temp_zona
    (float | None, para la §14), mes (int | None, para la §14).
    """
    ahora = datetime.now(timezone.utc).isoformat()
    anillos = ctx.get("anillos", [])
    veredicto, confianza, factores = decidir_veredicto(anillos)
    if ctx.get("veredicto_forzado") in VEREDICTOS:
        veredicto = ctx["veredicto_forzado"]

    # Perfil de empresa activo (si existe): nombre y productos para el
    # encabezado. Silencioso si no hay.
    perfil_empresa = _perfil_empresa_activo()

    demanda = ctx.get("demanda", {})
    hogares = ctx.get("hogares", {})
    huff = ctx.get("huff", {})
    tam_mxn = ctx.get("tam_mxn")
    tam_rango = ctx.get("tam_rango", (None, None))

    payload = {
        "tipo": "reporte_ubicacion",
        "version_reporte": "1.0.0",
        "generado_en": ahora,
        "cabecera": {
            "etiqueta": "REPORTE DE UBICACIÓN",
            "titulo": ctx.get("titulo", "Análisis de ubicación"),
            "empresa": (perfil_empresa or {}).get("nombre"),
            "giro": ctx.get("giro"),
            "scian": ctx.get("scian"),
            "ubicacion": ctx.get("etiqueta_ubicacion", f"{ctx.get('lat')}, {ctx.get('lon')}"),
            "lat": ctx.get("lat"),
            "lon": ctx.get("lon"),
            "fecha": ctx.get("fecha", ahora[:10]),
            "radios_m": ctx.get("radios", []),
        },
        # ── Perfil de empresa (si hay configuración inicial activa) ───
        "perfil_empresa": (
            {
                "nombre_empresa": perfil_empresa["nombre"],
                "vertical_id": perfil_empresa["vertical_id"],
                "productos": perfil_empresa["productos"],
            }
            if perfil_empresa
            else {"estado": "sin perfil activo"}
        ),
        # ── Sección 0: veredicto ──────────────────────────────────────
        "veredicto": {
            "decision": veredicto,
            "confianza": confianza,
            "factores": factores,
            "riesgos": ctx.get("riesgos", []),
        },
        # ── 1. Perfil del cliente (editorial del giro) ─────────────────
        # Sin editorial no se inventa texto: se declara "dato no disponible".
        "perfil_cliente": (
            {"editorial": ctx["perfil_editorial"]}
            if ctx.get("perfil_editorial")
            else {
                "editorial": None,
                "estado": "dato no disponible",
                "nota": "No hay texto editorial para este giro; se omite en "
                        "lugar de inventarlo.",
            }
        ),
        # ── 2. Clientes y resultado de la zona ─────────────────────────
        "clientes_zona": {
            "nota": "Es población de la zona, no una estimación de compradores.",
            "segmentos": demanda.get("segmentos", []),
            "poblacion_total": demanda.get("poblacion_total"),
            "poblacion_objetivo": demanda.get("poblacion_objetivo"),
        },
        # ── 3. Hogares y familias ──────────────────────────────────────
        "hogares_familias": {
            "viviendas_habitadas": hogares.get("viviendas_habitadas"),
            "promedio_ocupantes": hogares.get("promedio_ocupantes"),
            "pct_internet": hogares.get("pct_internet"),
            "pct_computadora": hogares.get("pct_computadora"),
            "pct_automovil": hogares.get("pct_automovil"),
        },
        # ── 4. Atractores de tráfico ───────────────────────────────────
        "atractores_trafico": {
            "nota": "No son clientes confirmados.",
            "items": ctx.get("atractores", []),
        },
        # ── 5. Competencia en la zona ──────────────────────────────────
        "competencia": {
            "por_anillo": [
                {
                    "radio_m": a.get("radio_m"),
                    "conteo": a.get("competencia"),
                    "ism": a.get("ism"),
                    "ism_banda": a.get("ism_banda"),
                }
                for a in anillos
            ],
            "lista": ctx.get("competencia_lista", []),
            # Diferencial del anillo exterior (p. ej. 1–2 km): conteo
            # ≤radio mayor menos conteo ≤radio menor (reporte Sabueso §6).
            "anillo_exterior": ctx.get("competencia_anillo_1_2_km"),
        },
        # ── 6. Mapas (descriptores de capas) ───────────────────────────
        "mapas": {
            "capas": [
                "ubicacion_y_negocios",
                "atractores_por_categoria",
                "vialidades",
                "corredor_vial",
                "flujo_peatonal",
                "isocrona_5_10_15",
            ],
            "centro": {"lat": ctx.get("lat"), "lon": ctx.get("lon")},
        },
        # ── 7. Entorno comercial ───────────────────────────────────────
        "entorno_comercial": ctx.get("entorno", {"total_negocios": None, "categorias": []}),
        # ── 8. Población y viviendas ───────────────────────────────────
        "poblacion_viviendas": {
            "advertencia": "Cifras censales observadas; no son proyecciones de clientes.",
            "detalle": demanda.get("detalle_edad_sexo", {}),
            "viviendas": hogares,
        },
        # ── 9. Movimiento y acceso ─────────────────────────────────────
        "movimiento_acceso": {
            "nse_etiqueta": ctx.get("nse_etiqueta"),
            "nse_nota": "Etiqueta simplificada, no letra AMAI oficial.",
            "vialidades": ctx.get("vialidades", []),
            "movilidad": ctx.get("movilidad", {}),
        },
        # ── 10. Área de alcance por tiempo ─────────────────────────────
        "area_alcance_tiempo": {
            "isocronas": ctx.get("isocronas", []),
            # Honestidad: sin polígonos reales el alcance son radios.
            "alcance_tipo": ctx.get("alcance_tipo", "radios"),
            "como_usarla": "Cada isócrona delimita la población alcanzable en ese tiempo de viaje.",
        },
        # ── 11. Modelos ────────────────────────────────────────────────
        "modelos": {
            "ism": {
                "formula": "ISM = D / (O + 1)",
                "por_anillo": [
                    {"radio_m": a.get("radio_m"), "D": a.get("demanda_pob_30_59"),
                     "O": a.get("competencia"), "ISM": a.get("ism"),
                     "banda": a.get("ism_banda")}
                    for a in anillos
                ],
            },
            "huff": {
                "formula": "P_ij = (A_j^α / D_ij^λ) / Σ_k (A_k^α / D_ik^λ)",
                "cuota_punto": huff.get("cuota_punto"),
                "rango_cuota": huff.get("rango_cuota"),
                "alpha": huff.get("alpha"),
                "lambda": huff.get("lambda"),
            },
            "tam": {
                "formula": "TAM = P_obj × G_pc × F_nse × F_pen",
                "tam_mxn_anual": tam_mxn,
                "rango_mxn": list(tam_rango),
                "advertencia": "El TAM es el tamaño del mercado, no las ventas del punto.",
                "supuestos": ctx.get("supuestos", []),
            },
        },
        # ── 12. Fuentes y datos ────────────────────────────────────────
        "fuentes_datos": {
            "ediciones": ctx.get("ediciones", []),
            # Lista nominal estilo Sabueso: fuente + rol, solo de las
            # fuentes efectivamente usadas en este reporte.
            "fuentes": ctx.get("fuentes", []),
            "fecha_calculo": ahora,
            "model_version": ctx.get("model_version", "1.0.0"),
        },
        # ── 13. Metodología y advertencias ─────────────────────────────
        "metodologia_advertencias": {
            "estimado_vs_observado": ctx.get("advertencias", []),
            "nota_general": "Las cifras marcadas como 'estimado' provienen de modelos; "
                            "las 'observadas' provienen de ediciones oficiales citadas.",
        },
        # ── 14. Plan de contacto sugerido (módulo Radar) ─────────────────
        "plan_contacto": sugerir_plan_contacto(
            ctx.get("giro"), ctx.get("temp_zona"), ctx.get("mes")
        ),
    }
    # ── Bloques de la Sección 1 (Sabueso) presentes solo si el contexto
    # los calculó: datos sectoriales del giro, bloque de delivery,
    # plantilla de punto de equilibrio y negocios ancla (§3.12).
    if ctx.get("sector") is not None:
        payload["datos_sector"] = ctx["sector"]
    if ctx.get("delivery") is not None:
        payload["delivery"] = ctx["delivery"]
    if ctx.get("break_even") is not None:
        payload["punto_equilibrio"] = ctx["break_even"]
    if ctx.get("anclas") is not None:
        payload["negocios_ancla"] = {
            "nota": "Un negocio ancla trae afluencia constante a su "
                    "entorno (ANC-01); su efecto multiplica la "
                    "atractividad en Huff: A' = A × (1 + Σ w_a).",
            "items": ctx["anclas"],
        }
    return payload
