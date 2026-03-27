import streamlit as st
from google import genai
import pandas as pd
import json
import os
import time

# --- 1. GLOBAL SETTINGS & MEMORY ---
st.set_page_config(page_title="RFP Master Auditor", layout="wide", page_icon="🏆")

# Initialize memory stores
if 'rfp_data' not in st.session_state:
    st.session_state.rfp_data = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- 2. SIDEBAR ---
with st.sidebar:
    st.title("🏆 Hack-A-Mpions")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    if st.button("🗑️ Wipe All Data"):
        st.session_state.rfp_data = []
        st.session_state.chat_history = []
        st.rerun()

# --- 3. EXTRACTION LOGIC ---
st.title("📄 RFP Deep Condition Extractor")

if api_key:
    client = genai.Client(api_key=api_key)
    MODEL_ID = "gemini-2.0-flash-lite"

    files = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

    if files and st.button("🚀 Start Analysis"):
        for f in files:
            with st.status(f"Scanning {f.name}...") as status:
                t_path = f"temp_{f.name}"
                with open(t_path, "wb") as tmp: tmp.write(f.getbuffer())
                
                g_file = client.files.upload(file=t_path)
                while g_file.state == "PROCESSING":
                    time.sleep(2)
                    g_file = client.files.get(name=g_file.name)
                
                prompt = """
                Extract these 8 conditions as a JSON object: 
                Customer, Tender_ID, EMD_Amount, Min_Turnover, 
                Eligibility_Criteria, Bid_Validity, PBG_Percent, Penalty_Summary.
                """
                
                try:
                    response = client.models.generate_content(model=MODEL_ID, contents=[g_file, prompt])
                    # FAIL-SAFE: If JSON fails, we still save the raw text
                    clean_text = response.text.replace('```json', '').replace('```', '').strip()
                    try:
                        data = json.loads(clean_text)
                    except:
                        data = {"Raw_Output": clean_text} # Fallback if JSON is broken
                    
                    data['Filename'] = f.name
                    st.session_state.rfp_data.append(data)
                    status.update(label=f"✅ {f.name} Extracted", state="complete")
                except Exception as e:
                    st.error(f"Critical Error: {e}")
                
                os.remove(t_path)
                time.sleep(5) 
        
        st.rerun() # Force UI Update

# --- 4. THE OUTPUT (LOCKED OUTSIDE THE BUTTON) ---
# If this block is not showing, check your requirements.txt for 'pandas'
if st.session_state.rfp_data:
    st.divider()
    st.subheader("📊 Extracted Data")
    
    df = pd.DataFrame(st.session_state.rfp_data)
    # Ensure it displays as a table
    st.table(df) # Using st.table instead of st.dataframe for better cloud visibility

    # --- 5. THE CHAT BOX ---
    st.divider()
    st.subheader("💬 Analysis Chat")
    
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    if user_q := st.chat_input("Ask a question..."):
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.chat_message("user"): st.markdown(user_q)

        with st.chat_message("assistant"):
            context = f"Table Data: {df.to_string()}"
            chat_res = client.models.generate_content(model=MODEL_ID, contents=[context, user_q])
            st.markdown(chat_res.text)
            st.session_state.chat_history.append({"role": "assistant", "content": chat_res.text})
