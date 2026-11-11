from dataclasses import dataclass
from typing import Optional
from domain.enums.resource_type import ResourceType


@dataclass(frozen=True)
class Resource:
    type: ResourceType
    catalog: str
    schema: Optional[str] = None
    name: Optional[str] = None

    def __post_init__(self):
        if not self.catalog or not self.catalog.strip():
            raise ValueError("Resource catalog cannot be empty.")

        if self.type in (ResourceType.SCHEMA, ResourceType.TABLE, ResourceType.VIEW) and not self.schema:
            raise ValueError(f"Resource of type {self.type.value} requires a schema.")

        if self.type in (ResourceType.TABLE, ResourceType.VIEW) and not self.name:
            raise ValueError(f"Resource of type {self.type.value} requires a name.")

    @property
    def full_name(self) -> str:
        """Returns the 3-level or 2-level Unity Catalog full name."""
        if self.type == ResourceType.CATALOG:
            return self.catalog
        elif self.type == ResourceType.SCHEMA:
            return f"{self.catalog}.{self.schema}"
        else:
            return f"{self.catalog}.{self.schema}.{self.name}"
