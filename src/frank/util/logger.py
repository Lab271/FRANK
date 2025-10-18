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


def get_module_logger(module_name: str, default_level: int = logging.DEBUG) -> logging.Logger:
    """
    Get a logger for a specific module with guaranteed DEBUG level.
    
    Args:
        module_name: Name of the module (e.g., 'frank.auth', 'frank.storage')
        default_level: Default logging level if not already configured
        
    Returns:
        logging.Logger: Configured logger with DEBUG level
    """
    logger = logging.getLogger(module_name)
    
    # Set level if not already configured
    if logger.level == logging.NOTSET:
        logger.setLevel(default_level)
    
    # Ensure we have at least one handler for output
    if not logger.handlers and not logger.parent.handlers:
        # Create a console handler if none exists
        console_handler = logging.StreamHandler()
        console_handler.setLevel(default_level)
        
        # Try to use Uvicorn's formatter for consistency
        try:
            from uvicorn.logging import DefaultFormatter
            # formatter = DefaultFormatter(fmt="%(levelprefix)s [%(name)s] %(message)s")
            formatter = DefaultFormatter(fmt="%(levelprefix)s %(message)s")
        except ImportError:
            # Fallback to simple formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate messages
        logger.propagate = False
    
    return logger


def configure_frank_logging(log_level_name: str) -> None:
    """
    Configure logging levels for all FRANK components and Uvicorn using discovery.
    
    This function automatically discovers and configures:
    - All existing loggers that match known patterns (uvicorn*, frank*)
    - Sets consistent log levels across all FRANK components
    - Handles root logger inheritance properly
    
    Args:
        log_level_name: Log level name ('debug', 'info', 'warning', 'error')
    """
    log_level = getattr(logging, log_level_name.upper())
    
    # Get all existing loggers from the logging registry
    logger_dict = logging.Logger.manager.loggerDict
    
    # Patterns to match for automatic configuration
    target_patterns = [
        'uvicorn',      # uvicorn, uvicorn.access, uvicorn.error, etc.
        'frank',        # frank, frank.auth, frank.storage, etc.
        'fastapi',      # FastAPI framework loggers
        'boto3',        # AWS SDK loggers (if we want to control them)
        'botocore',     # AWS SDK core loggers
    ]
    
    configured_loggers = []
    
    # Configure all matching existing loggers
    for logger_name in logger_dict:
        for pattern in target_patterns:
            if logger_name.startswith(pattern):
                logger = logging.getLogger(logger_name)
                logger.setLevel(log_level)
                configured_loggers.append(logger_name)
                break
    
    # Always ensure root logger level allows our target level
    root_logger = logging.getLogger()
    if root_logger.level > log_level:  # Only lower the level, don't raise it
        root_logger.setLevel(log_level)
    
    # Log what we configured (useful for debugging)
    setup_logger = logging.getLogger("frank.logger")
    if configured_loggers:
        setup_logger.debug(f"Configured {len(configured_loggers)} loggers to {log_level_name.upper()}: {sorted(configured_loggers)}")
    else:
        setup_logger.debug(f"No existing loggers found matching patterns: {target_patterns}")
        setup_logger.debug(f"Available loggers: {sorted(logger_dict.keys())}")
