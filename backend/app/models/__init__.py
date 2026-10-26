"""Modelos SQLAlchemy — espejo del DDL del SRS §5."""
from app.models.aggregates import AggAgebScian, AggHexH3
from app.models.audit import AuditLog
from app.models.catalog import (
    CatGiroScian,
    CatScian,
    DataEdition,
    DataSource,
    ModelParam,
)
from app.models.company import AiUsageLog, CompanyProfile, KnowledgeFact
from app.models.denue import DenueEstablishment, DenueHistory
from app.models.investigations import InvestigationLead, UserInvestigation
from app.models.radar import (
    Lead,
    LeadRaw,
    LinkedinStat,
    Proposal,
    Provider,
    Run,
    WarmSignal,
)
from app.models.reports import Report, ReportShare
from app.models.territorio import (
    InegiAgeb,
    InegiManzana,
    MarcoEntidad,
    MarcoMunicipio,
)

__all__ = [
    "AggAgebScian",
    "AggHexH3",
    "AiUsageLog",
    "AuditLog",
    "CatGiroScian",
    "CatScian",
    "CompanyProfile",
    "DataEdition",
    "DataSource",
    "DenueEstablishment",
    "DenueHistory",
    "InegiAgeb",
    "InegiManzana",
    "InvestigationLead",
    "KnowledgeFact",
    "Lead",
    "LeadRaw",
    "LinkedinStat",
    "MarcoEntidad",
    "MarcoMunicipio",
    "ModelParam",
    "Proposal",
    "Provider",
    "Report",
    "ReportShare",
    "Run",
    "UserInvestigation",
    "WarmSignal",
]
