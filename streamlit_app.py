"""
Root-level entry point for Streamlit Cloud deployment.
This file imports and runs the actual app from src/
"""
import sys
from pathlib import Path

# Add src directory to path so we can import the app
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import and run the app
from streamlit_app import *  # noqa: F401, F403
