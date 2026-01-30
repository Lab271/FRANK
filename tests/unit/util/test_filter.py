#!/usr/bin/env python3
"""
Tests for FRANK filtering logic.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import pytest
from datetime import datetime, timezone

from frank.core.enum import AccessTier
from frank.util.filter import FRANKFilter


@pytest.fixture
def sample_submission():
    """Create a sample submission dictionary for testing."""
    return {
        'submission_id': 'sub-123',
        'timestamp': '2026-01-30T12:00:00Z',
        'tlp_level': 'amber',
        'sighting': {
            'confidence': 85,
            'timestamp': '2026-01-30T11:00:00Z',
            'observation_count': 5,
            'observables': {
                'network': [
                    {'type': 'ipv4', 'value': '192.168.1.100'},
                    {'type': 'domain', 'value': 'malicious.example.com'}
                ],
                'file': [
                    {'type': 'sha256', 'value': 'a' * 64}
                ]
            }
        },
        'hit_target': {
            'organisation_id': 'org-456',
            'sector': 'finance'
        },
        'submitter': {
            'organisation_id': 'org-789',
            'access_tier': 'PARTNER'
        }
    }


@pytest.fixture
def sample_observable():
    """Create a sample observable summary for testing."""
    return {
        'observable_type': 'ipv4',
        'observable_value': '192.168.1.100',
        'total_sightings': 42,
        'last_seen': '2026-01-30T12:00:00Z',
        'first_seen': '2026-01-01T00:00:00Z',
        'unique_organisations': 5
    }


class TestFRANKFilterSubmission:
    """Tests for submission filtering by access level."""

    def test_public_access_returns_minimal_data(self, sample_submission):
        """Test PUBLIC access returns only basic statistics."""
        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.PUBLIC)

        assert 'submission' in result
        sub = result['submission']

        # Should only have these fields
        assert 'submission_id' in sub
        assert 'timestamp' in sub
        assert 'sighting' in sub

        # Sighting should only have basic stats
        assert 'confidence' in sub['sighting']
        assert 'timestamp' in sub['sighting']
        assert 'observation_count' in sub['sighting']

        # Should NOT have sensitive data
        assert 'hit_target' not in sub
        assert 'submitter' not in sub
        assert 'tlp_level' not in sub
        assert 'observables' not in sub['sighting']

    def test_observer_access_masks_observable_values(self, sample_submission):
        """Test OBSERVER access masks observable values."""
        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.OBSERVER)

        assert 'submission' in result
        sub = result['submission']

        # Should have observables but values masked
        observables = sub['sighting']['observables']
        assert 'network' in observables

        # Check that long values are masked
        network_obs = observables['network']
        for obs in network_obs:
            if len(obs['value']) > 10:
                assert obs['value'].endswith('...')

        # Should NOT have hit_target or tlp_level
        assert 'hit_target' not in sub
        assert 'tlp_level' not in sub

    def test_observer_access_masks_short_values_unchanged(self, sample_submission):
        """Test OBSERVER access keeps short values unchanged."""
        # Add a short observable value
        sample_submission['sighting']['observables']['network'].append({
            'type': 'port',
            'value': '443'
        })

        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.OBSERVER)

        network_obs = result['submission']['sighting']['observables']['network']
        # Find the port observable
        port_obs = [o for o in network_obs if o.get('type') == 'port'][0]

        # Short values should not be masked
        assert port_obs['value'] == '443'

    def test_contributor_access_anonymizes_hit_target(self, sample_submission):
        """Test CONTRIBUTOR access anonymizes hit target."""
        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.CONTRIBUTOR)

        assert 'submission' in result
        sub = result['submission']

        # Should have hit_target but with anonymized org_id
        assert 'hit_target' in sub
        assert 'organisation_id' not in sub['hit_target']
        assert 'sector' in sub['hit_target']

        # Should have full observable values
        observables = sub['sighting']['observables']
        assert len(observables['network'][0]['value']) > 10  # Not masked

    def test_contributor_access_with_missing_hit_target(self, sample_submission):
        """Test CONTRIBUTOR access handles missing hit_target."""
        del sample_submission['hit_target']

        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.CONTRIBUTOR)

        # Should not error, just no hit_target in result
        assert 'submission' in result
        assert 'hit_target' not in result['submission']

    def test_partner_access_returns_full_data(self, sample_submission):
        """Test PARTNER access returns full unfiltered data."""
        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.PARTNER)

        assert 'submission' in result
        sub = result['submission']

        # Should have all fields unchanged
        assert sub['submission_id'] == 'sub-123'
        assert 'hit_target' in sub
        assert sub['hit_target']['organisation_id'] == 'org-456'
        assert 'tlp_level' in sub
        assert sub['sighting']['observables']['network'][0]['value'] == '192.168.1.100'

    def test_core_member_access_returns_full_data(self, sample_submission):
        """Test CORE_MEMBER access returns full unfiltered data."""
        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.CORE_MEMBER)

        assert 'submission' in result
        sub = result['submission']

        # Should have all fields unchanged
        assert sub == sample_submission


class TestFRANKFilterObservable:
    """Tests for observable filtering by access level."""

    def test_public_access_returns_minimal_observable(self, sample_observable):
        """Test PUBLIC access returns only basic statistics."""
        filter_obj = FRANKFilter()
        result = filter_obj.filter_observable_by_access_level(sample_observable, AccessTier.PUBLIC)

        # Should only have these fields
        assert 'observable_type' in result
        assert 'total_sightings' in result
        assert 'last_seen' in result

        # Should NOT have these fields
        assert 'observable_value' not in result
        assert 'first_seen' not in result
        assert 'unique_organisations' not in result

    def test_observer_access_masks_observable_value(self, sample_observable):
        """Test OBSERVER access masks observable value."""
        filter_obj = FRANKFilter()
        result = filter_obj.filter_observable_by_access_level(sample_observable, AccessTier.OBSERVER)

        # Should have all fields but value masked
        assert 'observable_type' in result
        assert 'observable_value' in result
        assert 'total_sightings' in result

        # Value should be masked
        assert result['observable_value'].endswith('...')

    def test_observer_access_short_value_unchanged(self):
        """Test OBSERVER access keeps short values unchanged."""
        short_observable = {
            'observable_type': 'port',
            'observable_value': '443',
            'total_sightings': 10,
            'last_seen': '2026-01-30T12:00:00Z'
        }

        filter_obj = FRANKFilter()
        result = filter_obj.filter_observable_by_access_level(short_observable, AccessTier.OBSERVER)

        # Short value should not be masked
        assert result['observable_value'] == '443'

    def test_contributor_access_returns_full_observable(self, sample_observable):
        """Test CONTRIBUTOR access returns full observable data."""
        filter_obj = FRANKFilter()
        result = filter_obj.filter_observable_by_access_level(sample_observable, AccessTier.CONTRIBUTOR)

        # Should return unmodified observable
        assert result == sample_observable

    def test_partner_access_returns_full_observable(self, sample_observable):
        """Test PARTNER access returns full observable data."""
        filter_obj = FRANKFilter()
        result = filter_obj.filter_observable_by_access_level(sample_observable, AccessTier.PARTNER)

        assert result == sample_observable

    def test_core_member_access_returns_full_observable(self, sample_observable):
        """Test CORE_MEMBER access returns full observable data."""
        filter_obj = FRANKFilter()
        result = filter_obj.filter_observable_by_access_level(sample_observable, AccessTier.CORE_MEMBER)

        assert result == sample_observable


class TestDeepCopy:
    """Tests for the _deep_copy utility method."""

    def test_deep_copy_dict(self):
        """Test deep copy of dictionary."""
        filter_obj = FRANKFilter()
        original = {'a': 1, 'b': {'c': 2}}
        copied = filter_obj._deep_copy(original)

        # Should be equal but not same object
        assert copied == original
        assert copied is not original
        assert copied['b'] is not original['b']

    def test_deep_copy_list(self):
        """Test deep copy of list."""
        filter_obj = FRANKFilter()
        original = [1, 2, [3, 4]]
        copied = filter_obj._deep_copy(original)

        # Should be equal but not same object
        assert copied == original
        assert copied is not original
        assert copied[2] is not original[2]

    def test_deep_copy_nested_structure(self):
        """Test deep copy of nested structure."""
        filter_obj = FRANKFilter()
        original = {
            'list': [1, 2, {'nested': 'value'}],
            'dict': {'inner': [3, 4]}
        }
        copied = filter_obj._deep_copy(original)

        # Modify copy
        copied['list'][2]['nested'] = 'modified'
        copied['dict']['inner'].append(5)

        # Original should be unchanged
        assert original['list'][2]['nested'] == 'value'
        assert len(original['dict']['inner']) == 2

    def test_deep_copy_primitives(self):
        """Test deep copy returns primitives unchanged."""
        filter_obj = FRANKFilter()

        assert filter_obj._deep_copy(42) == 42
        assert filter_obj._deep_copy('text') == 'text'
        assert filter_obj._deep_copy(3.14) == 3.14
        assert filter_obj._deep_copy(True) is True


class TestFormatSightingResponse:
    """Tests for sighting response formatting."""

    @pytest.fixture
    def sample_sighting_result(self):
        """Sample sighting query result."""
        return {
            'observable_hash': 'abc123def456',
            'observable_type': 'ipv4',
            'observable_value': '192.168.1.100',
            'last_seen': '2026-01-30T12:00:00Z',
            'first_seen': '2026-01-01T00:00:00Z',
            'avg_confidence': 75,
            'total_sightings': 42,
            'unique_organisations': 5,
            'sectors': ['finance', 'healthcare'],
            'regions': ['eu', 'us']
        }

    def test_observer_sighting_response_masks_data(self, sample_sighting_result):
        """Test OBSERVER gets masked sighting response."""
        filter_obj = FRANKFilter()
        result = filter_obj.format_sighting_response(
            sample_sighting_result,
            AccessTier.OBSERVER,
            'json'
        )

        assert 'sighting_id' in result
        assert result['sighting_id'].startswith('sighting-masked-')
        assert 'observable_value' in result
        assert result['observable_value'] == '192.168.1.***'
        assert result['geographic_region'] == 'masked'

        # Should not have detailed fields
        assert 'unique_organisations' not in result
        assert 'sectors' not in result

    def test_contributor_sighting_response_partial_data(self, sample_sighting_result):
        """Test CONTRIBUTOR gets partial sighting response."""
        filter_obj = FRANKFilter()
        result = filter_obj.format_sighting_response(
            sample_sighting_result,
            AccessTier.CONTRIBUTOR,
            'json'
        )

        assert 'sighting_id' in result
        assert result['sighting_id'].startswith('sighting-abc123')
        assert 'observable' in result
        assert result['observable']['value'] == '192.168.1.100'
        assert 'total_sightings' in result
        assert 'sectors' in result

        # Should not have some fields
        assert 'unique_organisations' not in result
        assert 'regions' not in result

    def test_partner_sighting_response_full_data(self, sample_sighting_result):
        """Test PARTNER gets full sighting response."""
        filter_obj = FRANKFilter()
        result = filter_obj.format_sighting_response(
            sample_sighting_result,
            AccessTier.PARTNER,
            'json'
        )

        assert 'sighting_id' in result
        assert 'observable' in result
        assert 'total_sightings' in result
        assert 'unique_organisations' in result
        assert 'first_seen' in result
        assert 'sectors' in result
        assert 'regions' in result

    def test_core_member_sighting_response_full_data(self, sample_sighting_result):
        """Test CORE_MEMBER gets full sighting response."""
        filter_obj = FRANKFilter()
        result = filter_obj.format_sighting_response(
            sample_sighting_result,
            AccessTier.CORE_MEMBER,
            'json'
        )

        # Should have all fields
        assert result['observable']['value'] == '192.168.1.100'
        assert result['unique_organisations'] == 5


class TestMaskObservableValue:
    """Tests for observable value masking."""

    def test_mask_ipv4_address(self):
        """Test masking IPv4 addresses."""
        filter_obj = FRANKFilter()
        result = filter_obj._mask_observable_value('192.168.1.100', 'ipv4')

        assert result == '192.168.1.***'

    def test_mask_invalid_ipv4(self):
        """Test masking invalid IPv4 returns original."""
        filter_obj = FRANKFilter()
        result = filter_obj._mask_observable_value('not.an.ip', 'ipv4')

        # Not a valid IP with 4 parts, should return as-is (short string)
        assert result == 'not.an.ip'

    def test_mask_domain(self):
        """Test masking domain names."""
        filter_obj = FRANKFilter()
        result = filter_obj._mask_observable_value('malicious.example.com', 'domain')

        # Half should be masked
        assert result.startswith('*')
        assert result.endswith('ample.com')

    def test_mask_long_generic_value(self):
        """Test masking long generic values."""
        filter_obj = FRANKFilter()
        long_value = 'a' * 64
        result = filter_obj._mask_observable_value(long_value, 'sha256')

        assert result == 'a' * 10 + '...'

    def test_mask_short_generic_value(self):
        """Test short values returned unchanged."""
        filter_obj = FRANKFilter()
        result = filter_obj._mask_observable_value('443', 'port')

        assert result == '443'


class TestFRANKFilterWithLogger:
    """Tests for FRANKFilter with custom logger."""

    def test_filter_with_custom_logger(self, sample_submission):
        """Test filter can use custom logger."""
        import logging
        logger = logging.getLogger('test')

        filter_obj = FRANKFilter(logger=logger)
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.PUBLIC)

        assert 'submission' in result
        assert filter_obj.logger == logger

    def test_filter_with_null_logger(self, sample_submission):
        """Test filter works with default NullLogger."""
        filter_obj = FRANKFilter()
        result = filter_obj.submission_by_access_level(sample_submission, AccessTier.PUBLIC)

        assert 'submission' in result
        # Should not raise any errors even though logger is called
