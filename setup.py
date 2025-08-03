#!/usr/bin/env python3
"""
House Finance Tracker - Setup and Configuration Script
This script helps set up the application and configure the database.
"""

import asyncio
import os
import sys
from getpass import getpass
from dotenv import load_dotenv

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import Database
from models import UserCreate
from auth import AuthManager

async def setup_database():
    """Initialize the database and create indexes for better performance."""
    print("🔧 Setting up database...")
    
    db = Database()
    await db.connect_to_mongo()
    
    # Get the database instance
    database = await db.get_database()
    
    # Create indexes for better performance
    await database.users.create_index("username", unique=True)
    await database.users.create_index("email", unique=True)
    await database.contributions.create_index("username")
    await database.contributions.create_index("date_created")
    
    print("✅ Database setup completed!")
    return db

async def create_admin_user(db: Database):
    """Create an admin user if none exists."""
    print("\n👤 Setting up admin user...")
    
    # Check if any users exist
    database = await db.get_database()
    user_count = await database.users.count_documents({})
    
    if user_count > 0:
        print("ℹ️  Users already exist in the database. Skipping admin user creation.")
        return
    
    print("No users found. Let's create the first admin user:")
    
    username = input("Enter admin username: ").strip()
    if not username:
        print("❌ Username cannot be empty!")
        return
    
    email = input("Enter admin email: ").strip()
    if not email:
        print("❌ Email cannot be empty!")
        return
    
    full_name = input("Enter full name: ").strip()
    if not full_name:
        print("❌ Full name cannot be empty!")
        return
    
    password = getpass("Enter password: ").strip()
    if len(password) < 6:
        print("❌ Password must be at least 6 characters long!")
        return
    
    confirm_password = getpass("Confirm password: ").strip()
    if password != confirm_password:
        print("❌ Passwords do not match!")
        return
    
    try:
        user_create = UserCreate(
            username=username,
            email=email,
            full_name=full_name,
            password=password
        )
        
        user = await db.create_user(user_create)
        print(f"✅ Admin user '{username}' created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")

def check_environment():
    """Check if environment variables are properly configured."""
    print("🔍 Checking environment configuration...")
    
    load_dotenv()
    
    required_vars = [
        "MONGODB_URL",
        "DATABASE_NAME", 
        "SECRET_KEY",
        "ALGORITHM",
        "ACCESS_TOKEN_EXPIRE_MINUTES"
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print("❌ Missing environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        return False
    
    print("✅ Environment configuration looks good!")
    return True

async def test_database_connection():
    """Test the database connection."""
    print("🔗 Testing database connection...")
    
    try:
        db = Database()
        await db.connect_to_mongo()
        
        # Try a simple operation
        database = await db.get_database()
        await database.users.count_documents({})
        
        await db.close_mongo_connection()
        print("✅ Database connection successful!")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print("Please check your MongoDB configuration and ensure MongoDB is running.")
        return False

def print_banner():
    """Print application banner."""
    print("""
🏠 House Finance Tracker Setup
================================
Welcome to the House Finance Tracker setup wizard!
This will help you configure your application.
    """)

def print_completion_message():
    """Print setup completion message."""
    print("""
🎉 Setup Complete!
==================
Your House Finance Tracker is now ready to use.

To start the application:
1. Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
2. Open your browser to: http://localhost:8000
3. Login with your admin credentials

Enjoy tracking your house finances! 🏡💰
    """)

async def main():
    """Main setup function."""
    print_banner()
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Test database connection
    if not await test_database_connection():
        sys.exit(1)
    
    # Setup database
    db = await setup_database()
    
    # Create admin user
    await create_admin_user(db)
    
    # Close database connection
    await db.close_mongo_connection()
    
    print_completion_message()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n❌ Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Setup failed: {e}")
        sys.exit(1)
