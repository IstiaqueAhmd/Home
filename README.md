# House Finance Tracker

A simple web application to track house contributions and expenses among members using FastAPI and MongoDB.

## Features

- **User Authentication**: Secure login and registration system
- **Dashboard**: Overview of contributions and statistics
- **Contribution Tracking**: Add and view individual contributions
- **Product Management**: Track which products were purchased
- **Responsive Design**: Works on desktop and mobile devices

## Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: MongoDB
- **Frontend**: HTML, CSS, Bootstrap 5, Jinja2 templates
- **Authentication**: JWT tokens with bcrypt password hashing

## Setup Instructions

### Prerequisites

- Python 3.8+
- MongoDB (local installation or MongoDB Atlas)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd house-finance-tracker
   ```

2. **Set up virtual environment**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # On Windows
   # or
   source .venv/bin/activate  # On macOS/Linux
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   copy .env.example .env  # On Windows
   # or
   cp .env.example .env    # On macOS/Linux
   ```
   
   Edit `.env` file with your MongoDB connection details:
   ```
   MONGODB_URL=mongodb://localhost:27017
   DATABASE_NAME=house_finance_tracker
   SECRET_KEY=your-secret-key-here
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ```

5. **Start MongoDB**
   - Make sure MongoDB is running locally, or
   - Use MongoDB Atlas and update the connection string in `.env`

6. **Run the application**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```
   
   Or simply run the batch file on Windows:
   ```bash
   run.bat
   ```

7. **Access the application**
   Open your browser and go to: `http://localhost:8000`

## Usage

1. **Register**: Create a new account with username, email, full name, and password
2. **Login**: Use your credentials to access the dashboard
3. **Add Contributions**: Click "Add Contribution" to record new purchases
4. **View Dashboard**: See your contribution history and statistics

## Project Structure

```
house-finance-tracker/
├── main.py              # Main FastAPI application
├── models.py            # Pydantic models
├── database.py          # MongoDB database operations
├── auth.py              # Authentication and password hashing
├── requirements.txt     # Python dependencies
├── templates/           # HTML templates
│   ├── base.html
│   ├── dashboard.html
│   ├── login.html
│   └── register.html
├── static/              # Static files (CSS, JS)
│   └── css/
│       └── style.css
├── .env.example         # Environment variables template
└── README.md
```

## API Endpoints

- `GET /` - Home page
- `GET /login` - Login page
- `POST /login` - Process login
- `GET /register` - Registration page
- `POST /register` - Process registration
- `GET /dashboard` - User dashboard (authenticated)
- `POST /add-contribution` - Add new contribution (authenticated)
- `POST /logout` - Logout user
- `POST /token` - Get access token (API)

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

