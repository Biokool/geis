"""Router de señales cálidas: el SDR registra señales manuales que el
pipeline radar-03 procesa (upsert con +25 score legacy, normalizado)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.radar import WarmSignal
from app.schemas.radar import SignalIn, SignalOut

router = APIRouter(prefix="/signals", tags=["signals"])


@router.post("", response_model=SignalOut, status_code=201)
def registrar_signal(payload: SignalIn, db: Session = Depends(get_db)):
    """Registra una señal (por defecto fuente='manual') en warm_signals."""
    s = WarmSignal(
        fuente=payload.fuente,
        titulo=payload.titulo,
        detalle=payload.detalle,
        empresa_ref=payload.empresa_ref,
        procesada=False,
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return SignalOut(
        signal_id=s.signal_id,
        fuente=s.fuente,
        titulo=s.titulo,
        detalle=s.detalle,
        empresa_ref=s.empresa_ref,
        procesada=s.procesada,
        created_at=s.created_at,
    )
