import pandas as pd
from typing import Dict, List
import json


def categorize_transactions(df: pd.DataFrame, categorizer) -> pd.DataFrame:
    """Categorize transactions using LLM."""
    df = df.copy()

    # Try batched categorization if available (fewer HTTP calls)
    try:
        if hasattr(categorizer, "categorize_batch"):
            transactions = df.to_dict(orient="records")
            batched = categorizer.categorize_batch(transactions)
            if batched:
                # map index -> category
                index_map = {item["index"]: item.get("category", "Transfers & Others") for item in batched}
                cats = [index_map.get(i, "Transfers & Others") for i in range(len(transactions))]
                df["category"] = cats
                return df
    except Exception as e:
        # fallback to per-row if batch fails
        print(f"Batch categorize failed: {e}")

    # Fallback: per-row categorization
    categories = []
    for _, row in df.iterrows():
        try:
            cat = categorizer.categorize(
                name=row.get("name", ""),
                description=row.get("description", ""),
                amount=row.get("amount", 0),
                date=row.get("date", "")
            )
        except Exception:
            cat = "Transfers & Others"
        categories.append(cat)

    df["category"] = categories
    return df


def monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Generate monthly spending summary by category."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    
    summary = (
        df.groupby(["month", "category"])["amount"]
        .sum()
        .reset_index()
        .sort_values(["month", "amount"], ascending=[True, False])
    )
    
    return summary


def detect_anomalies(df: pd.DataFrame, std_multiplier: float = 2.0) -> pd.DataFrame:
    """Detect unusual spending anomalies."""
    df = df.copy()
    
    if len(df) < 2:
        return pd.DataFrame()
    
    threshold = df["amount"].mean() + std_multiplier * df["amount"].std()
    anomalies = df[df["amount"] > threshold].copy()
    
    return anomalies.sort_values("amount", ascending=False)


def detect_subscriptions(df: pd.DataFrame) -> pd.DataFrame:
    """Detect recurring subscriptions and payments."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    # Group by name and amount to find recurring payments; use size() to avoid column collisions
    freq = (
        df.groupby(["name", "amount"]).size().reset_index(name="frequency")
    )

    # Get representative category for each (name, amount) pair when available
    if "category" in df.columns:
        cat_map = (
            df[["name", "amount", "category"]]
            .drop_duplicates()
            .groupby(["name", "amount"])["category"]
            .first()
            .reset_index()
        )
        subscriptions = freq.merge(cat_map, on=["name", "amount"], how="left")
    else:
        subscriptions = freq

    subscriptions = subscriptions.query("frequency >= 2").sort_values("frequency", ascending=False)

    return subscriptions


def category_breakdown(df: pd.DataFrame) -> Dict:
    """Get spending breakdown by category."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    
    breakdown = (
        df.groupby("category")["amount"]
        .agg(["sum", "count", "mean"])
        .reset_index()
        .rename(columns={"sum": "total", "count": "transactions", "mean": "avg_transaction"})
        .sort_values("total", ascending=False)
    )
    
    return breakdown


def spending_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Analyze spending trends over time."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M")
    
    trends = (
        df.groupby("month")["amount"]
        .agg(["sum", "count", "mean"])
        .rename(columns={"sum": "total", "count": "transactions", "mean": "avg"})
        .reset_index()
    )
    
    return trends


def budget_analysis(df: pd.DataFrame, budget_by_category: Dict[str, float]) -> Dict:
    """Analyze spending vs budget."""
    df = df.copy()
    
    category_spending = df.groupby("category")["amount"].sum().to_dict()
    
    analysis = {}
    for category, budget in budget_by_category.items():
        spent = category_spending.get(category, 0)
        remaining = budget - spent
        percentage = (spent / budget * 100) if budget > 0 else 0
        
        analysis[category] = {
            "budget": budget,
            "spent": spent,
            "remaining": remaining,
            "percentage": round(percentage, 2),
            "status": "Over Budget" if spent > budget else "Within Budget"
        }
    
    return analysis
