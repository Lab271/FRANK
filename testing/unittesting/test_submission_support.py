#     def test_enhance_submission(self):
#         """Test submission enhancement functionality."""
#         minimal = self.frank.generate_minimal_submission()
        
#         enhancements = {
#             'submission': {
#                 'sighting': {
#                     'severity': 'critical',
#                     'custom_field': 'custom_value'
#                 },
#                 'custom_section': {
#                     'data': 'test'
#                 }
#             }
#         }
        
#         enhanced = self.frank.enhance_submission(minimal, enhancements)
        
#         # Should have metadata added
#         self.assertIn('metadata', enhanced['submission'])
#         metadata = enhanced['submission']['metadata']
#         self.assertIn('submission_id', metadata)
#         self.assertIn('format_version', metadata)
        
#         # Should have enhanced fields
#         sighting = enhanced['submission']['sighting']
#         self.assertEqual(sighting['severity'], 'critical')
#         self.assertEqual(sighting['custom_field'], 'custom_value')
        
#         # Should have new section
#         self.assertIn('custom_section', enhanced['submission'])
#         self.assertEqual(enhanced['submission']['custom_section']['data'], 'test')
        
#         # Should have default submission method
#         submitter = enhanced['submission']['submitter']
#         self.assertEqual(submitter['submission_method'], 'manual')
    
#     def test_deep_copy(self):
#         """Test deep copy utility method."""
#         original = {
#             'dict': {'nested': 'value'},
#             'list': [1, {'nested_in_list': 'value'}],
#             'simple': 'value'
#         }
        
#         copied = self.frank._deep_copy(original)
        
#         # Should be equal but not the same object
#         self.assertEqual(copied, original)
#         self.assertIsNot(copied, original)
        
#         # Nested objects should also be different
#         self.assertIsNot(copied['dict'], original['dict'])
#         self.assertIsNot(copied['list'], original['list'])
#         self.assertIsNot(copied['list'][1], original['list'][1])
        
#         # Modifying copy shouldn't affect original
#         copied['dict']['nested'] = 'modified'
#         self.assertEqual(original['dict']['nested'], 'value')
    
#     def test_deep_merge(self):
#         """Test deep merge utility method."""
#         base = {
#             'existing': {
#                 'keep': 'original',
#                 'overwrite': 'original'
#             },
#             'simple': 'original'
#         }
        
#         overlay = {
#             'existing': {
#                 'overwrite': 'new',
#                 'add': 'added'
#             },
#             'new_section': 'new'
#         }
        
#         self.frank._deep_merge(base, overlay)
        
#         # Should merge nested dicts
#         self.assertEqual(base['existing']['keep'], 'original')
#         self.assertEqual(base['existing']['overwrite'], 'new')
#         self.assertEqual(base['existing']['add'], 'added')
        
#         # Should add new top-level keys
#         self.assertEqual(base['new_section'], 'new')
        
#         # Simple values should be overwritten
#         self.assertEqual(base['simple'], 'original')
    
#     def test_hash_observable(self):
#         """Test observable hashing functionality."""
#         hash1 = self.frank.hash_observable('ipv4', '192.168.1.1')
#         hash2 = self.frank.hash_observable('ipv4', '192.168.1.1')
#         hash3 = self.frank.hash_observable('ipv4', '192.168.1.2')
#         hash4 = self.frank.hash_observable('domain', '192.168.1.1')
        
#         # Same type and value should produce same hash
#         self.assertEqual(hash1, hash2)
        
#         # Different values should produce different hashes
#         self.assertNotEqual(hash1, hash3)
        
#         # Different types should produce different hashes
#         self.assertNotEqual(hash1, hash4)
        
#         # Should be deterministic
#         self.assertEqual(len(hash1), 64)  # SHA256 hex length
    
#     def test_extract_observables(self):
#         """Test observable extraction functionality."""
#         submission = self.frank.generate_comprehensive_submission(
#             org_id=self.valid_org_id,
#             observables=self.valid_observables
#         )
        
#         extracted = self.frank.extract_observables(submission)
        
#         self.assertEqual(len(extracted), 2)
        
#         # Check structure of extracted observables
#         obs1 = extracted[0]
#         self.assertIn('id', obs1)
#         self.assertIn('type', obs1)
#         self.assertIn('value', obs1)
#         self.assertIn('category', obs1)
#         self.assertIn('hash', obs1)
        
#         # Should have correct category
#         self.assertEqual(obs1['category'], 'network')
        
#         # Hash should be computed
#         expected_hash = self.frank.hash_observable(obs1['type'], obs1['value'])
#         self.assertEqual(obs1['hash'], expected_hash)
    
#     def test_extract_observables_empty_submission(self):
#         """Test observable extraction from submission without observables."""
#         submission = {'submission': {'sighting': {}}}
#         extracted = self.frank.extract_observables(submission)
#         self.assertEqual(len(extracted), 0)

#     def test_normalize_submission(self):
#         """Test submission normalization functionality."""
#         # Create minimal submission
#         submission = self.frank.generate_minimal_submission()
        
#         # Remove some optional fields to test normalization
#         del submission['submission']['sighting']['confidence']
        
#         normalized = self.frank.normalize_submission(submission)
        
#         # Should have defaults filled in
#         sighting = normalized['submission']['sighting']
#         self.assertEqual(sighting['confidence'], 69)  # default
#         self.assertEqual(sighting['severity'], 'medium')  # default
        
#         # Should have metadata
#         self.assertIn('metadata', normalized['submission'])
#         metadata = normalized['submission']['metadata']
#         self.assertIn('format_version', metadata)
#         self.assertIn('submission_id', metadata)
        
#         # Should have IDs for observables
#         observables = normalized['submission']['sighting']['observables']['network']
#         for obs in observables:
#             self.assertIn('id', obs)
    
#     def test_normalize_submission_invalid(self):
#         """Test normalization rejects invalid submissions."""
#         invalid_submission = {"invalid": "structure"}
        
#         with self.assertRaises(FRANKValidationError) as context:
#             self.frank.normalize_submission(invalid_submission)
        
#         self.assertIn("Cannot normalize invalid submission", str(context.exception))
    
#     def test_normalize_submission_timestamp_handling(self):
#         """Test timestamp normalization in submissions."""
#         submission = self.frank.generate_minimal_submission()
        
#         # Test with Z timezone
#         submission['submission']['sighting']['timestamp'] = "2023-01-01T12:00:00Z"
#         normalized = self.frank.normalize_submission(submission)
        
#         # Should be converted to proper ISO format
#         timestamp = normalized['submission']['sighting']['timestamp']
#         self.assertIn("+00:00", timestamp)
        
#         # Test with invalid timestamp
#         submission['submission']['sighting']['timestamp'] = "invalid-timestamp"
#         normalized = self.frank.normalize_submission(submission)
        
#         # Should be replaced with current timestamp
#         timestamp = normalized['submission']['sighting']['timestamp']
#         self.assertIsNotNone(timestamp)