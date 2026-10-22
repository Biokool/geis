"""Base declarativa de SQLAlchemy para todos los modelos."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos del DDL (§5 del SRS)."""
