import pandas as pd
import numpy as np
import json
from typing import TypedDict, List, Dict, Any

from langgraph.graph import StateGraph, END
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_groq import ChatGroq

from tools import (
    categorize_transactions,
    monthly_summary,
    detect_anomalies,
    detect_subscriptions,
    category_breakdown,
    spending_trends,
    budget_analysis
)


def sanitize_for_json(obj):
    """Recursively convert pandas/numpy objects to JSON-serializable Python types."""
    # dict
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    # list/tuple
    if isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    # pandas NA
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    # pandas types
    if isinstance(obj, pd.Period):
        return str(obj)
    if isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
        return str(obj)
    if isinstance(obj, (pd.Timedelta,)):
        return str(obj)
    # numpy scalar types
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    # numpy arrays and pandas Series
    if hasattr(obj, "tolist") and not isinstance(obj, (str, bytes)):
        try:
            return sanitize_for_json(obj.tolist())
        except Exception:
            pass
    # fallback
    return obj


ADVANCED_CATEGORIZATION_PROMPT = """You are an expert financial transaction classification AI with deep knowledge of spending patterns.

Your task: Classify transactions into ONE category with high accuracy.

**Categories Available:**
- Food & Dining (restaurants, cafes, food delivery - Swiggy, Zomato, Uber Eats)
- Transport & Travel (uber, ola, metro, flights, cabs, gas)
- Shopping & Retail (clothing, groceries, amazon, flipkart, malls)
- Bills & Utilities (electricity, water, internet, phone, insurance)
- Subscriptions & Memberships (netflix, spotify, prime, gym, apps)
- Income (salary, bonus, refunds, freelance)
- Investments & Savings (stocks, mutual funds, savings, deposits)
- Transfers & Others (bank transfers, cash transfers, misc)
- Entertainment & Hobbies (movies, gaming, concerts, sports)
- Healthcare & Wellness (medicine, doctor, hospital, gym)
- Education (courses, tuition, books, training)
- Travel & Vacation (hotels, flights for vacation)
- Work & Office (stationery, office supplies)

**Classification Rules:**
1. Match transaction name/description against keywords
2. Consider transaction amount (small = food, large = investment)
3. Date patterns matter (salary = income, recurring = subscription)
4. Default to 'Transfers & Others' if unsure

**Keywords:**
- Food: swiggy, zomato, ubereats, restaurant, cafe, pizza, biryani, lunch, dinner, bakery
- Transport: uber, ola, metro, bus, taxi, petrol, fuel, parking, vehicle
- Shopping: amazon, flipkart, mall, store, dress, cloth, grocery, shoes, walmart
- Bills: electricity, water, gas, internet, phone, mobile, broadband, isp
- Subscriptions: netflix, spotify, prime, hulu, app, membership, subscription, monthly
- Income: salary, bonus, refund, credit, salary deposit
- Investments: stock, mutual, fund, investment, nifty, bse, trading
- Healthcare: doctor, hospital, medicine, pharmacy, medical, dental, health
- Entertainment: cinema, movie, game, spotify, music, concert, ticket
- Transfers: transfer, payment, send, receive, bank, upi

**Response Format (STRICT JSON):**
{
  "category": "Category Name",
  "confidence": 0.95,
  "reason": "Brief explanation"
}

Example:
Input: Swiggy, Food Delivery, 450 INR
Output: {"category": "Food & Dining", "confidence": 0.99, "reason": "Food delivery service"}
"""


class AgentState(TypedDict):
    """State for the expense analysis agent."""
    transactions: List[Dict]
    categorized_df: dict
    monthly_summary: dict
    anomalies: dict
    subscriptions: dict
    category_breakdown: dict
    spending_trends: dict
    financial_insights: str
    budget_analysis: dict
    error: str


class TransactionCategorizer:
    """Categorizes transactions using Groq LLM."""
    
    def __init__(self, groq_api_key: str):
        self.llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=groq_api_key,
            temperature=0.1
        )
    
    def categorize(self, name: str, description: str, amount: float, date: str) -> str:
        """Categorize a single transaction."""
        prompt = f"""
Classify this transaction:

Name: {name}
Description: {description}
Amount: {amount}
Date: {date}

Return ONLY valid JSON.
"""
        
        try:
            response = self.llm.invoke([
                SystemMessage(content=ADVANCED_CATEGORIZATION_PROMPT),
                HumanMessage(content=prompt)
            ])
            
            result = json.loads(response.content)
            return result.get("category", "Transfers & Others")
        except Exception as e:
            print(f"Categorization error: {e}")
            return "Transfers & Others"

    def categorize_batch(self, transactions: list) -> list:
        """Categorize a list of transactions in a single batched LLM call.

        transactions: list of dicts with keys: name, description, amount, date
        Returns: list of dicts with at least `index` and `category` fields.
        """
        # Build a prompt that lists transactions with an index, and request a JSON array
        lines = []
        for i, t in enumerate(transactions):
            name = t.get("name", "")
            desc = t.get("description", "")
            amt = t.get("amount", "")
            date = t.get("date", "")
            lines.append(f"{i}|{name}|{desc}|{amt}|{date}")

        payload = (
            "Classify the following transactions. Return ONLY valid JSON: a list of objects with keys `index`, `category`, `confidence`, and `reason`.\n"
            "Each object must map to the input index. Example: [{\"index\":0,\"category\":\"Food & Dining\",\"confidence\":0.95,\"reason\":\"...\"}]\n\n"
            "Transactions (format: index|name|description|amount|date):\n"
            + "\n".join(lines)
        )

        try:
            response = self.llm.invoke([
                SystemMessage(content=ADVANCED_CATEGORIZATION_PROMPT),
                HumanMessage(content=payload)
            ])
            parsed = json.loads(response.content)
            # Validate and normalize
            out = []
            for item in parsed:
                if isinstance(item, dict) and "index" in item:
                    out.append({
                        "index": int(item.get("index")),
                        "category": item.get("category", "Transfers & Others"),
                        "confidence": float(item.get("confidence", 0.0)),
                        "reason": item.get("reason", "")
                    })
            return out
        except Exception as e:
            # On any failure, fallback to per-item approach
            print(f"Batched categorization failed: {e}")
            # Return empty list to indicate failure to caller
            return []


def categorize_node(state: AgentState, categorizer: TransactionCategorizer) -> Dict:
    """Node: Categorize all transactions."""
    try:
        df = pd.DataFrame(state["transactions"])
        
        if df.empty:
            return {"error": "No transactions to categorize"}
        
        df = categorize_transactions(df, categorizer)
        
        return {"categorized_df": df.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Categorization failed: {str(e)}"}


def summary_node(state: AgentState) -> Dict:
    """Node: Generate monthly spending summary."""
    try:
        if isinstance(state.get("categorized_df"), list):
            df = pd.DataFrame(state["categorized_df"])
        else:
            df = pd.DataFrame(state.get("categorized_df", []))
        
        if df.empty:
            return {}
        
        summary = monthly_summary(df)
        return {"monthly_summary": summary.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Summary generation failed: {str(e)}"}


def anomaly_node(state: AgentState) -> Dict:
    """Node: Detect spending anomalies."""
    try:
        if isinstance(state.get("categorized_df"), list):
            df = pd.DataFrame(state["categorized_df"])
        else:
            df = pd.DataFrame(state.get("categorized_df", []))
        
        if df.empty:
            return {}
        
        anomalies = detect_anomalies(df)
        return {"anomalies": anomalies.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Anomaly detection failed: {str(e)}"}


def subscription_node(state: AgentState) -> Dict:
    """Node: Detect subscriptions."""
    try:
        if isinstance(state.get("categorized_df"), list):
            df = pd.DataFrame(state["categorized_df"])
        else:
            df = pd.DataFrame(state.get("categorized_df", []))
        
        if df.empty:
            return {}
        
        subs = detect_subscriptions(df)
        return {"subscriptions": subs.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Subscription detection failed: {str(e)}"}


def breakdown_node(state: AgentState) -> Dict:
    """Node: Category spending breakdown."""
    try:
        if isinstance(state.get("categorized_df"), list):
            df = pd.DataFrame(state["categorized_df"])
        else:
            df = pd.DataFrame(state.get("categorized_df", []))
        
        if df.empty:
            return {}
        
        breakdown = category_breakdown(df)
        return {"category_breakdown": breakdown.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Breakdown failed: {str(e)}"}


def trends_node(state: AgentState) -> Dict:
    """Node: Spending trends analysis."""
    try:
        if isinstance(state.get("categorized_df"), list):
            df = pd.DataFrame(state["categorized_df"])
        else:
            df = pd.DataFrame(state.get("categorized_df", []))
        
        if df.empty:
            return {}
        
        trends = spending_trends(df)
        return {"spending_trends": trends.to_dict(orient="records")}
    except Exception as e:
        return {"error": f"Trends analysis failed: {str(e)}"}


def insights_node(state: AgentState, llm: ChatGroq) -> Dict:
    """Node: Generate AI financial insights."""
    try:
        summary = state.get("monthly_summary", [])
        anomalies = state.get("anomalies", [])
        subscriptions = state.get("subscriptions", [])
        # Ensure everything in the prompt is JSON-serializable (Period/Timestamp -> str, numpy -> native)
        safe_summary = sanitize_for_json(summary)
        safe_anomalies = sanitize_for_json(anomalies)
        safe_subs = sanitize_for_json(subscriptions)

        prompt = f"""Based on financial data analysis, provide actionable insights:

Monthly Summary:
{json.dumps(safe_summary[:10] if isinstance(safe_summary, list) else safe_summary, indent=2)}

Anomalies Detected:
{json.dumps(safe_anomalies[:5] if isinstance(safe_anomalies, list) else safe_anomalies, indent=2)}

Subscriptions:
{json.dumps(safe_subs[:5] if isinstance(safe_subs, list) else safe_subs, indent=2)}

Provide:
1. **Spending Pattern Analysis** - Key trends
2. **Risk Alerts** - Any concerning spending
3. **Savings Opportunities** - Where to cut costs
4. **Subscription Audit** - Which to cancel
5. **Financial Recommendations** - Action items

Keep it concise and actionable."""

        response = llm.invoke([
            HumanMessage(content=prompt)
        ])
        
        return {"financial_insights": response.content}
    except Exception as e:
        return {"error": f"Insights generation failed: {str(e)}"}


def build_agent(groq_api_key: str):
    """Build LangGraph agent for expense analysis."""
    
    categorizer = TransactionCategorizer(groq_api_key)
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        api_key=groq_api_key,
        temperature=0.7
    )
    
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("categorize", lambda s: categorize_node(s, categorizer))
    graph.add_node("summary", summary_node)
    graph.add_node("anomaly", anomaly_node)
    graph.add_node("subscriptions", subscription_node)
    graph.add_node("breakdown", breakdown_node)
    graph.add_node("trends", trends_node)
    graph.add_node("insights", lambda s: insights_node(s, llm))
    
    # Set entry point
    graph.set_entry_point("categorize")
    
    # Add edges
    graph.add_edge("categorize", "summary")
    graph.add_edge("summary", "anomaly")
    graph.add_edge("anomaly", "subscriptions")
    graph.add_edge("subscriptions", "breakdown")
    graph.add_edge("breakdown", "trends")
    graph.add_edge("trends", "insights")
    graph.add_edge("insights", END)
    
    return graph.compile()
