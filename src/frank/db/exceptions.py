class FRANKDatabaseError(Exception):
    """Base exception for FRANK database operations."""
    pass

class FRANKConfigurationError(FRANKDatabaseError):
    """Raised when database configuration fails."""
    pass

class FRANKConnectionError(FRANKDatabaseError):
    """Raised when database connection fails."""
    pass

class FRANKStorageError(FRANKDatabaseError):
    """Raised when storage operations fail."""
    pass

class FRANKQueryError(FRANKDatabaseError):
    """Raised when query operations fail."""
    pass
