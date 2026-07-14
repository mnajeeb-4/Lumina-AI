import streamlit as st
import json
import uuid
from datetime import datetime

class IntegrationSimulator:
    """Simulate incoming webhook requests and display a terminal log."""

    def __init__(self):
        if "webhook_urls" not in st.session_state:
            st.session_state["webhook_urls"] = {}
        if "simulation_logs" not in st.session_state:
            st.session_state["simulation_logs"] = []

    def generate_webhook_url(self, bot_id: int) -> str:
        """Generate a unique, fake webhook endpoint for the bot."""
        unique_id = str(uuid.uuid4())[:8]
        base = "https://ai-support-saas.streamlit.app/webhook"
        url = f"{base}/{bot_id}/{unique_id}"
        st.session_state["webhook_urls"][bot_id] = url
        return url

    def simulate_incoming_message(self, bot_id: int, payload: dict):
        """Log a simulated incoming payload to the terminal."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] RECEIVED for bot_{bot_id}:\n{json.dumps(payload, indent=2)}"
        st.session_state["simulation_logs"].append(log_entry)
        # Here you could trigger automatic responses in a real integration.
        # For demo, we'll just return a mock response.
        return {"status": "received", "bot_id": bot_id}

    def get_logs(self, limit=10):
        """Return the most recent log entries."""
        logs = st.session_state["simulation_logs"]
        return logs[-limit:]
