"""Router de propuestas comerciales asociadas a leads (fase 2 del Radar)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.radar import Lead, Proposal
from app.schemas.radar import ProposalIn, ProposalOut, ProposalUpdate

router = APIRouter(prefix="/proposals", tags=["proposals"])


def _to_out(p: Proposal) -> ProposalOut:
    return ProposalOut(
        proposal_id=p.proposal_id,
        lead_id=p.lead_id,
        titulo=p.titulo,
        linea=p.linea,
        monto=float(p.monto) if p.monto is not None else None,
        estado=p.estado,
        created_at=p.created_at,
    )


@router.post("", response_model=ProposalOut, status_code=201)
def crear_proposal(payload: ProposalIn, db: Session = Depends(get_db)):
    """Crea una propuesta para un lead existente."""
    if db.get(Lead, payload.lead_id) is None:
        raise HTTPException(
            status_code=404, detail=f"lead {payload.lead_id} no encontrado"
        )
    p = Proposal(
        lead_id=payload.lead_id,
        titulo=payload.titulo,
        linea=payload.linea,
        monto=payload.monto,
        estado="borrador",
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.get("", response_model=list[ProposalOut])
def listar_proposals(
    lead_id: int | None = Query(default=None, description="Filtra por lead"),
    db: Session = Depends(get_db),
):
    """Lista propuestas, opcionalmente filtradas por lead."""
    q = db.query(Proposal)
    if lead_id is not None:
        q = q.filter(Proposal.lead_id == lead_id)
    return [_to_out(p) for p in q.order_by(desc(Proposal.proposal_id)).all()]


@router.get("/{proposal_id}", response_model=ProposalOut)
def obtener_proposal(proposal_id: int, db: Session = Depends(get_db)):
    """Detalle de una propuesta."""
    p = db.get(Proposal, proposal_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"propuesta {proposal_id} no encontrada"
        )
    return _to_out(p)


@router.patch("/{proposal_id}", response_model=ProposalOut)
def actualizar_proposal(
    proposal_id: int, payload: ProposalUpdate, db: Session = Depends(get_db)
):
    """Actualiza título, línea, monto y/o estado de una propuesta."""
    p = db.get(Proposal, proposal_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"propuesta {proposal_id} no encontrada"
        )
    if payload.titulo is not None:
        p.titulo = payload.titulo
    if payload.linea is not None:
        p.linea = payload.linea
    if payload.monto is not None:
        p.monto = payload.monto
    if payload.estado is not None:
        p.estado = payload.estado
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.delete("/{proposal_id}", status_code=204)
def eliminar_proposal(proposal_id: int, db: Session = Depends(get_db)):
    """Elimina una propuesta (borrado duro)."""
    p = db.get(Proposal, proposal_id)
    if p is None:
        raise HTTPException(
            status_code=404, detail=f"propuesta {proposal_id} no encontrada"
        )
    db.delete(p)
    db.commit()
    return None
