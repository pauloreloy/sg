from enum import Enum


class ResourceType(str, Enum):
    CATALOG = "CATALOG"
    SCHEMA = "SCHEMA"
    TABLE = "TABLE"
    VIEW = "VIEW"
