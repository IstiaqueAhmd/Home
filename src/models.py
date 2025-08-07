from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class HomeBase(BaseModel):
    name: str
    description: Optional[str] = None

class HomeCreate(HomeBase):
    pass

class Home(HomeBase):
    id: Optional[str] = None
    leader_username: str
    members: List[str] = []
    date_created: datetime = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    is_active: bool = True
    home_id: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    password: str

class User(UserBase):
    id: Optional[str] = None

class UserInDB(User):
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ContributionCreate(BaseModel):
    product_name: str
    amount: float
    description: Optional[str] = None

class Contribution(BaseModel):
    id: Optional[str] = None
    username: str
    home_id: str
    product_name: str
    amount: float
    description: Optional[str] = None
    date_created: datetime = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class TransferCreate(BaseModel):
    recipient_username: str
    amount: float
    description: Optional[str] = None

class Transfer(BaseModel):
    id: Optional[str] = None
    sender_username: str
    recipient_username: str
    home_id: str
    amount: float
    description: Optional[str] = None
    date_created: datetime = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
