class DomainException(Exception):
    """Base exception for Databricks service domain."""

    def __init__(self, message: str, code: str = "DOMAIN_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class PrincipalNotFoundException(DomainException):
    def __init__(self, principal_name: str):
        super().__init__(
            f"Principal '{principal_name}' was not found in the workspace.",
            code="PRINCIPAL_NOT_FOUND",
        )


class ResourceNotFoundException(DomainException):
    def __init__(self, resource_name: str):
        super().__init__(
            f"Resource '{resource_name}' was not found in Unity Catalog.",
            code="RESOURCE_NOT_FOUND",
        )


class InvalidPrivilegeException(DomainException):
    def __init__(self, privilege: str, resource_type: str):
        super().__init__(
            f"Privilege '{privilege}' is not valid for resource type '{resource_type}'.",
            code="INVALID_PRIVILEGE",
        )


class UnityCatalogPermissionDeniedException(DomainException):
    def __init__(self, message: str = "The service principal does not have sufficient privileges in Unity Catalog."):
        super().__init__(message, code="UNITY_CATALOG_PERMISSION_DENIED")


class UnityCatalogUnavailableException(DomainException):
    def __init__(self, message: str = "Unity Catalog API is temporarily unavailable or throttled."):
        super().__init__(message, code="UNITY_CATALOG_UNAVAILABLE")
