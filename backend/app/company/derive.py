"""Derivación de la VerticalConfig operativa a partir del perfil de empresa.

Reglas:
- ``scian_sugeridos`` → ``scian_targets`` e intensidad de demanda 0.8 por
  código (0.5 neutral si la lista está vacía o es PENDIENTE).
- Pesos de scoring: si el ``vertical.id`` es climatización (o contiene
  "clima"/"koolkat") se usan los pesos Biokool existentes
  (``PESOS_BIOKOOL``); si no, se parte de ``PESOS_GENERICO`` y se ajusta
  para B2C (detectado por palabras en giro/tamaño: "personas", "años",
  "b2c"): baja el peso de estrato/tamaño y sube densidad de cuentas y
  atractivo de zona (idt). Los ajustes se documentan en ``line_rules``.
- ``productos`` → ``tam_defaults`` (ticket = promedio min/max; PENDIENTE
  → ticket 0 y se marca en ``line_rules``).
- ``cliente_ideal.dolores`` (separados por ``;``) → ``icp_keywords``
  (minúsculas, sin duplicados).
- ``modelo_comercial.canales_contacto`` → ``outreach_channels`` (split
  por coma). ``vocabulario`` → ``vocabulary`` tal cual.
"""
from __future__ import annotations

import math
import re

from app.analytics.scoring_unificado import PESOS_BIOKOOL, PESOS_GENERICO
from app.company.profile import es_faltante
from app.company.schemas import TamDefault, VerticalConfig

#: Palabras que delatan un giro B2C en la descripción del giro o del ICP.
_PISTAS_B2C = ("personas", "años", "b2c")

#: Pistas de climatización en el vertical.id.
_PISTAS_CLIMA = ("climatizacion", "clima", "koolkat")


def _limpiar_scian(valor: object) -> str:
    s = str(valor or "").strip().strip('"').strip("'")
    return "" if es_faltante(s) or s.lower() == "n/a" else s


def _es_climatizacion(vertical_id: str) -> bool:
    vid = (vertical_id or "").lower()
    return any(p in vid for p in _PISTAS_CLIMA)


def _es_b2c(perfil: dict) -> bool:
    vertical = perfil.get("vertical") or {}
    cliente = perfil.get("cliente_ideal") or {}
    texto = " ".join([
        str(vertical.get("giro_descripcion", "")),
        str(cliente.get("tamano", "")),
        str(cliente.get("descripcion", "")),
    ]).lower()
    return any(p in texto for p in _PISTAS_B2C)


def _numero(valor: object) -> float | None:
    """Parsea un número de un string; None si es PENDIENTE/no numérico."""
    if valor is None:
        return None
    s = str(valor).strip().replace(",", "").replace("$", "")
    if es_faltante(s):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _pesos_para_vertical(
    vertical_id: str, perfil: dict, line_rules: list[str]
) -> dict[str, float]:
    """Pesos del score unificado según el vertical del perfil."""
    if _es_climatizacion(vertical_id):
        line_rules.append(
            "scoring_weights = PESOS_BIOKOOL (perfil de climatización): "
            "se conservan los 8 componentes del §5 del blueprint."
        )
        return dict(PESOS_BIOKOOL)

    pesos = dict(PESOS_GENERICO)
    if _es_b2c(perfil):
        # B2C: el estrato/tamaño del establecimiento pesa menos; importan
        # más la densidad de cuentas y el atractivo de la zona (idt).
        pesos["tamano"] = pesos.get("tamano", 0.0) * 0.5
        pesos["densidad"] = pesos.get("densidad", 0.0) * 1.5
        pesos["idt"] = pesos.get("idt", 0.0) * 1.25
        total = sum(pesos.values())
        if total > 0:
            pesos = {k: v / total for k, v in pesos.items()}
        line_rules.append(
            "ajuste B2C: peso de tamano ×0.5 (el tamaño del local importa "
            "menos en consumo personal), densidad ×1.5 e idt ×1.25 "
            "(cuentas cercanas y zona atractiva mandan); renormalizado a 1.0."
        )
    else:
        line_rules.append(
            "scoring_weights = PESOS_GENERICO (solo componentes espaciales, "
            "renormalizados a 1.0)."
        )
    return pesos


def _tam_defaults(perfil: dict, line_rules: list[str]) -> list[TamDefault]:
    tam: list[TamDefault] = []
    for prod in perfil.get("productos") or []:
        if not isinstance(prod, dict):
            continue
        nombre = str(prod.get("nombre", "") or "").strip()
        if es_faltante(nombre):
            continue
        tmin = _numero(prod.get("ticket_min_mxn"))
        tmax = _numero(prod.get("ticket_max_mxn"))
        if tmin is None or tmax is None:
            ticket = 0.0
            line_rules.append(
                f"tam_defaults: producto «{nombre}» sin ticket válido "
                "(PENDIENTE) → ticket_mxn=0; completar en el perfil."
            )
        else:
            ticket = (tmin + tmax) / 2.0
            if ticket == math.floor(ticket):
                ticket = float(int(ticket))
        ciclo_raw = _numero(prod.get("ciclo_venta_dias"))
        ciclo = int(ciclo_raw) if ciclo_raw is not None else 0
        tam.append(TamDefault(producto=nombre, ticket_mxn=ticket, ciclo_dias=ciclo))
    return tam


def _icp_keywords(perfil: dict) -> list[str]:
    cliente = perfil.get("cliente_ideal") or {}
    dolores = str(cliente.get("dolores", "") or "")
    vistos: set[str] = set()
    keywords: list[str] = []
    for parte in dolores.split(";"):
        kw = re.sub(r"\s+", " ", parte).strip().lower()
        if not kw or es_faltante(kw) or kw in vistos:
            continue
        vistos.add(kw)
        keywords.append(kw)
    return keywords


def derive_config(perfil: dict) -> VerticalConfig:
    """Deriva la configuración operativa desde el dict del frontmatter."""
    empresa = perfil.get("empresa") or {}
    vertical = perfil.get("vertical") or {}
    modelo = perfil.get("modelo_comercial") or {}

    vertical_id = str(vertical.get("id", "") or "").strip()
    nombre_empresa = str(empresa.get("nombre", "") or "").strip()
    line_rules: list[str] = []

    # ── SCIAN targets e intensidad de demanda ──────────────────────────
    scian_targets = [
        s for s in (_limpiar_scian(x) for x in (perfil.get("scian_sugeridos") or [])) if s
    ]
    if scian_targets:
        demand_intensity = {s: 0.8 for s in scian_targets}
        line_rules.append(
            f"demand_intensity: {len(scian_targets)} SCIAN sugeridos con "
            "intensidad 0.8 (demanda prioritaria del perfil)."
        )
    else:
        demand_intensity = {}
        line_rules.append(
            "demand_intensity: sin SCIAN sugeridos (vacío o PENDIENTE) → "
            "intensidad neutral 0.5; completar scian_sugeridos en el perfil."
        )

    # ── Pesos de scoring ───────────────────────────────────────────────
    scoring_weights = _pesos_para_vertical(vertical_id, perfil, line_rules)

    # ── TAM defaults por producto ──────────────────────────────────────
    tam_defaults = _tam_defaults(perfil, line_rules)

    # ── Canales de contacto ────────────────────────────────────────────
    canales_raw = str(modelo.get("canales_contacto", "") or "")
    outreach_channels = [
        c.strip() for c in canales_raw.split(",") if c.strip() and not es_faltante(c.strip())
    ]

    # ── Vocabulario tal cual ───────────────────────────────────────────
    vocabulario = perfil.get("vocabulario") or {}
    vocabulary = (
        {str(k): str(v) for k, v in vocabulario.items()}
        if isinstance(vocabulario, dict)
        else {}
    )

    return VerticalConfig(
        vertical_id=vertical_id,
        nombre_empresa=nombre_empresa,
        scian_targets=scian_targets,
        demand_intensity=demand_intensity,
        scoring_weights=scoring_weights,
        tam_defaults=tam_defaults,
        line_rules=line_rules,
        outreach_channels=outreach_channels,
        vocabulary=vocabulary,
        icp_keywords=_icp_keywords(perfil),
    )
