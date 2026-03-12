import streamlit as st
import pandas as pd
import requests
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io
import subprocess
import os
import signal
import time
import numpy as np
from streamlit.components.v1 import html as st_components_html

# Page configuration
st.set_page_config(
    page_title="💰 Expense AI Assistant",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .alert-danger {
        background-color: #fee;
        border: 1px solid #fcc;
        border-radius: 5px;
        padding: 1rem;
        color: #c33;
    }
    .alert-success {
        background-color: #efe;
        border: 1px solid #cfc;
        border-radius: 5px;
        padding: 1rem;
        color: #3c3;
    }
    /* Chat styling */
    .chat-container {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }
    .chat-msg {
        padding: 0.75rem 1rem;
        border-radius: 12px;
        max-width: 80%;
        margin-bottom: 0.5rem;
        line-height: 1.3;
    }
    .chat-user { background:#0b5cff; color: white; margin-left: auto; }
    .chat-assistant { background:#f1f3f5; color: #111; margin-right: auto; }
    .chat-meta { font-size: 0.8rem; color: #666; margin-bottom: 0.25rem; }
</style>
""", unsafe_allow_html=True)

# Sidebar - Configuration (only backend control, settings moved to tabs)
st.sidebar.title("⚙️ Configuration")

# Initialize session state for API settings (loaded from env or persisted in session)
if "api_base_url" not in st.session_state:
    st.session_state.api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
if "groq_api_key" not in st.session_state:
    st.session_state.groq_api_key = os.getenv("GROQ_API_KEY", "")

# Simplified sidebar (backend control only)
API_BASE_URL = st.session_state.api_base_url
GROQ_API_KEY_INPUT = st.session_state.groq_api_key

# Backend control utilities (start/stop local FastAPI)
PROJECT_DIR = os.path.dirname(__file__)
BACKEND_CMD = ["python", "main.py"]

def is_pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True

def start_local_backend() -> int:
    """Start the FastAPI backend in background and return its PID."""
    log_path = os.path.join(PROJECT_DIR, "backend.log")
    f = open(log_path, "a")
    # Start process detached
    proc = subprocess.Popen(
        BACKEND_CMD,
        cwd=PROJECT_DIR,
        stdout=f,
        stderr=subprocess.STDOUT,
        start_new_session=True
    )
    # give server a moment to boot
    time.sleep(0.5)
    return proc.pid

def stop_local_backend(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except Exception:
        pass

# --------------------
# Helper AI tool functions
# --------------------
def _get_transactions_df() -> pd.DataFrame | None:
    # Prefer session preview, then analysis_result transactions
    if "df_preview" in st.session_state:
        return st.session_state.df_preview.copy()
    if "analysis_result" in st.session_state:
        ar = st.session_state.analysis_result if isinstance(st.session_state.analysis_result, dict) else {}
        details = ar.get("analysis") if isinstance(ar, dict) else None
        txns = []
        if isinstance(details, dict):
            txns = details.get("categorized", []) or details.get("transactions", [])
        if txns:
            try:
                df = pd.DataFrame(txns)
                if "amount" in df.columns:
                    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
                return df
            except Exception:
                return None
    return None


def budget_analyzer(df: pd.DataFrame) -> dict:
    # Simple per-category spend breakdown and top categories
    out = {}
    if df is None or df.empty:
        return {"error": "No transactions available"}
    df = df.copy()
    if "category" not in df.columns:
        df["category"] = "Uncategorized"
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    totals = df.groupby("category")["amount"].sum().sort_values(ascending=False)
    out["totals"] = totals.to_dict()
    out["top_categories"] = totals.head(5).to_dict()
    out["total_spend"] = float(totals.sum())
    return out


def spend_forecast(df: pd.DataFrame, months_ahead: int = 3) -> dict:
    # Monthly totals and a simple linear forecast for the next N months
    out = {}
    if df is None or df.empty:
        return {"error": "No transactions available"}
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"])    
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    monthly = df.set_index("date").resample("M")["amount"].sum()
    if len(monthly) < 2:
        return {"error": "Not enough monthly data to forecast"}
    x = np.arange(len(monthly))
    y = monthly.values
    coef = np.polyfit(x, y, 1)
    trend = float(np.polyval(coef, x[-1]))
    preds = []
    for i in range(1, months_ahead + 1):
        p = float(np.polyval(coef, x[-1] + i))
        preds.append(p)
    out["monthly"] = monthly.round(2).to_dict()
    out["forecast_next_months"] = [round(float(v), 2) for v in preds]
    return out


def detect_anomalies(df: pd.DataFrame) -> dict:
    # Simple z-score anomaly detection on amounts
    out = {}
    if df is None or df.empty:
        return {"error": "No transactions available"}
    df = df.copy()
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df = df.dropna(subset=["amount"])
    if df.empty:
        return {"error": "No numeric amounts found"}
    mu = df["amount"].mean()
    sigma = df["amount"].std()
    if sigma == 0 or np.isnan(sigma):
        return {"error": "No variance in amounts"}
    df["zscore"] = (df["amount"] - mu) / sigma
    anomalies = df.loc[df["zscore"].abs() > 3].sort_values("zscore", key=abs, ascending=False)
    out["count"] = len(anomalies)
    out["examples"] = anomalies.head(10).to_dict(orient="records")
    return out


def savings_opportunities(df: pd.DataFrame) -> dict:
    # Heuristic: identify top discretionary categories by avg amount and frequency
    out = {}
    if df is None or df.empty:
        return {"error": "No transactions available"}
    df = df.copy()
    if "category" not in df.columns:
        df["category"] = "Uncategorized"
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    bucket = df.groupby("category").agg(total_spend=("amount", "sum"), avg_txn=("amount", "mean"), count=("amount", "count"))
    bucket = bucket.sort_values("total_spend", ascending=False)
    suggestions = []
    for cat, row in bucket.head(5).iterrows():
        suggestions.append({
            "category": cat,
            "total_spend": float(row["total_spend"]),
            "avg_txn": float(row["avg_txn"]),
            "count": int(row["count"]),
            "suggested_cut_pct": 10
        })
    out["suggestions"] = suggestions
    return out

# --------------------
# RAG prompt templates
# --------------------
MAIN_SYSTEM_PROMPT = (
    "You are an AI expense analysis assistant.\n\n"
    "Your job is to answer questions ONLY using the provided expense data.\n\n"
    "Rules:\n"
    "1. Use ONLY the provided context data.\n"
    "2. Do NOT use outside knowledge.\n"
    "3. If the answer is not found in the data, say:\n"
    "   \"I cannot find that in the uploaded expense data.\"\n"
    "4. Be precise and concise.\n"
    "5. If the user asks about totals, categories, or patterns, calculate based on the provided data.\n"
    "6. If relevant, explain insights about spending patterns.\n\n"
    "Context (Expense Data):\n{context}\n\nUser Question:\n{question}\n\nAnswer:"
)

STRICT_RAG_PROMPT = (
    "You are an expense assistant.\n\n"
    "Answer the user's question ONLY using the expense records provided in the context.\n"
    "Do NOT make up information.\n"
    "Do NOT use external knowledge.\n"
    "If the information is not present in the context, respond with:\n"
    "\"I cannot find that in the uploaded expense data.\"\n\n"
    "Context:\n{context}\n\nQuestion:\n{question}\n\nAnswer clearly based only on the context."
)

SMART_PROMPT = (
    "You are an intelligent expense analysis assistant.\n\n"
    "You analyze personal expense records and help users understand their spending.\n\n"
    "Instructions:\n"
    "- Use ONLY the expense data provided in the context.\n"
    "- Do NOT use outside information.\n"
    "- If the answer cannot be found in the data, say:\n"
    "\"I cannot find that in the uploaded expense data.\"\n"
    "- If possible, calculate totals, averages, or category spending.\n"
    "- Provide short insights if useful.\n\n"
    "Expense Records:\n{context}\n\nUser Question:\n{question}\n\nAnswer:"
)


def _build_context_from_df(df: pd.DataFrame, max_rows: int = 200) -> str:
    """Serialize a transactions DataFrame into a compact context string for RAG prompts."""
    if df is None or df.empty:
        return ""
    # limit rows
    df2 = df.head(max_rows).copy()
    # ensure columns exist
    cols = [c for c in ["name", "description", "amount", "date", "category"] if c in df2.columns]
    lines = []
    for _, r in df2.iterrows():
        parts = []
        for c in cols:
            val = r.get(c, "")
            parts.append(f"{c}: {val}")
        lines.append("; ".join(parts))
    return "\n".join(lines)


def _render_chat_html(messages: list) -> str:
        """Build HTML for chat messages with avatars, bubbles and auto-scroll."""
        safe_messages = []
        for m in messages:
                role = m.get("role", "assistant")
                content = str(m.get("content", ""))
                # simple escape
                content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                ts = ""
                if role == "user":
                        safe_messages.append({"side": "right", "avatar": "U", "content": content, "ts": ts})
                else:
                        safe_messages.append({"side": "left", "avatar": "AI", "content": content, "ts": ts})

        # build html
        items = []
        for m in safe_messages:
                if m["side"] == "right":
                        items.append(f"<div class=\"msg-row right\"><div class=\"bubble user\">{m['content']}</div><div class=\"avatar user\">{m['avatar']}</div></div>")
                else:
                        items.append(f"<div class=\"msg-row left\"><div class=\"avatar bot\">{m['avatar']}</div><div class=\"bubble bot\">{m['content']}</div></div>")

        html = f"""
<style>
    .chat-wrap {{ background: linear-gradient(180deg,#0f1724 0%, #0b1220 100%); padding:12px; border-radius:8px; }}
    .msg-row {{ display:flex; align-items:flex-end; gap:8px; margin:8px 0; }}
    .msg-row.right {{ justify-content:flex-end; }}
    .msg-row.left {{ justify-content:flex-start; }}
    .avatar {{ width:36px; height:36px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; font-weight:700; color:#fff; }}
    .avatar.bot {{ background:#e6eef8; color:#111; border:1px solid rgba(255,255,255,0.06); }}
    .avatar.user {{ background:#0b5cff; }}
    .bubble {{ max-width:78%; padding:10px 14px; border-radius:12px; line-height:1.4; white-space:pre-wrap; }}
    .bubble.bot {{ background:#f1f3f5; color:#111; border-radius:12px 12px 12px 4px; }}
    .bubble.user {{ background:#0b5cff; color:#fff; border-radius:12px 12px 4px 12px; }}
    .chat-scroll {{ max-height:56vh; overflow:auto; padding:8px; }}
</style>
<div class="chat-wrap">
    <div id="chat-scroll" class="chat-scroll">
        {''.join(items)}
    </div>
</div>
<script>
    const el = document.getElementById('chat-scroll');
    if (el) {{ el.scrollTop = el.scrollHeight; }}
</script>
"""
        return html


def _choose_prompt_template(key: str) -> str:
    if key == "main":
        return MAIN_SYSTEM_PROMPT
    if key == "strict":
        return STRICT_RAG_PROMPT
    return SMART_PROMPT


def _call_api_with_retry(endpoint: str, payload: dict, headers: dict, retries: int = 2) -> tuple:
    """Call API endpoint with retry logic. Returns (success, response_text)."""
    api_url = st.session_state.get("api_base_url", "http://localhost:8000")
    for attempt in range(retries):
        try:
            response = requests.post(f"{api_url}{endpoint}", json=payload, headers=headers, timeout=120)
            if response.status_code == 200:
                return True, response.json().get("response", "No response")
            elif response.status_code == 429:
                # Rate limited, wait and retry
                if attempt < retries - 1:
                    time.sleep(2)
                    continue
            return False, f"Error {response.status_code}"
        except requests.exceptions.Timeout:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return False, "Request timeout - API may be overloaded"
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(1)
                continue
            return False, f"Error: {str(e)}"
    return False, "Failed after retries"


def render_analysis_ui(result: dict) -> None:
    """Render analysis metrics and charts on the Analysis tab given API result."""
    analysis_section = result if isinstance(result, dict) else {}
    metrics = analysis_section.get("analysis") if isinstance(analysis_section, dict) else {}

    st.divider()
    st.subheader("📊 Overview Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_transactions = result.get("total_transactions", 0)
        st.metric("Total Transactions", total_transactions)
    with col2:
        categorized = len(metrics.get("categorized", [])) if isinstance(metrics, dict) else 0
        st.metric("Categorized", categorized)
    with col3:
        anomalies = len(metrics.get("anomalies", [])) if isinstance(metrics, dict) else 0
        st.metric("Anomalies Detected", anomalies)
    with col4:
        subscriptions = len(metrics.get("subscriptions", [])) if isinstance(metrics, dict) else 0
        st.metric("Subscriptions Found", subscriptions)

    st.divider()
    st.subheader("📅 Monthly Spending Summary")
    monthly_data = pd.DataFrame(metrics.get("monthly_summary", [])) if isinstance(metrics, dict) else pd.DataFrame()
    if not monthly_data.empty:
        fig = px.bar(
            monthly_data,
            x="month",
            y="amount",
            color="category",
            title="Monthly Spending by Category",
            barmode="stack"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
        st.write("**Detailed Summary:**")
        st.dataframe(monthly_data, use_container_width=True)

    st.divider()
    st.subheader("🥧 Spending by Category")
    breakdown_data = pd.DataFrame(metrics.get("category_breakdown", [])) if isinstance(metrics, dict) else pd.DataFrame()
    if not breakdown_data.empty:
        try:
            fig = px.bar(
                breakdown_data,
                x="category",
                y="total",
                title="Spending by Category",
                text=breakdown_data["total"].round(2)
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(height=400, xaxis_title="Category", yaxis_title="Total Spend")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            fig = px.pie(breakdown_data, values="total", names="category", title="Spending Distribution")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        breakdown_display = breakdown_data.copy()
        if "total" in breakdown_display.columns:
            breakdown_display["total"] = breakdown_display["total"].round(2)
        if "avg_transaction" in breakdown_display.columns:
            breakdown_display["avg_transaction"] = breakdown_display["avg_transaction"].round(2)
        st.dataframe(breakdown_display, use_container_width=True)

    st.divider()
    st.subheader("📈 Spending Trends")
    trends_data = pd.DataFrame(metrics.get("spending_trends", [])) if isinstance(metrics, dict) else pd.DataFrame()
    if not trends_data.empty:
        fig = px.line(trends_data, x="month", y="total", title="Monthly Total Spending Trend", markers=True)
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)

    st.divider()
    st.subheader("⚠️ Spending Anomalies")
    anomalies = metrics.get("anomalies", []) if isinstance(metrics, dict) else []
    if anomalies:
        anomalies_df = pd.DataFrame(anomalies)
        if "category" not in anomalies_df.columns:
            anomalies_df["category"] = ""
        st.warning(f"🚨 Found {len(anomalies)} unusual transactions")
        st.dataframe(anomalies_df, use_container_width=True)
    else:
        st.info("✅ No anomalies detected")

    st.divider()
    st.subheader("🔄 Recurring Subscriptions")
    subscriptions = metrics.get("subscriptions", []) if isinstance(metrics, dict) else []
    if subscriptions:
        subs_df = pd.DataFrame(subscriptions)
        subs_df = subs_df.rename(columns={"frequency": "# of Times"})
        if "category" not in subs_df.columns:
            subs_df["category"] = ""
        total_sub_cost = subs_df.get("amount", pd.Series([])).sum()
        st.info(f"📌 Total recurring spend: ₹{total_sub_cost:.2f}")
        st.dataframe(subs_df, use_container_width=True)
    else:
        st.info("No recurring transactions found")

    st.divider()
    st.subheader("🧾 Transactions (with categories)")
    display_df = st.session_state.get("df_preview") if "df_preview" in st.session_state else None
    if display_df is None and isinstance(result, dict):
        # fall back to transactions in the result if available
        details = result.get("analysis") if isinstance(result, dict) else None
        display_df = pd.DataFrame(details.get("categorized", [])) if isinstance(details, dict) else pd.DataFrame()
    if display_df is None:
        st.info("No transaction preview available")
    else:
        if "category" not in display_df.columns:
            display_df["category"] = ""
        st.dataframe(display_df, use_container_width=True)

# Note: Local backend controls are only for local development
# On Streamlit Cloud, configure the remote backend URL in Settings tab

# Cache the API health check for 30 seconds to avoid repeated calls
@st.cache_data(ttl=30, show_spinner=False)
def check_api_health_cached():
    """Check API health with caching to speed up page loads."""
    for attempt in range(2):
        try:
            # Use session state for API URL and key
            api_url = st.session_state.get("api_base_url", "http://localhost:8000")
            # Quick health check without auth header
            response = requests.get(f"{api_url}/health", timeout=3)
            if response.status_code == 200:
                return True
        except Exception:
            pass

        try:
            api_url = st.session_state.get("api_base_url", "http://localhost:8000")
            headers = {}
            key = st.session_state.get("groq_api_key", "") or os.getenv("GROQ_API_KEY")
            if key:
                headers["X-GROQ-API-KEY"] = key
                response = requests.get(f"{api_url}/health", timeout=5, headers=headers)
                if response.status_code == 200:
                    return True
        except Exception:
            pass

        # Small delay before retry
        if attempt < 1:
            time.sleep(0.5)

    return False

# Check API health (cached for 30 seconds)
api_healthy = check_api_health_cached()

# Show status
if api_healthy:
    st.sidebar.success("✅ API Connected")
else:
    st.sidebar.warning("⚠️ API Not Connected - Check Settings")

# Main content
st.title("💰 Expense AI Assistant")
st.write("Powered by LangGraph + Groq Llama 3.1 8B Instant")

# Tabs
tab1, tab2, tab3, tab_settings, tab4 = st.tabs(["📊 Analysis", "📈 Insights", "💬 Chat", "⚙️ Settings", "ℹ️ About"])

# ============================================================================
# TAB 1: Analysis
# ============================================================================
with tab1:
    st.header("Upload & Analyze Expenses")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "Upload CSV file",
            type="csv",
            help="CSV columns: name, description, amount, date"
        )
    with col2:
        st.write("**CSV Format:**")
        st.code("name, description, amount, date")
    # Upload preview + analyze actions
    if uploaded_file is not None:
        st.divider()
        try:
            df_preview = pd.read_csv(uploaded_file)
        except Exception as e:
            st.error(f"Failed to read CSV: {e}")
            df_preview = None

        if df_preview is not None:
            if "category" not in df_preview.columns:
                df_preview["category"] = ""
            st.write(f"**Preview ({len(df_preview)} transactions):**")
            st.dataframe(df_preview.head(10), use_container_width=True)
            # store preview in session so other tabs/tools can access
            st.session_state.df_preview = df_preview

            if st.button("🚀 Analyze with AI", use_container_width=True, type="primary"):
                if not api_healthy:
                    st.error("❌ API is not connected. Please check the connection settings.")
                else:
                    with st.spinner("🤖 AI Agent analyzing your expenses..."):
                        try:
                            api_url = st.session_state.get("api_base_url", "http://localhost:8000")
                            groq_key = st.session_state.get("groq_api_key", "")
                            headers = {}
                            if groq_key:
                                headers["X-GROQ-API-KEY"] = groq_key

                            response = requests.post(
                                f"{api_url}/analyze-expenses",
                                files={"file": ("file.csv", io.BytesIO(uploaded_file.getvalue()), "text/csv")},
                                headers=headers,
                                timeout=None
                            )

                            if response.status_code == 200:
                                result = response.json()
                                st.session_state.analysis_result = result
                                # try to update preview categories if provided
                                try:
                                    analysis_section = result if isinstance(result, dict) else {}
                                    analysis_details = analysis_section.get("analysis") if isinstance(analysis_section, dict) else None
                                    categorized = pd.DataFrame(analysis_details.get("categorized", []) if isinstance(analysis_details, dict) else [])
                                    if not categorized.empty:
                                        # Merge categorized categories back into original preview (by name+amount+date)
                                        preview = df_preview.copy()
                                        if {"name", "amount", "date"}.issubset(categorized.columns):
                                            categorized["amount"] = pd.to_numeric(categorized["amount"], errors="coerce")
                                            preview["amount"] = pd.to_numeric(preview["amount"], errors="coerce")
                                            merged = preview.merge(
                                                categorized[["name", "amount", "date", "category"]],
                                                on=["name", "amount", "date"],
                                                how="left",
                                                suffixes=("", "_ai")
                                            )
                                            # prefer AI category when present
                                            if "category_ai" in merged.columns:
                                                merged["category"] = merged["category_ai"].combine_first(merged["category"])
                                                merged = merged.drop(columns=[c for c in merged.columns if c.endswith("_ai")])
                                            st.session_state.df_preview = merged
                                        else:
                                            st.session_state.df_preview = categorized.reindex(columns=list(categorized.columns))
                                except Exception:
                                    # if merging fails, ignore and keep original preview
                                    pass

                                # persist analysis result and render UI
                                st.session_state.analysis_result = result
                                st.success("✅ Analysis complete! Results shown below.")
                                render_analysis_ui(result)
                            else:
                                st.error(f"❌ API Error: {response.status_code} - {response.text}")
                        except Exception as e:
                            st.error(f"Error: {e}")
    

# Sample data loader removed from sidebar; sample loading is intentionally omitted per user request.
if False:
    # placeholder block kept to preserve file structure in diffs
    pass

# ============================================================================
# TAB 2: AI Insights
# ============================================================================
with tab2:
    st.header("🧠 AI Financial Insights")
    
    if "analysis_result" in st.session_state:
        # Safely handle cases where the API returned no 'analysis' key
        analysis_section = st.session_state.analysis_result if isinstance(st.session_state.analysis_result, dict) else {}
        analysis_details = analysis_section.get("analysis") if isinstance(analysis_section, dict) else None
        insights = ""
        if isinstance(analysis_details, dict):
            insights = analysis_details.get("financial_insights", "")
        else:
            st.warning("Analysis result is missing detailed 'analysis' information.")

        if insights:
            st.markdown(insights)
        else:
            st.info("No insights available. Please complete analysis first.")
    else:
        st.info("👈 Complete analysis in the **Analysis** tab first to see AI insights.")

    # Quick AI Tools (moved here from sidebar)
    st.divider()
    st.subheader("⚡ Quick AI Tools")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("Budget Analyzer", key="tool_budget"):
            df = _get_transactions_df()
            st.session_state.tool_result = ("Budget Analyzer", budget_analyzer(df))
    with c2:
        if st.button("Spend Forecast", key="tool_forecast"):
            df = _get_transactions_df()
            st.session_state.tool_result = ("Spend Forecast", spend_forecast(df))
    with c3:
        if st.button("Anomaly Detector", key="tool_anomaly"):
            df = _get_transactions_df()
            st.session_state.tool_result = ("Anomaly Detector", detect_anomalies(df))
    with c4:
        if st.button("Savings Opportunities", key="tool_savings"):
            df = _get_transactions_df()
            st.session_state.tool_result = ("Savings Opportunities", savings_opportunities(df))

    # Display tool results
    if "tool_result" in st.session_state:
        name, payload = st.session_state.tool_result
        st.markdown(f"**{name}**")
        if name == "Budget Analyzer" and isinstance(payload, dict) and payload.get("totals"):
            totals = payload.get("totals", {})
            df_tot = pd.DataFrame(list(totals.items()), columns=["category", "total"]).sort_values("total", ascending=False)
            fig = px.bar(df_tot, x="category", y="total", title="Spend by Category")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df_tot, use_container_width=True)
        elif name == "Spend Forecast" and isinstance(payload, dict) and payload.get("monthly"):
            monthly = payload.get("monthly", {})
            if monthly:
                df_mon = pd.DataFrame(list(monthly.items()), columns=["month", "total"])                
                fig = px.line(df_mon, x="month", y="total", title="Monthly Spend")
                st.plotly_chart(fig, use_container_width=True)
                st.json(payload)
            else:
                st.json(payload)
        else:
            st.json(payload)

# ============================================================================
# TAB 3: Chat (ChatGPT-style UI)
# ============================================================================
with tab3:
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    st.title("💬 Chat with AI")

    # Chat settings section (only visible here, in the Chat tab)
    with st.expander("⚙️ Chat Settings", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            rag_mode = st.checkbox("🔍 Use RAG", value=False, help="Answer only from uploaded data")
        with col2:
            prompt_choice = st.selectbox(
                "Prompt Template",
                options=["main", "strict", "smart"],
                format_func=lambda k: {"main": "Main", "strict": "Strict", "smart": "Smart"}[k],
            )
        preview_prompt = st.checkbox("📋 Preview RAG Prompt", value=False, help="Show the assembled prompt before sending")
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    st.divider()

    # Display chat messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask something about your expenses..."):
        
        # Store and display user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Prepare API request
        groq_key = st.session_state.get("groq_api_key", "")
        headers = {}
        if groq_key:
            headers["X-GROQ-API-KEY"] = groq_key

        payload = None
        use_rag = rag_mode

        if use_rag:
            df_context = _get_transactions_df()
            if df_context is None or df_context.empty:
                with st.chat_message("assistant"):
                    st.error("❌ No uploaded data. Upload a CSV in Analysis tab first.")
                st.session_state.messages.append({"role": "assistant", "content": "❌ No uploaded data. Upload a CSV in Analysis tab first."})
            else:
                context_str = _build_context_from_df(df_context)
                template = _choose_prompt_template(prompt_choice)
                prompt_text = template.format(context=context_str, question=prompt)
                if preview_prompt:
                    with st.expander("📋 RAG Prompt Preview"):
                        st.code(prompt_text, language="text")
                payload = {"query": prompt_text}
        else:
            payload = {"query": prompt}
            if "analysis_result" in st.session_state:
                analysis_section = st.session_state.analysis_result if isinstance(st.session_state.analysis_result, dict) else {}
                categorized = []
                if isinstance(analysis_section, dict):
                    analysis_details = analysis_section.get("analysis") if isinstance(analysis_section, dict) else None
                    if isinstance(analysis_details, dict):
                        categorized = analysis_details.get("categorized", [])
                if categorized:
                    payload["transactions"] = categorized

        if payload is not None and api_healthy:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                message_placeholder.markdown("⏳ Thinking...")

                success, response_text = _call_api_with_retry("/chat", payload, headers, retries=2)
                if success:
                    full_response = response_text
                else:
                    full_response = f"❌ {response_text}"

                message_placeholder.markdown(full_response)

            st.session_state.messages.append({"role": "assistant", "content": full_response})
            st.rerun()
        elif payload is not None and not api_healthy:
            with st.chat_message("assistant"):
                st.error("❌ API not connected. Attempting to reconnect...")

# ============================================================================
# TAB 4 (Settings): Configuration for Deployment
# ============================================================================
with tab_settings:
    st.header("⚙️ Configuration & API Keys")
    
    st.write("Configure your API settings for this session. Settings are stored locally in your browser session.")
    
    st.divider()
    
    # API Base URL
    st.subheader("🔗 API Backend")
    api_url = st.text_input(
        "API Base URL",
        value=st.session_state.api_base_url,
        help="The FastAPI backend URL. Default: http://localhost:8000",
        placeholder="http://localhost:8000"
    )
    if api_url != st.session_state.api_base_url:
        st.session_state.api_base_url = api_url
        st.success("✅ API URL updated")
    
    st.divider()
    
    # Groq API Key
    st.subheader("🔑 Groq API Key")
    st.write("""
    Get your free Groq API key from [console.groq.com](https://console.groq.com)
    - Free tier includes 30 requests/minute
    - No credit card required
    """)
    
    groq_key = st.text_input(
        "Groq API Key",
        value=st.session_state.groq_api_key,
        type="password",
        help="Your Groq API key. This is sent to the backend in request headers and NOT stored.",
        placeholder="gsk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    )
    if groq_key != st.session_state.groq_api_key:
        st.session_state.groq_api_key = groq_key
        st.success("✅ API key updated")
    
    st.info("💡 **Note:** API keys are only stored in your session and sent via secure headers. They are NOT persisted to disk.")
    
    st.divider()
    
    # Backend Status
    st.subheader("📊 Backend Status")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Check Health", use_container_width=True):
            try:
                response = requests.get(f"{st.session_state.api_base_url}/health", timeout=5)
                if response.status_code == 200:
                    health = response.json()
                    st.success(f"✅ Backend healthy")
                    st.json(health)
                else:
                    st.error(f"❌ Backend returned {response.status_code}")
            except Exception as e:
                st.error(f"❌ Cannot reach backend: {e}")
    
    with col2:
        if st.button("🚀 Start Backend", use_container_width=True):
            if not api_healthy:
                try:
                    pid = start_local_backend()
                    st.success(f"✅ Backend started (PID: {pid})")
                    time.sleep(2)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to start backend: {e}")
            else:
                st.info("Backend is already running")
    
    with col3:
        if st.button("⏹️ Stop Backend", use_container_width=True):
            if "backend_pid" in st.session_state and st.session_state.backend_pid:
                try:
                    stop_local_backend()
                    st.success("✅ Backend stopped")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to stop backend: {e}")
            else:
                st.info("No local backend running")
    
    st.divider()
    
    # Deployment guide
    st.subheader("🚀 Deployment Guide")
    st.write("""
    ### For Self-Hosting or Cloud Deployment:
    
    1. **Environment Setup:**
       - Python 3.9+
       - Install: `pip install -r requirements.txt`
    
    2. **Backend Configuration:**
       - Set `GROQ_API_KEY` environment variable OR have users provide it via UI
       - Run: `python main.py` (or via `uvicorn main:app --host 0.0.0.0 --port 8000`)
    
    3. **Frontend Configuration:**
       - Run: `streamlit run streamlit_app.py`
       - Users configure API URL & key in the Settings tab
    
    4. **Docker Deployment:**
       ```bash
       docker build -t expense-ai .
       docker run -p 8000:8000 -p 8501:8501 expense-ai
       ```
    
    5. **Cloud Platforms (Streamlit Cloud, Heroku, AWS, etc):**
       - Backend: Deploy FastAPI to Heroku/AWS/Railway
       - Frontend: Deploy to Streamlit Cloud (free)
       - Users set API URL to your backend URL in Settings tab
    """)

# ============================================================================
# TAB 5: About
# ============================================================================
with tab4:
    st.header("ℹ️ About This Application")
    
    st.write("""
    ### 🚀 Advanced Expense Analysis System
    
    This is a **production-ready** AI-powered expense analysis platform built with:
    
    **Frontend:**
    - Streamlit (Python web framework)
    - Plotly (interactive charts)
    
    **Backend:**
    - FastAPI (high-performance API)
    - LangGraph (agentic workflow)
    - Groq API (fast LLM inference)
    - Llama 3.1 8B Instant (state-of-the-art open model)
    
    ### 🎯 Features
    
    ✅ **Smart Categorization** - AI classifies transactions  
    ✅ **Monthly Analytics** - Spending trends & patterns  
    ✅ **Anomaly Detection** - Unusual spending alerts  
    ✅ **Subscription Tracking** - Recurring payment detection  
    ✅ **Financial Insights** - AI-powered recommendations  
    ✅ **Chat Interface** - Ask questions about your spending  
    
    ### 📋 CSV Format
    
    Your CSV must have these columns:
    - `name` - Transaction name/merchant
    - `description` - Transaction description
    - `amount` - Transaction amount
    - `date` - Transaction date (YYYY-MM-DD)
    
    Example:
    """)
    
    st.code("""name,description,amount,date
Swiggy,Food Delivery,450,2024-01-15
Amazon,Online Shopping,2500,2024-01-16
Netflix,Streaming Service,499,2024-01-10
Uber,Taxi Ride,250,2024-01-17""")
    
    st.write("""
    ### 🔧 Setup Instructions
    
    1. **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
    
    2. **Set your Groq API key:**
    ```bash
    export GROQ_API_KEY="your_api_key_here"
    ```
    
    3. **Start the backend:**
    ```bash
    python main.py
    ```
    
    4. **Start the frontend:**
    ```bash
    streamlit run streamlit_app.py
    ```
    
    5. **Open browser:**
    ```
    http://localhost:8501
    ```
    
    ### 🏗️ Architecture
    
    The system uses **LangGraph** to orchestrate a multi-step agent workflow:
    
    1. **Categorization** - Classify each transaction
    2. **Summary** - Monthly breakdown
    3. **Anomaly Detection** - Find unusual spending
    4. **Subscriptions** - Identify recurring payments
    5. **Breakdown** - Category analysis
    6. **Trends** - Temporal analysis
    7. **Insights** - AI recommendations
    
    Each step is modular and can run independently.
    
    ### 📞 Support
    
    For issues or questions, check:
    - API Docs: http://localhost:8000/docs
    - Groq API: https://console.groq.com
    """)
