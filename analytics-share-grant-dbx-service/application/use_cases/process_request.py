from application.dto.operation_result_dto import OperationResultDTO
from application.dto.permission_request_dto import PermissionRequestDTO
from application.ports.inbound.process_request_port import ProcessRequestPort
from application.workflows.permission_workflow import PermissionWorkflow


class ProcessRequestUseCase(ProcessRequestPort):
    def __init__(self, workflow: PermissionWorkflow):
        self.workflow = workflow

    def process(self, request: PermissionRequestDTO) -> OperationResultDTO:
        return self.workflow.execute(request)
