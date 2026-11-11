from enum import Enum


class Privilege(str, Enum):
    USE_CATALOG = "USE_CATALOG"
    USE_SCHEMA = "USE_SCHEMA"
    SELECT = "SELECT"
    MODIFY = "MODIFY"
    READ_METADATA = "READ_METADATA"
    ALL_PRIVILEGES = "ALL_PRIVILEGES"
