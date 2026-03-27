import streamlit as st
from google import genai
import pandas as pd
import json
import os
import time

# --- 1. CLOUD STORAGE (SESSION STATE) ---
st.set_page_config(page_title="RFP Master Auditor", layout="wide", page_icon="🏆")

# These variables stay in the app's memory even when the page reruns
if 'master_table' not in st.session_state:
    st.session_state.master_table = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- 2. SIDEBAR CONTROLS ---
with st.sidebar:
    st.title("🏆 Hack-A-Mpions")
    st.info("v2026.8 - Cloud Stable")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    if st.button("🗑️ Clear All Memory"):
        st.session_state.master_table = []
        st.session_state.chat_history = []
        st.rerun()

# --- 3. EXTRACTION INTERFACE ---
st.title("📄 RFP Deep Condition Extractor")

if api_key:
    client = genai.Client(api_key=api_key)
    MODEL_ID = "gemini-2.0-flash-lite"

    files = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

    if files and st.button("🚀 Start Analysis"):
        for f in files:
            with st.status(f"Processing {f.name}...") as status:
                t_path = f"temp_{f.name}"
                with open(t_path, "wb") as tmp: tmp.write(f.getbuffer())
                
                # Upload to Google
                g_file = client.files.upload(file=t_path)
                while g_file.state == "PROCESSING":
                    time.sleep(2)
                    g_file = client.files.get(name=g_file.name)
                
                # THE 8 CONDITIONS PROMPT
                prompt = """
                Extract the following as a JSON object:
                Customer, Tender_ID, EMD_Details, Min_Turnover, 
                Eligibility_Criteria, Bid_Validity, PBG_Percent, Penalty_Summary.
                """
                
                try:
                    response = client.models.generate_content(model=MODEL_ID, contents=[g_file, prompt])
                    # Clean and Parse JSON
                    raw_json = response.text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(raw_json)
                    data['Source_File'] = f.name
                    
                    # SAVE TO MASTER MEMORY
                    st.session_state.master_table.append(data)
                    status.update(label=f"✅ {f.name} Ready", state="complete")
                except Exception as e:
                    st.error(f"Failed to extract {f.name}. Error: {e}")
                
                os.remove(t_path)
                time.sleep(5) # Rate limit gap
        
        # After loop, force a rerun to refresh the UI and show the table
        st.rerun()

# --- 4. THE OUTPUT AREA (STAYS VISIBLE) ---
# This block is OUTSIDE the button logic so it never disappears
if st.session_state.master_table:
    st.divider()
    st.subheader("📊 Extracted RFP Table")
    
    # Create the DataFrame
    df = pd.DataFrame(st.session_state.master_table)
    
    # Display using st.table for guaranteed visibility
    st.table(df)

    # --- 5. CHAT BOX (PERSISTENT) ---
    st.divider()
    st.subheader("💬 Chat Analysis")
    
    # Render existing chat
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    # Chat input
    if user_q := st.chat_input("Ask a question about the table..."):
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.chat_message("user"): st.markdown(user_q)

        with st.chat_message("assistant"):
            # Provide the table context to the AI
            table_context = df.to_string()
            chat_res = client.models.generate_content(model=MODEL_ID, contents=[table_context, user_q])
            st.markdown(chat_res.text)
            st.session_state.chat_history.append({"role": "assistant", "content": chat_res.text})
