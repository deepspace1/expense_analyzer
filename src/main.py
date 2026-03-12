import pandas as pd
import json
import os
import logging
from io import StringIO

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from langchain_groq import ChatGroq

from agent import build_agent, AgentState, sanitize_for_json

# Get API key from environment
GROQ_API_KEY = os.getenv("GROQ_API_KEY", None)

# Initialize FastAPI app
app = FastAPI(
    title="Expense Analysis AI Agent",
    description="LangGraph-based AI agent for financial expense analysis",
    version="1.0.0"
)

# Configure basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Agents are created per-request using the provided GROQ API key (header or env).


@app.get("/health")
async def health_check(request: Request):
    """Health check endpoint. If a header `X-GROQ-API-KEY` is provided, report readiness for that key."""
    header_key = request.headers.get("X-GROQ-API-KEY") or GROQ_API_KEY
    return {
        "status": "healthy",
        "service": "Expense Analysis AI Agent",
        "groq_key_provided": bool(header_key)
    }


@app.post("/analyze-expenses")
async def analyze_expenses(request: Request, file: UploadFile = File(...)):
    """
    Analyze expenses from CSV file.
    
    Expected CSV columns: name, description, amount, date
    
    Returns: Complete analysis with categories, summaries, anomalies, etc.
    """
    
    try:
        # Determine GROQ API key: header overrides environment
        groq_key = request.headers.get("X-GROQ-API-KEY") or request.headers.get("X-Groq-Api-Key") or GROQ_API_KEY
        if not groq_key:
            raise HTTPException(status_code=400, detail="Missing Groq API key. Provide X-GROQ-API-KEY header or set GROQ_API_KEY environment variable.")
        # Read CSV file
        contents = await file.read()
        df = pd.read_csv(StringIO(contents.decode('utf-8')))
        
        # Validate required columns
        required_cols = ['name', 'description', 'amount', 'date']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required columns: {', '.join(missing_cols)}"
            )
        
        # Clean data: convert amounts to numeric, then drop rows with invalid amount/date
        df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
        df = df.dropna(subset=['amount', 'date'])
        df['amount'] = df['amount'].astype(float)
        
        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="No valid transactions found in file"
            )
        
        # Build agent using provided key (creates categorizer + llm instances)
        # Validate Groq API key with a light LLM call to return a clear 401 if invalid
        try:
            from langchain_core.messages import HumanMessage
            validator_llm = ChatGroq(model="llama-3.1-8b-instant", api_key=groq_key, temperature=0.0)
            # simple test invoke to validate key
            validator_llm.invoke([HumanMessage(content="Validate key: respond OK")])
        except Exception:
            logger.exception("Groq API key validation failed")
            raise HTTPException(status_code=401, detail="Invalid Groq API key. Provide a valid X-GROQ-API-KEY header or set GROQ_API_KEY environment variable.")

        agent = build_agent(groq_key)

        # Prepare state for agent
        initial_state: AgentState = {
            "transactions": df.to_dict(orient="records"),
            "categorized_df": [],
            "monthly_summary": [],
            "anomalies": [],
            "subscriptions": [],
            "category_breakdown": [],
            "spending_trends": [],
            "financial_insights": "",
            "budget_analysis": {},
            "error": ""
        }
        
        # Run agent
        result = agent.invoke(initial_state)
        
        # Check for errors
        if result.get("error"):
            raise HTTPException(
                status_code=500,
                detail=f"Analysis failed: {result['error']}"
            )
        
        # Sanitize outputs to ensure JSON-serializable types (Period/Timestamp -> str, numpy -> native)
        categorized = sanitize_for_json(result.get("categorized_df", []))[:100]
        monthly_summary = sanitize_for_json(result.get("monthly_summary", []))
        anomalies = sanitize_for_json(result.get("anomalies", []))
        subscriptions = sanitize_for_json(result.get("subscriptions", []))
        category_breakdown = sanitize_for_json(result.get("category_breakdown", []))
        spending_trends = sanitize_for_json(result.get("spending_trends", []))
        financial_insights = result.get("financial_insights", "")
        budget_analysis = sanitize_for_json(result.get("budget_analysis", {}))

        return {
            "success": True,
            "total_transactions": len(result.get("transactions", [])),
            "analysis": {
                "categorized": categorized,
                "monthly_summary": monthly_summary,
                "anomalies": anomalies,
                "subscriptions": subscriptions,
                "category_breakdown": category_breakdown,
                "spending_trends": spending_trends,
                "financial_insights": financial_insights,
                "budget_analysis": budget_analysis
            }
        }
    
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    except Exception as e:
        # If we've already raised an HTTPException (e.g., invalid API key), re-raise it
        if isinstance(e, HTTPException):
            raise e
        # Log full exception with stacktrace for debugging
        logger.exception("Unhandled error while processing uploaded CSV")
        err_text = str(e) or ""
        # Detect unauthorized errors from the Groq API and return 401
        if "Invalid API Key" in err_text or "invalid_api_key" in err_text or "401" in err_text:
            raise HTTPException(status_code=401, detail="Invalid Groq API key. Provide a valid X-GROQ-API-KEY header or set GROQ_API_KEY environment variable.")
        raise HTTPException(status_code=500, detail=f"Error processing file: {err_text}")


@app.post("/chat")
async def chat_with_agent(request: Request, query: dict = Body(...)):
    """
    Chat with AI about expenses (extension point).
    
    Request: {"query": "Why did I spend so much in February?"}
    """
    
    try:
        user_query = query.get("query", "") if isinstance(query, dict) else ""
        # Optional transactions context for RAG-style answers
        transactions_ctx = query.get("transactions", []) if isinstance(query, dict) else []
        
        if not user_query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        # Determine GROQ API key from header or env
        groq_key = request.headers.get("X-GROQ-API-KEY") or request.headers.get("X-Groq-Api-Key") or GROQ_API_KEY
        if not groq_key:
            raise HTTPException(status_code=400, detail="Missing Groq API key. Provide X-GROQ-API-KEY header or set GROQ_API_KEY environment variable.")

        # Initialize LLM for chat using provided key
        llm = ChatGroq(
            model="llama-3.1-8b-instant",
            api_key=groq_key,
            temperature=0.2
        )

        from langchain_core.messages import HumanMessage

        # If transactions context provided, try embedding-based retrieval (TF-IDF)
        def retrieve_relevant(txns, question, k=6):
            try:
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics.pairwise import cosine_similarity
            except Exception:
                # Fallback to keyword overlap if sklearn not available
                import re
                q_tokens = set(re.findall(r"\w+", question.lower()))
                scored = []
                for i, t in enumerate(txns):
                    text = f"{t.get('name','')} {t.get('description','')} {t.get('category','')} {t.get('amount','')} {t.get('date','')}"
                    tokens = set(re.findall(r"\w+", str(text).lower()))
                    score = len(q_tokens & tokens)
                    scored.append((score, i, text))
                scored.sort(reverse=True)
                return [s[2] for s in scored[:k] if s[0] > 0]

            # Build documents
            docs = []
            for t in txns:
                docs.append(f"{t.get('name','')} {t.get('description','')} {t.get('category','')} {t.get('amount','')} {t.get('date','')}")

            # Vectorize docs + query
            vectorizer = TfidfVectorizer(stop_words='english')
            try:
                doc_vectors = vectorizer.fit_transform(docs)
                q_vec = vectorizer.transform([question])
                sims = cosine_similarity(q_vec, doc_vectors).flatten()
                top_idx = sims.argsort()[::-1][:k]
                results = [docs[i] for i in top_idx if sims[i] > 0]
                return results
            except Exception:
                # final fallback to keyword overlap
                import re
                q_tokens = set(re.findall(r"\w+", question.lower()))
                scored = []
                for i, t in enumerate(txns):
                    text = docs[i]
                    tokens = set(re.findall(r"\w+", str(text).lower()))
                    score = len(q_tokens & tokens)
                    scored.append((score, i, text))
                scored.sort(reverse=True)
                return [s[2] for s in scored[:k] if s[0] > 0]

        context_snippets = []
        if transactions_ctx:
            try:
                context_snippets = retrieve_relevant(transactions_ctx, user_query, k=8)
            except Exception:
                context_snippets = []

        if context_snippets:
            context_text = "\n\n".join(context_snippets)
            prompt = (
                "You are a financial assistant. Answer the user only using the provided transaction data below. "
                "If the answer is not present in the data, say you don't have enough information.\n\n"
                f"Context:\n{context_text}\n\nQuestion: {user_query}\nAnswer concisely."
            )
        else:
            prompt = f"As a financial advisor, answer this using the available transaction data: {user_query}"

        response = llm.invoke([
            HumanMessage(content=prompt)
        ])

        return {
            "query": user_query,
            "response": response.content,
            "used_context_count": len(context_snippets)
        }
    
    except Exception as e:
        # If an HTTPException was raised upstream, re-raise it
        if isinstance(e, HTTPException):
            raise e
        logger.exception("Chat endpoint error")
        err_text = str(e) or ""
        if "Invalid API Key" in err_text or "invalid_api_key" in err_text or "401" in err_text:
            raise HTTPException(status_code=401, detail="Invalid Groq API key. Provide a valid X-GROQ-API-KEY header or set GROQ_API_KEY environment variable.")
        raise HTTPException(status_code=500, detail=f"Chat error: {err_text}")


@app.get("/")
async def root():
    """Root endpoint with API documentation."""
    return {
        "message": "Expense Analysis AI Agent API",
        "endpoints": {
            "POST /analyze-expenses": "Upload CSV and get full analysis",
            "POST /chat": "Chat about expenses",
            "GET /health": "Health check",
            "GET /docs": "Swagger UI documentation"
        },
        "csv_format": {
            "columns": ["name", "description", "amount", "date"],
            "example": {
                "name": "Swiggy",
                "description": "Food Delivery",
                "amount": 450,
                "date": "2024-01-15"
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    # Use import string when enabling reload/workers to avoid warnings
    # and ensure running via `python main.py` works as expected.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
