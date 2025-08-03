from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from datetime import datetime, timedelta
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from database import Database
from models import User, UserCreate, UserInDB, Token, Contribution, Transfer, TransferCreate
from auth import AuthManager

# Load environment variables
load_dotenv()

# Initialize database and auth
db = Database()
auth_manager = AuthManager()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    await db.connect_to_mongo()
    yield
    # Shutdown
    await db.close_mongo_connection()

app = FastAPI(
    title="House Finance Tracker", 
    description="Track house contributions and expenses",
    lifespan=lifespan
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = auth_manager.verify_token(token)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = await db.get_user(username)
        if user is None:
            raise credentials_exception
        return user
    except:
        raise credentials_exception

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(
    username: str = Form(...),
    email: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...)
):
    # Check if user already exists
    if await db.get_user(username):
        raise HTTPException(status_code=400, detail="Username already registered")
    
    if await db.get_user_by_email(email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_create = UserCreate(
        username=username,
        email=email,
        full_name=full_name,
        password=password
    )
    
    user = await db.create_user(user_create)
    return RedirectResponse(url="/login?message=Registration successful", status_code=303)

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)))
    access_token = auth_manager.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    user = await db.authenticate_user(username, password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)))
    access_token = auth_manager.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
    return response

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_authenticated(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get user's contributions
        contributions = await db.get_user_contributions(user.username)
        
        # Get user's current balance
        user_balance = await db.get_user_balance(user.username)
        
        # Get current month's summary
        from datetime import datetime
        now = datetime.now()
        current_month_summary = await db.get_monthly_summary(now.year, now.month)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "user": user,
            "contributions": contributions,
            "user_balance": user_balance,
            "current_month_summary": current_month_summary,
            "current_month_name": now.strftime("%B")
        })
    except:
        return RedirectResponse(url="/login")

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(key="access_token")
    return response

@app.post("/add-contribution")
async def add_contribution(
    request: Request,
    product_name: str = Form(...),
    amount: float = Form(...),
    description: str = Form("")
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        contribution_data = {
            "product_name": product_name,
            "amount": amount,
            "description": description
        }
        
        await db.create_contribution(user.username, contribution_data)
        return RedirectResponse(url="/dashboard", status_code=303)
    except:
        return RedirectResponse(url="/login")

@app.get("/all-contributions", response_class=HTMLResponse)
async def all_contributions(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get all contributions with user details
        all_contributions = await db.get_all_contributions_with_users()
        
        return templates.TemplateResponse("all_contributions.html", {
            "request": request,
            "user": user,
            "contributions": all_contributions
        })
    except:
        return RedirectResponse(url="/login")

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get analytics data
        analytics_data = await db.get_analytics()
        
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "user": user,
            "analytics": analytics_data
        })
    except:
        return RedirectResponse(url="/login")

@app.post("/delete-contribution/{contribution_id}")
async def delete_contribution(request: Request, contribution_id: str):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Only allow users to delete their own contributions
        success = await db.delete_contribution(contribution_id, user.username)
        if not success:
            raise HTTPException(status_code=403, detail="Not authorized to delete this contribution")
        
        return RedirectResponse(url="/dashboard", status_code=303)
    except:
        return RedirectResponse(url="/login")

@app.get("/profile", response_class=HTMLResponse)
async def profile(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get user statistics
        user_stats = await db.get_user_statistics(user.username)
        
        return templates.TemplateResponse("profile.html", {
            "request": request,
            "user": user,
            "stats": user_stats
        })
    except:
        return RedirectResponse(url="/login")

@app.post("/update-profile")
async def update_profile(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Update user profile
        await db.update_user_profile(user.username, full_name, email)
        
        return RedirectResponse(url="/profile?message=Profile updated successfully", status_code=303)
    except:
        return RedirectResponse(url="/login")

@app.get("/monthly-contributions", response_class=HTMLResponse)
async def monthly_contributions(request: Request, year: int = None, month: int = None):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get current date if no year/month specified
        if not year or not month:
            from datetime import datetime
            now = datetime.now()
            year = year or now.year
            month = month or now.month
        
        # Get monthly contributions and summary
        contributions = await db.get_monthly_contributions(year, month)
        monthly_summary = await db.get_monthly_summary(year, month)
        
        # Get available months (last 12 months)
        available_months = []
        from datetime import datetime, timedelta
        current_date = datetime.now()
        for i in range(12):
            date = current_date - timedelta(days=30*i)
            available_months.append({
                "year": date.year,
                "month": date.month,
                "month_name": date.strftime("%B"),
                "is_current": date.year == year and date.month == month
            })
        
        return templates.TemplateResponse("monthly_contributions.html", {
            "request": request,
            "user": user,
            "contributions": contributions,
            "monthly_summary": monthly_summary,
            "available_months": available_months,
            "current_year": year,
            "current_month": month,
            "month_name": datetime(year, month, 1).strftime("%B")
        })
    except:
        return RedirectResponse(url="/login")

@app.get("/transfers", response_class=HTMLResponse)
async def transfers_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get user's transfers
        transfers = await db.get_user_transfers(user.username)
        
        # Get user's current balance
        balance = await db.get_user_balance(user.username)
        
        # Get all users for transfer form
        all_users = await db.get_all_users()
        # Remove current user from the list
        available_users = [u for u in all_users if u.username != user.username]
        
        return templates.TemplateResponse("transfers.html", {
            "request": request,
            "user": user,
            "transfers": transfers,
            "balance": balance,
            "available_users": available_users
        })
    except:
        return RedirectResponse(url="/login")

@app.post("/transfer")
async def create_transfer(
    request: Request,
    recipient_username: str = Form(...),
    amount: float = Form(...),
    description: str = Form("")
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Validate amount
        if amount <= 0:
            return RedirectResponse(url="/transfers?error=Invalid amount", status_code=303)
        
        transfer_data = TransferCreate(
            recipient_username=recipient_username,
            amount=amount,
            description=description
        )
        
        try:
            await db.create_transfer(user.username, transfer_data)
            return RedirectResponse(url="/transfers?message=Transfer completed successfully", status_code=303)
        except ValueError as e:
            return RedirectResponse(url=f"/transfers?error={str(e)}", status_code=303)
        
    except:
        return RedirectResponse(url="/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
