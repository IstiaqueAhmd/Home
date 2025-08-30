# Authentication Issues Troubleshooting Guide

## Problem: Login works locally but fails in production (Vercel)

This is a common issue when deploying to serverless environments. Here are the most likely causes and solutions:

## 1. Environment Variables Issues

### Check if environment variables are properly set:
Visit: `https://your-app.vercel.app/debug/auth`

This endpoint will tell you:
- If SECRET_KEY is set
- If POSTGRES_URL is set  
- If bcrypt is working
- If password hashing/verification works

### Fix:
1. Go to Vercel Dashboard → Your Project → Settings → Environment Variables
2. Ensure these are set for Production, Preview, and Development:
   - `SECRET_KEY` (use a long random string)
   - `POSTGRES_URL` (your Neon database URL)
   - `ALGORITHM=HS256`
   - `ACCESS_TOKEN_EXPIRE_MINUTES=30`

## 2. Bcrypt/Passlib Compatibility Issues

Serverless environments sometimes have issues with bcrypt compilation.

### Current fixes applied:
- Added explicit bcrypt rounds setting (`bcrypt__rounds=12`)
- Added `cffi==1.15.1` to requirements.txt for better compatibility
- Enhanced error logging in auth functions

### If still failing:
Try alternative approach - replace bcrypt with argon2:

```python
# In requirements.txt, replace:
passlib[bcrypt]==1.7.4
# With:
passlib[argon2]==1.7.4

# In auth.py, change:
self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# To:
self.pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
```

## 3. Database Connection Issues

The authentication might fail if:
- Database queries are timing out
- Connection pool is exhausted
- Database is not accessible from Vercel

### Check:
1. Visit: `https://your-app.vercel.app/health`
2. Verify database connection status

### Fix:
1. Ensure your Neon database allows external connections
2. Check connection string format is correct
3. Test database access from Vercel functions

## 4. Case Sensitivity Issues

PostgreSQL is case-sensitive for usernames.

### Check:
- Ensure usernames are stored and queried consistently
- Check if registration uses different case than login

## 5. Cookie/Session Issues

### Check:
- Browser developer tools → Application → Cookies
- Verify cookies are being set correctly
- Check if `httponly` flag is causing issues

## Debugging Steps

### Step 1: Check Debug Endpoint
Visit: `https://your-app.vercel.app/debug/auth`

### Step 2: Check Vercel Function Logs
1. Go to Vercel Dashboard
2. Click on your project
3. Go to "Deployments" tab
4. Click on the latest deployment
5. Click "View Function Logs"
6. Try to login and watch the logs

### Step 3: Test with New User
1. Register a new user in production
2. Immediately try to login with that user
3. Check if the issue persists

## Quick Fixes to Try

### Fix 1: Update bcrypt configuration
The auth.py has been updated with:
```python
self.pwd_context = CryptContext(
    schemes=["bcrypt"], 
    deprecated="auto",
    bcrypt__rounds=12  # Explicit rounds for consistency
)
```

### Fix 2: Enhanced logging
Check Vercel function logs for detailed error messages.

### Fix 3: Environment variable verification
Ensure all environment variables are properly set in Vercel dashboard.

## If All Else Fails

### Option 1: Use Argon2 instead of bcrypt
```bash
# Update requirements.txt
pip install "passlib[argon2]"
```

### Option 2: Simplified auth for testing
Create a temporary simple auth mechanism to isolate the issue.

### Option 3: Check for username conflicts
Verify that the username you're trying to login with actually exists in the production database.

## Monitoring

After deployment, monitor:
1. Vercel function logs for authentication errors
2. Database logs (if available in Neon dashboard)
3. User feedback about login issues

## Common Production vs Local Differences

1. **Environment variables**: Different loading mechanisms
2. **Bcrypt compilation**: Different architectures/dependencies
3. **Database connections**: Connection pooling, timeouts
4. **Logging**: Different log destinations
5. **File paths**: Serverless vs local file system

## Next Steps

1. Deploy the updated code with enhanced logging
2. Test the `/debug/auth` endpoint
3. Check Vercel function logs during login attempts
4. Report back with specific error messages from logs
