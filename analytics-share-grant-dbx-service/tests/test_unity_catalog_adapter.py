from types import SimpleNamespace

import pytest
import databricks.sdk
from databricks.sdk.errors import NotFound, PermissionDenied

from adapters.outbound.databricks.unity_catalog_adapter import UnityCatalogAdapter
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.exceptions.domain_exceptions import (
    UnityCatalogPermissionDeniedException,
    UnityCatalogUnavailableException,
)
from domain.enums.privilege import Privilege
from domain.enums.resource_type import ResourceType
from infrastructure.config import Settings


class FakeCollection:
    def __init__(self, items=(), error=None):
        self.items = list(items)
        self.error = error
        self.list_calls = []
        self.get_calls = []

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        if self.error:
            raise self.error
        return iter(self.items)

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        if self.error:
            raise self.error
        if not self.items:
            raise NotFound("Not found")
        return self.items[0]


class FakeGrants:
    def __init__(self):
        self.get_response = SimpleNamespace(privilege_assignments=[])
        self.get_error = None
        self.get_calls = []
        self.update_calls = []

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        if self.get_error:
            raise self.get_error
        return self.get_response

    def update(self, **kwargs):
        self.update_calls.append(kwargs)


class FakeWorkspaceClient:
    def __init__(self):
        self.groups = FakeCollection()
        self.users = FakeCollection()
        self.service_principals = FakeCollection()
        self.catalogs = FakeCollection([object()])
        self.schemas = FakeCollection([object()])
        self.tables = FakeCollection([object()])
        self.grants = FakeGrants()


def _settings(**overrides):
    values = {
        "databricks_use_mock": True,
        "databricks_host": "https://workspace.example.com",
        "databricks_client_id": "client-id",
        "databricks_client_secret": "client-secret",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _live_adapter(client, **settings_overrides):
    return UnityCatalogAdapter(
        config=_settings(**settings_overrides),
        use_mock=False,
        workspace_client=client,
    )


def test_unity_catalog_simulator_grant_and_revoke():
    adapter = UnityCatalogAdapter(use_mock=True)

    principal = Principal(type="GROUP", name="data_engineers")
    resource = Resource(type=ResourceType.TABLE, catalog="shared", schema="sales", name="customers")

    # Initial permissions
    initial_perms = adapter.list_permissions(resource, principal)
    assert Privilege.SELECT not in initial_perms

    # Grant SELECT
    granted = adapter.grant(resource, principal, [Privilege.SELECT])
    assert Privilege.SELECT in granted

    # Check updated permissions
    updated_perms = adapter.list_permissions(resource, principal)
    assert Privilege.SELECT in updated_perms

    # Revoke SELECT
    revoked = adapter.revoke(resource, principal, [Privilege.SELECT])
    assert Privilege.SELECT in revoked

    # Check permissions after revoke
    after_revoke_perms = adapter.list_permissions(resource, principal)
    assert Privilege.SELECT not in after_revoke_perms


def test_unity_catalog_simulator_principal_and_resource_checks():
    adapter = UnityCatalogAdapter(use_mock=True)

    valid_p = Principal(type="GROUP", name="analytics_readers")
    invalid_p = Principal(type="GROUP", name="unknown_principal_foo")

    assert adapter.principal_exists(valid_p) is True
    assert adapter.principal_exists(invalid_p) is False

    valid_res = Resource(type=ResourceType.TABLE, catalog="shared", schema="sales", name="orders")
    invalid_res = Resource(type=ResourceType.TABLE, catalog="shared", schema="sales", name="unknown_xyz")

    assert adapter.resource_exists(valid_res) is True
    assert adapter.resource_exists(invalid_res) is False


def test_explicit_false_overrides_mock_configuration():
    adapter = UnityCatalogAdapter(
        config=_settings(databricks_use_mock=True),
        use_mock=False,
        workspace_client=FakeWorkspaceClient(),
    )

    assert adapter.use_mock is False


def test_configured_live_mode_creates_workspace_client(monkeypatch):
    client = FakeWorkspaceClient()
    constructor_calls = []

    def create_workspace_client(**kwargs):
        constructor_calls.append(kwargs)
        return client

    monkeypatch.setattr(databricks.sdk, "WorkspaceClient", create_workspace_client)

    adapter = UnityCatalogAdapter(
        config=_settings(databricks_use_mock=False),
    )

    assert adapter.use_mock is False
    assert adapter._workspace_client is client
    assert constructor_calls == [
        {
            "host": "https://workspace.example.com",
            "client_id": "client-id",
            "client_secret": "client-secret",
        }
    ]


def test_live_mode_requires_real_databricks_configuration():
    with pytest.raises(UnityCatalogUnavailableException, match="DATABRICKS_HOST"):
        UnityCatalogAdapter(
            config=_settings(
                databricks_host=None,
                databricks_client_id=None,
                databricks_client_secret=None,
            ),
            use_mock=False,
        )


def test_live_principal_exists_uses_scim_filter():
    client = FakeWorkspaceClient()
    client.groups = FakeCollection(
        [SimpleNamespace(display_name='Analytics "Readers"')]
    )
    adapter = _live_adapter(client)
    principal = Principal(type="GROUP", name='Analytics "Readers"')

    assert adapter.principal_exists(principal) is True
    assert client.groups.list_calls == [
        {"filter": 'displayName eq "Analytics \\"Readers\\""'}
    ]


@pytest.mark.parametrize(
    ("principal_type", "collection_name", "result_field", "filter_field"),
    [
        ("USER", "users", "user_name", "userName"),
        (
            "SERVICE_PRINCIPAL",
            "service_principals",
            "application_id",
            "applicationId",
        ),
    ],
)
def test_live_principal_exists_supports_users_and_service_principals(
    principal_type, collection_name, result_field, filter_field
):
    client = FakeWorkspaceClient()
    principal_name = "principal@example.com" if principal_type == "USER" else "app-id"
    setattr(
        client,
        collection_name,
        FakeCollection([SimpleNamespace(**{result_field: principal_name})]),
    )
    adapter = _live_adapter(client)

    assert adapter.principal_exists(Principal(type=principal_type, name=principal_name))
    assert getattr(client, collection_name).list_calls == [
        {"filter": f'{filter_field} eq "{principal_name}"'}
    ]


@pytest.mark.parametrize(
    ("resource", "expected_collection", "expected_query"),
    [
        (
            Resource(type=ResourceType.CATALOG, catalog="shared"),
            "catalogs",
            {"name": "shared"},
        ),
        (
            Resource(type=ResourceType.SCHEMA, catalog="shared", schema="sales"),
            "schemas",
            {"full_name": "shared.sales"},
        ),
        (
            Resource(
                type=ResourceType.TABLE,
                catalog="shared",
                schema="sales",
                name="orders",
            ),
            "tables",
            {"full_name": "shared.sales.orders"},
        ),
        (
            Resource(
                type=ResourceType.VIEW,
                catalog="shared",
                schema="sales",
                name="order_view",
            ),
            "tables",
            {"full_name": "shared.sales.order_view"},
        ),
    ],
)
def test_live_resource_exists_calls_unity_catalog_get(
    resource, expected_collection, expected_query
):
    client = FakeWorkspaceClient()
    adapter = _live_adapter(client)

    assert adapter.resource_exists(resource) is True
    assert getattr(client, expected_collection).get_calls == [expected_query]


def test_live_resource_exists_returns_false_only_for_not_found():
    client = FakeWorkspaceClient()
    client.tables = FakeCollection(error=NotFound("Not found"))
    adapter = _live_adapter(client)
    resource = Resource(
        type=ResourceType.TABLE,
        catalog="shared",
        schema="sales",
        name="missing",
    )

    assert adapter.resource_exists(resource) is False

    client.tables.error = PermissionDenied("Denied")
    with pytest.raises(UnityCatalogPermissionDeniedException):
        adapter.resource_exists(resource)


def test_live_list_permissions_and_grant_revoke_use_sdk_models():
    client = FakeWorkspaceClient()
    client.grants.get_response = SimpleNamespace(
        privilege_assignments=[
            SimpleNamespace(
                principal="analytics_readers",
                privileges=[SimpleNamespace(value="SELECT")],
            )
        ]
    )
    adapter = _live_adapter(client)
    principal = Principal(type="GROUP", name="analytics_readers")
    resource = Resource(
        type=ResourceType.VIEW,
        catalog="shared",
        schema="sales",
        name="orders_view",
    )

    assert adapter.list_permissions(resource, principal) == {Privilege.SELECT}
    assert client.grants.get_calls == [
        {
            "securable_type": "TABLE",
            "full_name": "shared.sales.orders_view",
            "principal": "analytics_readers",
        }
    ]

    adapter.grant(resource, principal, [Privilege.SELECT, Privilege.READ_METADATA])
    adapter.revoke(resource, principal, [Privilege.SELECT])

    grant_change = client.grants.update_calls[0]["changes"][0]
    revoke_change = client.grants.update_calls[1]["changes"][0]
    assert grant_change.principal == "analytics_readers"
    assert [privilege.value for privilege in grant_change.add] == [
        "SELECT",
        "READ_METADATA",
    ]
    assert [privilege.value for privilege in revoke_change.remove] == ["SELECT"]


def test_live_api_errors_are_not_reported_as_success():
    client = FakeWorkspaceClient()
    client.grants.get_error = RuntimeError("API unavailable")
    adapter = _live_adapter(client)
    principal = Principal(type="GROUP", name="analytics_readers")
    resource = Resource(type=ResourceType.CATALOG, catalog="shared")

    with pytest.raises(UnityCatalogUnavailableException, match="API unavailable"):
        adapter.list_permissions(resource, principal)
