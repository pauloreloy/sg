from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    type: str  # e.g., "GROUP", "USER", "SERVICE_PRINCIPAL"
    name: str

    def __post_init__(self):
        if not self.name or not self.name.strip():
            raise ValueError("Principal name cannot be empty.")
        if not self.type or not self.type.strip():
            raise ValueError("Principal type cannot be empty.")
