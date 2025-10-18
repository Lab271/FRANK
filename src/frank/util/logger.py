"""
FRANK Platform - Utility Logger
Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling

This module provides a NullLogger class that can be used to disable logging
by discarding all log messages. 

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import logging

class NullLogger:
    """Null logger that discards all log messages"""
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass
    def exception(self, *args, **kwargs): pass

# ===================================
# Logging Setup
# ===================================
def setup_logging(silent=False) -> logging.Logger:
    """Setup logging to match Uvicorn's colored output, a bit over the top but nice for dev"""
    
    if silent:
        # Silent mode - disable ALL logging
       
        # Specifically silence known loggers
        for logger_name in ['uvicorn', 'uvicorn.access', 'uvicorn.error', 'fastapi', 'root']:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.CRITICAL)
            logger.disabled = True
            # Remove all handlers
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
        
        return logging.getLogger("uvicorn")  # Return a silenced logger
    
    # Try to use Uvicorn's colored formatter
    try:
        from uvicorn.logging import DefaultFormatter
        
        # Create a colored formatter like Uvicorn uses
        formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s")
        
        # Setup root logger with the colored formatter
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Add new handler with colored formatter
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        
        # Also setup uvicorn logger specifically
        uvicorn_logger = logging.getLogger("uvicorn")
        uvicorn_logger.setLevel(logging.INFO)
        return uvicorn_logger
        
    except ImportError:
        # Fallback to basic colored format if Uvicorn formatter not available
        logging.basicConfig(
            level=logging.INFO,
            format="\033[32mINFO\033[0m:     %(message)s",  # Green INFO text
            handlers=[logging.StreamHandler()]
        )
        return logging.getLogger("uvicorn")
