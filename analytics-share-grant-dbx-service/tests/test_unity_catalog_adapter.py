from adapters.outbound.databricks.unity_catalog_adapter import UnityCatalogAdapter
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.privilege import Privilege
from domain.enums.resource_type import ResourceType


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
