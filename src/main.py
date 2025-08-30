from fastapi import FastAPI, Request, Depends, HTTPException, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from typing import Optional, AsyncGenerator
from contextlib import asynccontextmanager
import os
import logging
from dotenv import load_dotenv
from database import Database
from models import User, UserCreate, UserInDB, Token, Contribution, Transfer, TransferCreate, Home, HomeCreate
from auth import AuthManager

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database and auth with error handling
try:
    db = Database()
    auth_manager = AuthManager()
except Exception as e:
    logger.error(f"Failed to initialize database or auth manager: {e}")
    # Create dummy instances to prevent import errors
    db = None
    auth_manager = None

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    if db is not None:
        try:
            logger.info("Starting up application...")
            await db.connect_to_postgres()
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Startup error: {str(e)}")
            logger.warning("Application starting without database connection")
            # Don't raise the error to allow the app to start even without DB
    else:
        logger.warning("Database not initialized, starting without database connection")
    
    try:
        yield
    finally:
        # Shutdown
        if db is not None:
            try:
                logger.info("Shutting down application...")
                await db.close_postgres_connection()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Shutdown error: {str(e)}")

app = FastAPI(
    title="House Finance Tracker", 
    description="Track house contributions and expenses",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Mount static files - use relative path for Vercel
import os
# Get the directory of the current file, then go up one level to get the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
static_dir = os.path.join(project_root, "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates - use relative path for Vercel  
templates_dir = os.path.join(project_root, "templates")
templates = Jinja2Templates(directory=templates_dir)

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

@app.get("/api")
async def api_root():
    """API root endpoint for testing"""
    return {
        "message": "House Finance Tracker API", 
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for deployment"""
    health_status = {"status": "healthy", "timestamp": datetime.now().isoformat()}
    
    if db is None:
        health_status["database"] = "not_initialized"
        health_status["status"] = "degraded"
        health_status["message"] = "Database not initialized"
        return health_status
    
    try:
        # Test database connection
        database = await db.get_database()
        # Simple test query to check if database is accessible
        await database.users.count_documents({})
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = "disconnected"
        health_status["database_error"] = str(e)
        health_status["status"] = "degraded"
    
    return health_status

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
    try:
        logger.info(f"Registration attempt for username: {username}, email: {email}")
        
        # Check if user already exists
        existing_user = await db.get_user(username)
        if existing_user:
            logger.warning(f"Registration failed: Username {username} already exists")
            return RedirectResponse(url="/register?error=Username already registered", status_code=303)
        
        existing_email = await db.get_user_by_email(email)
        if existing_email:
            logger.warning(f"Registration failed: Email {email} already exists")
            return RedirectResponse(url="/register?error=Email already registered", status_code=303)
        
        # Create new user
        user_create = UserCreate(
            username=username,
            email=email,
            full_name=full_name,
            password=password
        )
        
        user = await db.create_user(user_create)
        logger.info(f"User {username} registered successfully")
        return RedirectResponse(url="/login?message=Registration successful", status_code=303)
    except Exception as e:
        # Log the error for debugging
        logger.error(f"Registration error for {username}: {str(e)}", exc_info=True)
        return RedirectResponse(url="/register?error=Registration failed. Please try again.", status_code=303)

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
    try:
        logger.info(f"Login attempt for username: {username}")
        user = await db.authenticate_user(username, password)
        if not user:
            logger.warning(f"Login failed for username: {username}")
            return RedirectResponse(url="/login?error=Incorrect username or password", status_code=303)
        
        access_token_expires = timedelta(minutes=int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 30)))
        access_token = auth_manager.create_access_token(
            data={"sub": user.username}, expires_delta=access_token_expires
        )
        
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="access_token", value=f"Bearer {access_token}", httponly=True)
        logger.info(f"Login successful for username: {username}")
        return response
    except Exception as e:
        logger.error(f"Login error for {username}: {str(e)}", exc_info=True)
        return RedirectResponse(url="/login?error=Login failed. Please try again.", status_code=303)

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
        
        # Get user's home (optional)
        user_home = await db.get_user_home(user.username)
        
        # Get user's contributions
        contributions = await db.get_user_contributions(user.username)
        
        # Get user's current balance
        user_balance = await db.get_user_balance(user.username)
        
        # Get current month's summary (home-specific if user has home, otherwise empty)
        current_month_summary = {}
        if user_home:
            from datetime import datetime
            now = datetime.now()
            current_month_summary = await db.get_home_monthly_summary(user_home.id, now.year, now.month)
        
        # Get contribution to average data
        contribution_to_average = await db.get_contribution_to_average(user.username)
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "user": user,
            "user_home": user_home,
            "contributions": contributions,
            "user_balance": user_balance,
            "current_month_summary": current_month_summary,
            "current_month_name": datetime.now().strftime("%B") if user_home else None,
            "contribution_to_average": contribution_to_average
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
        
        # Check if user belongs to a home
        user_home = await db.get_user_home(user.username)
        if not user_home:
            return RedirectResponse(url="/dashboard?error=Please create or join a home to add contributions", status_code=303)
        
        contribution_data = {
            "product_name": product_name,
            "amount": amount,
            "description": description
        }
        
        await db.create_contribution(user.username, contribution_data)
        return RedirectResponse(url="/dashboard", status_code=303)
    except ValueError as e:
        return RedirectResponse(url=f"/dashboard?error={str(e)}", status_code=303)
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
        
        # Check if user belongs to a home
        user_home = await db.get_user_home(user.username)
        if not user_home:
            return RedirectResponse(url="/dashboard?error=Please create or join a home to view contributions from your household", status_code=303)
        
        # Get home contributions with user details
        home_contributions = await db.get_home_contributions_with_users(user_home.id)
        
        return templates.TemplateResponse("all_contributions.html", {
            "request": request,
            "user": user,
            "user_home": user_home,
            "contributions": home_contributions
        })
    except:
        return RedirectResponse(url="/dashboard?error=Please create or join a home to view contributions", status_code=303)

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        
        # Verify token and get user directly
        payload = auth_manager.verify_token(token)
        username = payload.get("sub")
        if username is None:
            return RedirectResponse(url="/login")
        
        user = await db.get_user(username)
        if user is None:
            return RedirectResponse(url="/login")
        
        # Check if user belongs to a home
        user_home = await db.get_user_home(user.username)
        if not user_home:
            return RedirectResponse(url="/dashboard?error=Please create or join a home to view analytics for your household", status_code=303)
        
        # Get home-specific analytics data
        analytics_data = await db.get_home_analytics(user_home.id)
        
        return templates.TemplateResponse("analytics.html", {
            "request": request,
            "user": user,
            "user_home": user_home,
            "analytics": analytics_data
        })
    except:
        return RedirectResponse(url="/dashboard?error=Please create or join a home to view analytics", status_code=303)

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
        
        # Check if user belongs to a home
        user_home = await db.get_user_home(user.username)
        if not user_home:
            return RedirectResponse(url="/dashboard?error=Please create or join a home to view monthly contributions for your household", status_code=303)
        
        # Get current date if no year/month specified
        if not year or not month:
            from datetime import datetime
            now = datetime.now()
            year = year or now.year
            month = month or now.month
        
        # Get monthly contributions and summary for the home
        contributions = await db.get_home_monthly_contributions(user_home.id, year, month)
        monthly_summary = await db.get_home_monthly_summary(user_home.id, year, month)
        
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
            "user_home": user_home,
            "contributions": contributions,
            "monthly_summary": monthly_summary,
            "available_months": available_months,
            "current_year": year,
            "current_month": month,
            "month_name": datetime(year, month, 1).strftime("%B")
        })
    except:
        return RedirectResponse(url="/dashboard?error=Please create or join a home to view monthly contributions", status_code=303)

@app.get("/transfers", response_class=HTMLResponse)
async def transfers_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Check if user belongs to a home
        user_home = await db.get_user_home(user.username)
        if not user_home:
            return templates.TemplateResponse("transfers.html", {
                "request": request,
                "user": user,
                "user_home": None,
                "transfers": {"sent": [], "received": []},
                "balance": 0,
                "available_users": [],
                "contribution_stats": None,
                "can_transfer": False,
                "no_home_message": "Please create or join a home to transfer money with your household members."
            })
        
        # Get user's transfers
        transfers = await db.get_user_transfers(user.username)
        
        # Get user's current balance (total contributions)
        balance = await db.get_user_balance(user.username)
        
        # Get user's contribution statistics for display
        contribution_stats = await db.get_contribution_to_average(user.username)
        
        # Anyone in a home can make transfers to other home members
        can_transfer = user_home is not None
        
        # Get eligible recipients (all home members except sender)
        eligible_recipients = []
        if can_transfer:
            eligible_recipients = await db.get_eligible_transfer_recipients(user.username)
        
        return templates.TemplateResponse("transfers.html", {
            "request": request,
            "user": user,
            "user_home": user_home,
            "transfers": transfers,
            "balance": balance,
            "available_users": eligible_recipients,
            "contribution_stats": contribution_stats,
            "can_transfer": can_transfer
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
        
        # Check if user belongs to a home
        user_home = await db.get_user_home(user.username)
        if not user_home:
            return RedirectResponse(url="/transfers?error=Please create or join a home to transfer money", status_code=303)
        
        # Validate amount
        if amount <= 0:
            return RedirectResponse(url="/transfers?error=Transfer amount must be positive", status_code=303)
        
        transfer_data = TransferCreate(
            recipient_username=recipient_username,
            amount=amount,
            description=description
        )
        
        try:
            await db.create_transfer(user.username, transfer_data)
            return RedirectResponse(url="/transfers?message=Fund transfer completed successfully - contributions adjusted", status_code=303)
        except ValueError as e:
            return RedirectResponse(url=f"/transfers?error={str(e)}", status_code=303)
        
    except:
        return RedirectResponse(url="/login")

@app.get("/home", response_class=HTMLResponse)
async def home_management(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Get user's home
        user_home = await db.get_user_home(user.username)
        
        # Get home members if user belongs to a home
        home_members = []
        pending_requests = []
        user_pending_request = None
        
        if user_home:
            home_members = await db.get_home_members(user_home.id)
            # Get pending join requests if user is leader
            if user_home.leader_username == user.username:
                pending_requests = await db.get_pending_join_requests(user_home.id)
        else:
            # Check if user has a pending join request
            user_pending_request = await db.get_user_pending_request(user.username)
        
        return templates.TemplateResponse("home_management.html", {
            "request": request,
            "user": user,
            "user_home": user_home,
            "home_members": home_members,
            "pending_requests": pending_requests,
            "user_pending_request": user_pending_request,
            "is_leader": user_home and user_home.leader_username == user.username
        })
    except:
        return RedirectResponse(url="/login")

@app.post("/create-home")
async def create_home(
    request: Request,
    name: str = Form(...),
    description: str = Form("")
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Check if user is already in a home
        if user.home_id:
            return RedirectResponse(url="/home?error=You are already in a home", status_code=303)
        
        home_data = HomeCreate(name=name, description=description)
        await db.create_home(home_data, user.username)
        
        return RedirectResponse(url="/home?message=Home created successfully", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/home?error={str(e)}", status_code=303)

@app.post("/add-member")
async def add_member_to_home(
    request: Request,
    username: str = Form(...)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        if not user.home_id:
            return RedirectResponse(url="/home?error=You must be in a home to add members", status_code=303)
        
        success = await db.add_member_to_home(user.home_id, username, user.username)
        if success:
            return RedirectResponse(url="/home?message=Member added successfully", status_code=303)
        else:
            return RedirectResponse(url="/home?error=Failed to add member. Check if user exists and is not already in a home.", status_code=303)
    except:
        return RedirectResponse(url="/login")

@app.post("/remove-member")
async def remove_member_from_home(
    request: Request,
    username: str = Form(...)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        if not user.home_id:
            return RedirectResponse(url="/home?error=You must be in a home to remove members", status_code=303)
        
        success = await db.remove_member_from_home(user.home_id, username, user.username)
        if success:
            return RedirectResponse(url="/home?message=Member removed successfully", status_code=303)
        else:
            return RedirectResponse(url="/home?error=Failed to remove member. Only leaders can remove members.", status_code=303)
    except:
        return RedirectResponse(url="/login")

@app.post("/leave-home")
async def leave_home(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        success = await db.leave_home(user.username)
        if success:
            return RedirectResponse(url="/home?message=Left home successfully", status_code=303)
        else:
            return RedirectResponse(url="/home?error=Cannot leave home. Leaders cannot leave unless they are the only member.", status_code=303)
    except:
        return RedirectResponse(url="/login")

@app.post("/request-join-home")
async def request_join_home(
    request: Request,
    home_name: str = Form(...)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        # Check if user is already in a home
        if user.home_id:
            return RedirectResponse(url="/home?error=You are already in a home", status_code=303)
        
        # Create join request
        success = await db.create_join_request(user.username, home_name)
        if success:
            return RedirectResponse(url="/home?message=Join request sent successfully. Wait for leader approval.", status_code=303)
        else:
            return RedirectResponse(url="/home?error=Failed to send join request. Check if home exists or if you already have a pending request.", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/home?error={str(e)}", status_code=303)

@app.post("/approve-join-request")
async def approve_join_request(
    request: Request,
    request_id: str = Form(...),
    action: str = Form(...)  # "approve" or "reject"
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login")
    
    try:
        if token.startswith("Bearer "):
            token = token[7:]
        user = await get_current_user(token)
        
        if action == "approve":
            success = await db.approve_join_request(request_id, user.username)
            message = "Join request approved successfully" if success else "Failed to approve join request"
        elif action == "reject":
            success = await db.reject_join_request(request_id, user.username)
            message = "Join request rejected successfully" if success else "Failed to reject join request"
        else:
            return RedirectResponse(url="/home?error=Invalid action", status_code=303)
        
        if success:
            return RedirectResponse(url=f"/home?message={message}", status_code=303)
        else:
            return RedirectResponse(url=f"/home?error={message}", status_code=303)
    except Exception as e:
        return RedirectResponse(url=f"/home?error={str(e)}", status_code=303)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

