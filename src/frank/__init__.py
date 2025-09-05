"""
FRANK Platform - Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

A threat intelligence sharing platform that enables anonymous and secure exchange
of cybersecurity information between organizations following a tiered access model.
"""

__version__ = "0.2.0"
__author__ = "Schuberg Philis"
__description__ = "FRANK Platform - Cybersecurity Threat Intelligence Sharing"

# Main public API imports - what users should typically use
from frank.core.submission import FRANKSubmission
from frank.core.exceptions import (
    FRANKError,
    FRANKValidationError,
    FRANKFormatError
)

# Convenience functions for quick operations
from frank.core.submission import (
    validate_submission,
    validate_submission_dict,
    to_yaml,
    from_yaml,
    to_json,
    from_json
)



# Package metadata
__all__ = [
    # Main classes
    'FRANKSubmission',

    # Exceptions
    'FRANKError',
    'FRANKValidationError', 
    'FRANKFormatError',
    
    # Convenience functions
    'validate_submission',
    'validate_submission_dict',
    'to_yaml',
    'from_yaml',
    'to_json',
    'from_json'
]
