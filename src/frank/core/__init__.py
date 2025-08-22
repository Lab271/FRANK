"""
Core FRANK functionality - submission handling, database abstraction, and client.
"""

from .submission import FRANKSubmission
from .exceptions import *

__all__ = [
    'FRANKSubmission'
]