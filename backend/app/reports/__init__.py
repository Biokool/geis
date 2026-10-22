"""Composición de reportes (JSON + PDF en fase 2)."""
from app.reports.builder import VEREDICTOS, build_location_report, decidir_veredicto

__all__ = ["VEREDICTOS", "build_location_report", "decidir_veredicto"]
