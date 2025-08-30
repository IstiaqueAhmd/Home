import os
import asyncio
from databases import Database as AsyncDatabase
import asyncpg
from typing import Optional, List
from models import User, UserCreate, UserInDB, Contribution, Transfer, TransferCreate, Home, HomeCreate
from auth import AuthManager
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables with explicit path
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(env_path)

# Also try loading from current directory
load_dotenv()

class Database:
    def __init__(self):
        self.postgres_url = os.getenv("POSTGRES_URL")
        self.database = None
        self.auth_manager = AuthManager()
        
        # Debug: Print loaded environment variables (without password)
        if not self.postgres_url:
            print("ERROR: POSTGRES_URL environment variable is not set")
        else:
            # Print URL without password for debugging
            safe_url = self.postgres_url.replace(self.postgres_url.split('://')[1].split('@')[0], "***:***")
            print(f"PostgreSQL URL loaded: {safe_url}")
    
    async def connect_to_postgres(self):
        """Connect to PostgreSQL database"""
        if not self.postgres_url:
            raise ValueError("PostgreSQL connection URL not set")
        
        try:
            self.database = AsyncDatabase(self.postgres_url)
            await self.database.connect()
            print("PostgreSQL connection successful")
            
            # Create tables if they don't exist
            await self.create_tables()
            
        except Exception as e:
            print(f"PostgreSQL connection failed: {str(e)}")
            raise e

    async def close_postgres_connection(self):
        if self.database:
            await self.database.disconnect()
    
    async def get_database(self):
        try:
            if self.database is None:
                await self.connect_to_postgres()
            return self.database
        except Exception as e:
            print(f"Database access error: {str(e)}")
            raise e
    
    async def create_tables(self):
        """Create all required tables"""
        db = await self.get_database()
        
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                full_name VARCHAR(100) NOT NULL,
                hashed_password VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                home_id INTEGER,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Homes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS homes (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) UNIQUE NOT NULL,
                description TEXT,
                leader_username VARCHAR(50) NOT NULL,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Contributions table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS contributions (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                home_id INTEGER,
                product_name VARCHAR(200) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                description TEXT,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Transfers table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transfers (
                id SERIAL PRIMARY KEY,
                sender_username VARCHAR(50) NOT NULL,
                recipient_username VARCHAR(50) NOT NULL,
                home_id INTEGER NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                description TEXT,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Join requests table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS join_requests (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                home_id INTEGER NOT NULL,
                home_name VARCHAR(100) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_processed TIMESTAMP
            )
        """)
        
        # Home members table (for tracking home membership)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS home_members (
                id SERIAL PRIMARY KEY,
                home_id INTEGER NOT NULL,
                username VARCHAR(50) NOT NULL,
                date_joined TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(home_id, username)
            )
        """)
        
        # Create indexes for better performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_contributions_username ON contributions(username)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_contributions_home_id ON contributions(home_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_transfers_sender ON transfers(sender_username)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_transfers_recipient ON transfers(recipient_username)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_join_requests_status ON join_requests(status)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_home_members_home_id ON home_members(home_id)")
    
    async def create_user(self, user: UserCreate) -> UserInDB:
        db = await self.get_database()
        
        hashed_password = self.auth_manager.get_password_hash(user.password)
        
        try:
            query = """
                INSERT INTO users (username, email, full_name, hashed_password, is_active, date_created)
                VALUES (:username, :email, :full_name, :hashed_password, :is_active, :date_created)
                RETURNING id, username, email, full_name, hashed_password, is_active, home_id, date_created
            """
            values = {
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "hashed_password": hashed_password,
                "is_active": True,
                "date_created": datetime.utcnow()
            }
            
            result = await db.fetch_one(query, values)
            return UserInDB(
                id=str(result["id"]),
                username=result["username"],
                email=result["email"],
                full_name=result["full_name"],
                hashed_password=result["hashed_password"],
                is_active=result["is_active"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                date_created=result["date_created"]
            )
        except asyncpg.UniqueViolationError:
            raise ValueError("User already exists")
    
    async def get_user(self, username: str) -> Optional[UserInDB]:
        db = await self.get_database()
        query = "SELECT * FROM users WHERE username = :username"
        result = await db.fetch_one(query, {"username": username})
        
        if result:
            return UserInDB(
                id=str(result["id"]),
                username=result["username"],
                email=result["email"],
                full_name=result["full_name"],
                hashed_password=result["hashed_password"],
                is_active=result["is_active"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                date_created=result["date_created"]
            )
        return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        db = await self.get_database()
        query = "SELECT * FROM users WHERE email = :email"
        result = await db.fetch_one(query, {"email": email})
        
        if result:
            return UserInDB(
                id=str(result["id"]),
                username=result["username"],
                email=result["email"],
                full_name=result["full_name"],
                hashed_password=result["hashed_password"],
                is_active=result["is_active"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                date_created=result["date_created"]
            )
        return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[UserInDB]:
        user = await self.get_user(username)
        if not user:
            return None
        if not self.auth_manager.verify_password(password, user.hashed_password):
            return None
        return user
    
    async def create_contribution(self, username: str, contribution_data: dict) -> Contribution:
        db = await self.get_database()
        
        # Get user's home_id
        user = await self.get_user(username)
        if not user or not user.home_id:
            raise ValueError("User must belong to a home to create contributions")
        
        query = """
            INSERT INTO contributions (username, home_id, product_name, amount, description, date_created)
            VALUES (:username, :home_id, :product_name, :amount, :description, :date_created)
            RETURNING id, username, home_id, product_name, amount, description, date_created
        """
        values = {
            "username": username,
            "home_id": int(user.home_id),
            "product_name": contribution_data["product_name"],
            "amount": contribution_data["amount"],
            "description": contribution_data.get("description", ""),
            "date_created": datetime.utcnow()
        }
        
        result = await db.fetch_one(query, values)
        return Contribution(
            id=str(result["id"]),
            username=result["username"],
            home_id=str(result["home_id"]),
            product_name=result["product_name"],
            amount=float(result["amount"]),
            description=result["description"],
            date_created=result["date_created"]
        )
    
    async def get_user_contributions(self, username: str) -> List[Contribution]:
        db = await self.get_database()
        query = "SELECT * FROM contributions WHERE username = :username ORDER BY date_created DESC"
        results = await db.fetch_all(query, {"username": username})
        
        contributions = []
        for result in results:
            contributions.append(Contribution(
                id=str(result["id"]),
                username=result["username"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                product_name=result["product_name"],
                amount=float(result["amount"]),
                description=result["description"],
                date_created=result["date_created"]
            ))
        
        return contributions

    async def get_home_contributions(self, home_id: str) -> List[Contribution]:
        db = await self.get_database()
        query = "SELECT * FROM contributions WHERE home_id = :home_id ORDER BY date_created DESC"
        results = await db.fetch_all(query, {"home_id": int(home_id)})
        
        contributions = []
        for result in results:
            contributions.append(Contribution(
                id=str(result["id"]),
                username=result["username"],
                home_id=str(result["home_id"]),
                product_name=result["product_name"],
                amount=float(result["amount"]),
                description=result["description"],
                date_created=result["date_created"]
            ))
        
        return contributions
    
    async def get_all_contributions(self) -> List[Contribution]:
        db = await self.get_database()
        query = "SELECT * FROM contributions ORDER BY date_created DESC"
        results = await db.fetch_all(query)
        
        contributions = []
        for result in results:
            contributions.append(Contribution(
                id=str(result["id"]),
                username=result["username"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                product_name=result["product_name"],
                amount=float(result["amount"]),
                description=result["description"],
                date_created=result["date_created"]
            ))
        
        return contributions
    
    async def get_all_contributions_with_users(self) -> List[dict]:
        db = await self.get_database()
        query = """
            SELECT c.*, u.full_name as user_full_name
            FROM contributions c
            JOIN users u ON c.username = u.username
            ORDER BY c.date_created DESC
        """
        results = await db.fetch_all(query)
        
        contributions = []
        for result in results:
            contributions.append({
                "id": str(result["id"]),
                "username": result["username"],
                "home_id": str(result["home_id"]) if result["home_id"] else "",
                "product_name": result["product_name"],
                "amount": float(result["amount"]),
                "description": result["description"],
                "date_created": result["date_created"],
                "user_full_name": result["user_full_name"]
            })
        
        return contributions

    async def get_home_contributions_with_users(self, home_id: str) -> List[dict]:
        db = await self.get_database()
        query = """
            SELECT c.*, u.full_name as user_full_name
            FROM contributions c
            JOIN users u ON c.username = u.username
            WHERE c.home_id = :home_id
            ORDER BY c.date_created DESC
        """
        results = await db.fetch_all(query, {"home_id": int(home_id)})
        
        contributions = []
        for result in results:
            contributions.append({
                "id": str(result["id"]),
                "username": result["username"],
                "home_id": str(result["home_id"]),
                "product_name": result["product_name"],
                "amount": float(result["amount"]),
                "description": result["description"],
                "date_created": result["date_created"],
                "user_full_name": result["user_full_name"]
            })
        
        return contributions
    
    async def delete_contribution(self, contribution_id: str, username: str) -> bool:
        db = await self.get_database()
        
        query = "DELETE FROM contributions WHERE id = :id AND username = :username"
        result = await db.execute(query, {"id": int(contribution_id), "username": username})
        
        return result > 0
    
    async def get_analytics(self) -> dict:
        db = await self.get_database()
        
        # Total contributions
        total_contributions_query = "SELECT COUNT(*) as count FROM contributions"
        total_contributions_result = await db.fetch_one(total_contributions_query)
        total_contributions = total_contributions_result["count"]
        
        # Total amount
        total_amount_query = "SELECT COALESCE(SUM(amount), 0) as total FROM contributions"
        total_amount_result = await db.fetch_one(total_amount_query)
        total_amount = float(total_amount_result["total"])
        
        # Contributions by user
        contributions_by_user_query = """
            SELECT 
                c.username,
                u.full_name,
                COALESCE(SUM(c.amount), 0) as total_amount,
                COUNT(c.id) as count
            FROM contributions c
            JOIN users u ON c.username = u.username
            GROUP BY c.username, u.full_name
            ORDER BY total_amount DESC
        """
        contributions_by_user_results = await db.fetch_all(contributions_by_user_query)
        contributions_by_user = [
            {
                "username": result["username"],
                "full_name": result["full_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in contributions_by_user_results
        ]
        
        # Contributions by product (excluding fund transfers)
        contributions_by_product_query = """
            SELECT 
                product_name,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(id) as count
            FROM contributions
            WHERE product_name NOT LIKE 'Fund transfer%' AND product_name NOT LIKE 'Fund received%'
            GROUP BY product_name
            ORDER BY total_amount DESC
        """
        contributions_by_product_results = await db.fetch_all(contributions_by_product_query)
        contributions_by_product = [
            {
                "product_name": result["product_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in contributions_by_product_results
        ]
        
        # Monthly contributions
        monthly_contributions_query = """
            SELECT 
                EXTRACT(YEAR FROM date_created) as year,
                EXTRACT(MONTH FROM date_created) as month,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(id) as count
            FROM contributions
            GROUP BY EXTRACT(YEAR FROM date_created), EXTRACT(MONTH FROM date_created)
            ORDER BY year DESC, month DESC
        """
        monthly_contributions_results = await db.fetch_all(monthly_contributions_query)
        monthly_contributions = [
            {
                "year": int(result["year"]),
                "month": int(result["month"]),
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in monthly_contributions_results
        ]
        
        return {
            "total_contributions": total_contributions,
            "total_amount": total_amount,
            "contributions_by_user": contributions_by_user,
            "contributions_by_product": contributions_by_product,
            "monthly_contributions": monthly_contributions
        }

    async def get_home_analytics(self, home_id: str) -> dict:
        db = await self.get_database()
        
        # Total contributions for this home
        total_contributions_query = "SELECT COUNT(*) as count FROM contributions WHERE home_id = :home_id"
        total_contributions_result = await db.fetch_one(total_contributions_query, {"home_id": int(home_id)})
        total_contributions = total_contributions_result["count"]
        
        # Total amount for this home
        total_amount_query = "SELECT COALESCE(SUM(amount), 0) as total FROM contributions WHERE home_id = :home_id"
        total_amount_result = await db.fetch_one(total_amount_query, {"home_id": int(home_id)})
        total_amount = float(total_amount_result["total"])
        
        # Contributions by user in this home
        contributions_by_user_query = """
            SELECT 
                c.username,
                u.full_name,
                COALESCE(SUM(c.amount), 0) as total_amount,
                COUNT(c.id) as count
            FROM contributions c
            JOIN users u ON c.username = u.username
            WHERE c.home_id = :home_id
            GROUP BY c.username, u.full_name
            ORDER BY total_amount DESC
        """
        contributions_by_user_results = await db.fetch_all(contributions_by_user_query, {"home_id": int(home_id)})
        contributions_by_user = [
            {
                "username": result["username"],
                "full_name": result["full_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in contributions_by_user_results
        ]
        
        # Contributions by product in this home (excluding fund transfers)
        contributions_by_product_query = """
            SELECT 
                product_name,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(id) as count
            FROM contributions
            WHERE home_id = :home_id 
                AND product_name NOT LIKE 'Fund transfer%' 
                AND product_name NOT LIKE 'Fund received%'
            GROUP BY product_name
            ORDER BY total_amount DESC
        """
        contributions_by_product_results = await db.fetch_all(contributions_by_product_query, {"home_id": int(home_id)})
        contributions_by_product = [
            {
                "product_name": result["product_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in contributions_by_product_results
        ]
        
        # Monthly contributions for this home
        monthly_contributions_query = """
            SELECT 
                EXTRACT(YEAR FROM date_created) as year,
                EXTRACT(MONTH FROM date_created) as month,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(id) as count
            FROM contributions
            WHERE home_id = :home_id
            GROUP BY EXTRACT(YEAR FROM date_created), EXTRACT(MONTH FROM date_created)
            ORDER BY year DESC, month DESC
        """
        monthly_contributions_results = await db.fetch_all(monthly_contributions_query, {"home_id": int(home_id)})
        monthly_contributions = [
            {
                "year": int(result["year"]),
                "month": int(result["month"]),
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in monthly_contributions_results
        ]
        
        return {
            "total_contributions": total_contributions,
            "total_amount": total_amount,
            "contributions_by_user": contributions_by_user,
            "contributions_by_product": contributions_by_product,
            "monthly_contributions": monthly_contributions
        }
    
    async def get_user_statistics(self, username: str) -> dict:
        db = await self.get_database()
        
        # User's total contributions (including positive and negative amounts)
        user_contributions_query = "SELECT COUNT(*) as count FROM contributions WHERE username = :username"
        user_contributions_result = await db.fetch_one(user_contributions_query, {"username": username})
        user_contributions = user_contributions_result["count"]
        
        # User's total contribution amount
        user_total_amount = await self.get_user_balance(username)
        
        # User's transfer statistics
        sent_transfers_query = "SELECT COUNT(*) as count FROM transfers WHERE sender_username = :username"
        sent_transfers_result = await db.fetch_one(sent_transfers_query, {"username": username})
        sent_transfers = sent_transfers_result["count"]
        
        received_transfers_query = "SELECT COUNT(*) as count FROM transfers WHERE recipient_username = :username"
        received_transfers_result = await db.fetch_one(received_transfers_query, {"username": username})
        received_transfers = received_transfers_result["count"]
        
        # User's recent contributions
        recent_contributions_query = """
            SELECT * FROM contributions 
            WHERE username = :username 
            ORDER BY date_created DESC 
            LIMIT 5
        """
        recent_contributions_results = await db.fetch_all(recent_contributions_query, {"username": username})
        recent_contributions = [
            Contribution(
                id=str(result["id"]),
                username=result["username"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                product_name=result["product_name"],
                amount=float(result["amount"]),
                description=result["description"],
                date_created=result["date_created"]
            )
            for result in recent_contributions_results
        ]
        
        # Get contribution to average statistics
        contribution_stats = await self.get_contribution_to_average(username)
        
        return {
            "total_contributions": user_contributions,
            "total_amount": user_total_amount,
            "current_balance": user_total_amount,  # Same as total amount now
            "sent_transfers": sent_transfers,
            "received_transfers": received_transfers,
            "recent_contributions": recent_contributions,
            "contribution_to_average": contribution_stats
        }
    
    async def update_user_profile(self, username: str, full_name: str, email: str) -> bool:
        db = await self.get_database()
        
        query = "UPDATE users SET full_name = :full_name, email = :email WHERE username = :username"
        result = await db.execute(query, {
            "full_name": full_name,
            "email": email,
            "username": username
        })
        
        return result > 0

    async def get_monthly_contributions(self, year: int = None, month: int = None) -> List[dict]:
        """Get contributions filtered by month and year"""
        db = await self.get_database()
        
        # Build WHERE condition
        where_conditions = []
        params = {}
        
        if year and month:
            # Get contributions for specific month
            where_conditions.append("EXTRACT(YEAR FROM date_created) = :year AND EXTRACT(MONTH FROM date_created) = :month")
            params["year"] = year
            params["month"] = month
        elif year:
            # Get contributions for entire year
            where_conditions.append("EXTRACT(YEAR FROM date_created) = :year")
            params["year"] = year
        
        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Get contributions with user information
        query = f"""
            SELECT 
                c.id,
                c.username,
                c.product_name,
                c.amount,
                c.description,
                c.date_created,
                u.full_name as user_full_name
            FROM contributions c
            JOIN users u ON c.username = u.username
            {where_clause}
            ORDER BY c.date_created DESC
        """
        
        results = await db.fetch_all(query, params)
        
        contributions = []
        for result in results:
            contributions.append({
                "id": str(result["id"]),
                "username": result["username"],
                "product_name": result["product_name"],
                "amount": float(result["amount"]),
                "description": result["description"],
                "date_created": result["date_created"],
                "user_full_name": result["user_full_name"]
            })
        
        return contributions

    async def get_home_monthly_contributions(self, home_id: str, year: int = None, month: int = None) -> List[dict]:
        """Get contributions filtered by home, month and year"""
        db = await self.get_database()
        
        # Build WHERE condition
        where_conditions = ["c.home_id = :home_id"]
        params = {"home_id": int(home_id)}
        
        if year and month:
            # Get contributions for specific month
            where_conditions.append("EXTRACT(YEAR FROM c.date_created) = :year AND EXTRACT(MONTH FROM c.date_created) = :month")
            params["year"] = year
            params["month"] = month
        elif year:
            # Get contributions for entire year
            where_conditions.append("EXTRACT(YEAR FROM c.date_created) = :year")
            params["year"] = year
        
        where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # Get contributions with user information
        query = f"""
            SELECT 
                c.id,
                c.username,
                c.home_id,
                c.product_name,
                c.amount,
                c.description,
                c.date_created,
                u.full_name as user_full_name
            FROM contributions c
            JOIN users u ON c.username = u.username
            {where_clause}
            ORDER BY c.date_created DESC
        """
        
        results = await db.fetch_all(query, params)
        
        contributions = []
        for result in results:
            contributions.append({
                "id": str(result["id"]),
                "username": result["username"],
                "home_id": str(result["home_id"]),
                "product_name": result["product_name"],
                "amount": float(result["amount"]),
                "description": result["description"],
                "date_created": result["date_created"],
                "user_full_name": result["user_full_name"]
            })
        
        return contributions

    async def get_monthly_summary(self, year: int, month: int) -> dict:
        """Get monthly summary statistics"""
        db = await self.get_database()
        
        # Total contributions and amount for the month
        total_query = """
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(amount), 0) as total_amount
            FROM contributions
            WHERE EXTRACT(YEAR FROM date_created) = :year 
                AND EXTRACT(MONTH FROM date_created) = :month
        """
        total_result = await db.fetch_one(total_query, {"year": year, "month": month})
        total_amount = float(total_result["total_amount"])
        total_count = total_result["total_count"]
        
        # Contributions by user for the month
        user_query = """
            SELECT 
                c.username,
                u.full_name,
                COALESCE(SUM(c.amount), 0) as total_amount,
                COUNT(c.id) as count
            FROM contributions c
            JOIN users u ON c.username = u.username
            WHERE EXTRACT(YEAR FROM c.date_created) = :year 
                AND EXTRACT(MONTH FROM c.date_created) = :month
            GROUP BY c.username, u.full_name
            ORDER BY total_amount DESC
        """
        user_results = await db.fetch_all(user_query, {"year": year, "month": month})
        user_contributions = [
            {
                "username": result["username"],
                "full_name": result["full_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in user_results
        ]
        
        # Contributions by product for the month (excluding fund transfers)
        product_query = """
            SELECT 
                product_name,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(id) as count
            FROM contributions
            WHERE EXTRACT(YEAR FROM date_created) = :year 
                AND EXTRACT(MONTH FROM date_created) = :month
                AND product_name NOT LIKE 'Fund transfer%' 
                AND product_name NOT LIKE 'Fund received%'
            GROUP BY product_name
            ORDER BY total_amount DESC
        """
        product_results = await db.fetch_all(product_query, {"year": year, "month": month})
        product_contributions = [
            {
                "product_name": result["product_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in product_results
        ]
        
        return {
            "year": year,
            "month": month,
            "total_amount": total_amount,
            "total_count": total_count,
            "contributions_by_user": user_contributions,
            "contributions_by_product": product_contributions
        }

    async def get_home_monthly_summary(self, home_id: str, year: int, month: int) -> dict:
        """Get monthly summary statistics for a specific home"""
        db = await self.get_database()
        
        # Total contributions and amount for the month in this home
        total_query = """
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(amount), 0) as total_amount
            FROM contributions
            WHERE home_id = :home_id
                AND EXTRACT(YEAR FROM date_created) = :year 
                AND EXTRACT(MONTH FROM date_created) = :month
        """
        total_result = await db.fetch_one(total_query, {"home_id": int(home_id), "year": year, "month": month})
        total_amount = float(total_result["total_amount"])
        total_count = total_result["total_count"]
        
        # Contributions by user for the month in this home
        user_query = """
            SELECT 
                c.username,
                u.full_name,
                COALESCE(SUM(c.amount), 0) as total_amount,
                COUNT(c.id) as count
            FROM contributions c
            JOIN users u ON c.username = u.username
            WHERE c.home_id = :home_id
                AND EXTRACT(YEAR FROM c.date_created) = :year 
                AND EXTRACT(MONTH FROM c.date_created) = :month
            GROUP BY c.username, u.full_name
            ORDER BY total_amount DESC
        """
        user_results = await db.fetch_all(user_query, {"home_id": int(home_id), "year": year, "month": month})
        user_contributions = [
            {
                "username": result["username"],
                "full_name": result["full_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in user_results
        ]
        
        # Contributions by product for the month in this home (excluding fund transfers)
        product_query = """
            SELECT 
                product_name,
                COALESCE(SUM(amount), 0) as total_amount,
                COUNT(id) as count
            FROM contributions
            WHERE home_id = :home_id
                AND EXTRACT(YEAR FROM date_created) = :year 
                AND EXTRACT(MONTH FROM date_created) = :month
                AND product_name NOT LIKE 'Fund transfer%' 
                AND product_name NOT LIKE 'Fund received%'
            GROUP BY product_name
            ORDER BY total_amount DESC
        """
        product_results = await db.fetch_all(product_query, {"home_id": int(home_id), "year": year, "month": month})
        product_contributions = [
            {
                "product_name": result["product_name"],
                "total_amount": float(result["total_amount"]),
                "count": result["count"]
            }
            for result in product_results
        ]
        
        return {
            "year": year,
            "month": month,
            "total_amount": total_amount,
            "total_count": total_count,
            "contributions_by_user": user_contributions,
            "contributions_by_product": product_contributions
        }

    async def get_user_balance(self, username: str) -> float:
        """Get user's total contribution amount (including negative transfers)"""
        db = await self.get_database()
        
        # Get total contributions (including negative amounts from transfers received)
        query = "SELECT COALESCE(SUM(amount), 0) as total FROM contributions WHERE username = :username"
        result = await db.fetch_one(query, {"username": username})
        total_contributions = float(result["total"])
        
        return total_contributions

    async def create_transfer(self, sender_username: str, transfer_data: TransferCreate) -> Transfer:
        """Create a new transfer between users - adjusts contribution amounts"""
        db = await self.get_database()
        
        # Get sender and recipient users
        sender = await self.get_user(sender_username)
        recipient = await self.get_user(transfer_data.recipient_username)
        
        if not sender or not recipient:
            raise ValueError("User not found")
        
        # Check if both users belong to the same home
        if not sender.home_id or sender.home_id != recipient.home_id:
            raise ValueError("Users must belong to the same home to transfer money")
        
        # Check if sender is not transferring to themselves
        if sender_username == transfer_data.recipient_username:
            raise ValueError("Cannot transfer to yourself")
        
        # Validate transfer amount
        if transfer_data.amount <= 0:
            raise ValueError("Transfer amount must be positive")
        
        # Create the transfer record
        transfer_query = """
            INSERT INTO transfers (sender_username, recipient_username, home_id, amount, description, date_created)
            VALUES (:sender_username, :recipient_username, :home_id, :amount, :description, :date_created)
            RETURNING id, sender_username, recipient_username, home_id, amount, description, date_created
        """
        transfer_values = {
            "sender_username": sender_username,
            "recipient_username": transfer_data.recipient_username,
            "home_id": int(sender.home_id),
            "amount": transfer_data.amount,
            "description": transfer_data.description or "Fund transfer to balance contributions",
            "date_created": datetime.utcnow()
        }
        
        result = await db.fetch_one(transfer_query, transfer_values)
        
        # Create contribution adjustments
        # Add contribution for sender (giver)
        await self.create_contribution(sender_username, {
            "product_name": f"Fund transfer to {recipient.full_name}",
            "amount": transfer_data.amount,
            "description": f"Transfer to {recipient.full_name}: {transfer_data.description or 'Balancing household contributions'}"
        })
        
        # Subtract contribution for recipient (receiver) by creating a negative contribution
        await self.create_contribution(transfer_data.recipient_username, {
            "product_name": f"Fund received from {sender.full_name}",
            "amount": -transfer_data.amount,
            "description": f"Received from {sender.full_name}: {transfer_data.description or 'Balancing household contributions'}"
        })
        
        return Transfer(
            id=str(result["id"]),
            sender_username=result["sender_username"],
            recipient_username=result["recipient_username"],
            home_id=str(result["home_id"]),
            amount=float(result["amount"]),
            description=result["description"],
            date_created=result["date_created"]
        )

    async def get_user_transfers(self, username: str) -> dict:
        """Get all transfers for a user (sent and received)"""
        db = await self.get_database()
        
        # Get sent transfers
        sent_query = "SELECT * FROM transfers WHERE sender_username = :username ORDER BY date_created DESC"
        sent_results = await db.fetch_all(sent_query, {"username": username})
        
        sent_transfers = []
        for result in sent_results:
            # Get recipient full name
            recipient = await self.get_user(result["recipient_username"])
            transfer = Transfer(
                id=str(result["id"]),
                sender_username=result["sender_username"],
                recipient_username=result["recipient_username"],
                home_id=str(result["home_id"]),
                amount=float(result["amount"]),
                description=result["description"],
                date_created=result["date_created"]
            )
            # Add recipient full name as an attribute
            transfer.recipient_full_name = recipient.full_name if recipient else "Unknown"
            sent_transfers.append(transfer)
        
        # Get received transfers
        received_query = "SELECT * FROM transfers WHERE recipient_username = :username ORDER BY date_created DESC"
        received_results = await db.fetch_all(received_query, {"username": username})
        
        received_transfers = []
        for result in received_results:
            # Get sender full name
            sender = await self.get_user(result["sender_username"])
            transfer = Transfer(
                id=str(result["id"]),
                sender_username=result["sender_username"],
                recipient_username=result["recipient_username"],
                home_id=str(result["home_id"]),
                amount=float(result["amount"]),
                description=result["description"],
                date_created=result["date_created"]
            )
            # Add sender full name as an attribute
            transfer.sender_full_name = sender.full_name if sender else "Unknown"
            received_transfers.append(transfer)
        
        return {
            "sent": sent_transfers,
            "received": received_transfers
        }

    async def get_all_users(self) -> List[UserInDB]:
        """Get all users for transfer recipient selection"""
        db = await self.get_database()
        query = "SELECT id, username, email, full_name, is_active, home_id, date_created FROM users ORDER BY full_name"
        results = await db.fetch_all(query)
        
        users = []
        for result in results:
            users.append(UserInDB(
                id=str(result["id"]),
                username=result["username"],
                email=result["email"],
                full_name=result["full_name"],
                hashed_password="",  # Don't return password hash
                is_active=result["is_active"],
                home_id=str(result["home_id"]) if result["home_id"] else None,
                date_created=result["date_created"]
            ))
        
        return users

    # Home management methods
    async def create_home(self, home_data: HomeCreate, leader_username: str) -> Home:
        db = await self.get_database()
        
        home_query = """
            INSERT INTO homes (name, description, leader_username, date_created)
            VALUES (:name, :description, :leader_username, :date_created)
            RETURNING id, name, description, leader_username, date_created
        """
        home_values = {
            "name": home_data.name,
            "description": home_data.description,
            "leader_username": leader_username,
            "date_created": datetime.utcnow()
        }
        
        result = await db.fetch_one(home_query, home_values)
        home_id = result["id"]
        
        # Update the user's home_id
        await db.execute(
            "UPDATE users SET home_id = :home_id WHERE username = :username",
            {"home_id": home_id, "username": leader_username}
        )
        
        # Add to home_members table
        await db.execute(
            "INSERT INTO home_members (home_id, username) VALUES (:home_id, :username)",
            {"home_id": home_id, "username": leader_username}
        )
        
        # Get members list (just the leader for now)
        members = [leader_username]
        
        return Home(
            id=str(result["id"]),
            name=result["name"],
            description=result["description"],
            leader_username=result["leader_username"],
            members=members,
            date_created=result["date_created"]
        )

    async def get_home(self, home_id: str) -> Optional[Home]:
        db = await self.get_database()
        
        try:
            # Get home info
            home_query = "SELECT * FROM homes WHERE id = :home_id"
            home_result = await db.fetch_one(home_query, {"home_id": int(home_id)})
            
            if home_result:
                # Get members
                members_query = "SELECT username FROM home_members WHERE home_id = :home_id"
                members_results = await db.fetch_all(members_query, {"home_id": int(home_id)})
                members = [row["username"] for row in members_results]
                
                return Home(
                    id=str(home_result["id"]),
                    name=home_result["name"],
                    description=home_result["description"],
                    leader_username=home_result["leader_username"],
                    members=members,
                    date_created=home_result["date_created"]
                )
        except:
            pass
        return None

    async def get_user_home(self, username: str) -> Optional[Home]:
        db = await self.get_database()
        user = await self.get_user(username)
        if user and user.home_id:
            return await self.get_home(user.home_id)
        return None

    async def add_member_to_home(self, home_id: str, username: str, leader_username: str) -> bool:
        db = await self.get_database()
        
        # Check if the requester is the home leader
        home = await self.get_home(home_id)
        if not home or home.leader_username != leader_username:
            return False
        
        # Check if user exists and is not already in a home
        user = await self.get_user(username)
        if not user or user.home_id:
            return False
        
        try:
            # Add user to home members
            await db.execute(
                "INSERT INTO home_members (home_id, username) VALUES (:home_id, :username)",
                {"home_id": int(home_id), "username": username}
            )
            
            # Update user's home_id
            await db.execute(
                "UPDATE users SET home_id = :home_id WHERE username = :username",
                {"home_id": int(home_id), "username": username}
            )
            
            return True
        except:
            return False

    async def remove_member_from_home(self, home_id: str, username: str, leader_username: str) -> bool:
        db = await self.get_database()
        
        # Check if the requester is the home leader
        home = await self.get_home(home_id)
        if not home or home.leader_username != leader_username:
            return False
        
        # Cannot remove the leader
        if username == leader_username:
            return False
        
        try:
            # Remove user from home members
            await db.execute(
                "DELETE FROM home_members WHERE home_id = :home_id AND username = :username",
                {"home_id": int(home_id), "username": username}
            )
            
            # Remove user's home_id
            await db.execute(
                "UPDATE users SET home_id = NULL WHERE username = :username",
                {"username": username}
            )
            
            return True
        except:
            return False

    async def get_home_members(self, home_id: str) -> List[User]:
        db = await self.get_database()
        home = await self.get_home(home_id)
        if not home:
            return []
        
        members = []
        for username in home.members:
            user = await self.get_user(username)
            if user:
                members.append(User(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    full_name=user.full_name,
                    is_active=user.is_active,
                    home_id=user.home_id
                ))
        
        return members

    async def leave_home(self, username: str) -> bool:
        db = await self.get_database()
        user = await self.get_user(username)
        
        if not user or not user.home_id:
            return False
        
        home = await self.get_home(user.home_id)
        if not home:
            return False
        
        # If user is the leader, they cannot leave unless they're the only member
        if home.leader_username == username and len(home.members) > 1:
            return False
        
        try:
            # Remove user from home members
            await db.execute(
                "DELETE FROM home_members WHERE home_id = :home_id AND username = :username",
                {"home_id": int(user.home_id), "username": username}
            )
            
            # Remove user's home_id
            await db.execute(
                "UPDATE users SET home_id = NULL WHERE username = :username",
                {"username": username}
            )
            
            # If user was the leader and the only member, delete the home
            if home.leader_username == username and len(home.members) == 1:
                await db.execute(
                    "DELETE FROM homes WHERE id = :home_id",
                    {"home_id": int(user.home_id)}
                )
            
            return True
        except:
            return False

    async def create_join_request(self, username: str, home_name: str) -> bool:
        """Create a join request for a user to join a home"""
        db = await self.get_database()
        
        try:
            # Check if home exists
            home_query = "SELECT * FROM homes WHERE name = :home_name"
            home_result = await db.fetch_one(home_query, {"home_name": home_name})
            if not home_result:
                return False
            
            # Check if user already has a pending request for this home
            existing_query = """
                SELECT * FROM join_requests 
                WHERE username = :username AND home_id = :home_id AND status = 'pending'
            """
            existing_result = await db.fetch_one(existing_query, {
                "username": username,
                "home_id": home_result["id"]
            })
            if existing_result:
                return False
            
            # Create join request
            request_query = """
                INSERT INTO join_requests (username, home_id, home_name, status, date_created)
                VALUES (:username, :home_id, :home_name, :status, :date_created)
            """
            await db.execute(request_query, {
                "username": username,
                "home_id": home_result["id"],
                "home_name": home_name,
                "status": "pending",
                "date_created": datetime.utcnow()
            })
            
            return True
        except:
            return False
    
    async def get_pending_join_requests(self, home_id: str) -> List[dict]:
        """Get all pending join requests for a home"""
        db = await self.get_database()
        
        try:
            query = """
                SELECT jr.*, u.full_name, u.email
                FROM join_requests jr
                JOIN users u ON jr.username = u.username
                WHERE jr.home_id = :home_id AND jr.status = 'pending'
                ORDER BY jr.date_created DESC
            """
            results = await db.fetch_all(query, {"home_id": int(home_id)})
            
            requests = []
            for result in results:
                requests.append({
                    "id": str(result["id"]),
                    "username": result["username"],
                    "full_name": result["full_name"],
                    "email": result["email"],
                    "date_created": result["date_created"]
                })
            
            return requests
        except:
            return []
    
    async def get_user_pending_request(self, username: str) -> Optional[dict]:
        """Get user's pending join request if any"""
        db = await self.get_database()
        
        try:
            query = """
                SELECT * FROM join_requests 
                WHERE username = :username AND status = 'pending'
            """
            result = await db.fetch_one(query, {"username": username})
            
            if result:
                return {
                    "id": str(result["id"]),
                    "home_name": result["home_name"],
                    "date_created": result["date_created"]
                }
            return None
        except:
            return None
    
    async def approve_join_request(self, request_id: str, leader_username: str) -> bool:
        """Approve a join request"""
        db = await self.get_database()
        
        try:
            # Get the join request
            request_query = "SELECT * FROM join_requests WHERE id = :request_id"
            request_result = await db.fetch_one(request_query, {"request_id": int(request_id)})
            if not request_result or request_result["status"] != "pending":
                return False
            
            # Verify that the current user is the leader of the home
            home_query = "SELECT * FROM homes WHERE id = :home_id"
            home_result = await db.fetch_one(home_query, {"home_id": request_result["home_id"]})
            if not home_result or home_result["leader_username"] != leader_username:
                return False
            
            # Add user to home
            await db.execute(
                "UPDATE users SET home_id = :home_id WHERE username = :username",
                {"home_id": request_result["home_id"], "username": request_result["username"]}
            )
            
            # Add user to home members
            await db.execute(
                "INSERT INTO home_members (home_id, username) VALUES (:home_id, :username)",
                {"home_id": request_result["home_id"], "username": request_result["username"]}
            )
            
            # Update request status
            await db.execute(
                "UPDATE join_requests SET status = 'approved', date_processed = :date_processed WHERE id = :request_id",
                {"request_id": int(request_id), "date_processed": datetime.utcnow()}
            )
            
            return True
        except:
            return False
    
    async def reject_join_request(self, request_id: str, leader_username: str) -> bool:
        """Reject a join request"""
        db = await self.get_database()
        
        try:
            # Get the join request
            request_query = "SELECT * FROM join_requests WHERE id = :request_id"
            request_result = await db.fetch_one(request_query, {"request_id": int(request_id)})
            if not request_result or request_result["status"] != "pending":
                return False
            
            # Verify that the current user is the leader of the home
            home_query = "SELECT * FROM homes WHERE id = :home_id"
            home_result = await db.fetch_one(home_query, {"home_id": request_result["home_id"]})
            if not home_result or home_result["leader_username"] != leader_username:
                return False
            
            # Update request status
            await db.execute(
                "UPDATE join_requests SET status = 'rejected', date_processed = :date_processed WHERE id = :request_id",
                {"request_id": int(request_id), "date_processed": datetime.utcnow()}
            )
            
            return True
        except:
            return False

    async def get_eligible_transfer_recipients(self, sender_username: str) -> List[dict]:
        """Get users in the same home who are eligible to receive fund transfers (all home members except sender)"""
        db = await self.get_database()
        
        try:
            # Get sender's home
            sender = await self.get_user(sender_username)
            if not sender or not sender.home_id:
                return []
            
            home = await self.get_home(sender.home_id)
            if not home:
                return []
            
            # Get all home members (excluding sender) with their contribution totals
            query = """
                SELECT 
                    u.username,
                    u.full_name,
                    COALESCE(SUM(c.amount), 0) as total_contribution
                FROM users u
                LEFT JOIN contributions c ON u.username = c.username AND c.home_id = :home_id
                WHERE u.home_id = :home_id AND u.username != :sender_username
                GROUP BY u.username, u.full_name
                ORDER BY u.full_name
            """
            
            results = await db.fetch_all(query, {
                "home_id": int(sender.home_id),
                "sender_username": sender_username
            })
            
            eligible_recipients = []
            for result in results:
                eligible_recipients.append({
                    "username": result["username"],
                    "full_name": result["full_name"],
                    "total_contribution": float(result["total_contribution"])
                })
            
            return eligible_recipients
            
        except Exception as e:
            print(f"Error getting eligible transfer recipients: {str(e)}")
            return []

    async def get_contribution_to_average(self, username: str) -> dict:
        """Calculate how much user needs to contribute to reach the average contribution of their home"""
        db = await self.get_database()
        
        try:
            # Get user's home
            user = await self.get_user(username)
            if not user or not user.home_id:
                return {
                    "user_total": 0,
                    "average_contribution": 0,
                    "amount_to_reach_average": 0,
                    "is_above_average": False,
                    "home_members_count": 0
                }
            
            # Get home members count
            home = await self.get_home(user.home_id)
            if not home:
                return {
                    "user_total": 0,
                    "average_contribution": 0,
                    "amount_to_reach_average": 0,
                    "is_above_average": False,
                    "home_members_count": 0
                }
            
            # Get total contributions by all home members
            home_total_query = "SELECT COALESCE(SUM(amount), 0) as total FROM contributions WHERE home_id = :home_id"
            home_total_result = await db.fetch_one(home_total_query, {"home_id": int(user.home_id)})
            home_total = float(home_total_result["total"])
            
            # Get user's total contributions
            user_total_query = "SELECT COALESCE(SUM(amount), 0) as total FROM contributions WHERE username = :username AND home_id = :home_id"
            user_total_result = await db.fetch_one(user_total_query, {"username": username, "home_id": int(user.home_id)})
            user_total = float(user_total_result["total"])
            
            # Calculate average contribution per member
            home_members_count = len(home.members)
            average_contribution = home_total / home_members_count if home_members_count > 0 else 0
            
            # Calculate amount needed to reach average
            amount_to_reach_average = max(0, average_contribution - user_total)
            is_above_average = user_total >= average_contribution
            
            return {
                "user_total": user_total,
                "average_contribution": average_contribution,
                "amount_to_reach_average": amount_to_reach_average,
                "is_above_average": is_above_average,
                "home_members_count": home_members_count,
                "home_total": home_total
            }
        except Exception as e:
            print(f"Error calculating contribution to average: {str(e)}")
            return {
                "user_total": 0,
                "average_contribution": 0,
                "amount_to_reach_average": 0,
                "is_above_average": False,
                "home_members_count": 0
            }
