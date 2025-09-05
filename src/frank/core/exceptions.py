"""
FRANK Platform Exception Hierarchy

Centralized exception definitions following Python best practices.
All FRANK exceptions inherit from FRANKError for easy catching.
"""


class FRANKError(Exception):
    """
    Base exception for all FRANK platform operations.
    
    All FRANK-specific exceptions inherit from this class,
    allowing users to catch all FRANK errors with a single except clause.
    """
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"{self.message} (Code: {self.error_code}, Details: {self.details})"
        return f"{self.message} (Code: {self.error_code})"


# Submission-related exceptions
class FRANKSubmissionError(FRANKError):
    """Base exception for submission-related operations."""
    pass


class FRANKValidationError(FRANKSubmissionError):
    """Raised when submission validation fails."""
    
    def __init__(self, message: str, validation_errors: list = None, **kwargs):
        super().__init__(message, **kwargs)
        self.validation_errors = validation_errors or []


class FRANKFormatError(FRANKSubmissionError):
    """Raised when submission format is invalid (YAML/JSON parsing errors)."""
    pass