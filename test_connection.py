import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import ssl

async def test_connection():
    print("🔄 Testing MongoDB connection...")
    
    # Try different connection approaches
    connection_strings = [
        # Approach 1: Let mongodb+srv handle SSL automatically 
        "mongodb+srv://istiaqueahmd:1234@cluster0.tbnplj9.mongodb.net/house_finance_tracker?retryWrites=true&w=majority&appName=Cluster0",
        
        # Approach 2: Explicit SSL parameters
        "mongodb+srv://istiaqueahmd:1234@cluster0.tbnplj9.mongodb.net/house_finance_tracker?retryWrites=true&w=majority&appName=Cluster0&ssl=true&tlsAllowInvalidCertificates=true",
        
        # Approach 3: Alternative SSL parameters
        "mongodb+srv://istiaqueahmd:1234@cluster0.tbnplj9.mongodb.net/house_finance_tracker?retryWrites=true&w=majority&appName=Cluster0&tls=true"
    ]
    
    for i, conn_str in enumerate(connection_strings, 1):
        try:
            print(f"\n🔄 Approach {i}: Testing connection...")
            
            client = AsyncIOMotorClient(
                conn_str,
                serverSelectionTimeoutMS=10000,
                connectTimeoutMS=10000,
                socketTimeoutMS=10000
            )
            
            print("🔄 Attempting to ping MongoDB server...")
            await client.admin.command('ping')
            print(f"✅ Approach {i} successful!")
            
            # Test database access
            db = client.house_finance_tracker
            count = await db.users.count_documents({})
            print(f"✅ Database accessible. Users count: {count}")
            
            client.close()
            return  # Exit on first successful connection
            
        except Exception as e:
            print(f"❌ Approach {i} failed: {e}")
            if 'client' in locals():
                client.close()
    
    print("\n❌ All connection approaches failed")

if __name__ == "__main__":
    asyncio.run(test_connection())
