"""
Root-level entry point for Streamlit Cloud.
Runs the app from src/streamlit_app.py
"""
import sys
import os
from pathlib import Path

# Add src to path
src_path = str(Path(__file__).parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Now run the actual app - import everything from src/streamlit_app
# This should execute the Streamlit app code directly
try:
    # Execute the app module directly
    import runpy
    app_file = Path(__file__).parent / "src" / "streamlit_app.py"
    runpy.run_path(str(app_file), run_name="__main__")
except Exception as e:
    import streamlit as st
    st.error(f"Failed to load app: {e}")
    st.write(str(e))
