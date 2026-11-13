import logging
from typing import Any, Dict, List, Set
from application.ports.outbound.unity_catalog_port import UnityCatalogPort
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege
from domain.enums.resource_type import ResourceType
from domain.exceptions.domain_exceptions import (
    UnityCatalogPermissionDeniedException,
    UnityCatalogUnavailableException,
)
from infrastructure.config import Settings, settings

logger = logging.getLogger(__name__)


class UnityCatalogAdapter(UnityCatalogPort):
    """
    Outbound Adapter implementing UnityCatalogPort.
    Supports either in-memory mock simulator mode (ideal for local development/Docker Compose)
    or live Databricks SDK integration when configured with real credentials.
    """

    def __init__(
        self,
        config: Settings = settings,
        use_mock: bool | None = None,
        workspace_client: Any | None = None,
    ):
        self.config = config
        self.use_mock = config.databricks_use_mock if use_mock is None else use_mock

        if self.use_mock:
            logger.info("Initializing UnityCatalogAdapter in SIMULATED / MOCK mode.")
            # Seed mock data
            self._principals: Set[str] = {
                "analytics_readers",
                "data_engineers",
                "finance_users",
                "admin_user",
            }
            self._resources: Set[str] = {
                "shared",
                "shared.sales",
                "shared.sales.orders",
                "shared.sales.customers",
                "main",
                "main.default",
            }
            # Key: (resource_full_name, principal_name) -> Set[Privilege]
            self._grants: Dict[tuple, Set[Privilege]] = {
                ("shared", "analytics_readers"): {Privilege.USE_CATALOG},
                ("shared.sales", "analytics_readers"): {Privilege.USE_SCHEMA},
            }
        else:
            missing_config = [
                name
                for name, value in (
                    ("DATABRICKS_HOST", config.databricks_host),
                    ("DATABRICKS_CLIENT_ID", config.databricks_client_id),
                    ("DATABRICKS_CLIENT_SECRET", config.databricks_client_secret),
                )
                if not value
            ]
            if missing_config and workspace_client is None:
                raise UnityCatalogUnavailableException(
                    "Missing required Databricks configuration: "
                    + ", ".join(missing_config)
                )

            logger.info(
                f"Initializing UnityCatalogAdapter with Databricks SDK (Host: {config.databricks_host})"
            )
            if workspace_client is not None:
                self._workspace_client = workspace_client
            else:
                try:
                    from databricks.sdk import WorkspaceClient

                    self._workspace_client = WorkspaceClient(
                        host=config.databricks_host,
                        client_id=config.databricks_client_id,
                        client_secret=config.databricks_client_secret,
                    )
                except Exception as e:
                    logger.error(f"Failed to initialize Databricks WorkspaceClient: {e}")
                    raise UnityCatalogUnavailableException(str(e)) from e

    def principal_exists(self, principal: Principal) -> bool:
        if self.use_mock:
            # If principal is explicitly unknown in tests
            if "unknown" in principal.name.lower() or "nonexistent" in principal.name.lower():
                return False
            # Automatically accept or check seeded set
            return True

        try:
            principal_type = principal.type.upper()
            filter_field, collection_name, result_field = {
                "GROUP": ("displayName", "groups", "display_name"),
                "USER": ("userName", "users", "user_name"),
                "SERVICE_PRINCIPAL": (
                    "applicationId",
                    "service_principals",
                    "application_id",
                ),
            }.get(principal_type, (None, None, None))
            if filter_field is None or collection_name is None or result_field is None:
                return False

            query = self._scim_filter(filter_field, principal.name)
            client_collection = getattr(self._workspace_client, collection_name)
            return any(
                getattr(candidate, result_field, None) == principal.name
                for candidate in client_collection.list(filter=query)
            )
        except Exception as e:
            if self._is_permission_denied(e):
                raise UnityCatalogPermissionDeniedException(str(e)) from e
            logger.error(f"Error checking principal in Unity Catalog: {e}")
            raise UnityCatalogUnavailableException(str(e)) from e

    def resource_exists(self, resource: Resource) -> bool:
        if self.use_mock:
            if "unknown" in resource.full_name.lower() or "nonexistent" in resource.full_name.lower():
                return False
            return True

        try:
            if resource.type == ResourceType.CATALOG:
                self._workspace_client.catalogs.get(name=resource.full_name)
            elif resource.type == ResourceType.SCHEMA:
                self._workspace_client.schemas.get(full_name=resource.full_name)
            else:
                self._workspace_client.tables.get(full_name=resource.full_name)
            return True
        except Exception as e:
            if self._is_not_found(e):
                return False
            if self._is_permission_denied(e):
                raise UnityCatalogPermissionDeniedException(str(e)) from e
            logger.error(f"Error checking resource in Unity Catalog: {e}")
            raise UnityCatalogUnavailableException(str(e)) from e

    def list_permissions(self, resource: Resource, principal: Principal) -> Set[Privilege]:
        if self.use_mock:
            key = (resource.full_name, principal.name)
            return set(self._grants.get(key, set()))

        try:
            response = self._workspace_client.grants.get(
                securable_type=self._securable_type(resource),
                full_name=resource.full_name,
                principal=principal.name,
            )
            privileges: Set[Privilege] = set()
            for assignment in response.privilege_assignments or []:
                if assignment.principal != principal.name:
                    continue
                for privilege in assignment.privileges or []:
                    value = getattr(privilege, "value", privilege)
                    try:
                        privileges.add(Privilege(value))
                    except ValueError:
                        logger.warning("Ignoring unsupported Databricks privilege: %s", value)
            return privileges
        except Exception as e:
            if self._is_permission_denied(e):
                raise UnityCatalogPermissionDeniedException(str(e)) from e
            logger.error(f"Error listing permissions in Unity Catalog: {e}")
            raise UnityCatalogUnavailableException(str(e)) from e

    def grant(
        self, resource: Resource, principal: Principal, privileges: List[Privilege]
    ) -> List[Privilege]:
        if self.use_mock:
            key = (resource.full_name, principal.name)
            current = self._grants.setdefault(key, set())
            for priv in privileges:
                current.add(priv)
            logger.info(
                f"[SIMULATOR] Granted {privileges} on {resource.full_name} to {principal.name}"
            )
            return privileges

        try:
            if privileges:
                from databricks.sdk.service.catalog import Privilege as DatabricksPrivilege
                from databricks.sdk.service.catalog import PermissionsChange

                self._workspace_client.grants.update(
                    securable_type=self._securable_type(resource),
                    full_name=resource.full_name,
                    changes=[
                        PermissionsChange(
                            principal=principal.name,
                            add=[DatabricksPrivilege(privilege.value) for privilege in privileges],
                        )
                    ],
                )
            logger.info(
                f"[LIVE] Granted {privileges} on {resource.full_name} to {principal.name} via Databricks SDK"
            )
            return privileges
        except Exception as e:
            if self._is_permission_denied(e):
                raise UnityCatalogPermissionDeniedException(str(e)) from e
            logger.error(f"Databricks grant call failed: {e}")
            raise UnityCatalogUnavailableException(str(e)) from e

    def revoke(
        self, resource: Resource, principal: Principal, privileges: List[Privilege]
    ) -> List[Privilege]:
        if self.use_mock:
            key = (resource.full_name, principal.name)
            current = self._grants.get(key, set())
            revoked = []
            for priv in privileges:
                if priv in current:
                    current.remove(priv)
                    revoked.append(priv)
            logger.info(
                f"[SIMULATOR] Revoked {privileges} on {resource.full_name} from {principal.name}"
            )
            return privileges

        try:
            if privileges:
                from databricks.sdk.service.catalog import Privilege as DatabricksPrivilege
                from databricks.sdk.service.catalog import PermissionsChange

                self._workspace_client.grants.update(
                    securable_type=self._securable_type(resource),
                    full_name=resource.full_name,
                    changes=[
                        PermissionsChange(
                            principal=principal.name,
                            remove=[DatabricksPrivilege(privilege.value) for privilege in privileges],
                        )
                    ],
                )
            logger.info(
                f"[LIVE] Revoked {privileges} on {resource.full_name} from {principal.name} via Databricks SDK"
            )
            return privileges
        except Exception as e:
            if self._is_permission_denied(e):
                raise UnityCatalogPermissionDeniedException(str(e)) from e
            logger.error(f"Databricks revoke call failed: {e}")
            raise UnityCatalogUnavailableException(str(e)) from e

    @staticmethod
    def _scim_filter(field: str, value: str) -> str:
        escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'{field} eq "{escaped_value}"'

    @staticmethod
    def _securable_type(resource: Resource) -> str:
        if resource.type == ResourceType.VIEW:
            return ResourceType.TABLE.value
        return resource.type.value

    @staticmethod
    def _is_not_found(error: Exception) -> bool:
        from databricks.sdk.errors import NotFound

        return isinstance(error, NotFound)

    @staticmethod
    def _is_permission_denied(error: Exception) -> bool:
        from databricks.sdk.errors import PermissionDenied

        return isinstance(error, PermissionDenied)
