# Configuration file for Expense AI Agent

# Groq API Settings
GROQ_MODEL = "llama-3.1-8b-instant"

# FastAPI Settings
API_HOST = "0.0.0.0"
API_PORT = 8000
API_RELOAD = True

# Categorization Settings
TEMPERATURE_CATEGORIZATION = 0.1  # Low for consistent categorization
TEMPERATURE_INSIGHTS = 0.7        # Higher for creative insights

# Analysis Settings
ANOMALY_STD_MULTIPLIER = 2.0      # 2 standard deviations threshold
MIN_SUBSCRIPTION_FREQUENCY = 2    # Minimum occurrences to be considered subscription

# Categories
CATEGORIES = [
    "Food & Dining",
    "Transport & Travel",
    "Shopping & Retail",
    "Bills & Utilities",
    "Subscriptions & Memberships",
    "Income",
    "Investments & Savings",
    "Transfers & Others",
    "Entertainment & Hobbies",
    "Healthcare & Wellness",
    "Education",
    "Travel & Vacation",
    "Work & Office",
]

# Budget Limits (Optional - for budget_analysis function)
BUDGET_LIMITS = {
    "Food & Dining": 10000,
    "Transport & Travel": 5000,
    "Shopping & Retail": 8000,
    "Bills & Utilities": 5000,
    "Subscriptions & Memberships": 2000,
    "Entertainment & Hobbies": 3000,
    "Healthcare & Wellness": 2000,
    "Education": 5000,
}

# CORS Settings
CORS_ORIGINS = [
    "http://localhost:8501",      # Streamlit
    "http://localhost:3000",      # React/Next.js
    "http://localhost:5173",      # Vite
    "*",                           # Allow all (for development)
]

# Streamlit Settings
STREAMLIT_THEME = "light"
STREAMLIT_WIDE_MODE = True
