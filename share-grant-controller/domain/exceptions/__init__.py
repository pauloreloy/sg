class ControllerDomainException(Exception):
    """Base domain exception for Controller."""

    def __init__(self, message: str, code: str = "CONTROLLER_ERROR"):
        super().__init__(message)
        self.message = message
        self.code = code


class RequestAlreadyExistsException(ControllerDomainException):
    def __init__(self, request_id: str, message: str = "Request already exists for this idempotency key."):
        super().__init__(message, code="REQUEST_ALREADY_EXISTS")
        self.request_id = request_id


class RequestNotFoundException(ControllerDomainException):
    def __init__(self, request_id: str):
        super().__init__(f"Request {request_id} not found.", code="REQUEST_NOT_FOUND")
        self.request_id = request_id


class InvalidStateTransitionException(ControllerDomainException):
    def __init__(self, message: str):
        super().__init__(message, code="INVALID_STATE_TRANSITION")


class DispatchFailedException(ControllerDomainException):
    def __init__(self, message: str):
        super().__init__(message, code="DISPATCH_FAILED")


class RepositoryException(ControllerDomainException):
    def __init__(self, message: str):
        super().__init__(message, code="REPOSITORY_ERROR")
