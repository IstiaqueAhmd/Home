import os
import ssl
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
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
        self.mongodb_url = os.getenv("MONGODB_URL")
        self.database_name = os.getenv("DATABASE_NAME")
        self.client = None
        self.database = None
        self.auth_manager = AuthManager()
        
        # Debug: Print loaded environment variables (without password)
        if not self.mongodb_url:
            print("ERROR: MONGODB_URL environment variable is not set")
        else:
            # Print URL without password for debugging
            safe_url = self.mongodb_url.replace(self.mongodb_url.split('://')[1].split('@')[0], "***:***")
            print(f"MongoDB URL loaded: {safe_url}")
            
        if not self.database_name:
            print("ERROR: DATABASE_NAME environment variable is not set")
        else:
            print(f"Database name loaded: {self.database_name}")
        
    
    async def connect_to_mongo(self):
        """Simplified connection with better SSL handling"""
        if not self.mongodb_url or not self.database_name:
            raise ValueError("MongoDB connection variables not set")
        
        try:
            # Use a clean URL without explicit TLS parameter
            clean_url = self.mongodb_url.replace("&tls=true", "").replace("?tls=true", "")
            
            # Simple connection with SSL auto-detection
            self.client = AsyncIOMotorClient(
                clean_url,
                serverSelectionTimeoutMS=30000,
                connectTimeoutMS=30000,
                socketTimeoutMS=30000
            )
            
            self.database = self.client[self.database_name]
            
            # Test connection
            await asyncio.wait_for(
                self.client.admin.command('ping'), 
                timeout=30
            )
            print("MongoDB connection successful")
            
        except Exception as e:
            print(f"MongoDB connection failed: {str(e)}")
            raise e

    async def close_mongo_connection(self):
        if self.client:
            self.client.close()
    
    async def get_database(self):
        try:
            if self.database is None:
                await self.connect_to_mongo()
            return self.database
        except Exception as e:
            print(f"Database access error: {str(e)}")
            raise e
    
    async def create_user(self, user: UserCreate) -> UserInDB:
        db = await self.get_database()
        
        hashed_password = self.auth_manager.get_password_hash(user.password)
        user_dict = {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "hashed_password": hashed_password,
            "is_active": True,
            "date_created": datetime.utcnow()
        }
        
        try:
            result = await db.users.insert_one(user_dict)
            user_dict["_id"] = str(result.inserted_id)
            return UserInDB(**user_dict)
        except DuplicateKeyError:
            raise ValueError("User already exists")
    
    async def get_user(self, username: str) -> Optional[UserInDB]:
        db = await self.get_database()
        user_doc = await db.users.find_one({"username": username})
        if user_doc:
            user_doc["id"] = str(user_doc["_id"])
            return UserInDB(**user_doc)
        return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        db = await self.get_database()
        user_doc = await db.users.find_one({"email": email})
        if user_doc:
            user_doc["id"] = str(user_doc["_id"])
            return UserInDB(**user_doc)
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
        
        contribution_dict = {
            "username": username,
            "home_id": user.home_id,
            "product_name": contribution_data["product_name"],
            "amount": contribution_data["amount"],
            "description": contribution_data.get("description", ""),
            "date_created": datetime.utcnow()
        }
        
        result = await db.contributions.insert_one(contribution_dict)
        contribution_dict["id"] = str(result.inserted_id)
        return Contribution(**contribution_dict)
    
    async def get_user_contributions(self, username: str) -> List[Contribution]:
        db = await self.get_database()
        contributions = []
        
        async for doc in db.contributions.find({"username": username}).sort("date_created", -1):
            doc["id"] = str(doc["_id"])
            contributions.append(Contribution(**doc))
        
        return contributions

    async def get_home_contributions(self, home_id: str) -> List[Contribution]:
        db = await self.get_database()
        contributions = []
        
        async for doc in db.contributions.find({"home_id": home_id}).sort("date_created", -1):
            doc["id"] = str(doc["_id"])
            contributions.append(Contribution(**doc))
        
        return contributions
    
    async def get_all_contributions(self) -> List[Contribution]:
        db = await self.get_database()
        contributions = []
        
        async for doc in db.contributions.find().sort("date_created", -1):
            doc["id"] = str(doc["_id"])
            contributions.append(Contribution(**doc))
        
        return contributions
    
    async def get_all_contributions_with_users(self) -> List[dict]:
        db = await self.get_database()
        contributions = []
        
        # Aggregate contributions with user information
        pipeline = [
            {
                "$lookup": {
                    "from": "users",
                    "localField": "username",
                    "foreignField": "username",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$sort": {"date_created": -1}
            }
        ]
        
        async for doc in db.contributions.aggregate(pipeline):
            contribution_data = {
                "id": str(doc["_id"]),
                "username": doc["username"],
                "home_id": doc.get("home_id", ""),
                "product_name": doc["product_name"],
                "amount": doc["amount"],
                "description": doc.get("description", ""),
                "date_created": doc["date_created"],
                "user_full_name": doc["user_info"]["full_name"]
            }
            contributions.append(contribution_data)
        
        return contributions

    async def get_home_contributions_with_users(self, home_id: str) -> List[dict]:
        db = await self.get_database()
        contributions = []
        
        # Aggregate contributions with user information for a specific home
        pipeline = [
            {
                "$match": {"home_id": home_id}
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "username",
                    "foreignField": "username",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$sort": {"date_created": -1}
            }
        ]
        
        async for doc in db.contributions.aggregate(pipeline):
            contribution_data = {
                "id": str(doc["_id"]),
                "username": doc["username"],
                "home_id": doc["home_id"],
                "product_name": doc["product_name"],
                "amount": doc["amount"],
                "description": doc.get("description", ""),
                "date_created": doc["date_created"],
                "user_full_name": doc["user_info"]["full_name"]
            }
            contributions.append(contribution_data)
        
        return contributions
    
    async def delete_contribution(self, contribution_id: str, username: str) -> bool:
        db = await self.get_database()
        from bson import ObjectId
        
        # Only allow deletion if the contribution belongs to the user
        result = await db.contributions.delete_one({
            "_id": ObjectId(contribution_id),
            "username": username
        })
        
        return result.deleted_count > 0
    
    async def get_analytics(self) -> dict:
        db = await self.get_database()
        
        # Total contributions
        total_contributions = await db.contributions.count_documents({})
        
        # Total amount
        pipeline_total = [
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        total_amount_result = []
        async for doc in db.contributions.aggregate(pipeline_total):
            total_amount_result.append(doc)
        total_amount = total_amount_result[0]["total"] if total_amount_result else 0
        
        # Contributions by user
        pipeline_by_user = [
            {
                "$group": {
                    "_id": "$username",
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "username",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        contributions_by_user = []
        async for doc in db.contributions.aggregate(pipeline_by_user):
            contributions_by_user.append({
                "username": doc["_id"],
                "full_name": doc["user_info"]["full_name"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
        # Contributions by product (excluding fund transfers)
        pipeline_by_product = [
            {
                "$match": {
                    "product_name": {
                        "$not": {
                            "$regex": "^Fund (transfer|received)"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$product_name",
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        contributions_by_product = []
        async for doc in db.contributions.aggregate(pipeline_by_product):
            contributions_by_product.append({
                "product_name": doc["_id"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
        # Monthly contributions
        pipeline_monthly = [
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$date_created"},
                        "month": {"$month": "$date_created"}
                    },
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id.year": -1, "_id.month": -1}
            }
        ]
        
        monthly_contributions = []
        async for doc in db.contributions.aggregate(pipeline_monthly):
            monthly_contributions.append({
                "year": doc["_id"]["year"],
                "month": doc["_id"]["month"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
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
        total_contributions = await db.contributions.count_documents({"home_id": home_id})
        
        # Total amount for this home
        pipeline_total = [
            {"$match": {"home_id": home_id}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        total_amount_result = []
        async for doc in db.contributions.aggregate(pipeline_total):
            total_amount_result.append(doc)
        total_amount = total_amount_result[0]["total"] if total_amount_result else 0
        
        # Contributions by user in this home
        pipeline_by_user = [
            {"$match": {"home_id": home_id}},
            {
                "$group": {
                    "_id": "$username",
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "_id",
                    "foreignField": "username",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        contributions_by_user = []
        async for doc in db.contributions.aggregate(pipeline_by_user):
            contributions_by_user.append({
                "username": doc["_id"],
                "full_name": doc["user_info"]["full_name"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
        # Contributions by product in this home (excluding fund transfers)
        pipeline_by_product = [
            {
                "$match": {
                    "home_id": home_id,
                    "product_name": {
                        "$not": {
                            "$regex": "^Fund (transfer|received)"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$product_name",
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        contributions_by_product = []
        async for doc in db.contributions.aggregate(pipeline_by_product):
            contributions_by_product.append({
                "product_name": doc["_id"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
        # Monthly contributions for this home
        pipeline_monthly = [
            {"$match": {"home_id": home_id}},
            {
                "$group": {
                    "_id": {
                        "year": {"$year": "$date_created"},
                        "month": {"$month": "$date_created"}
                    },
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id.year": -1, "_id.month": -1}
            }
        ]
        
        monthly_contributions = []
        async for doc in db.contributions.aggregate(pipeline_monthly):
            monthly_contributions.append({
                "year": doc["_id"]["year"],
                "month": doc["_id"]["month"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
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
        user_contributions = await db.contributions.count_documents({"username": username})
        
        # User's total contribution amount
        user_total_amount = await self.get_user_balance(username)
        
        # User's transfer statistics
        sent_transfers = await db.transfers.count_documents({"sender_username": username})
        received_transfers = await db.transfers.count_documents({"recipient_username": username})
        
        # User's recent contributions
        recent_contributions = []
        async for doc in db.contributions.find({"username": username}).sort("date_created", -1).limit(5):
            doc["id"] = str(doc["_id"])
            recent_contributions.append(Contribution(**doc))
        
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
        
        result = await db.users.update_one(
            {"username": username},
            {"$set": {"full_name": full_name, "email": email}}
        )
        
        return result.modified_count > 0

    async def get_monthly_contributions(self, year: int = None, month: int = None) -> List[dict]:
        """Get contributions filtered by month and year"""
        db = await self.get_database()
        
        # Build match condition
        match_condition = {}
        if year and month:
            # Get contributions for specific month
            from datetime import datetime
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            match_condition["date_created"] = {"$gte": start_date, "$lt": end_date}
        elif year:
            # Get contributions for entire year
            from datetime import datetime
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            match_condition["date_created"] = {"$gte": start_date, "$lt": end_date}
        
        # Aggregate contributions with user information
        pipeline = [
            {"$match": match_condition},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "username", 
                    "foreignField": "username",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$sort": {"date_created": -1}
            }
        ]
        
        contributions = []
        async for doc in db.contributions.aggregate(pipeline):
            contribution_data = {
                "id": str(doc["_id"]),
                "username": doc["username"],
                "product_name": doc["product_name"],
                "amount": doc["amount"],
                "description": doc.get("description", ""),
                "date_created": doc["date_created"],
                "user_full_name": doc["user_info"]["full_name"]
            }
            contributions.append(contribution_data)
        
        return contributions

    async def get_home_monthly_contributions(self, home_id: str, year: int = None, month: int = None) -> List[dict]:
        """Get contributions filtered by home, month and year"""
        db = await self.get_database()
        
        # Build match condition
        match_condition = {"home_id": home_id}
        if year and month:
            # Get contributions for specific month
            from datetime import datetime
            start_date = datetime(year, month, 1)
            if month == 12:
                end_date = datetime(year + 1, 1, 1)
            else:
                end_date = datetime(year, month + 1, 1)
            match_condition["date_created"] = {"$gte": start_date, "$lt": end_date}
        elif year:
            # Get contributions for entire year
            from datetime import datetime
            start_date = datetime(year, 1, 1)
            end_date = datetime(year + 1, 1, 1)
            match_condition["date_created"] = {"$gte": start_date, "$lt": end_date}
        
        # Aggregate contributions with user information
        pipeline = [
            {"$match": match_condition},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "username", 
                    "foreignField": "username",
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$sort": {"date_created": -1}
            }
        ]
        
        contributions = []
        async for doc in db.contributions.aggregate(pipeline):
            contribution_data = {
                "id": str(doc["_id"]),
                "username": doc["username"],
                "home_id": doc["home_id"],
                "product_name": doc["product_name"],
                "amount": doc["amount"],
                "description": doc.get("description", ""),
                "date_created": doc["date_created"],
                "user_full_name": doc["user_info"]["full_name"]
            }
            contributions.append(contribution_data)
        
        return contributions

    async def get_monthly_summary(self, year: int, month: int) -> dict:
        """Get monthly summary statistics"""
        db = await self.get_database()
        
        from datetime import datetime
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        match_condition = {"date_created": {"$gte": start_date, "$lt": end_date}}
        
        # Total contributions and amount for the month
        total_pipeline = [
            {"$match": match_condition},
            {
                "$group": {
                    "_id": None,
                    "total_amount": {"$sum": "$amount"},
                    "total_count": {"$sum": 1}
                }
            }
        ]
        
        total_result = []
        async for doc in db.contributions.aggregate(total_pipeline):
            total_result.append(doc)
        
        total_amount = total_result[0]["total_amount"] if total_result else 0
        total_count = total_result[0]["total_count"] if total_result else 0
        
        # Contributions by user for the month
        user_pipeline = [
            {"$match": match_condition},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "username",
                    "foreignField": "username", 
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$group": {
                    "_id": "$username",
                    "full_name": {"$first": "$user_info.full_name"},
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        user_contributions = []
        async for doc in db.contributions.aggregate(user_pipeline):
            user_contributions.append({
                "username": doc["_id"],
                "full_name": doc["full_name"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
        # Contributions by product for the month (excluding fund transfers)
        product_pipeline = [
            {
                "$match": {
                    **match_condition,
                    "product_name": {
                        "$not": {
                            "$regex": "^Fund (transfer|received)"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$product_name",
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        product_contributions = []
        async for doc in db.contributions.aggregate(product_pipeline):
            product_contributions.append({
                "product_name": doc["_id"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
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
        
        from datetime import datetime
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        match_condition = {
            "home_id": home_id,
            "date_created": {"$gte": start_date, "$lt": end_date}
        }
        
        # Total contributions and amount for the month in this home
        total_pipeline = [
            {"$match": match_condition},
            {
                "$group": {
                    "_id": None,
                    "total_amount": {"$sum": "$amount"},
                    "total_count": {"$sum": 1}
                }
            }
        ]
        
        total_result = []
        async for doc in db.contributions.aggregate(total_pipeline):
            total_result.append(doc)
        
        total_amount = total_result[0]["total_amount"] if total_result else 0
        total_count = total_result[0]["total_count"] if total_result else 0
        
        # Contributions by user for the month in this home
        user_pipeline = [
            {"$match": match_condition},
            {
                "$lookup": {
                    "from": "users",
                    "localField": "username",
                    "foreignField": "username", 
                    "as": "user_info"
                }
            },
            {
                "$unwind": "$user_info"
            },
            {
                "$group": {
                    "_id": "$username",
                    "full_name": {"$first": "$user_info.full_name"},
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        user_contributions = []
        async for doc in db.contributions.aggregate(user_pipeline):
            user_contributions.append({
                "username": doc["_id"],
                "full_name": doc["full_name"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
        # Contributions by product for the month in this home (excluding fund transfers)
        product_pipeline = [
            {
                "$match": {
                    **match_condition,
                    "product_name": {
                        "$not": {
                            "$regex": "^Fund (transfer|received)"
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": "$product_name",
                    "total_amount": {"$sum": "$amount"},
                    "count": {"$sum": 1}
                }
            },
            {
                "$sort": {"total_amount": -1}
            }
        ]
        
        product_contributions = []
        async for doc in db.contributions.aggregate(product_pipeline):
            product_contributions.append({
                "product_name": doc["_id"],
                "total_amount": doc["total_amount"],
                "count": doc["count"]
            })
        
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
        contributions_pipeline = [
            {"$match": {"username": username}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        
        contributions_result = []
        async for doc in db.contributions.aggregate(contributions_pipeline):
            contributions_result.append(doc)
        total_contributions = contributions_result[0]["total"] if contributions_result else 0
        
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
        
        # Get contribution stats to validate the transfer logic
        sender_stats = await self.get_contribution_to_average(sender_username)
        recipient_stats = await self.get_contribution_to_average(transfer_data.recipient_username)
        
        # Validate that sender has lower contributions than average
        if sender_stats["is_above_average"]:
            raise ValueError("Only users with below-average contributions can give money to others")
        
        # Validate that recipient has higher than average contributions
        if not recipient_stats["is_above_average"]:
            raise ValueError("You can only transfer money to users with above-average contributions")
        
        # Validate transfer amount
        if transfer_data.amount <= 0:
            raise ValueError("Transfer amount must be positive")
        
        # Check if sender can afford this without going into negative contribution
        if sender_stats["user_total"] < transfer_data.amount:
            raise ValueError("Cannot transfer more than your total contributions")
        
        # Create the transfer record
        transfer_dict = {
            "sender_username": sender_username,
            "recipient_username": transfer_data.recipient_username,
            "home_id": sender.home_id,
            "amount": transfer_data.amount,
            "description": transfer_data.description or "Fund transfer to balance contributions",
            "date_created": datetime.utcnow()
        }
        
        result = await db.transfers.insert_one(transfer_dict)
        transfer_dict["id"] = str(result.inserted_id)
        
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
        
        return Transfer(**transfer_dict)

    async def get_user_transfers(self, username: str) -> dict:
        """Get all transfers for a user (sent and received)"""
        db = await self.get_database()
        
        # Get sent transfers
        sent_transfers = []
        async for doc in db.transfers.find({"sender_username": username}).sort("date_created", -1):
            doc["id"] = str(doc["_id"])
            # Get recipient full name
            recipient = await self.get_user(doc["recipient_username"])
            doc["recipient_full_name"] = recipient.full_name if recipient else "Unknown"
            sent_transfers.append(Transfer(**doc))
        
        # Get received transfers
        received_transfers = []
        async for doc in db.transfers.find({"recipient_username": username}).sort("date_created", -1):
            doc["id"] = str(doc["_id"])
            # Get sender full name
            sender = await self.get_user(doc["sender_username"])
            doc["sender_full_name"] = sender.full_name if sender else "Unknown"
            received_transfers.append(Transfer(**doc))
        
        return {
            "sent": sent_transfers,
            "received": received_transfers
        }

    async def get_all_users(self) -> List[UserInDB]:
        """Get all users for transfer recipient selection"""
        db = await self.get_database()
        users = []
        
        async for doc in db.users.find({}, {"hashed_password": 0}).sort("full_name", 1):
            doc["id"] = str(doc["_id"])
            users.append(UserInDB(**doc, hashed_password=""))
        
        return users

    # Home management methods
    async def create_home(self, home_data: HomeCreate, leader_username: str) -> Home:
        db = await self.get_database()
        
        home_dict = {
            "name": home_data.name,
            "description": home_data.description,
            "leader_username": leader_username,
            "members": [leader_username],
            "date_created": datetime.utcnow()
        }
        
        result = await db.homes.insert_one(home_dict)
        home_dict["id"] = str(result.inserted_id)
        
        # Update the user's home_id
        await db.users.update_one(
            {"username": leader_username},
            {"$set": {"home_id": str(result.inserted_id)}}
        )
        
        return Home(**home_dict)

    async def get_home(self, home_id: str) -> Optional[Home]:
        db = await self.get_database()
        from bson import ObjectId
        
        try:
            home_doc = await db.homes.find_one({"_id": ObjectId(home_id)})
            if home_doc:
                home_doc["id"] = str(home_doc["_id"])
                return Home(**home_doc)
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
        from bson import ObjectId
        
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
            await db.homes.update_one(
                {"_id": ObjectId(home_id)},
                {"$addToSet": {"members": username}}
            )
            
            # Update user's home_id
            await db.users.update_one(
                {"username": username},
                {"$set": {"home_id": home_id}}
            )
            
            return True
        except:
            return False

    async def remove_member_from_home(self, home_id: str, username: str, leader_username: str) -> bool:
        db = await self.get_database()
        from bson import ObjectId
        
        # Check if the requester is the home leader
        home = await self.get_home(home_id)
        if not home or home.leader_username != leader_username:
            return False
        
        # Cannot remove the leader
        if username == leader_username:
            return False
        
        try:
            # Remove user from home members
            await db.homes.update_one(
                {"_id": ObjectId(home_id)},
                {"$pull": {"members": username}}
            )
            
            # Remove user's home_id
            await db.users.update_one(
                {"username": username},
                {"$unset": {"home_id": ""}}
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
            from bson import ObjectId
            
            # Remove user from home members
            await db.homes.update_one(
                {"_id": ObjectId(user.home_id)},
                {"$pull": {"members": username}}
            )
            
            # Remove user's home_id
            await db.users.update_one(
                {"username": username},
                {"$unset": {"home_id": ""}}
            )
            
            # If user was the leader and the only member, delete the home
            if home.leader_username == username and len(home.members) == 1:
                await db.homes.delete_one({"_id": ObjectId(user.home_id)})
            
            return True
        except:
            return False

    async def create_join_request(self, username: str, home_name: str) -> bool:
        """Create a join request for a user to join a home"""
        db = await self.get_database()
        
        try:
            # Check if home exists
            home = await db.homes.find_one({"name": home_name})
            if not home:
                return False
            
            # Check if user already has a pending request for this home
            existing_request = await db.join_requests.find_one({
                "username": username,
                "home_id": str(home["_id"]),
                "status": "pending"
            })
            if existing_request:
                return False
            
            # Create join request
            request_data = {
                "username": username,
                "home_id": str(home["_id"]),
                "home_name": home_name,
                "status": "pending",
                "date_created": datetime.utcnow()
            }
            
            await db.join_requests.insert_one(request_data)
            return True
        except:
            return False
    
    async def get_pending_join_requests(self, home_id: str) -> List[dict]:
        """Get all pending join requests for a home"""
        db = await self.get_database()
        
        try:
            requests = []
            cursor = db.join_requests.find({
                "home_id": home_id,
                "status": "pending"
            }).sort("date_created", -1)
            
            async for request in cursor:
                # Get user details
                user = await db.users.find_one({"username": request["username"]})
                if user:
                    request_data = {
                        "id": str(request["_id"]),
                        "username": request["username"],
                        "full_name": user["full_name"],
                        "email": user["email"],
                        "date_created": request["date_created"]
                    }
                    requests.append(request_data)
            
            return requests
        except:
            return []
    
    async def get_user_pending_request(self, username: str) -> Optional[dict]:
        """Get user's pending join request if any"""
        db = await self.get_database()
        
        try:
            request = await db.join_requests.find_one({
                "username": username,
                "status": "pending"
            })
            
            if request:
                return {
                    "id": str(request["_id"]),
                    "home_name": request["home_name"],
                    "date_created": request["date_created"]
                }
            return None
        except:
            return None
    
    async def approve_join_request(self, request_id: str, leader_username: str) -> bool:
        """Approve a join request"""
        db = await self.get_database()
        
        try:
            from bson import ObjectId
            
            # Get the join request
            request = await db.join_requests.find_one({"_id": ObjectId(request_id)})
            if not request or request["status"] != "pending":
                return False
            
            # Verify that the current user is the leader of the home
            home = await db.homes.find_one({"_id": ObjectId(request["home_id"])})
            if not home or home["leader_username"] != leader_username:
                return False
            
            # Add user to home
            await db.users.update_one(
                {"username": request["username"]},
                {"$set": {"home_id": request["home_id"]}}
            )
            
            # Add user to home members
            await db.homes.update_one(
                {"_id": ObjectId(request["home_id"])},
                {"$addToSet": {"members": request["username"]}}
            )
            
            # Update request status
            await db.join_requests.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {"status": "approved", "date_processed": datetime.utcnow()}}
            )
            
            return True
        except:
            return False
    
    async def reject_join_request(self, request_id: str, leader_username: str) -> bool:
        """Reject a join request"""
        db = await self.get_database()
        
        try:
            from bson import ObjectId
            
            # Get the join request
            request = await db.join_requests.find_one({"_id": ObjectId(request_id)})
            if not request or request["status"] != "pending":
                return False
            
            # Verify that the current user is the leader of the home
            home = await db.homes.find_one({"_id": ObjectId(request["home_id"])})
            if not home or home["leader_username"] != leader_username:
                return False
            
            # Update request status
            await db.join_requests.update_one(
                {"_id": ObjectId(request_id)},
                {"$set": {"status": "rejected", "date_processed": datetime.utcnow()}}
            )
            
            return True
        except:
            return False

    async def get_eligible_transfer_recipients(self, sender_username: str) -> List[dict]:
        """Get users in the same home who are eligible to receive fund transfers (above-average contributors)"""
        db = await self.get_database()
        
        try:
            # Get sender's home
            sender = await self.get_user(sender_username)
            if not sender or not sender.home_id:
                return []
            
            home = await self.get_home(sender.home_id)
            if not home:
                return []
            
            # Get home average contribution
            home_total_pipeline = [
                {"$match": {"home_id": sender.home_id}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            
            home_total_result = []
            async for doc in db.contributions.aggregate(home_total_pipeline):
                home_total_result.append(doc)
            home_total = home_total_result[0]["total"] if home_total_result else 0
            
            home_members_count = len(home.members)
            average_contribution = home_total / home_members_count if home_members_count > 0 else 0
            
            # Get eligible recipients (excluding sender)
            eligible_recipients = []
            for member_username in home.members:
                if member_username == sender_username:
                    continue
                
                # Get member's total contribution
                member_total_pipeline = [
                    {"$match": {"username": member_username, "home_id": sender.home_id}},
                    {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
                ]
                
                member_total_result = []
                async for doc in db.contributions.aggregate(member_total_pipeline):
                    member_total_result.append(doc)
                member_total = member_total_result[0]["total"] if member_total_result else 0
                
                # Only include if above average
                if member_total >= average_contribution:
                    member = await self.get_user(member_username)
                    if member:
                        eligible_recipients.append({
                            "username": member_username,
                            "full_name": member.full_name,
                            "total_contribution": member_total,
                            "above_average_by": member_total - average_contribution
                        })
            
            # Sort by contribution amount (highest first)
            eligible_recipients.sort(key=lambda x: x["total_contribution"], reverse=True)
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
            home_total_pipeline = [
                {"$match": {"home_id": user.home_id}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            
            home_total_result = []
            async for doc in db.contributions.aggregate(home_total_pipeline):
                home_total_result.append(doc)
            home_total = home_total_result[0]["total"] if home_total_result else 0
            
            # Get user's total contributions
            user_total_pipeline = [
                {"$match": {"username": username, "home_id": user.home_id}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            
            user_total_result = []
            async for doc in db.contributions.aggregate(user_total_pipeline):
                user_total_result.append(doc)
            user_total = user_total_result[0]["total"] if user_total_result else 0
            
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
