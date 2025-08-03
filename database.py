import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from typing import Optional, List
from models import User, UserCreate, UserInDB, Contribution, Transfer
from auth import AuthManager
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        self.mongodb_url = os.getenv("MONGODB_URL", "mongodb://localhost:27017")
        self.database_name = os.getenv("DATABASE_NAME", "house_finance_tracker")
        self.client = None
        self.database = None
        self.auth_manager = AuthManager()
        
    async def connect_to_mongo(self):
        self.client = AsyncIOMotorClient(self.mongodb_url)
        self.database = self.client[self.database_name]
        
    async def close_mongo_connection(self):
        if self.client:
            self.client.close()
    
    async def get_database(self):
        if self.database is None:
            await self.connect_to_mongo()
        return self.database
    
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
        
        contribution_dict = {
            "username": username,
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
        
        # Contributions by product
        pipeline_by_product = [
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
    
    async def get_user_statistics(self, username: str) -> dict:
        db = await self.get_database()
        
        # User's total contributions
        user_contributions = await db.contributions.count_documents({"username": username})
        
        # User's total amount
        pipeline_user_total = [
            {"$match": {"username": username}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        user_total_result = []
        async for doc in db.contributions.aggregate(pipeline_user_total):
            user_total_result.append(doc)
        user_total_amount = user_total_result[0]["total"] if user_total_result else 0
        
        # User's recent contributions
        recent_contributions = []
        async for doc in db.contributions.find({"username": username}).sort("date_created", -1).limit(5):
            doc["id"] = str(doc["_id"])
            recent_contributions.append(Contribution(**doc))
        
        return {
            "total_contributions": user_contributions,
            "total_amount": user_total_amount,
            "recent_contributions": recent_contributions
        }
    
    async def update_user_profile(self, username: str, full_name: str, email: str) -> bool:
        db = await self.get_database()
        
        result = await db.users.update_one(
            {"username": username},
            {"$set": {"full_name": full_name, "email": email}}
        )
        
        return result.modified_count > 0
    
    async def get_all_users_except(self, exclude_username: str) -> List[User]:
        db = await self.get_database()
        users = []
        
        async for doc in db.users.find({"username": {"$ne": exclude_username}, "is_active": True}):
            doc["id"] = str(doc["_id"])
            users.append(User(**doc))
        
        return users
    
    async def get_user_balance(self, username: str) -> float:
        db = await self.get_database()
        
        # Calculate balance from contributions (money spent)
        contributions_pipeline = [
            {"$match": {"username": username}},
            {"$group": {"_id": None, "total_spent": {"$sum": "$amount"}}}
        ]
        
        total_spent = 0
        async for doc in db.contributions.aggregate(contributions_pipeline):
            total_spent = doc["total_spent"]
        
        # Calculate money received from transfers
        received_pipeline = [
            {"$match": {"to_username": username}},
            {"$group": {"_id": None, "total_received": {"$sum": "$amount"}}}
        ]
        
        total_received = 0
        async for doc in db.transfers.aggregate(received_pipeline):
            total_received = doc["total_received"]
        
        # Calculate money sent via transfers
        sent_pipeline = [
            {"$match": {"from_username": username}},
            {"$group": {"_id": None, "total_sent": {"$sum": "$amount"}}}
        ]
        
        total_sent = 0
        async for doc in db.transfers.aggregate(sent_pipeline):
            total_sent = doc["total_sent"]
        
        # Balance = money received - money spent - money transferred out
        balance = total_received - total_spent - total_sent
        return balance
    
    async def create_transfer(self, from_username: str, to_username: str, amount: float, description: str = "") -> bool:
        db = await self.get_database()
        
        try:
            # Create transfer record
            transfer_dict = {
                "from_username": from_username,
                "to_username": to_username,
                "amount": amount,
                "description": description,
                "date_created": datetime.utcnow()
            }
            
            result = await db.transfers.insert_one(transfer_dict)
            return result.inserted_id is not None
            
        except Exception as e:
            print(f"Transfer error: {e}")
            return False
    
    async def get_user_transfers(self, username: str) -> List[dict]:
        db = await self.get_database()
        transfers = []
        
        # Get transfers where user is sender or receiver
        pipeline = [
            {
                "$match": {
                    "$or": [
                        {"from_username": username},
                        {"to_username": username}
                    ]
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "from_username",
                    "foreignField": "username",
                    "as": "from_user_info"
                }
            },
            {
                "$lookup": {
                    "from": "users",
                    "localField": "to_username",
                    "foreignField": "username",
                    "as": "to_user_info"
                }
            },
            {
                "$unwind": "$from_user_info"
            },
            {
                "$unwind": "$to_user_info"
            },
            {
                "$sort": {"date_created": -1}
            }
        ]
        
        async for doc in db.transfers.aggregate(pipeline):
            transfer_data = {
                "id": str(doc["_id"]),
                "from_username": doc["from_username"],
                "to_username": doc["to_username"],
                "amount": doc["amount"],
                "description": doc.get("description", ""),
                "date_created": doc["date_created"],
                "from_user_full_name": doc["from_user_info"]["full_name"],
                "to_user_full_name": doc["to_user_info"]["full_name"],
                "is_sender": doc["from_username"] == username,
                "is_receiver": doc["to_username"] == username
            }
            transfers.append(transfer_data)
        
        return transfers
    
    async def get_all_user_balances(self) -> List[dict]:
        db = await self.get_database()
        user_balances = []
        
        # Get all users
        async for user_doc in db.users.find({"is_active": True}):
            username = user_doc["username"]
            balance = await self.get_user_balance(username)
            
            user_balances.append({
                "username": username,
                "full_name": user_doc["full_name"],
                "balance": balance
            })
        
        # Sort by balance descending
        user_balances.sort(key=lambda x: x["balance"], reverse=True)
        return user_balances
