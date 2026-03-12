"""Utility functions for the Expense AI Agent."""

import json
import pandas as pd
from typing import Dict, Any


def safe_json_load(text: str, default: Any = None) -> Any:
    """Safely load JSON with fallback."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def format_currency(amount: float, currency: str = "₹") -> str:
    """Format amount as currency."""
    return f"{currency}{amount:,.2f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """Format value as percentage."""
    return f"{value:.{decimals}f}%"


def format_dataframe_for_display(df: pd.DataFrame, currency_columns: list = None) -> pd.DataFrame:
    """Format dataframe for display."""
    df_display = df.copy()
    
    if currency_columns:
        for col in currency_columns:
            if col in df_display.columns:
                df_display[col] = df_display[col].apply(lambda x: format_currency(x))
    
    # Round numeric columns
    numeric_cols = df_display.select_dtypes(include=['number']).columns
    for col in numeric_cols:
        if col not in (currency_columns or []):
            df_display[col] = df_display[col].round(2)
    
    return df_display


def get_spending_summary(df: pd.DataFrame) -> Dict[str, float]:
    """Get quick spending summary stats."""
    return {
        "total": float(df["amount"].sum()),
        "average": float(df["amount"].mean()),
        "median": float(df["amount"].median()),
        "min": float(df["amount"].min()),
        "max": float(df["amount"].max()),
        "count": len(df)
    }


def categorize_amount(amount: float, category: str) -> str:
    """Categorize amount size within a category."""
    if amount < 100:
        return "Small"
    elif amount < 500:
        return "Medium"
    elif amount < 2000:
        return "Large"
    else:
        return "Very Large"


def get_spending_advice(total_spent: float, days: int = 30) -> str:
    """Generate spending advice based on total."""
    daily_average = total_spent / days
    
    if daily_average < 500:
        return "📉 Low spending - Great control!"
    elif daily_average < 1000:
        return "✅ Moderate spending - Good balance"
    elif daily_average < 1500:
        return "⚠️ Elevated spending - Monitor closely"
    else:
        return "🚨 High spending - Consider budget cuts"


def highlight_anomaly_reasons(row: dict, avg_amount: float) -> list:
    """Generate reasons why a transaction is anomalous."""
    reasons = []
    amount = row.get("amount", 0)
    
    if amount > avg_amount * 3:
        reasons.append("Amount is 3x higher than average")
    if amount > avg_amount * 5:
        reasons.append("Amount is 5x higher than average")
    
    return reasons
