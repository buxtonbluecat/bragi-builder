#!/usr/bin/env python3
"""
Test script to verify Bragi Builder setup
"""
import sys
import json
from pathlib import Path

def test_imports():
    """Test that all modules can be imported"""
    try:
        from src.azure_client import AzureClient
        from src.template_manager import TemplateManager
        from src.deployment_manager import DeploymentManager
        print("✓ All modules imported successfully")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_templates():
    """Test that templates can be loaded"""
    try:
        from src.template_manager import TemplateManager
        tm = TemplateManager()
        templates = tm.list_templates()
        print(f"✓ Found {len(templates)} templates: {', '.join(templates)}")
        
        # Test loading each template
        for template_name in templates:
            template = tm.get_template(template_name)
            if template:
                validation = tm.validate_template(template)
                status = "valid" if validation['valid'] else "invalid"
                print(f"  - {template_name}: {status}")
            else:
                print(f"  - {template_name}: failed to load")
        
        return True
    except Exception as e:
        print(f"✗ Template error: {e}")
        return False

def test_azure_client():
    """Test Azure client initialization (without credentials)"""
    try:
        # This will fail without proper credentials, but we can test the structure
        from src.azure_client import AzureClient
        print("✓ Azure client module loaded")
        return True
    except Exception as e:
        print(f"✗ Azure client error: {e}")
        return False

def main():
    """Run all tests"""
    print("Testing Bragi Builder setup...")
    print("=" * 40)
    
    tests = [
        ("Module Imports", test_imports),
        ("Template Loading", test_templates),
        ("Azure Client", test_azure_client),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        if test_func():
            passed += 1
        else:
            print(f"  Test failed!")
    
    print("\n" + "=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! Bragi Builder is ready to use.")
        print("\nNext steps:")
        print("1. Set up Azure credentials (see env.example)")
        print("2. Run 'python app.py' to start the web interface")
        print("3. Or use 'python cli.py --help' for command line usage")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)

if __name__ == '__main__':
    main()
