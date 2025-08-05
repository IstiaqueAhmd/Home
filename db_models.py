from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    home_id = Column(String, ForeignKey("homes.id"), nullable=True)
    date_created = Column(DateTime, default=func.now())
    
    # Relationships
    home = relationship("Home", back_populates="members", foreign_keys=[home_id])
    led_homes = relationship("Home", back_populates="leader", foreign_keys="Home.leader_id")
    contributions = relationship("Contribution", back_populates="user", cascade="all, delete-orphan")
    sent_transfers = relationship("Transfer", back_populates="sender", foreign_keys="Transfer.sender_id")
    received_transfers = relationship("Transfer", back_populates="recipient", foreign_keys="Transfer.recipient_id")

class Home(Base):
    __tablename__ = "homes"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    leader_id = Column(String, ForeignKey("users.id"), nullable=False)
    date_created = Column(DateTime, default=func.now())
    
    # Relationships
    leader = relationship("User", back_populates="led_homes", foreign_keys=[leader_id])
    members = relationship("User", back_populates="home", foreign_keys="User.home_id")
    contributions = relationship("Contribution", back_populates="home", cascade="all, delete-orphan")
    transfers = relationship("Transfer", back_populates="home", cascade="all, delete-orphan")
    join_requests = relationship("JoinRequest", back_populates="home", cascade="all, delete-orphan")

class Contribution(Base):
    __tablename__ = "contributions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    home_id = Column(String, ForeignKey("homes.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    date_created = Column(DateTime, default=func.now())
    
    # Relationships
    user = relationship("User", back_populates="contributions")
    home = relationship("Home", back_populates="contributions")

class Transfer(Base):
    __tablename__ = "transfers"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = Column(String, ForeignKey("users.id"), nullable=False)
    recipient_id = Column(String, ForeignKey("users.id"), nullable=False)
    home_id = Column(String, ForeignKey("homes.id"), nullable=False)
    amount = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    date_created = Column(DateTime, default=func.now())
    
    # Relationships
    sender = relationship("User", back_populates="sent_transfers", foreign_keys=[sender_id])
    recipient = relationship("User", back_populates="received_transfers", foreign_keys=[recipient_id])
    home = relationship("Home", back_populates="transfers")

class JoinRequest(Base):
    __tablename__ = "join_requests"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    home_id = Column(String, ForeignKey("homes.id"), nullable=False)
    status = Column(String(20), default="pending")  # pending, approved, rejected
    date_created = Column(DateTime, default=func.now())
    date_processed = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User")
    home = relationship("Home", back_populates="join_requests")
