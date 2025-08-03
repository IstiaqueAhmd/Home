from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: str
    is_active: bool = True

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
    product_name: str
    amount: float
    description: Optional[str] = None
    date_created: datetime = datetime.now()
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
