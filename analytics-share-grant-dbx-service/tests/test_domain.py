import pytest
from domain.entities.permission import Permission
from domain.entities.principal import Principal
from domain.entities.resource import Resource
from domain.enums.operation_type import OperationType
from domain.enums.privilege import Privilege
from domain.enums.resource_type import ResourceType
from domain.exceptions.domain_exceptions import InvalidPrivilegeException
from domain.services.permission_domain_service import PermissionDomainService


def test_principal_validation():
    p = Principal(type="GROUP", name="readers")
    assert p.type == "GROUP"
    assert p.name == "readers"

    with pytest.raises(ValueError):
        Principal(type="", name="readers")

    with pytest.raises(ValueError):
        Principal(type="GROUP", name="")


def test_resource_full_names():
    cat = Resource(type=ResourceType.CATALOG, catalog="main")
    assert cat.full_name == "main"

    schema = Resource(type=ResourceType.SCHEMA, catalog="main", schema="sales")
    assert schema.full_name == "main.sales"

    table = Resource(type=ResourceType.TABLE, catalog="main", schema="sales", name="orders")
    assert table.full_name == "main.sales.orders"


def test_resource_validation():
    with pytest.raises(ValueError):
        Resource(type=ResourceType.TABLE, catalog="main", schema="sales")  # missing name

    with pytest.raises(ValueError):
        Resource(type=ResourceType.SCHEMA, catalog="main")  # missing schema


def test_permission_domain_service_validations():
    table = Resource(type=ResourceType.TABLE, catalog="main", schema="sales", name="orders")
    # SELECT is valid for TABLE
    PermissionDomainService.validate_privileges_for_resource(table, [Privilege.SELECT])

    # USE_CATALOG is NOT valid for TABLE
    with pytest.raises(InvalidPrivilegeException):
        PermissionDomainService.validate_privileges_for_resource(table, [Privilege.USE_CATALOG])


def test_calculate_grant_diff():
    # When already has SELECT, diff is empty (idempotent)
    requested = {Privilege.SELECT}
    current = {Privilege.SELECT}
    diff = PermissionDomainService.calculate_grant_diff(requested, current)
    assert diff == set()

    # When does not have SELECT, diff contains SELECT
    diff2 = PermissionDomainService.calculate_grant_diff(requested, set())
    assert diff2 == {Privilege.SELECT}

    # When has ALL_PRIVILEGES, diff is empty
    diff3 = PermissionDomainService.calculate_grant_diff(requested, {Privilege.ALL_PRIVILEGES})
    assert diff3 == set()


def test_calculate_revoke_diff():
    requested = {Privilege.SELECT}
    current = {Privilege.SELECT, Privilege.MODIFY}
    diff = PermissionDomainService.calculate_revoke_diff(requested, current)
    assert diff == {Privilege.SELECT}

    # When current does not have SELECT, diff is empty (idempotent)
    diff2 = PermissionDomainService.calculate_revoke_diff(requested, {Privilege.MODIFY})
    assert diff2 == set()
