"""
FRANK Platform - Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

A threat intelligence sharing platform that enables anonymous and secure exchange
of cybersecurity information between organizations following a tiered access model.
"""

__version__ = "0.1.0"
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
    generate_minimal,
    validate_submission,
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
    'generate_minimal',
    'validate_submission',
    'to_yaml',
    'from_yaml',
    'to_json',
    'from_json'
]
