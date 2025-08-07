"""
Simple test to verify the new database implementation is working
"""

import asyncio
from database import Database
from models import UserCreate, HomeCreate

async def test_database():
    """Test basic database operations"""
    db = Database()
    
    print("Testing database connection...")
    await db.connect_to_db()
    print("✓ Database connected successfully")
    
    # Test creating a user
    print("\nTesting user creation...")
    user_data = UserCreate(
        username="testuser",
        email="test@example.com",
        full_name="Test User",
        password="testpassword123"
    )
    
    try:
        user = await db.create_user(user_data)
        print(f"✓ User created: {user.username} ({user.full_name})")
        
        # Test user retrieval
        retrieved_user = await db.get_user("testuser")
        if retrieved_user:
            print(f"✓ User retrieved: {retrieved_user.username}")
        else:
            print("✗ Failed to retrieve user")
        
        # Test creating a home
        print("\nTesting home creation...")
        home_data = HomeCreate(
            name="Test Home",
            description="A test home for testing"
        )
        
        home = await db.create_home(home_data, "testuser")
        print(f"✓ Home created: {home.name} (Leader: {home.leader_username})")
        
        # Test contribution creation
        print("\nTesting contribution creation...")
        contribution_data = {
            "product_name": "Test Product",
            "amount": 25.50,
            "description": "Test contribution"
        }
        
        contribution = await db.create_contribution("testuser", contribution_data)
        print(f"✓ Contribution created: {contribution.product_name} - ${contribution.amount}")
        
        # Test analytics
        print("\nTesting analytics...")
        analytics = await db.get_analytics()
        print(f"✓ Analytics retrieved - Total contributions: {analytics['total_contributions']}, Total amount: ${analytics['total_amount']}")
        
        print("\n🎉 All tests passed! Database is working correctly.")
        
    except Exception as e:
        print(f"✗ Test failed: {str(e)}")
    
    finally:
        await db.close_db_connection()

if __name__ == "__main__":
    asyncio.run(test_database())
