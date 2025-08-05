"""
Test script to verify the WSGI application works
"""
import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

def test_wsgi_app():
    """Test the WSGI application"""
    try:
        from api.index import app
        print("✓ Successfully imported WSGI app")
        
        # Test environ for root path
        environ = {
            'REQUEST_METHOD': 'GET',
            'PATH_INFO': '/',
            'QUERY_STRING': ''
        }
        
        def start_response(status, headers):
            print(f"✓ Status: {status}")
            print(f"✓ Headers: {headers}")
        
        response = app(environ, start_response)
        print(f"✓ Response: {response}")
        
        # Test health endpoint
        environ['PATH_INFO'] = '/health'
        response = app(environ, start_response)
        print(f"✓ Health response: {response}")
        
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_wsgi_app()
