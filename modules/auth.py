import streamlit as st
from modules.database import create_user, get_user_by_username, verify_password, init_db

def login_user(username: str, password: str) -> bool:
    """Attempt to log in. Sets session state on success."""
    user = get_user_by_username(username)
    if user and verify_password(password, user["password_hash"]):
        st.session_state["user"] = dict(user)
        return True
    return False

def signup_user(username: str, password: str, company: str) -> bool:
    """Register a new user. Returns True if successful."""
    if create_user(username, password, company):
        # Automatically log in after signup
        user = get_user_by_username(username)
        st.session_state["user"] = dict(user)
        return True
    return False

def logout_user():
    """Clear user session."""
    st.session_state.pop("user", None)

def is_logged_in() -> bool:
    return "user" in st.session_state

def get_current_user():
    return st.session_state.get("user")
