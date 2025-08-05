# Database Migration from MongoDB to PostgreSQL

This project has been migrated from MongoDB to PostgreSQL for better production reliability and performance.

## Quick Setup

### Option 1: SQLite (Development/Testing)
The easiest way to get started is with SQLite. The application is configured to use SQLite by default:

1. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

2. The database will be automatically created when you run the application.

### Option 2: PostgreSQL (Production)

1. Install PostgreSQL on your system

2. Create a database:
   ```sql
   CREATE DATABASE house_finance_tracker;
   CREATE USER your_username WITH PASSWORD 'your_password';
   GRANT ALL PRIVILEGES ON DATABASE house_finance_tracker TO your_username;
   ```

3. Copy `.env.example` to `.env` and update the database URL:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` and uncomment the PostgreSQL line:
   ```
   DATABASE_URL=postgresql+asyncpg://your_username:your_password@localhost:5432/house_finance_tracker
   ```

5. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

6. Create the database tables:
   ```bash
   python create_tables.py
   ```

## Key Changes

### Database Models
- All MongoDB collections have been converted to PostgreSQL tables
- Relationships are now properly defined with foreign keys
- UUIDs are used for primary keys instead of MongoDB ObjectIds

### Main Benefits
1. **ACID Compliance**: Better data integrity
2. **Relations**: Proper foreign key constraints
3. **Performance**: Better query optimization
4. **Production Ready**: More suitable for production environments
5. **Backup & Recovery**: Better tooling available

### File Changes
- `database.py`: Completely rewritten for PostgreSQL/SQLite
- `db_models.py`: New SQLAlchemy models
- `requirements.txt`: Updated dependencies
- `database_mongo_backup.py`: Backup of original MongoDB implementation

### Migration from MongoDB
If you have existing data in MongoDB, you'll need to:

1. Export your MongoDB data
2. Transform it to fit the new schema
3. Import it into PostgreSQL

The old MongoDB implementation is preserved in `database_mongo_backup.py` for reference.

## Environment Variables

The application now uses these environment variables:

- `DATABASE_URL`: Connection string for PostgreSQL/SQLite
- `SECRET_KEY`: JWT secret key
- `ALGORITHM`: JWT algorithm (default: HS256)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration time

## Running the Application

After setting up the database, run the application as before:

```bash
uvicorn main:app --reload
```

The application will automatically create database tables if they don't exist.
