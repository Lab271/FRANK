#!/usr/bin/env python3
"""
Quick CloudFormation template YAML syntax validator for Cognito UserPool
"""

import yaml
import json
import sys

def validate_cognito_section():
    try:
        with open('stages/stage3/ansible/templates/frank-stage3-infra.yaml', 'r') as f:
            template = yaml.safe_load(f)
        
        # Find the CognitoUserPool resource
        cognito_pool = template['Resources']['CognitoUserPool']['Properties']
        
        print("=== Cognito UserPool Configuration ===")
        print(f"AutoVerifiedAttributes: {cognito_pool.get('AutoVerifiedAttributes')}")
        print(f"Type: {type(cognito_pool.get('AutoVerifiedAttributes'))}")
        
        update_settings = cognito_pool.get('UserAttributeUpdateSettings', {})
        attr_verification = update_settings.get('AttributesRequireVerificationBeforeUpdate')
        print(f"AttributesRequireVerificationBeforeUpdate: {attr_verification}")
        print(f"Type: {type(attr_verification)}")
        
        # Find the CognitoUserPoolClient resource
        client_pool = template['Resources']['CognitoUserPoolClient']['Properties']
        print(f"\nReadAttributes: {client_pool.get('ReadAttributes')}")
        print(f"Type: {type(client_pool.get('ReadAttributes'))}")
        print(f"WriteAttributes: {client_pool.get('WriteAttributes')}")
        print(f"Type: {type(client_pool.get('WriteAttributes'))}")
        
        # Check if all arrays contain only strings
        def check_string_array(arr, name):
            if isinstance(arr, list):
                for item in arr:
                    if not isinstance(item, str):
                        print(f"ERROR: {name} contains non-string item: {item} (type: {type(item)})")
                        return False
                print(f"✅ {name} is valid string array")
                return True
            else:
                print(f"ERROR: {name} is not a list: {arr} (type: {type(arr)})")
                return False
        
        # Validate arrays
        valid = True
        valid &= check_string_array(cognito_pool.get('AutoVerifiedAttributes'), 'AutoVerifiedAttributes')
        valid &= check_string_array(attr_verification, 'AttributesRequireVerificationBeforeUpdate')
        valid &= check_string_array(client_pool.get('ReadAttributes'), 'ReadAttributes')
        valid &= check_string_array(client_pool.get('WriteAttributes'), 'WriteAttributes')
        
        if valid:
            print("\n✅ All Cognito configuration arrays are valid!")
        else:
            print("\n❌ Found validation errors in Cognito configuration")
            return False
            
        return True
        
    except Exception as e:
        print(f"Error validating template: {e}")
        return False

if __name__ == "__main__":
    success = validate_cognito_section()
    sys.exit(0 if success else 1)