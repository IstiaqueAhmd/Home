import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from typing import Optional, List
from models import User, UserCreate, UserInDB, Contribution, Transfer, TransferCreate, Home, HomeCreate
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
        
        # Contributions by product in this home
        pipeline_by_product = [
            {"$match": {"home_id": home_id}},
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
        
        # User's current balance
        user_balance = await self.get_user_balance(username)
        
        # User's transfer statistics
        sent_transfers = await db.transfers.count_documents({"sender_username": username})
        received_transfers = await db.transfers.count_documents({"recipient_username": username})
        
        # User's recent contributions
        recent_contributions = []
        async for doc in db.contributions.find({"username": username}).sort("date_created", -1).limit(5):
            doc["id"] = str(doc["_id"])
            recent_contributions.append(Contribution(**doc))
        
        return {
            "total_contributions": user_contributions,
            "total_amount": user_total_amount,
            "current_balance": user_balance,
            "sent_transfers": sent_transfers,
            "received_transfers": received_transfers,
            "recent_contributions": recent_contributions
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
        
        # Contributions by product for the month
        product_pipeline = [
            {"$match": match_condition},
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
        
        # Contributions by product for the month in this home
        product_pipeline = [
            {"$match": match_condition},
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
        """Calculate user's available balance from contributions and transfers"""
        db = await self.get_database()
        
        # Get total contributions
        contributions_pipeline = [
            {"$match": {"username": username}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        
        contributions_result = []
        async for doc in db.contributions.aggregate(contributions_pipeline):
            contributions_result.append(doc)
        total_contributions = contributions_result[0]["total"] if contributions_result else 0
        
        # Get total sent transfers
        sent_transfers_pipeline = [
            {"$match": {"sender_username": username}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        
        sent_result = []
        async for doc in db.transfers.aggregate(sent_transfers_pipeline):
            sent_result.append(doc)
        total_sent = sent_result[0]["total"] if sent_result else 0
        
        # Get total received transfers
        received_transfers_pipeline = [
            {"$match": {"recipient_username": username}},
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
        ]
        
        received_result = []
        async for doc in db.transfers.aggregate(received_transfers_pipeline):
            received_result.append(doc)
        total_received = received_result[0]["total"] if received_result else 0
        
        # Balance = contributions + received - sent
        return total_contributions + total_received - total_sent

    async def create_transfer(self, sender_username: str, transfer_data: TransferCreate) -> Transfer:
        """Create a new transfer between users"""
        db = await self.get_database()
        
        # Get sender and recipient users
        sender = await self.get_user(sender_username)
        recipient = await self.get_user(transfer_data.recipient_username)
        
        if not sender or not recipient:
            raise ValueError("User not found")
        
        # Check if both users belong to the same home
        if not sender.home_id or sender.home_id != recipient.home_id:
            raise ValueError("Users must belong to the same home to transfer money")
        
        # Check if sender has sufficient balance
        sender_balance = await self.get_user_balance(sender_username)
        if sender_balance < transfer_data.amount:
            raise ValueError("Insufficient balance for transfer")
        
        # Check if sender is not transferring to themselves
        if sender_username == transfer_data.recipient_username:
            raise ValueError("Cannot transfer to yourself")
        
        transfer_dict = {
            "sender_username": sender_username,
            "recipient_username": transfer_data.recipient_username,
            "home_id": sender.home_id,
            "amount": transfer_data.amount,
            "description": transfer_data.description or "",
            "date_created": datetime.utcnow()
        }
        
        result = await db.transfers.insert_one(transfer_dict)
        transfer_dict["id"] = str(result.inserted_id)
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
