"""Domain exceptions for the workflow and service layer."""


class WorkflowError(Exception):
    """Base exception for workflow domain errors."""
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class WorkflowNotFoundError(WorkflowError):
    """Resource not found or unauthorized department access (maps to 404)."""
    pass


class WorkflowConflictError(WorkflowError):
    """State conflict or invalid transition (maps to 409)."""
    pass


class WorkflowBadRequestError(WorkflowError):
    """Validation or missing required parameter error (maps to 400)."""
    pass


class WorkflowForbiddenError(WorkflowError):
    """Forbidden action or permission denied (maps to 403)."""
    pass
