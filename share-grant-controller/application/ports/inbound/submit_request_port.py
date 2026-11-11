from abc import ABC, abstractmethod
from application.dto.submission_dto import SubmissionRequestDTO, SubmissionResponseDTO


class SubmitRequestPort(ABC):
    """Inbound Port for submitting grant/revoke requests."""

    @abstractmethod
    def submit(self, request: SubmissionRequestDTO) -> SubmissionResponseDTO:
        raise NotImplementedError
