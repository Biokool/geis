"""Capa de conocimiento: lectura/escritura de ``knowledge_facts``.

Los hechos se direccionan por ``vertical_id``; ``save_fact`` hace upsert
sobre UNIQUE(vertical_id, fact_key). ``source`` típicos: 'manual',
'system', 'ai:{provider}'.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.company import KnowledgeFact


def get_fact(db: Session, vertical_id: str, key: str) -> dict | None:
    """Devuelve el hecho como dict, o None si no existe."""
    fila = (
        db.query(KnowledgeFact)
        .filter(
            KnowledgeFact.vertical_id == vertical_id,
            KnowledgeFact.fact_key == key,
        )
        .first()
    )
    if fila is None:
        return None
    return {
        "vertical_id": fila.vertical_id,
        "key": fila.fact_key,
        "value": fila.fact_value,
        "source": fila.source,
        "confidence": float(fila.confidence) if fila.confidence is not None else None,
    }


def save_fact(
    db: Session,
    vertical_id: str,
    key: str,
    value: dict,
    source: str = "manual",
    confidence: float = 1.0,
) -> dict:
    """Guarda o actualiza un hecho (upsert). Devuelve el hecho guardado."""
    fila = (
        db.query(KnowledgeFact)
        .filter(
            KnowledgeFact.vertical_id == vertical_id,
            KnowledgeFact.fact_key == key,
        )
        .first()
    )
    ahora = datetime.now(timezone.utc)
    if fila is None:
        fila = KnowledgeFact(
            vertical_id=vertical_id,
            fact_key=key,
            fact_value=value,
            source=source,
            confidence=confidence,
            created_at=ahora,
            updated_at=ahora,
        )
        db.add(fila)
    else:
        fila.fact_value = value
        fila.source = source
        fila.confidence = confidence
        fila.updated_at = ahora
    db.commit()
    return {
        "vertical_id": fila.vertical_id,
        "key": fila.fact_key,
        "value": fila.fact_value,
        "source": fila.source,
        "confidence": float(fila.confidence) if fila.confidence is not None else None,
    }


def list_facts(db: Session, vertical_id: str) -> list[dict]:
    """Lista todos los hechos de un vertical."""
    filas = (
        db.query(KnowledgeFact)
        .filter(KnowledgeFact.vertical_id == vertical_id)
        .order_by(KnowledgeFact.fact_key)
        .all()
    )
    return [
        {
            "key": f.fact_key,
            "value": f.fact_value,
            "source": f.source,
            "confidence": float(f.confidence) if f.confidence is not None else None,
        }
        for f in filas
    ]
