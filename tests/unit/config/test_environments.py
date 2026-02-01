"""
FRANK Platform - Environment Configuration Tests

Unit tests for Environment enum and EnvironmentConfig singleton.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import os
import pytest
from frank.config.environments import Environment, EnvironmentConfig


class TestEnvironmentEnum:
    """Test Environment enum values and methods."""

    def test_environment_values(self):
        """Test all environment enum values."""
        assert Environment.LOCAL_PYTHON.value == "local-python"
        assert Environment.LOCAL_DOCKER.value == "local-docker"
        assert Environment.AWS_DEV.value == "aws-dev"
        assert Environment.AWS_PREPROD.value == "aws-preprod"
        assert Environment.AWS_PROD.value == "aws-prod"

    def test_environment_from_string_exact(self):
        """Test creating Environment from exact string."""
        assert Environment.from_string("local-python") == Environment.LOCAL_PYTHON
        assert Environment.from_string("local-docker") == Environment.LOCAL_DOCKER
        assert Environment.from_string("aws-dev") == Environment.AWS_DEV
        assert Environment.from_string("aws-preprod") == Environment.AWS_PREPROD
        assert Environment.from_string("aws-prod") == Environment.AWS_PROD

    def test_environment_from_string_case_insensitive(self):
        """Test creating Environment from uppercase string."""
        assert Environment.from_string("LOCAL-PYTHON") == Environment.LOCAL_PYTHON
        assert Environment.from_string("LOCAL-DOCKER") == Environment.LOCAL_DOCKER
        assert Environment.from_string("AWS-PROD") == Environment.AWS_PROD

    def test_environment_from_string_underscore(self):
        """Test creating Environment from underscore-separated string."""
        assert Environment.from_string("local_python") == Environment.LOCAL_PYTHON
        assert Environment.from_string("local_docker") == Environment.LOCAL_DOCKER
        assert Environment.from_string("aws_dev") == Environment.AWS_DEV

    def test_environment_from_string_mixed_case_underscore(self):
        """Test creating Environment from mixed case with underscores."""
        assert Environment.from_string("LOCAL_PYTHON") == Environment.LOCAL_PYTHON
        assert Environment.from_string("Local_Docker") == Environment.LOCAL_DOCKER

    def test_environment_from_string_invalid(self):
        """Test creating Environment from invalid string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            Environment.from_string("invalid-env")

        assert "Invalid environment: 'invalid-env'" in str(exc_info.value)
        assert "local-python" in str(exc_info.value)

    def test_environment_direct_construction(self):
        """Test creating Environment directly."""
        env = Environment("local-docker")
        assert env == Environment.LOCAL_DOCKER


class TestEnvironmentConfig:
    """Test EnvironmentConfig singleton configuration."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        EnvironmentConfig.reset()
        yield
        EnvironmentConfig.reset()

    @pytest.fixture(autouse=True)
    def clean_env(self, monkeypatch):
        """Clean environment variables before each test."""
        monkeypatch.delenv("FRANK_ENVIRONMENT", raising=False)
        monkeypatch.delenv("FRANK_STAGE", raising=False)

    def test_configure_explicit(self):
        """Test explicit configuration."""
        config = EnvironmentConfig.configure(
            environment="local-docker",
            stage=3
        )

        assert config.environment == Environment.LOCAL_DOCKER
        assert config.stage == 3

    def test_configure_from_env_vars(self, monkeypatch):
        """Test configuration from environment variables."""
        monkeypatch.setenv("FRANK_ENVIRONMENT", "aws-prod")
        monkeypatch.setenv("FRANK_STAGE", "3")

        config = EnvironmentConfig.configure()

        assert config.environment == Environment.AWS_PROD
        assert config.stage == 3

    def test_configure_defaults(self):
        """Test configuration with defaults."""
        config = EnvironmentConfig.configure()

        assert config.environment == Environment.LOCAL_PYTHON
        assert config.stage == 1

    def test_configure_mixed_explicit_and_env(self, monkeypatch):
        """Test explicit parameters override environment variables."""
        monkeypatch.setenv("FRANK_ENVIRONMENT", "aws-dev")
        monkeypatch.setenv("FRANK_STAGE", "2")

        config = EnvironmentConfig.configure(
            environment="local-docker",
            stage=3
        )

        assert config.environment == Environment.LOCAL_DOCKER
        assert config.stage == 3

    def test_configure_singleton(self):
        """Test singleton pattern - same instance returned."""
        config1 = EnvironmentConfig.configure(environment="local-docker")
        config2 = EnvironmentConfig.configure(environment="aws-prod")

        # Second configure returns first instance (singleton)
        assert config1 is config2
        assert config2.environment == Environment.LOCAL_DOCKER  # First config

    def test_get_initializes_if_needed(self):
        """Test get() initializes singleton if not configured."""
        config = EnvironmentConfig.get()

        assert config.environment == Environment.LOCAL_PYTHON
        assert config.stage == 1

    def test_get_returns_existing(self):
        """Test get() returns existing singleton."""
        config1 = EnvironmentConfig.configure(environment="aws-prod", stage=3)
        config2 = EnvironmentConfig.get()

        assert config1 is config2
        assert config2.environment == Environment.AWS_PROD
        assert config2.stage == 3

    def test_reset_clears_singleton(self):
        """Test reset() clears singleton instance."""
        EnvironmentConfig.configure(environment="aws-prod", stage=3)
        EnvironmentConfig.reset()

        # After reset, get() should reinitialize with defaults
        config = EnvironmentConfig.get()
        assert config.environment == Environment.LOCAL_PYTHON
        assert config.stage == 1

    def test_invalid_environment_string(self):
        """Test invalid environment string raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            EnvironmentConfig.configure(environment="invalid")

        assert "Invalid environment" in str(exc_info.value)

    def test_invalid_stage_type(self):
        """Test invalid stage type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            EnvironmentConfig.configure(environment="local-docker", stage="invalid")

        assert "FRANK_STAGE must be an integer" in str(exc_info.value)

    def test_invalid_stage_value(self):
        """Test invalid stage value raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            EnvironmentConfig.configure(environment="local-docker", stage=5)

        assert "stage must be 1-4" in str(exc_info.value)

    def test_stage_boundary_values(self):
        """Test stage boundary values 1-4."""
        for stage in [1, 2, 3, 4]:
            EnvironmentConfig.reset()
            config = EnvironmentConfig.configure(
                environment="local-docker",
                stage=stage
            )
            assert config.stage == stage

    def test_invalid_stage_zero(self):
        """Test stage 0 raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            EnvironmentConfig.configure(environment="local-docker", stage=0)

        assert "stage must be 1-4" in str(exc_info.value)


class TestEnvironmentConfigProperties:
    """Test EnvironmentConfig helper properties."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        EnvironmentConfig.reset()
        yield
        EnvironmentConfig.reset()

    def test_is_local_python(self):
        """Test is_local for LOCAL_PYTHON."""
        config = EnvironmentConfig.configure(environment="local-python")
        assert config.is_local is True
        assert config.is_aws is False
        assert config.is_production is False
        assert config.is_docker is False
        assert config.is_python is True

    def test_is_local_docker(self):
        """Test is_local for LOCAL_DOCKER."""
        config = EnvironmentConfig.configure(environment="local-docker")
        assert config.is_local is True
        assert config.is_aws is False
        assert config.is_production is False
        assert config.is_docker is True
        assert config.is_python is False

    def test_is_aws_dev(self):
        """Test is_aws for AWS_DEV."""
        config = EnvironmentConfig.configure(environment="aws-dev")
        assert config.is_local is False
        assert config.is_aws is True
        assert config.is_production is False
        assert config.is_docker is False
        assert config.is_python is False

    def test_is_aws_preprod(self):
        """Test is_aws for AWS_PREPROD."""
        config = EnvironmentConfig.configure(environment="aws-preprod")
        assert config.is_local is False
        assert config.is_aws is True
        assert config.is_production is False
        assert config.is_docker is False
        assert config.is_python is False

    def test_is_production(self):
        """Test is_production for AWS_PROD."""
        config = EnvironmentConfig.configure(environment="aws-prod")
        assert config.is_local is False
        assert config.is_aws is True
        assert config.is_production is True
        assert config.is_docker is False
        assert config.is_python is False


class TestEnvironmentConfigRepr:
    """Test EnvironmentConfig string representation."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        EnvironmentConfig.reset()
        yield
        EnvironmentConfig.reset()

    def test_repr(self):
        """Test string representation."""
        config = EnvironmentConfig.configure(environment="aws-prod", stage=3)
        repr_str = repr(config)

        assert "EnvironmentConfig" in repr_str
        assert "environment=aws-prod" in repr_str
        assert "stage=3" in repr_str


class TestEnvironmentConfigIntegration:
    """Integration tests for EnvironmentConfig with environment variables."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton before and after each test."""
        EnvironmentConfig.reset()
        yield
        EnvironmentConfig.reset()

    def test_typical_local_python_usage(self, monkeypatch):
        """Test typical local Python development setup."""
        monkeypatch.setenv("FRANK_ENVIRONMENT", "local-python")
        monkeypatch.setenv("FRANK_STAGE", "1")

        config = EnvironmentConfig.get()

        assert config.environment == Environment.LOCAL_PYTHON
        assert config.stage == 1
        assert config.is_local is True
        assert config.is_python is True

    def test_typical_local_docker_usage(self, monkeypatch):
        """Test typical local Docker development setup."""
        monkeypatch.setenv("FRANK_ENVIRONMENT", "local-docker")
        monkeypatch.setenv("FRANK_STAGE", "3")

        config = EnvironmentConfig.get()

        assert config.environment == Environment.LOCAL_DOCKER
        assert config.stage == 3
        assert config.is_local is True
        assert config.is_docker is True

    def test_typical_aws_production_usage(self, monkeypatch):
        """Test typical AWS production setup."""
        monkeypatch.setenv("FRANK_ENVIRONMENT", "aws-prod")
        monkeypatch.setenv("FRANK_STAGE", "3")

        config = EnvironmentConfig.get()

        assert config.environment == Environment.AWS_PROD
        assert config.stage == 3
        assert config.is_aws is True
        assert config.is_production is True

    def test_underscore_env_var_compatibility(self, monkeypatch):
        """Test backward compatibility with underscore format."""
        monkeypatch.setenv("FRANK_ENVIRONMENT", "local_docker")
        monkeypatch.setenv("FRANK_STAGE", "2")

        config = EnvironmentConfig.get()

        assert config.environment == Environment.LOCAL_DOCKER
        assert config.stage == 2
