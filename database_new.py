import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func, and_, or_, extract, desc
from sqlalchemy.exc import IntegrityError
from typing import Optional, List
from models import User, UserCreate, UserInDB, Contribution, Transfer, TransferCreate, Home, HomeCreate
from db_models import Base, User as DBUser, Home as DBHome, Contribution as DBContribution, Transfer as DBTransfer, JoinRequest as DBJoinRequest
from auth import AuthManager
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        # For PostgreSQL: postgresql+asyncpg://user:password@host:port/database
        # For SQLite (development): sqlite+aiosqlite:///./database.db
        self.database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./house_finance_tracker.db")
        self.engine = None
        self.SessionLocal = None
        self.auth_manager = AuthManager()
        
    async def connect_to_db(self):
        try:
            self.engine = create_async_engine(
                self.database_url,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,
                pool_recycle=300
            )
            
            self.SessionLocal = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            print("Database connection successful")
        except Exception as e:
            print(f"Database connection failed: {str(e)}")
            raise e
        
    async def close_db_connection(self):
        if self.engine:
            await self.engine.dispose()
    
    async def get_session(self) -> AsyncSession:
        if self.SessionLocal is None:
            await self.connect_to_db()
        return self.SessionLocal()
    
    async def create_user(self, user: UserCreate) -> UserInDB:
        async with await self.get_session() as session:
            hashed_password = self.auth_manager.get_password_hash(user.password)
            
            db_user = DBUser(
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                hashed_password=hashed_password,
                is_active=True,
                date_created=datetime.utcnow()
            )
            
            try:
                session.add(db_user)
                await session.commit()
                await session.refresh(db_user)
                
                return UserInDB(
                    id=db_user.id,
                    username=db_user.username,
                    email=db_user.email,
                    full_name=db_user.full_name,
                    is_active=db_user.is_active,
                    home_id=db_user.home_id,
                    hashed_password=db_user.hashed_password
                )
            except IntegrityError:
                await session.rollback()
                raise ValueError("User already exists")
    
    async def get_user(self, username: str) -> Optional[UserInDB]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                return UserInDB(
                    id=db_user.id,
                    username=db_user.username,
                    email=db_user.email,
                    full_name=db_user.full_name,
                    is_active=db_user.is_active,
                    home_id=db_user.home_id,
                    hashed_password=db_user.hashed_password
                )
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[UserInDB]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBUser).where(DBUser.email == email)
            )
            db_user = result.scalar_one_or_none()
            
            if db_user:
                return UserInDB(
                    id=db_user.id,
                    username=db_user.username,
                    email=db_user.email,
                    full_name=db_user.full_name,
                    is_active=db_user.is_active,
                    home_id=db_user.home_id,
                    hashed_password=db_user.hashed_password
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
        async with await self.get_session() as session:
            # Get user
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or not user.home_id:
                raise ValueError("User must belong to a home to create contributions")
            
            db_contribution = DBContribution(
                user_id=user.id,
                home_id=user.home_id,
                product_name=contribution_data["product_name"],
                amount=contribution_data["amount"],
                description=contribution_data.get("description", ""),
                date_created=datetime.utcnow()
            )
            
            session.add(db_contribution)
            await session.commit()
            await session.refresh(db_contribution)
            
            return Contribution(
                id=db_contribution.id,
                username=username,
                home_id=db_contribution.home_id,
                product_name=db_contribution.product_name,
                amount=db_contribution.amount,
                description=db_contribution.description,
                date_created=db_contribution.date_created
            )
    
    async def get_user_contributions(self, username: str) -> List[Contribution]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBContribution)
                .join(DBUser)
                .where(DBUser.username == username)
                .order_by(desc(DBContribution.date_created))
            )
            db_contributions = result.scalars().all()
            
            contributions = []
            for db_contrib in db_contributions:
                contributions.append(Contribution(
                    id=db_contrib.id,
                    username=username,
                    home_id=db_contrib.home_id,
                    product_name=db_contrib.product_name,
                    amount=db_contrib.amount,
                    description=db_contrib.description,
                    date_created=db_contrib.date_created
                ))
            
            return contributions

    async def get_home_contributions(self, home_id: str) -> List[Contribution]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBContribution, DBUser)
                .join(DBUser)
                .where(DBContribution.home_id == home_id)
                .order_by(desc(DBContribution.date_created))
            )
            
            contributions = []
            for db_contrib, db_user in result.all():
                contributions.append(Contribution(
                    id=db_contrib.id,
                    username=db_user.username,
                    home_id=db_contrib.home_id,
                    product_name=db_contrib.product_name,
                    amount=db_contrib.amount,
                    description=db_contrib.description,
                    date_created=db_contrib.date_created
                ))
            
            return contributions
    
    async def get_all_contributions(self) -> List[Contribution]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBContribution, DBUser)
                .join(DBUser)
                .order_by(desc(DBContribution.date_created))
            )
            
            contributions = []
            for db_contrib, db_user in result.all():
                contributions.append(Contribution(
                    id=db_contrib.id,
                    username=db_user.username,
                    home_id=db_contrib.home_id,
                    product_name=db_contrib.product_name,
                    amount=db_contrib.amount,
                    description=db_contrib.description,
                    date_created=db_contrib.date_created
                ))
            
            return contributions
    
    async def get_all_contributions_with_users(self) -> List[dict]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBContribution, DBUser)
                .join(DBUser)
                .order_by(desc(DBContribution.date_created))
            )
            
            contributions = []
            for db_contrib, db_user in result.all():
                contribution_data = {
                    "id": db_contrib.id,
                    "username": db_user.username,
                    "home_id": db_contrib.home_id,
                    "product_name": db_contrib.product_name,
                    "amount": db_contrib.amount,
                    "description": db_contrib.description or "",
                    "date_created": db_contrib.date_created,
                    "user_full_name": db_user.full_name
                }
                contributions.append(contribution_data)
            
            return contributions

    async def get_home_contributions_with_users(self, home_id: str) -> List[dict]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBContribution, DBUser)
                .join(DBUser)
                .where(DBContribution.home_id == home_id)
                .order_by(desc(DBContribution.date_created))
            )
            
            contributions = []
            for db_contrib, db_user in result.all():
                contribution_data = {
                    "id": db_contrib.id,
                    "username": db_user.username,
                    "home_id": db_contrib.home_id,
                    "product_name": db_contrib.product_name,
                    "amount": db_contrib.amount,
                    "description": db_contrib.description or "",
                    "date_created": db_contrib.date_created,
                    "user_full_name": db_user.full_name
                }
                contributions.append(contribution_data)
            
            return contributions
    
    async def delete_contribution(self, contribution_id: str, username: str) -> bool:
        async with await self.get_session() as session:
            # Get user first
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                return False
            
            # Delete contribution only if it belongs to the user
            result = await session.execute(
                select(DBContribution).where(
                    and_(DBContribution.id == contribution_id, DBContribution.user_id == user.id)
                )
            )
            contribution = result.scalar_one_or_none()
            
            if contribution:
                await session.delete(contribution)
                await session.commit()
                return True
            
            return False

    async def get_analytics(self) -> dict:
        async with await self.get_session() as session:
            # Total contributions
            total_contributions_result = await session.execute(
                select(func.count(DBContribution.id))
            )
            total_contributions = total_contributions_result.scalar()
            
            # Total amount
            total_amount_result = await session.execute(
                select(func.sum(DBContribution.amount))
            )
            total_amount = total_amount_result.scalar() or 0
            
            # Contributions by user
            contributions_by_user_result = await session.execute(
                select(
                    DBUser.username,
                    DBUser.full_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .select_from(DBContribution)
                .join(DBUser)
                .group_by(DBUser.username, DBUser.full_name)
                .order_by(desc('total_amount'))
            )
            
            contributions_by_user = []
            for row in contributions_by_user_result.all():
                contributions_by_user.append({
                    "username": row.username,
                    "full_name": row.full_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            # Contributions by product
            contributions_by_product_result = await session.execute(
                select(
                    DBContribution.product_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .group_by(DBContribution.product_name)
                .order_by(desc('total_amount'))
            )
            
            contributions_by_product = []
            for row in contributions_by_product_result.all():
                contributions_by_product.append({
                    "product_name": row.product_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            # Monthly contributions
            monthly_contributions_result = await session.execute(
                select(
                    extract('year', DBContribution.date_created).label('year'),
                    extract('month', DBContribution.date_created).label('month'),
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .group_by('year', 'month')
                .order_by(desc('year'), desc('month'))
            )
            
            monthly_contributions = []
            for row in monthly_contributions_result.all():
                monthly_contributions.append({
                    "year": int(row.year),
                    "month": int(row.month),
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            return {
                "total_contributions": total_contributions,
                "total_amount": float(total_amount),
                "contributions_by_user": contributions_by_user,
                "contributions_by_product": contributions_by_product,
                "monthly_contributions": monthly_contributions
            }

    async def get_home_analytics(self, home_id: str) -> dict:
        async with await self.get_session() as session:
            # Total contributions for this home
            total_contributions_result = await session.execute(
                select(func.count(DBContribution.id))
                .where(DBContribution.home_id == home_id)
            )
            total_contributions = total_contributions_result.scalar()
            
            # Total amount for this home
            total_amount_result = await session.execute(
                select(func.sum(DBContribution.amount))
                .where(DBContribution.home_id == home_id)
            )
            total_amount = total_amount_result.scalar() or 0
            
            # Contributions by user in this home
            contributions_by_user_result = await session.execute(
                select(
                    DBUser.username,
                    DBUser.full_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .select_from(DBContribution)
                .join(DBUser)
                .where(DBContribution.home_id == home_id)
                .group_by(DBUser.username, DBUser.full_name)
                .order_by(desc('total_amount'))
            )
            
            contributions_by_user = []
            for row in contributions_by_user_result.all():
                contributions_by_user.append({
                    "username": row.username,
                    "full_name": row.full_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            # Contributions by product in this home
            contributions_by_product_result = await session.execute(
                select(
                    DBContribution.product_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .where(DBContribution.home_id == home_id)
                .group_by(DBContribution.product_name)
                .order_by(desc('total_amount'))
            )
            
            contributions_by_product = []
            for row in contributions_by_product_result.all():
                contributions_by_product.append({
                    "product_name": row.product_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            # Monthly contributions for this home
            monthly_contributions_result = await session.execute(
                select(
                    extract('year', DBContribution.date_created).label('year'),
                    extract('month', DBContribution.date_created).label('month'),
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .where(DBContribution.home_id == home_id)
                .group_by('year', 'month')
                .order_by(desc('year'), desc('month'))
            )
            
            monthly_contributions = []
            for row in monthly_contributions_result.all():
                monthly_contributions.append({
                    "year": int(row.year),
                    "month": int(row.month),
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            return {
                "total_contributions": total_contributions,
                "total_amount": float(total_amount),
                "contributions_by_user": contributions_by_user,
                "contributions_by_product": contributions_by_product,
                "monthly_contributions": monthly_contributions
            }

    async def get_user_balance(self, username: str) -> float:
        """Calculate user's available balance from contributions and transfers"""
        async with await self.get_session() as session:
            # Get user
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                return 0.0
            
            # Get total contributions
            contributions_result = await session.execute(
                select(func.sum(DBContribution.amount))
                .where(DBContribution.user_id == user.id)
            )
            total_contributions = contributions_result.scalar() or 0
            
            # Get total sent transfers
            sent_result = await session.execute(
                select(func.sum(DBTransfer.amount))
                .where(DBTransfer.sender_id == user.id)
            )
            total_sent = sent_result.scalar() or 0
            
            # Get total received transfers
            received_result = await session.execute(
                select(func.sum(DBTransfer.amount))
                .where(DBTransfer.recipient_id == user.id)
            )
            total_received = received_result.scalar() or 0
            
            # Balance = contributions + received - sent
            return float(total_contributions + total_received - total_sent)

    async def create_transfer(self, sender_username: str, transfer_data: TransferCreate) -> Transfer:
        """Create a new transfer between users"""
        async with await self.get_session() as session:
            # Get sender and recipient users
            sender_result = await session.execute(
                select(DBUser).where(DBUser.username == sender_username)
            )
            sender = sender_result.scalar_one_or_none()
            
            recipient_result = await session.execute(
                select(DBUser).where(DBUser.username == transfer_data.recipient_username)
            )
            recipient = recipient_result.scalar_one_or_none()
            
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
            
            db_transfer = DBTransfer(
                sender_id=sender.id,
                recipient_id=recipient.id,
                home_id=sender.home_id,
                amount=transfer_data.amount,
                description=transfer_data.description or "",
                date_created=datetime.utcnow()
            )
            
            session.add(db_transfer)
            await session.commit()
            await session.refresh(db_transfer)
            
            return Transfer(
                id=db_transfer.id,
                sender_username=sender_username,
                recipient_username=transfer_data.recipient_username,
                home_id=db_transfer.home_id,
                amount=db_transfer.amount,
                description=db_transfer.description,
                date_created=db_transfer.date_created
            )

    async def get_user_transfers(self, username: str) -> dict:
        """Get all transfers for a user (sent and received)"""
        async with await self.get_session() as session:
            # Get user
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                return {"sent": [], "received": []}
            
            # Get sent transfers
            sent_result = await session.execute(
                select(DBTransfer, DBUser)
                .join(DBUser, DBTransfer.recipient_id == DBUser.id)
                .where(DBTransfer.sender_id == user.id)
                .order_by(desc(DBTransfer.date_created))
            )
            
            sent_transfers = []
            for db_transfer, recipient in sent_result.all():
                transfer = Transfer(
                    id=db_transfer.id,
                    sender_username=username,
                    recipient_username=recipient.username,
                    home_id=db_transfer.home_id,
                    amount=db_transfer.amount,
                    description=db_transfer.description,
                    date_created=db_transfer.date_created
                )
                # Add recipient full name as additional attribute
                transfer.recipient_full_name = recipient.full_name
                sent_transfers.append(transfer)
            
            # Get received transfers
            received_result = await session.execute(
                select(DBTransfer, DBUser)
                .join(DBUser, DBTransfer.sender_id == DBUser.id)
                .where(DBTransfer.recipient_id == user.id)
                .order_by(desc(DBTransfer.date_created))
            )
            
            received_transfers = []
            for db_transfer, sender in received_result.all():
                transfer = Transfer(
                    id=db_transfer.id,
                    sender_username=sender.username,
                    recipient_username=username,
                    home_id=db_transfer.home_id,
                    amount=db_transfer.amount,
                    description=db_transfer.description,
                    date_created=db_transfer.date_created
                )
                # Add sender full name as additional attribute
                transfer.sender_full_name = sender.full_name
                received_transfers.append(transfer)
            
            return {
                "sent": sent_transfers,
                "received": received_transfers
            }

    async def get_all_users(self) -> List[UserInDB]:
        """Get all users for transfer recipient selection"""
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBUser).order_by(DBUser.full_name)
            )
            db_users = result.scalars().all()
            
            users = []
            for db_user in db_users:
                users.append(UserInDB(
                    id=db_user.id,
                    username=db_user.username,
                    email=db_user.email,
                    full_name=db_user.full_name,
                    is_active=db_user.is_active,
                    home_id=db_user.home_id,
                    hashed_password=""  # Don't return password
                ))
            
            return users

    # Home management methods
    async def create_home(self, home_data: HomeCreate, leader_username: str) -> Home:
        async with await self.get_session() as session:
            # Get leader user
            leader_result = await session.execute(
                select(DBUser).where(DBUser.username == leader_username)
            )
            leader = leader_result.scalar_one_or_none()
            
            if not leader:
                raise ValueError("Leader user not found")
            
            db_home = DBHome(
                name=home_data.name,
                description=home_data.description,
                leader_id=leader.id,
                date_created=datetime.utcnow()
            )
            
            session.add(db_home)
            await session.commit()
            await session.refresh(db_home)
            
            # Update the user's home_id
            leader.home_id = db_home.id
            await session.commit()
            
            return Home(
                id=db_home.id,
                name=db_home.name,
                description=db_home.description,
                leader_username=leader_username,
                members=[leader_username],
                date_created=db_home.date_created
            )

    async def get_home(self, home_id: str) -> Optional[Home]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBHome, DBUser)
                .join(DBUser, DBHome.leader_id == DBUser.id)
                .where(DBHome.id == home_id)
            )
            
            home_data = result.first()
            if not home_data:
                return None
            
            db_home, leader = home_data
            
            # Get all members
            members_result = await session.execute(
                select(DBUser).where(DBUser.home_id == home_id)
            )
            members = [member.username for member in members_result.scalars().all()]
            
            return Home(
                id=db_home.id,
                name=db_home.name,
                description=db_home.description,
                leader_username=leader.username,
                members=members,
                date_created=db_home.date_created
            )

    async def get_user_home(self, username: str) -> Optional[Home]:
        user = await self.get_user(username)
        if user and user.home_id:
            return await self.get_home(user.home_id)
        return None

    async def add_member_to_home(self, home_id: str, username: str, leader_username: str) -> bool:
        async with await self.get_session() as session:
            # Check if the requester is the home leader
            home = await self.get_home(home_id)
            if not home or home.leader_username != leader_username:
                return False
            
            # Get user to add
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            # Check if user exists and is not already in a home
            if not user or user.home_id:
                return False
            
            try:
                # Update user's home_id
                user.home_id = home_id
                await session.commit()
                return True
            except:
                await session.rollback()
                return False

    async def remove_member_from_home(self, home_id: str, username: str, leader_username: str) -> bool:
        async with await self.get_session() as session:
            # Check if the requester is the home leader
            home = await self.get_home(home_id)
            if not home or home.leader_username != leader_username:
                return False
            
            # Cannot remove the leader
            if username == leader_username:
                return False
            
            # Get user to remove
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or user.home_id != home_id:
                return False
            
            try:
                # Remove user's home_id
                user.home_id = None
                await session.commit()
                return True
            except:
                await session.rollback()
                return False

    async def get_home_members(self, home_id: str) -> List[User]:
        async with await self.get_session() as session:
            result = await session.execute(
                select(DBUser).where(DBUser.home_id == home_id)
            )
            db_users = result.scalars().all()
            
            members = []
            for db_user in db_users:
                members.append(User(
                    id=db_user.id,
                    username=db_user.username,
                    email=db_user.email,
                    full_name=db_user.full_name,
                    is_active=db_user.is_active,
                    home_id=db_user.home_id
                ))
            
            return members

    async def leave_home(self, username: str) -> bool:
        async with await self.get_session() as session:
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user or not user.home_id:
                return False
            
            home = await self.get_home(user.home_id)
            if not home:
                return False
            
            # If user is the leader, they cannot leave unless they're the only member
            if home.leader_username == username and len(home.members) > 1:
                return False
            
            try:
                home_id = user.home_id
                
                # Remove user's home_id
                user.home_id = None
                
                # If user was the leader and the only member, delete the home
                if home.leader_username == username and len(home.members) == 1:
                    home_result = await session.execute(
                        select(DBHome).where(DBHome.id == home_id)
                    )
                    db_home = home_result.scalar_one_or_none()
                    if db_home:
                        await session.delete(db_home)
                
                await session.commit()
                return True
            except:
                await session.rollback()
                return False

    async def create_join_request(self, username: str, home_name: str) -> bool:
        """Create a join request for a user to join a home"""
        async with await self.get_session() as session:
            try:
                # Get home by name
                home_result = await session.execute(
                    select(DBHome).where(DBHome.name == home_name)
                )
                home = home_result.scalar_one_or_none()
                
                if not home:
                    return False
                
                # Get user
                user_result = await session.execute(
                    select(DBUser).where(DBUser.username == username)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return False
                
                # Check if user already has a pending request for this home
                existing_result = await session.execute(
                    select(DBJoinRequest).where(
                        and_(
                            DBJoinRequest.user_id == user.id,
                            DBJoinRequest.home_id == home.id,
                            DBJoinRequest.status == "pending"
                        )
                    )
                )
                
                if existing_result.scalar_one_or_none():
                    return False
                
                # Create join request
                db_request = DBJoinRequest(
                    user_id=user.id,
                    home_id=home.id,
                    status="pending",
                    date_created=datetime.utcnow()
                )
                
                session.add(db_request)
                await session.commit()
                return True
            except:
                await session.rollback()
                return False
    
    async def get_pending_join_requests(self, home_id: str) -> List[dict]:
        """Get all pending join requests for a home"""
        async with await self.get_session() as session:
            try:
                result = await session.execute(
                    select(DBJoinRequest, DBUser)
                    .join(DBUser)
                    .where(
                        and_(
                            DBJoinRequest.home_id == home_id,
                            DBJoinRequest.status == "pending"
                        )
                    )
                    .order_by(desc(DBJoinRequest.date_created))
                )
                
                requests = []
                for db_request, db_user in result.all():
                    requests.append({
                        "id": db_request.id,
                        "username": db_user.username,
                        "full_name": db_user.full_name,
                        "email": db_user.email,
                        "date_created": db_request.date_created
                    })
                
                return requests
            except:
                return []
    
    async def get_user_pending_request(self, username: str) -> Optional[dict]:
        """Get user's pending join request if any"""
        async with await self.get_session() as session:
            try:
                user_result = await session.execute(
                    select(DBUser).where(DBUser.username == username)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return None
                
                result = await session.execute(
                    select(DBJoinRequest, DBHome)
                    .join(DBHome)
                    .where(
                        and_(
                            DBJoinRequest.user_id == user.id,
                            DBJoinRequest.status == "pending"
                        )
                    )
                )
                
                request_data = result.first()
                if request_data:
                    db_request, db_home = request_data
                    return {
                        "id": db_request.id,
                        "home_name": db_home.name,
                        "date_created": db_request.date_created
                    }
                return None
            except:
                return None
    
    async def approve_join_request(self, request_id: str, leader_username: str) -> bool:
        """Approve a join request"""
        async with await self.get_session() as session:
            try:
                # Get the join request
                request_result = await session.execute(
                    select(DBJoinRequest, DBUser, DBHome)
                    .join(DBUser, DBJoinRequest.user_id == DBUser.id)
                    .join(DBHome, DBJoinRequest.home_id == DBHome.id)
                    .where(DBJoinRequest.id == request_id)
                )
                
                request_data = request_result.first()
                if not request_data:
                    return False
                
                db_request, requesting_user, db_home = request_data
                
                if db_request.status != "pending":
                    return False
                
                # Verify that the current user is the leader of the home
                leader_result = await session.execute(
                    select(DBUser).where(DBUser.id == db_home.leader_id)
                )
                leader = leader_result.scalar_one_or_none()
                
                if not leader or leader.username != leader_username:
                    return False
                
                # Add user to home
                requesting_user.home_id = db_home.id
                
                # Update request status
                db_request.status = "approved"
                db_request.date_processed = datetime.utcnow()
                
                await session.commit()
                return True
            except:
                await session.rollback()
                return False
    
    async def reject_join_request(self, request_id: str, leader_username: str) -> bool:
        """Reject a join request"""
        async with await self.get_session() as session:
            try:
                # Get the join request
                request_result = await session.execute(
                    select(DBJoinRequest, DBHome)
                    .join(DBHome, DBJoinRequest.home_id == DBHome.id)
                    .where(DBJoinRequest.id == request_id)
                )
                
                request_data = request_result.first()
                if not request_data:
                    return False
                
                db_request, db_home = request_data
                
                if db_request.status != "pending":
                    return False
                
                # Verify that the current user is the leader of the home
                leader_result = await session.execute(
                    select(DBUser).where(DBUser.id == db_home.leader_id)
                )
                leader = leader_result.scalar_one_or_none()
                
                if not leader or leader.username != leader_username:
                    return False
                
                # Update request status
                db_request.status = "rejected"
                db_request.date_processed = datetime.utcnow()
                
                await session.commit()
                return True
            except:
                await session.rollback()
                return False

    # Additional methods for compatibility
    async def get_user_statistics(self, username: str) -> dict:
        async with await self.get_session() as session:
            # Get user
            user_result = await session.execute(
                select(DBUser).where(DBUser.username == username)
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                return {
                    "total_contributions": 0,
                    "total_amount": 0,
                    "current_balance": 0,
                    "sent_transfers": 0,
                    "received_transfers": 0,
                    "recent_contributions": []
                }
            
            # User's total contributions
            user_contributions_result = await session.execute(
                select(func.count(DBContribution.id))
                .where(DBContribution.user_id == user.id)
            )
            user_contributions = user_contributions_result.scalar()
            
            # User's total amount
            user_total_result = await session.execute(
                select(func.sum(DBContribution.amount))
                .where(DBContribution.user_id == user.id)
            )
            user_total_amount = user_total_result.scalar() or 0
            
            # User's current balance
            user_balance = await self.get_user_balance(username)
            
            # User's transfer statistics
            sent_transfers_result = await session.execute(
                select(func.count(DBTransfer.id))
                .where(DBTransfer.sender_id == user.id)
            )
            sent_transfers = sent_transfers_result.scalar()
            
            received_transfers_result = await session.execute(
                select(func.count(DBTransfer.id))
                .where(DBTransfer.recipient_id == user.id)
            )
            received_transfers = received_transfers_result.scalar()
            
            # User's recent contributions
            recent_result = await session.execute(
                select(DBContribution)
                .where(DBContribution.user_id == user.id)
                .order_by(desc(DBContribution.date_created))
                .limit(5)
            )
            
            recent_contributions = []
            for db_contrib in recent_result.scalars().all():
                recent_contributions.append(Contribution(
                    id=db_contrib.id,
                    username=username,
                    home_id=db_contrib.home_id,
                    product_name=db_contrib.product_name,
                    amount=db_contrib.amount,
                    description=db_contrib.description,
                    date_created=db_contrib.date_created
                ))
            
            return {
                "total_contributions": user_contributions,
                "total_amount": float(user_total_amount),
                "current_balance": user_balance,
                "sent_transfers": sent_transfers,
                "received_transfers": received_transfers,
                "recent_contributions": recent_contributions
            }
    
    async def update_user_profile(self, username: str, full_name: str, email: str) -> bool:
        async with await self.get_session() as session:
            try:
                result = await session.execute(
                    select(DBUser).where(DBUser.username == username)
                )
                user = result.scalar_one_or_none()
                
                if not user:
                    return False
                
                user.full_name = full_name
                user.email = email
                await session.commit()
                return True
            except:
                await session.rollback()
                return False

    async def get_monthly_contributions(self, year: int = None, month: int = None) -> List[dict]:
        """Get contributions filtered by month and year"""
        async with await self.get_session() as session:
            query = select(DBContribution, DBUser).join(DBUser)
            
            if year and month:
                # Get contributions for specific month
                query = query.where(
                    and_(
                        extract('year', DBContribution.date_created) == year,
                        extract('month', DBContribution.date_created) == month
                    )
                )
            elif year:
                # Get contributions for entire year
                query = query.where(extract('year', DBContribution.date_created) == year)
            
            query = query.order_by(desc(DBContribution.date_created))
            result = await session.execute(query)
            
            contributions = []
            for db_contrib, db_user in result.all():
                contribution_data = {
                    "id": db_contrib.id,
                    "username": db_user.username,
                    "product_name": db_contrib.product_name,
                    "amount": db_contrib.amount,
                    "description": db_contrib.description or "",
                    "date_created": db_contrib.date_created,
                    "user_full_name": db_user.full_name
                }
                contributions.append(contribution_data)
            
            return contributions

    async def get_home_monthly_contributions(self, home_id: str, year: int = None, month: int = None) -> List[dict]:
        """Get contributions filtered by home, month and year"""
        async with await self.get_session() as session:
            query = select(DBContribution, DBUser).join(DBUser).where(DBContribution.home_id == home_id)
            
            if year and month:
                # Get contributions for specific month
                query = query.where(
                    and_(
                        extract('year', DBContribution.date_created) == year,
                        extract('month', DBContribution.date_created) == month
                    )
                )
            elif year:
                # Get contributions for entire year
                query = query.where(extract('year', DBContribution.date_created) == year)
            
            query = query.order_by(desc(DBContribution.date_created))
            result = await session.execute(query)
            
            contributions = []
            for db_contrib, db_user in result.all():
                contribution_data = {
                    "id": db_contrib.id,
                    "username": db_user.username,
                    "home_id": db_contrib.home_id,
                    "product_name": db_contrib.product_name,
                    "amount": db_contrib.amount,
                    "description": db_contrib.description or "",
                    "date_created": db_contrib.date_created,
                    "user_full_name": db_user.full_name
                }
                contributions.append(contribution_data)
            
            return contributions

    async def get_monthly_summary(self, year: int, month: int) -> dict:
        """Get monthly summary statistics"""
        async with await self.get_session() as session:
            # Base condition for the month
            month_condition = and_(
                extract('year', DBContribution.date_created) == year,
                extract('month', DBContribution.date_created) == month
            )
            
            # Total contributions and amount for the month
            total_result = await session.execute(
                select(
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('total_count')
                )
                .where(month_condition)
            )
            
            total_data = total_result.first()
            total_amount = float(total_data.total_amount) if total_data.total_amount else 0
            total_count = total_data.total_count
            
            # Contributions by user for the month
            user_result = await session.execute(
                select(
                    DBUser.username,
                    DBUser.full_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .select_from(DBContribution)
                .join(DBUser)
                .where(month_condition)
                .group_by(DBUser.username, DBUser.full_name)
                .order_by(desc('total_amount'))
            )
            
            user_contributions = []
            for row in user_result.all():
                user_contributions.append({
                    "username": row.username,
                    "full_name": row.full_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            # Contributions by product for the month
            product_result = await session.execute(
                select(
                    DBContribution.product_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .where(month_condition)
                .group_by(DBContribution.product_name)
                .order_by(desc('total_amount'))
            )
            
            product_contributions = []
            for row in product_result.all():
                product_contributions.append({
                    "product_name": row.product_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
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
        async with await self.get_session() as session:
            # Base condition for the month and home
            month_condition = and_(
                DBContribution.home_id == home_id,
                extract('year', DBContribution.date_created) == year,
                extract('month', DBContribution.date_created) == month
            )
            
            # Total contributions and amount for the month in this home
            total_result = await session.execute(
                select(
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('total_count')
                )
                .where(month_condition)
            )
            
            total_data = total_result.first()
            total_amount = float(total_data.total_amount) if total_data.total_amount else 0
            total_count = total_data.total_count
            
            # Contributions by user for the month in this home
            user_result = await session.execute(
                select(
                    DBUser.username,
                    DBUser.full_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .select_from(DBContribution)
                .join(DBUser)
                .where(month_condition)
                .group_by(DBUser.username, DBUser.full_name)
                .order_by(desc('total_amount'))
            )
            
            user_contributions = []
            for row in user_result.all():
                user_contributions.append({
                    "username": row.username,
                    "full_name": row.full_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            # Contributions by product for the month in this home
            product_result = await session.execute(
                select(
                    DBContribution.product_name,
                    func.sum(DBContribution.amount).label('total_amount'),
                    func.count(DBContribution.id).label('count')
                )
                .where(month_condition)
                .group_by(DBContribution.product_name)
                .order_by(desc('total_amount'))
            )
            
            product_contributions = []
            for row in product_result.all():
                product_contributions.append({
                    "product_name": row.product_name,
                    "total_amount": float(row.total_amount) if row.total_amount else 0,
                    "count": row.count
                })
            
            return {
                "year": year,
                "month": month,
                "total_amount": total_amount,
                "total_count": total_count,
                "contributions_by_user": user_contributions,
                "contributions_by_product": product_contributions
            }
