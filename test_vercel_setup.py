#!/usr/bin/env python3
"""
Quick test script to verify the Vercel deployment setup
"""

import sys
import os

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def test_imports():
    """Test that all required modules can be imported"""
    try:
        print("Testing imports...")
        
        # Test main app import
        from src.main import app
        print("✅ Main app imported successfully")
        
        # Test that static and template directories exist
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        static_dir = os.path.join(project_root, "static")
        templates_dir = os.path.join(project_root, "templates")
        
        if os.path.exists(static_dir):
            print("✅ Static directory found")
        else:
            print("❌ Static directory not found")
            
        if os.path.exists(templates_dir):
            print("✅ Templates directory found")
        else:
            print("❌ Templates directory not found")
            
        # Test API entry point
        from api.index import app as api_app
        print("✅ API entry point imported successfully")
        
        print("\n🎉 All tests passed! Your app should deploy successfully to Vercel.")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_imports()
    sys.exit(0 if success else 1)
