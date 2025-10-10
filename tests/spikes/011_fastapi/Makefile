# FRANK Platform - FastAPI Testability Spike - Build Automation
# Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling
#
# This Makefile provides convenient commands for FastAPI testability spike
# development workflow including dependency installation, testing with coverage,
# development server management with hot-reload, and code quality validation.
#
# Key targets:
#   make install      - Install Python dependencies
#   make test         - Run comprehensive test suite
#   make test-coverage- Generate test coverage reports
#   make run-reload   - Start development server with hot-reload
#   make validate     - Complete validation workflow
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

# FastAPI Testability Spike - Makefile
# Provides convenient commands for development and testing

.PHONY: install dev test test-verbose test-coverage clean run run-reload validate-spike help

# Default target
help:
	@echo "Available commands:"
	@echo "  install       - Install dependencies"
	@echo "  dev           - Install development dependencies"
	@echo "  test          - Run all tests"
	@echo "  test-verbose  - Run tests with verbose output"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  run           - Run the FastAPI server"
	@echo "  run-reload    - Run the FastAPI server with auto-reload"
	@echo "  clean         - Clean up temporary files"

# Install dependencies
install:
	pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 httpx==0.25.2

# Install development dependencies (includes testing tools)
dev: install
	pip install pytest pytest-cov pytest-xdist coverage[toml]

# Run all tests
test:
	pytest test_simple_api.py

# Run tests with verbose output
test-verbose:
	pytest test_simple_api.py -v

# Run tests with coverage report
test-coverage:
	pytest test_simple_api.py --cov=simple_api --cov-report=html --cov-report=term-missing

# Run the FastAPI server
run:
	python simple_api.py --reload

# Clean up temporary files
clean:
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
