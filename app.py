import streamlit as st
from google import genai
import pandas as pd
import json
import os
import time

# --- 1. GLOBAL SETTINGS & MEMORY ---
st.set_page_config(page_title="RFP Master Auditor", layout="wide", page_icon="🏆")

# These keys ensure your data survives script reruns
if 'rfp_data' not in st.session_state:
    st.session_state.rfp_data = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# --- 2. SIDEBAR (STATUS & API) ---
with st.sidebar:
    st.markdown("## ⚙️ Control Center")
    api_key = st.text_input("Gemini API Key", type="password")
    
    st.divider()
    if st.button("🗑️ Wipe All Data"):
        st.session_state.rfp_data = []
        st.session_state.chat_history = []
        st.rerun()
    
    if st.session_state.rfp_data:
        st.success(f"Files in Memory: {len(st.session_state.rfp_data)}")

# --- 3. EXTRACTION LOGIC (INPUT) ---
st.title("📄 RFP Deep Condition Extractor")

if api_key:
    client = genai.Client(api_key=api_key)
    MODEL_ID = "gemini-2.0-flash-lite"

    files = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

    if files and st.button("🚀 Start Deep Analysis"):
        temp_batch = []
        for f in files:
            with st.status(f"Scanning {f.name}...") as status:
                # Save to temporary cloud storage
                t_path = f"temp_{f.name}"
                with open(t_path, "wb") as tmp: tmp.write(f.getbuffer())
                
                # Upload to Google AI
                g_file = client.files.upload(file=t_path)
                while g_file.state == "PROCESSING":
                    time.sleep(2)
                    g_file = client.files.get(name=g_file.name)
                
                # THE 8 KEY CONDITIONS PROMPT
                prompt = """
                Return ONLY a JSON object with these keys: 
                Customer, Tender_ID, EMD_Amount, Min_Turnover, 
                Eligibility_Criteria, Bid_Validity, PBG_Percent, Penalty_Summary.
                """
                
                try:
                    response = client.models.generate_content(model=MODEL_ID, contents=[g_file, prompt])
                    # Strip markdown and parse JSON
                    clean_text = response.text.replace('```json', '').replace('```', '').strip()
                    data = json.loads(clean_text)
                    data['Filename'] = f.name
                    temp_batch.append(data)
                    status.update(label=f"✅ {f.name} Extracted", state="complete")
                except Exception as e:
                    st.error(f"Error in {f.name}: {e}")
                
                os.remove(t_path)
                time.sleep(5) # Crucial 5s gap for Free Tier
        
        # Save to permanent session state
        st.session_state.rfp_data.extend(temp_batch)
        st.rerun() # Force UI to show the table immediately

# --- 4. THE OUTPUT (ALWAYS VISIBLE IF DATA EXISTS) ---
if st.session_state.rfp_data:
    st.divider()
    st.subheader("📊 Extracted RFP Conditions Table")
    
    # Create and Display Table
    df = pd.DataFrame(st.session_state.rfp_data)
    # Ensure Filename is the first column for clarity
    cols = ['Filename'] + [c for c in df.columns if c != 'Filename']
    st.dataframe(df[cols], use_container_width=True)

    # --- 5. THE CHAT BOX (ALWAYS AT THE BOTTOM) ---
    st.divider()
    st.subheader("💬 RFP Intelligent Chat")
    st.caption("The AI knows about the table above. Ask anything!")
    
    # Show previous chat messages
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    # Chat Input
    if user_q := st.chat_input("Ask a question about these RFPs..."):
        st.session_state.chat_history.append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)

        with st.chat_message("assistant"):
            # Provide the table context to the AI
            table_context = df.to_string()
            full_prompt = f"Data: {table_context}\n\nUser Question: {user_q}"
            
            chat_res = client.models.generate_content(model=MODEL_ID, contents=[full_prompt])
            st.markdown(chat_res.text)
            st.session_state.chat_history.append({"role": "assistant", "content": chat_res.text})
