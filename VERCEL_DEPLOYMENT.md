# Vercel Deployment Guide

This guide will help you deploy your House Finance Tracker application to Vercel.

## Pre-deployment Checklist

### 1. Required Files Created ✅
- `vercel.json` - Vercel configuration
- `api/index.py` - Entry point for Vercel
- `.vercelignore` - Files to exclude from deployment

### 2. Database Setup

Before deploying, you need a PostgreSQL database. Here are some free options:

#### Option A: Supabase (Recommended)
1. Go to [https://supabase.com](https://supabase.com)
2. Create a free account
3. Create a new project
4. Go to Settings > Database
5. Copy the connection string (it looks like: `postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres`)

#### Option B: Railway
1. Go to [https://railway.app](https://railway.app)
2. Create a free account
3. Create a new project
4. Add a PostgreSQL database
5. Copy the connection string from the database service

#### Option C: Neon
1. Go to [https://neon.tech](https://neon.tech)
2. Create a free account
3. Create a database
4. Copy the connection string

## Deployment Steps

### 1. Push to GitHub
Make sure your code is pushed to a GitHub repository.

```bash
git add .
git commit -m "Prepare for Vercel deployment"
git push origin main
```

### 2. Deploy to Vercel

#### Option A: Using Vercel Dashboard (Recommended)
1. Go to [https://vercel.com](https://vercel.com)
2. Sign up/Login with your GitHub account
3. Click "Import Project"
4. Select your GitHub repository
5. Configure the project:
   - **Framework Preset**: Other
   - **Root Directory**: Leave empty (.)
   - **Build Command**: Leave empty
   - **Output Directory**: Leave empty
   - **Install Command**: pip install -r requirements.txt

#### Option B: Using Vercel CLI
```bash
# Install Vercel CLI
npm i -g vercel

# Login to Vercel
vercel login

# Deploy
vercel --prod
```

### 3. Set Environment Variables

In your Vercel dashboard, go to your project > Settings > Environment Variables and add:

| Name | Value |
|------|-------|
| `POSTGRES_URL` | Your PostgreSQL connection string |
| `SECRET_KEY` | A random secret key (generate with: `openssl rand -hex 32`) |
| `ALGORITHM` | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` |

**Important**: Make sure to set these for "Production", "Preview", and "Development" environments.

### 4. Redeploy

After setting environment variables, redeploy your application:
- Go to your Vercel dashboard
- Click on your project
- Go to "Deployments" tab
- Click the three dots on the latest deployment
- Click "Redeploy"

## Database Initialization

After your first successful deployment, your application will automatically create the necessary database tables when it starts up.

## Testing Your Deployment

1. Visit your Vercel app URL
2. Try registering a new account
3. Create a home and add some contributions
4. Test the different features

## Common Issues and Solutions

### Issue: Import Errors
**Solution**: Make sure all imports in your Python files use relative imports (starting with `.`)

### Issue: Static Files Not Loading
**Solution**: The deployment configuration handles static files automatically with the updated path handling.

### Issue: Database Connection Errors
**Solution**: 
- Verify your `POSTGRES_URL` environment variable is set correctly
- Make sure your database is accessible from the internet
- Check that the connection string format is correct

### Issue: Template Not Found
**Solution**: The deployment configuration handles template paths automatically with the updated path handling.

## Environment Variables Template

Create a `.env` file locally for development:

```env
POSTGRES_URL=postgresql://username:password@host:port/database_name
SECRET_KEY=your-super-secret-key-here-make-it-long-and-random
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Performance Considerations

1. **Cold Starts**: Vercel functions may have cold starts. Consider using a serverless-friendly database connection pattern.
2. **Database Connections**: PostgreSQL connection pooling is handled automatically by the `databases` library.
3. **Static Files**: All static files are served efficiently by Vercel's CDN.

## Post-Deployment Steps

1. **Custom Domain** (Optional): Add a custom domain in Vercel dashboard > Project > Settings > Domains
2. **Analytics**: Enable Vercel Analytics for usage insights
3. **Monitoring**: Set up monitoring for your database and application

## Troubleshooting

If you encounter issues:

1. Check the Vercel function logs in your dashboard
2. Ensure all environment variables are set
3. Verify your database is accessible
4. Test database connection separately

## Support

For deployment issues:
- Check Vercel documentation: [https://vercel.com/docs](https://vercel.com/docs)
- Check FastAPI deployment guides
- Review Vercel function logs for specific errors

Good luck with your deployment! 🚀
