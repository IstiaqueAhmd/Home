"""
Test script to verify the HTTP handler works
"""
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_handler():
    """Test the HTTP handler"""
    try:
        from api.index import handler
        print("✓ Successfully imported handler")
        
        # Check if it's a class and subclass of BaseHTTPRequestHandler
        if isinstance(handler, type):
            print("✓ Handler is a class")
            
            if issubclass(handler, BaseHTTPRequestHandler):
                print("✓ Handler is a subclass of BaseHTTPRequestHandler")
            else:
                print("✗ Handler is not a subclass of BaseHTTPRequestHandler")
                return False
        else:
            print("✗ Handler is not a class")
            return False
        
        print("✓ Handler should work with Vercel!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_handler()
