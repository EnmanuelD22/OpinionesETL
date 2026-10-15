"""Elementos comunes del dominio.

El dominio no define una base ORM. Los modelos de SQLAlchemy viven en
`infrastructure.persistence.models`, que es el adaptador de persistencia.
"""

#region Domain marker
class DomainEntity:
    """Marcador sin dependencias para entidades del dominio."""


Base = DomainEntity
#endregion
