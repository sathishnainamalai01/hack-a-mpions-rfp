import streamlit as st
from google import genai
import pandas as pd
import json
import os
import time
import random

# --- 1. PERSISTENCE & UI SETUP ---
st.set_page_config(page_title="Hack-A-Mpions Auditor", layout="wide", page_icon="🏆")

if 'rfp_master_data' not in st.session_state:
    st.session_state.rfp_master_data = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'cooldown_until' not in st.session_state:
    st.session_state.cooldown_until = 0

# --- 2. SIDEBAR (STATUS INDICATOR) ---
with st.sidebar:
    st.markdown("## 🏆 Hack-A-Mpions")
    
    # LIVE STATUS INDICATOR
    current_time = time.time()
    if current_time < st.session_state.cooldown_until:
        remaining = int(st.session_state.cooldown_until - current_time)
        st.error(f"🔴 API STATUS: COOLING DOWN ({remaining}s)")
        st.caption("Please wait for the timer to hit 0 before processing.")
    else:
        st.success("🟢 API STATUS: READY")
        st.caption("Ready for next RFP extraction.")

    st.divider()
    api_key = st.text_input("Gemini API Key", type="password")
    
    if st.button("🗑️ Reset App & Clear Memory"):
        st.session_state.rfp_master_data = []
        st.session_state.chat_history = []
        st.session_state.cooldown_until = 0
        st.rerun()

# --- 3. THE SAFE EXTRACTION ENGINE ---
def safe_google_call(client, model, contents):
    for attempt in range(3):
        try:
            return client.models.generate_content(model=model, contents=contents)
        except Exception as e:
            if "429" in str(e):
                # Set the sidebar to RED for 60 seconds
                st.session_state.cooldown_until = time.time() + 60
                st.warning(f"⚠️ Limit hit. Locking UI for 60s cooldown...")
                time.sleep(60)
                return None # Stop current loop to prevent "poking the bear"
            else:
                st.error(f"Error: {e}")
                return None
    return None

# --- 4. MAIN INTERFACE ---
st.title("📄 RFP Deep Condition Extractor")

if api_key:
    client = genai.Client(api_key=api_key)
    MODEL_ID = "gemini-2.0-flash-lite"

    files = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

    # Disable button if cooling down
    btn_disabled = time.time() < st.session_state.cooldown_until
    
    if files and st.button("🚀 Run Deep Extraction", disabled=btn_disabled):
        new_results = []
        for f in files:
            with st.status(f"Analyzing {f.name}...") as status:
                t_path = f"temp_{f.name}"
                with open(t_path, "wb") as tmp: tmp.write(f.getbuffer())
                
                g_file = client.files.upload(file=t_path)
                while g_file.state == "PROCESSING":
                    time.sleep(2)
                    g_file = client.files.get(name=g_file.name)
                
                prompt = """
                Extract these 8 conditions as JSON:
                1. Customer Name, 2. Tender ID, 3. EMD Amount/Mode, 
                4. Min Turnover, 5. Technical Eligibility, 6. Bid Validity, 
                7. PBG %, 8. Penalty Summary.
                """
                
                response = safe_google_call(client, MODEL_ID, [g_file, prompt])
                
                if response:
                    try:
                        raw_text = response.text.replace('```json', '').replace('```', '').strip()
                        data = json.loads(raw_text)
                        data['Filename'] = f.name
                        new_results.append(data)
                        status.update(label=f"✅ {f.name} Completed", state="complete")
                    except:
                        st.error(f"JSON Error in {f.name}")
                
                os.remove(t_path)
                # Hard 6-second pause between files for local stability
                time.sleep(6)
        
        st.session_state.rfp_master_data.extend(new_results)
        st.rerun() # Refresh to show green status

# --- 5. DATA TABLE OUTPUT ---
if st.session_state.rfp_master_data:
    st.divider()
    st.subheader("📊 Extracted RFP Conditions")
    df = pd.DataFrame(st.session_state.rfp_master_data)
    cols = ['Filename'] + [c for c in df.columns if c != 'Filename']
    st.dataframe(df[cols], use_container_width=True)

    # --- 6. CHAT BOX ---
    st.divider()
    st.subheader("💬 Chat with your RFPs")
    
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])

    if user_query := st.chat_input("Ask about the extracted table..."):
        st.session_state.chat_history.append({"role": "user", "content": user_query})
        with st.chat_message("user"): st.markdown(user_query)

        with st.chat_message("assistant"):
            context = f"Data: {df.to_string()}"
            res = client.models.generate_content(model=MODEL_ID, contents=[context, user_query])
            st.markdown(res.text)
            st.session_state.chat_history.append({"role": "assistant", "content": res.text})
