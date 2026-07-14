import streamlit as st
from pathlib import Path
import sys
import os

# Add project root to path for module imports
sys.path.append(str(Path(__file__).parent))

from modules.database import init_db, create_bot, get_user_bots, get_bot, get_total_bots
from modules.auth import login_user, signup_user, logout_user, is_logged_in, get_current_user
from modules.ai_engine import train_bot, load_vector_store, get_conversation_chain, get_openai_api_key
from modules.integrations import IntegrationSimulator

# ---------- Page Config & CSS ----------
st.set_page_config(
    page_title="AI Support SaaS",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
def load_css(file_path: str):
    with open(file_path) as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

css_path = Path(__file__).parent / "assets" / "style.css"
if css_path.exists():
    load_css(css_path)

# Initialize database
init_db()

# ---------- Session State Defaults ----------
if "chat_histories" not in st.session_state:
    st.session_state["chat_histories"] = {}  # bot_id -> list of messages
if "active_bot_id" not in st.session_state:
    st.session_state["active_bot_id"] = None

# ---------- Sidebar: Auth & API Key ----------
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/chatbot.png", width=80)
    st.title("AI Support SaaS")

    if not is_logged_in():
        auth_mode = st.radio("Choose", ["Login", "Sign Up"], horizontal=True)
        if auth_mode == "Login":
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login", use_container_width=True)
                if submitted:
                    if login_user(username, password):
                        st.success("Logged in!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials")
        else:
            with st.form("signup_form"):
                new_user = st.text_input("Choose Username")
                new_pass = st.text_input("Password", type="password")
                company = st.text_input("Company (optional)")
                submitted = st.form_submit_button("Sign Up", use_container_width=True)
                if submitted:
                    if signup_user(new_user, new_pass, company):
                        st.success("Account created! Logging in...")
                        st.rerun()
                    else:
                        st.error("Username already exists")

        # API Key fallback for local testing
        st.divider()
        st.markdown("**OpenAI API Key** (for local use)")
        api_key_input = st.text_input("Enter Key", type="password", key="api_key")
        if api_key_input:
            st.session_state["api_key"] = api_key_input
    else:
        user = get_current_user()
        st.success(f"Welcome, **{user['username']}**")
        st.caption(f"Company: {user.get('company_name', 'N/A')}")
        if st.button("Logout", use_container_width=True):
            logout_user()
            st.rerun()

# ---------- Main App (when logged in) ----------
if is_logged_in():
    user = get_current_user()
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 Dashboard", "🧠 Bot Builder", "💬 Live Playground", "🔌 Integrations"]
    )

    # ------------------ Dashboard ------------------
    with tab1:
        st.header("Dashboard")
        col1, col2, col3, col4 = st.columns(4)
        total_chats = sum(len(st.session_state["chat_histories"].get(bot["id"], [])) for bot in get_user_bots(user["id"]))
        col1.metric("Total Chats", total_chats)
        col2.metric("Active Bots", get_total_bots(user["id"]))
        col3.metric("API Cost (est.)", "—")
        col4.metric("Webhooks", "1 active" if st.session_state.get("webhook_urls") else "0")

        st.subheader("Your Bots")
        bots = get_user_bots(user["id"])
        if bots:
            for bot in bots:
                st.write(f"**{bot['bot_name']}** – Status: {bot['status']}")
        else:
            st.info("No bots yet. Head to the Bot Builder!")

    # ------------------ Bot Builder ------------------
    with tab2:
        st.header("Create & Train a Support Bot")
        with st.form("bot_form"):
            bot_name = st.text_input("Bot Name", placeholder="e.g., ShopAssist Pro")
            system_prompt = st.text_area(
                "System Persona",
                value="You are a helpful and friendly customer support agent. Answer questions clearly and concisely.",
                height=120
            )
            welcome_msg = st.text_input("Welcome Message", value="Hello! How can I help you today?")
            uploaded_files = st.file_uploader(
                "Upload knowledge base (PDF/TXT)",
                type=["pdf", "txt"],
                accept_multiple_files=True
            )
            train_submitted = st.form_submit_button("🚀 Train Bot")
            if train_submitted:
                if not bot_name:
                    st.error("Please enter a bot name.")
                else:
                    with st.spinner("Creating bot and training..."):
                        # Create bot record
                        bot_id = create_bot(user["id"], bot_name, system_prompt, welcome_msg)
                        if uploaded_files:
                            success = train_bot(bot_id, uploaded_files, system_prompt)
                            if success:
                                st.success(f"Bot '{bot_name}' trained and activated!")
                            else:
                                st.warning("Bot created, but no documents were processed.")
                        else:
                            st.warning("Bot created without a knowledge base. Add documents to activate.")
                        st.rerun()

    # ------------------ Live Playground ------------------
    with tab3:
        st.header("Chat with Your Bot")
        bots = get_user_bots(user["id"])
        if not bots:
            st.warning("You need at least one trained bot. Go to Bot Builder.")
        else:
            # Bot selector
            bot_options = {bot["bot_name"]: bot["id"] for bot in bots}
            selected_bot_name = st.selectbox("Select Bot", list(bot_options.keys()))
            bot_id = bot_options[selected_bot_name]
            bot = get_bot(bot_id)

            if bot["status"] != "active":
                st.warning("This bot hasn't been trained yet. Please add documents in Bot Builder.")
            else:
                # Initialize chat history for this bot
                if bot_id not in st.session_state["chat_histories"]:
                    st.session_state["chat_histories"][bot_id] = []

                # Display chat messages
                for msg in st.session_state["chat_histories"][bot_id]:
                    if msg["role"] == "user":
                        st.markdown(f'<div class="chat-bubble user-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
                    else:
                        st.markdown(f'<div class="chat-bubble bot-bubble">{msg["content"]}</div>', unsafe_allow_html=True)

                # Chat input
                user_query = st.chat_input("Type your message...")
                if user_query:
                    # Add user message
                    st.session_state["chat_histories"][bot_id].append({"role": "user", "content": user_query})
                    # Get response
                    with st.spinner("Thinking..."):
                        api_key = get_openai_api_key()
                        vector_store = load_vector_store(bot_id, api_key)
                        if not vector_store:
                            st.error("Vector store not found. Please retrain the bot.")
                        else:
                            chain = get_conversation_chain(vector_store, bot["system_prompt"], api_key)
                            # Convert chat history to LangChain format
                            chat_history = [
                                (m["content"], next_msg["content"])
                                for m, next_msg in zip(
                                    st.session_state["chat_histories"][bot_id][::2],
                                    st.session_state["chat_histories"][bot_id][1::2]
                                ) if m["role"] == "user" and next_msg["role"] == "assistant"
                            ]
                            # Actually, memory is handled internally, but we can pass an empty list
                            result = chain.invoke({"question": user_query})
                            answer = result["answer"]
                            # Add assistant response
                            st.session_state["chat_histories"][bot_id].append({"role": "assistant", "content": answer})
                    st.rerun()

    # ------------------ Integration Panel ------------------
    with tab4:
        st.header("Integration & Webhooks")
        simulator = IntegrationSimulator()

        if not bots:
            st.warning("Create a bot first.")
        else:
            bot_names = [bot["bot_name"] for bot in bots]
            selected_bot = st.selectbox("Select Bot for Integration", bot_names, key="int_bot")
            bot_id = next(b["id"] for b in bots if b["bot_name"] == selected_bot)

            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.subheader("Webhook Endpoint")
                if st.button("Generate Webhook URL"):
                    url = simulator.generate_webhook_url(bot_id)
                    st.code(url, language="text")
                else:
                    if bot_id in st.session_state.get("webhook_urls", {}):
                        st.code(st.session_state["webhook_urls"][bot_id])
                    else:
                        st.info("Click to generate a unique webhook URL.")

            with col_b:
                st.subheader("Auto-Order Booking")
                auto_order = st.toggle("Enable Auto-Order", value=False)
                if auto_order:
                    st.success("Auto-order logic simulated.")

            st.divider()
            st.subheader("Simulate Incoming Message")
            with st.form("sim_form"):
                col1, col2 = st.columns(2)
                with col1:
                    sender = st.text_input("Sender", "customer@example.com")
                    message = st.text_area("Message", "I want to return my order #12345.")
                with col2:
                    st.markdown("**Optional JSON Payload**")
                    extra_json = st.text_area("Extra Data (JSON)", '{"order_id": "12345"}', height=100)
                submitted = st.form_submit_button("Send Test Webhook")
                if submitted:
                    try:
                        payload = {
                            "sender": sender,
                            "message": message,
                            "extra": json.loads(extra_json) if extra_json else {}
                        }
                    except json.JSONDecodeError:
                        st.error("Invalid JSON")
                        payload = {"sender": sender, "message": message}
                    response = simulator.simulate_incoming_message(bot_id, payload)
                    st.json(response)

            st.subheader("Webhook Logs")
            logs = simulator.get_logs()
            if logs:
                for log in reversed(logs):
                    st.code(log, language="json")
            else:
                st.caption("No incoming messages yet.")
else:
    st.info("Please log in or sign up to access the dashboard.")
