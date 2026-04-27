import streamlit as st
import httpx
import uuid
import json
import os
from datetime import datetime

# ── CONFIGURATION ──────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
APP_TITLE = "Conecta AI - Coaching Assistant"
APP_ICON = "🤖"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon=APP_ICON,
    layout="wide",
)

# ── CUSTOM STYLES ──────────────────────────────────
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stChatMessage {
        border-radius: 15px;
        padding: 10px;
        margin-bottom: 10px;
    }
    .stChatMessage.user {
        background-color: #e3f2fd;
    }
    .stChatMessage.assistant {
        background-color: #ffffff;
        border: 1px solid #dee2e6;
    }
    .source-tag {
        display: inline-block;
        background-color: #f1f3f5;
        color: #495057;
        font-size: 0.75rem;
        padding: 2px 8px;
        border-radius: 10px;
        margin-right: 5px;
        margin-bottom: 5px;
        border: 1px solid #ced4da;
    }
    </style>
    """, unsafe_allow_html=True)

# ── STATE MANAGEMENT ───────────────────────────────
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_id" not in st.session_state:
    st.session_state.user_id = "st-dev-user"

# ── SIDEBAR ────────────────────────────────────────
with st.sidebar:
    st.title(f"{APP_ICON} {APP_TITLE}")
    st.info("Agentic coaching platform powered by Abbott intelligence.")
    
    st.divider()
    
    st.subheader("Session Settings")
    st.session_state.user_id = st.text_input("User ID", value=st.session_state.user_id)
    st.caption("Using developer bypass mode.")
    
    current_session = st.text_input("Session ID", value=st.session_state.session_id)
    if current_session != st.session_state.session_id:
        st.session_state.session_id = current_session
        st.session_state.messages = []
        st.rerun()

    language = st.selectbox("Language", options=["en", "es", "pt", "fr", "de"], index=0)
    
    if st.button("Clear Chat History"):
        st.session_state.messages = []
        st.session_state.session_id = str(uuid.uuid4())
        st.rerun()

    st.divider()
    st.caption(f"Backend: {API_BASE_URL}")

# ── CHAT INTERFACE ─────────────────────────────────
st.title(f"Welcome back, {st.session_state.user_id}")

# Display existing messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("sources"):
            with st.expander("View Sources"):
                for source in msg["sources"]:
                    st.markdown(f"**{source.get('title', 'Document')}**")
                    st.caption(source.get("text", "")[:200] + "...")

# Chat Input
if prompt := st.chat_input("Ask me about coaching protocols, sales analytics, or regional performance..."):
    # Append user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call API
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        message_placeholder.markdown("*Thinking...*")
        
        try:
            # Use synchronous POST for simplicity in this version
            with httpx.Client(timeout=60.0) as client:
                headers = {
                    "X-Developer-Id": st.session_state.user_id,
                    "Content-Type": "application/json"
                }
                payload = {
                    "message": prompt,
                    "session_id": st.session_state.session_id,
                    "language": language
                }
                
                response = client.post(
                    f"{API_BASE_URL}/chat/",
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    full_response = data["message"]
                    sources = data.get("sources", [])
                    intent = data.get("intent", "general")
                    
                    # Display response
                    message_placeholder.markdown(full_response)
                    
                    if sources:
                        with st.expander("Referenced Sources"):
                            for s in sources:
                                st.write(f"- {s.get('document_name', 'Source')}: {s.get('text', '')[:150]}...")
                                
                    # Save to state
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": full_response,
                        "sources": sources,
                        "intent": intent
                    })
                else:
                    error_detail = response.json().get("detail", "Unknown error")
                    st.error(f"API Error ({response.status_code}): {error_detail}")
                    message_placeholder.markdown("Sorry, I encountered an error processing your request.")
                    
        except Exception as e:
            st.error(f"Connection Error: {str(e)}")
            message_placeholder.markdown("Could not connect to the backend server.")

# ── FOOTER ─────────────────────────────────────────
st.divider()
st.caption("Internal Use Only - Abbott Laboratories")
