# 💰 Expense AI Assistant

An AI-powered expense analysis application built with Streamlit, FastAPI, and LangGraph.

## 🎯 Features

✅ **Smart Categorization** - AI classifies transactions automatically  
✅ **Monthly Analytics** - Spending trends & insights  
✅ **Anomaly Detection** - Unusual spending alerts  
✅ **Chat Interface** - Ask questions about your expenses (with RAG)  
✅ **Budget Analysis** - Track spending by category  
✅ **Spending Forecasts** - Predict future spending  
✅ **Subscription Tracking** - Find recurring payments  

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Groq API key (free at https://console.groq.com)

### Option 1: Automatic Setup (Recommended)

**Linux/Mac:**
```bash
bash quickstart.sh
```

**Windows:**
```bash
quickstart.bat
```

### Option 2: Manual Setup

**Terminal 1:**
```bash
pip install -r requirements.txt
cd src
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

**Terminal 2:**
```bash
cd src
streamlit run streamlit_app.py
```

Open http://localhost:8501 in your browser.

## ⚙️ Configuration

1. Go to **Settings ⚙️ tab**
2. Enter your **Groq API Key** (get free at https://console.groq.com)
3. Click **Check Health** to verify
4. Upload CSV and start analyzing

## 📋 CSV File Format

Your expense CSV must have these columns:

```
name, description, amount, date
```

**Example:**
```csv
Swiggy,Food Delivery,450,2024-01-15
Amazon,Online Shopping,2500,2024-01-16
Netflix,Streaming Service,499,2024-01-10
Uber,Taxi Ride,250,2024-01-17
```

## 📁 Project Structure

```
.
├── src/
│   ├── streamlit_app.py      # Frontend UI
│   ├── main.py               # FastAPI backend
│   ├── agent.py              # LangGraph agent
│   ├── config.py             # Configuration
│   ├── tools.py              # Analysis tools
│   └── utils.py              # Utilities
├── data/
│   └── sample_expenses.csv   # Sample data
├── scripts/
│   ├── start_backend.sh      # Start backend script
│   ├── status_backend.sh     # Check backend status
│   └── stop_backend.sh       # Stop backend script
├── Dockerfile                # Docker image definition
├── docker-compose.yml        # Multi-container setup
├── requirements.txt          # Python dependencies
├── quickstart.sh             # Linux/Mac setup
├── quickstart.bat            # Windows setup
└── README.md                 # This file
```

## 🐳 Docker Deployment

```bash
# Using docker-compose
GROQ_API_KEY="your_key" docker-compose up

# Or manually
docker build -t expense-ai .
docker run -p 8000:8000 -p 8501:8501 \
  -e GROQ_API_KEY="your_key" \
  expense-ai
```

## 🆘 Troubleshooting

**"API Disconnected"**
```bash
# Check backend is running
curl http://localhost:8000/health
```

**"Invalid API Key"**
- Get key from https://console.groq.com
- Verify it's pasted correctly in Settings tab

**"CSV Upload Failed"**
- Ensure columns: `name, description, amount, date`
- Check file size is under 200MB

## 🛠️ Tech Stack

- **Frontend:** Streamlit (Python web framework)
- **Backend:** FastAPI (high-performance API)
- **LLM:** Groq API (Llama 3.1 8B Instant)
- **Workflow:** LangGraph (agentic framework)
- **Data:** Pandas, Plotly

## 📞 References

- **Groq API:** https://console.groq.com
- **FastAPI:** https://fastapi.tiangolo.com
- **Streamlit:** https://docs.streamlit.io
- **LangGraph:** https://langchain-ai.github.io/langgraph

---

**Made with ❤️ for smarter expense tracking**
