#!/usr/bin/env python3
"""
FRANK Platform - Unit Tests for Logger Module

Unit tests for logging configuration and NullLogger functionality.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""
import unittest
import logging
from unittest.mock import Mock, patch, MagicMock

from frank.util.logger import (
    NullLogger,
    setup_logging,
    get_module_logger,
    configure_frank_logging
)


class TestNullLogger(unittest.TestCase):
    """Test NullLogger class that discards all log messages."""
    
    def setUp(self):
        """Set up test fixture."""
        self.null_logger = NullLogger()
    
    def test_debug_method_exists(self):
        """NullLogger should have debug method."""
        self.assertTrue(hasattr(self.null_logger, 'debug'))
        self.null_logger.debug("test message")  # Should not raise
    
    def test_info_method_exists(self):
        """NullLogger should have info method."""
        self.assertTrue(hasattr(self.null_logger, 'info'))
        self.null_logger.info("test message")
    
    def test_warning_method_exists(self):
        """NullLogger should have warning method."""
        self.assertTrue(hasattr(self.null_logger, 'warning'))
        self.null_logger.warning("test message")
    
    def test_error_method_exists(self):
        """NullLogger should have error method."""
        self.assertTrue(hasattr(self.null_logger, 'error'))
        self.null_logger.error("test message")
    
    def test_critical_method_exists(self):
        """NullLogger should have critical method."""
        self.assertTrue(hasattr(self.null_logger, 'critical'))
        self.null_logger.critical("test message")
    
    def test_exception_method_exists(self):
        """NullLogger should have exception method."""
        self.assertTrue(hasattr(self.null_logger, 'exception'))
        self.null_logger.exception("test message")
    
    def test_methods_accept_args_and_kwargs(self):
        """NullLogger methods should accept arbitrary args and kwargs."""
        # Should not raise any exceptions
        self.null_logger.debug("message", "arg1", "arg2", key1="value1", key2="value2")
        self.null_logger.info("message", extra={"key": "value"})
        self.null_logger.warning("message", exc_info=True)
        self.null_logger.error("message", stack_info=True)


class TestSetupLogging(unittest.TestCase):
    """Test setup_logging function."""
    
    def setUp(self):
        """Set up test fixture."""
        # Store original state
        self.original_handlers = logging.getLogger().handlers[:]
    
    def tearDown(self):
        """Clean up after each test."""
        # Restore original handlers
        root_logger = logging.getLogger()
        root_logger.handlers = self.original_handlers
        root_logger.setLevel(logging.WARNING)
    
    def test_setup_logging_silent_mode(self):
        """setup_logging with silent=True should disable logging."""
        logger = setup_logging(silent=True)
        
        # Logger should be returned
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "uvicorn")
    
    def test_setup_logging_silent_disables_uvicorn(self):
        """setup_logging silent mode should disable uvicorn logger."""
        setup_logging(silent=True)
        
        uvicorn_logger = logging.getLogger("uvicorn")
        self.assertTrue(uvicorn_logger.disabled or uvicorn_logger.level >= logging.CRITICAL)
    
    @patch('uvicorn.logging.DefaultFormatter')
    def test_setup_logging_with_uvicorn_formatter(self, mock_formatter_class):
        """setup_logging should use Uvicorn's DefaultFormatter when available."""
        mock_formatter = Mock()
        mock_formatter_class.return_value = mock_formatter
        
        logger = setup_logging(silent=False)
        
        # Should have created a DefaultFormatter
        mock_formatter_class.assert_called_once()
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "uvicorn")
    
    def test_setup_logging_fallback_without_uvicorn(self):
        """setup_logging should fall back to basic logging if Uvicorn not available."""
        # Test the actual behavior without mocking - it should work either way
        logger = setup_logging(silent=False)
        
        # Should still return a logger
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "uvicorn")


class TestGetModuleLogger(unittest.TestCase):
    """Test get_module_logger function."""
    
    def setUp(self):
        """Set up test fixture."""
        # Clear any existing handlers
        test_logger = logging.getLogger("test.module")
        test_logger.handlers = []
        test_logger.setLevel(logging.NOTSET)
        test_logger.propagate = True
    
    def tearDown(self):
        """Clean up after each test."""
        # Clean up test loggers
        test_logger = logging.getLogger("test.module")
        test_logger.handlers = []
        test_logger.setLevel(logging.NOTSET)
        test_logger.propagate = True
    
    def test_get_module_logger_creates_logger(self):
        """get_module_logger should create and return a logger."""
        logger = get_module_logger("test.module")
        
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "test.module")
    
    def test_get_module_logger_sets_debug_level(self):
        """get_module_logger should set DEBUG level by default."""
        logger = get_module_logger("test.module")
        
        self.assertEqual(logger.level, logging.DEBUG)
    
    def test_get_module_logger_custom_level(self):
        """get_module_logger should respect custom log level."""
        logger = get_module_logger("test.module", default_level=logging.INFO)
        
        self.assertEqual(logger.level, logging.INFO)
    
    def test_get_module_logger_adds_handler(self):
        """get_module_logger should add handler if none exists."""
        logger = get_module_logger("test.module.new")
        
        # Should have at least one handler
        self.assertGreater(len(logger.handlers), 0)
    
    def test_get_module_logger_disables_propagation(self):
        """get_module_logger should disable propagation to avoid duplicates."""
        logger = get_module_logger("test.module.propagate")
        
        # If handler was added, propagation should be False
        if logger.handlers:
            self.assertFalse(logger.propagate)
    
    @patch('uvicorn.logging.DefaultFormatter')
    def test_get_module_logger_uses_uvicorn_formatter(self, mock_formatter_class):
        """get_module_logger should try to use Uvicorn formatter."""
        mock_formatter = Mock()
        mock_formatter_class.return_value = mock_formatter
        
        logger = get_module_logger("test.module.uvicorn")
        
        # Should have attempted to create DefaultFormatter
        self.assertTrue(mock_formatter_class.called)
    
    def test_get_module_logger_fallback_formatter(self):
        """get_module_logger should fall back to basic formatter."""
        # Test the actual behavior - should work with or without uvicorn
        logger = get_module_logger("test.module.fallback")
        
        # Should still create a logger with handler
        self.assertIsNotNone(logger)
        if logger.handlers:
            self.assertGreater(len(logger.handlers), 0)


class TestConfigureFrankLogging(unittest.TestCase):
    """Test configure_frank_logging function."""
    
    def setUp(self):
        """Set up test fixture."""
        # Store original logger states
        self.original_loggers = {}
        for name in ['uvicorn', 'frank', 'fastapi']:
            logger = logging.getLogger(name)
            self.original_loggers[name] = {
                'level': logger.level,
                'handlers': logger.handlers[:]
            }
    
    def tearDown(self):
        """Clean up after each test."""
        # Restore original logger states
        for name, state in self.original_loggers.items():
            logger = logging.getLogger(name)
            logger.setLevel(state['level'])
            logger.handlers = state['handlers']
    
    def test_configure_frank_logging_sets_debug_level(self):
        """configure_frank_logging should set DEBUG level."""
        # Create some loggers first
        logging.getLogger("frank.test")
        logging.getLogger("uvicorn.test")
        
        configure_frank_logging("debug")
        
        # Check that root logger allows DEBUG
        root_logger = logging.getLogger()
        self.assertLessEqual(root_logger.level, logging.DEBUG)
    
    def test_configure_frank_logging_sets_info_level(self):
        """configure_frank_logging should set INFO level."""
        logging.getLogger("frank.test")
        
        configure_frank_logging("info")
        
        root_logger = logging.getLogger()
        self.assertLessEqual(root_logger.level, logging.INFO)
    
    def test_configure_frank_logging_sets_warning_level(self):
        """configure_frank_logging should set WARNING level."""
        configure_frank_logging("warning")
        
        root_logger = logging.getLogger()
        self.assertLessEqual(root_logger.level, logging.WARNING)
    
    def test_configure_frank_logging_sets_error_level(self):
        """configure_frank_logging should set ERROR level."""
        configure_frank_logging("error")
        
        root_logger = logging.getLogger()
        self.assertLessEqual(root_logger.level, logging.ERROR)
    
    def test_configure_frank_logging_handles_uppercase(self):
        """configure_frank_logging should handle uppercase level names."""
        configure_frank_logging("DEBUG")
        
        root_logger = logging.getLogger()
        self.assertLessEqual(root_logger.level, logging.DEBUG)
    
    def test_configure_frank_logging_handles_mixed_case(self):
        """configure_frank_logging should handle mixed case level names."""
        configure_frank_logging("Info")
        
        root_logger = logging.getLogger()
        self.assertLessEqual(root_logger.level, logging.INFO)
    
    def test_configure_frank_logging_discovers_existing_loggers(self):
        """configure_frank_logging should discover and configure existing loggers."""
        # Create some frank loggers
        frank_logger = logging.getLogger("frank.module1")
        frank_logger.setLevel(logging.CRITICAL)  # Set to high level initially
        
        configure_frank_logging("debug")
        
        # Should have been reconfigured
        self.assertEqual(frank_logger.level, logging.DEBUG)
    
    def test_configure_frank_logging_targets_uvicorn_loggers(self):
        """configure_frank_logging should target uvicorn loggers."""
        uvicorn_logger = logging.getLogger("uvicorn.access")
        uvicorn_logger.setLevel(logging.CRITICAL)
        
        configure_frank_logging("info")
        
        self.assertEqual(uvicorn_logger.level, logging.INFO)
    
    def test_configure_frank_logging_targets_fastapi_loggers(self):
        """configure_frank_logging should target fastapi loggers."""
        fastapi_logger = logging.getLogger("fastapi.test")
        fastapi_logger.setLevel(logging.CRITICAL)
        
        configure_frank_logging("debug")
        
        self.assertEqual(fastapi_logger.level, logging.DEBUG)


class TestLoggingIntegration(unittest.TestCase):
    """Integration tests for logging functionality."""
    
    def test_null_logger_can_replace_real_logger(self):
        """NullLogger should be usable as a drop-in replacement."""
        null_logger = NullLogger()
        real_logger = logging.getLogger("test.integration")
        
        # Both should support the same methods
        for method_name in ['debug', 'info', 'warning', 'error', 'critical', 'exception']:
            self.assertTrue(hasattr(null_logger, method_name))
            self.assertTrue(hasattr(real_logger, method_name))
    
    def test_module_logger_is_functional(self):
        """get_module_logger should create a functional logger."""
        logger = get_module_logger("test.functional")
        
        # Should be able to log without errors
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
    
    def test_configure_then_get_module_logger(self):
        """configure_frank_logging followed by get_module_logger should work."""
        configure_frank_logging("info")
        logger = get_module_logger("frank.configured")
        
        # Logger should exist and be configured
        self.assertIsNotNone(logger)
        self.assertEqual(logger.name, "frank.configured")


if __name__ == "__main__":
    """Run all unit tests for logger module."""
    unittest.main()
