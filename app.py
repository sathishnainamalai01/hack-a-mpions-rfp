import streamlit as st
from google import genai
import os
import time

# --- 1. MEMORY SETUP ---
st.set_page_config(page_title="RFP Chat Auditor", layout="centered", page_icon="💬")

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'uploaded_file_ids' not in st.session_state:
    st.session_state.uploaded_file_ids = []

# --- 2. SIDEBAR ---
with st.sidebar:
    st.title("🏆 Hack-A-Mpions")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    if st.button("🗑️ Clear Chat & Files"):
        st.session_state.chat_history = []
        st.session_state.uploaded_file_ids = []
        st.rerun()
    
    if st.session_state.uploaded_file_ids:
        st.success(f"📂 {len(st.session_state.uploaded_file_ids)} Files Loaded")

# --- 3. UPLOAD SECTION ---
st.title("💬 Chat with your RFPs")
st.caption("Upload your PDFs first, then ask questions below.")

if api_key:
    client = genai.Client(api_key=api_key)
    MODEL_ID = "gemini-2.0-flash-lite"

    uploaded_pdfs = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

    if uploaded_pdfs and st.button("📥 Load Documents into Chat"):
        for f in uploaded_pdfs:
            with st.spinner(f"Reading {f.name}..."):
                t_path = f"temp_{f.name}"
                with open(t_path, "wb") as tmp: tmp.write(f.getbuffer())
                
                # Upload to Google AI's permanent session memory
                g_file = client.files.upload(file=t_path)
                while g_file.state == "PROCESSING":
                    time.sleep(1)
                    g_file = client.files.get(name=g_file.name)
                
                st.session_state.uploaded_file_ids.append(g_file)
                os.remove(t_path)
        
        st.success("Documents Loaded! You can now chat with them below.")

# --- 4. THE CHAT INTERFACE ---
if st.session_state.uploaded_file_ids:
    st.divider()
    
    # Display message history
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    # Chat Input Box
    if user_query := st.chat_input("Ex: What is the EMD and Turnover required in these files?"):
        # 1. Show user message
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"):
            st.markdown(user_query)

        # 2. Generate AI response using the uploaded files as context
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                # We send all uploaded files + the user question
                content_payload = st.session_state.uploaded_file_ids + [user_query]
                
                try:
                    response = client.models.generate_content(
                        model=MODEL_ID, 
                        contents=content_payload
                    )
                    st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Error: {e}")
else:
    st.info("Upload and 'Load' your documents to start the conversation.")
