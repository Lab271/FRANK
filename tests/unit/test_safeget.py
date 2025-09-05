#!/usr/bin/env python3
"""
Unit tests for the _safe_get function.
Tests various default types and None edge cases.
"""

import unittest
from typing import Any

from frank.core.submission import _safe_get

class TestSafeGet(unittest.TestCase):
    """Test cases for _safe_get function."""

    def test_dict_with_existing_key(self):
        """Test accessing existing key in dictionary."""
        test_dict = {'key1': 'value1', 'key2': 42}
        self.assertEqual(_safe_get(test_dict, 'key1'), 'value1')
        self.assertEqual(_safe_get(test_dict, 'key2'), 42)

    def test_dict_with_missing_key_default_none(self):
        """Test accessing missing key with default None."""
        test_dict = {'key1': 'value1'}
        self.assertIsNone(_safe_get(test_dict, 'missing_key'))

    def test_dict_with_missing_key_string_default(self):
        """Test accessing missing key with string default."""
        test_dict = {'key1': 'value1'}
        self.assertEqual(_safe_get(test_dict, 'missing_key', ''), '')
        self.assertEqual(_safe_get(test_dict, 'missing_key', 'default'), 'default')

    def test_dict_with_missing_key_int_default(self):
        """Test accessing missing key with integer default."""
        test_dict = {'key1': 'value1'}
        self.assertEqual(_safe_get(test_dict, 'missing_key', 0), 0)
        self.assertEqual(_safe_get(test_dict, 'missing_key', 42), 42)
        self.assertEqual(_safe_get(test_dict, 'missing_key', -1), -1)

    def test_dict_with_missing_key_dict_default(self):
        """Test accessing missing key with dictionary default."""
        test_dict = {'key1': 'value1'}
        default_dict = {'default': 'value'}
        self.assertEqual(_safe_get(test_dict, 'missing_key', {}), {})
        self.assertEqual(_safe_get(test_dict, 'missing_key', default_dict), default_dict)

    def test_dict_with_missing_key_list_default(self):
        """Test accessing missing key with list default."""
        test_dict = {'key1': 'value1'}
        default_list = ['a', 'b', 'c']
        self.assertEqual(_safe_get(test_dict, 'missing_key', []), [])
        self.assertEqual(_safe_get(test_dict, 'missing_key', default_list), default_list)

    def test_dict_with_none_value(self):
        """Test accessing key that has None as its value."""
        test_dict = {'key1': None, 'key2': 'value2'}
        self.assertIsNone(_safe_get(test_dict, 'key1'))
        self.assertIsNone(_safe_get(test_dict, 'key1', 'default'))

    def test_dict_with_empty_values(self):
        """Test accessing keys with empty values."""
        test_dict = {
            'empty_string': '',
            'empty_list': [],
            'empty_dict': {},
            'zero': 0,
            'false': False
        }
        self.assertEqual(_safe_get(test_dict, 'empty_string'), '')
        self.assertEqual(_safe_get(test_dict, 'empty_list'), [])
        self.assertEqual(_safe_get(test_dict, 'empty_dict'), {})
        self.assertEqual(_safe_get(test_dict, 'zero'), 0)
        self.assertEqual(_safe_get(test_dict, 'false'), False)

    def test_none_object(self):
        """Test passing None as the object."""
        self.assertIsNone(_safe_get(None, 'key'))
        self.assertEqual(_safe_get(None, 'key', 'default'), 'default')
        self.assertEqual(_safe_get(None, 'key', 0), 0)
        self.assertEqual(_safe_get(None, 'key', {}), {})

    def test_non_dict_objects(self):
        """Test passing non-dictionary objects."""
        # String
        self.assertIsNone(_safe_get('not_a_dict', 'key'))
        self.assertEqual(_safe_get('not_a_dict', 'key', 'default'), 'default')
        
        # List
        self.assertIsNone(_safe_get([1, 2, 3], 'key'))
        self.assertEqual(_safe_get([1, 2, 3], 'key', 'default'), 'default')
        
        # Integer
        self.assertIsNone(_safe_get(42, 'key'))
        self.assertEqual(_safe_get(42, 'key', 'default'), 'default')
        
        # Boolean
        self.assertIsNone(_safe_get(True, 'key'))
        self.assertEqual(_safe_get(True, 'key', 'default'), 'default')

    def test_empty_dict(self):
        """Test with empty dictionary."""
        empty_dict = {}
        self.assertIsNone(_safe_get(empty_dict, 'key'))
        self.assertEqual(_safe_get(empty_dict, 'key', 'default'), 'default')
        self.assertEqual(_safe_get(empty_dict, 'key', 0), 0)
        self.assertEqual(_safe_get(empty_dict, 'key', {}), {})

    def test_complex_default_types(self):
        """Test with complex default types."""
        test_dict = {'existing': 'value'}
        
        # Tuple default
        tuple_default = (1, 2, 3)
        self.assertEqual(_safe_get(test_dict, 'missing', tuple_default), tuple_default)
        
        # Set default
        set_default = {1, 2, 3}
        self.assertEqual(_safe_get(test_dict, 'missing', set_default), set_default)
        
        # Function default
        def dummy_func():
            return "hello"
        self.assertEqual(_safe_get(test_dict, 'missing', dummy_func), dummy_func)

    def test_key_edge_cases(self):
        """Test edge cases with keys."""
        test_dict = {
            '': 'empty_string_key',
            None: 'none_key',
            0: 'zero_key',
            True: 'true_key'
        }
        
        # Empty string key
        self.assertEqual(_safe_get(test_dict, ''), 'empty_string_key')
        
        # None as key should work fine - None is hashable
        self.assertEqual(_safe_get(test_dict, None), 'none_key')
        
        # Note: The function signature specifies key: str, but Python doesn't 
        # enforce this at runtime. In practice, any hashable type works as a dict key.

    def test_nested_dict_access(self):
        """Test that function doesn't do nested access - just one level."""
        nested_dict = {
            'level1': {
                'level2': 'deep_value'
            }
        }
        
        # Should get the inner dict, not the deep value
        inner_dict = _safe_get(nested_dict, 'level1')
        self.assertEqual(inner_dict, {'level2': 'deep_value'})
        
        # Missing nested key should return default
        self.assertIsNone(_safe_get(nested_dict, 'missing'))
        self.assertEqual(_safe_get(nested_dict, 'missing', {}), {})

    def test_mutable_default_safety(self):
        """Test that mutable defaults don't cause issues."""
        test_dict = {'key1': 'value1'}
        
        # Get mutable default
        result1 = _safe_get(test_dict, 'missing', {})
        result2 = _safe_get(test_dict, 'missing', {})
        
        # Modify one result
        result1['modified'] = True
        
        # Other result should not be affected (they're different objects)
        self.assertNotEqual(result1, result2)
        self.assertNotIn('modified', result2)

    def test_type_preservation(self):
        """Test that types are preserved correctly."""
        test_dict = {
            'string': 'hello',
            'int': 42,
            'float': 3.14,
            'bool': True,
            'list': [1, 2, 3],
            'dict': {'nested': 'value'},
            'none': None
        }
        
        self.assertIsInstance(_safe_get(test_dict, 'string'), str)
        self.assertIsInstance(_safe_get(test_dict, 'int'), int)
        self.assertIsInstance(_safe_get(test_dict, 'float'), float)
        self.assertIsInstance(_safe_get(test_dict, 'bool'), bool)
        self.assertIsInstance(_safe_get(test_dict, 'list'), list)
        self.assertIsInstance(_safe_get(test_dict, 'dict'), dict)
        self.assertIsNone(_safe_get(test_dict, 'none'))


if __name__ == '__main__':
    unittest.main()