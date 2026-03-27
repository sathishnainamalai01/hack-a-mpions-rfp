import streamlit as st
from google import genai
import pandas as pd
import json
import os
import time
import random

# --- 1. PAGE SETTINGS ---
st.set_page_config(
    page_title="Hack-A-Mpions Auditor",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. SESSION STATE (The "Memory" that keeps output visible) ---
if 'rfp_data_list' not in st.session_state:
    st.session_state.rfp_data_list = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'processing_done' not in st.session_state:
    st.session_state.processing_done = False

# --- 3. SIDEBAR BRANDING & API KEY ---
with st.sidebar:
    st.markdown("""
        <div style='text-align: center;'>
            <h1 style='color: #FF4B4B; margin-bottom: 0;'>🏆 Hack-A-Mpions</h1>
            <p style='color: gray; font-size: 14px;'>RFP Intelligence Hub v2026.6</p>
        </div>
        <hr>
    """, unsafe_allow_html=True)
    
    user_api_key = st.text_input("Gemini API Key", type="password", help="Enter your key from Google AI Studio")
    
    st.divider()
    if st.button("🗑️ Reset All Data"):
        st.session_state.rfp_data_list = []
        st.session_state.chat_history = []
        st.session_state.processing_done = False
        st.rerun()

# --- 4. EXTRACTION LOGIC (The "Engine") ---
st.title("📄 RFP Deep Condition Extractor")
st.info("Upload your RFP PDFs below. The AI will extract EMD, PBG, Turnover, and more.")

if not user_api_key:
    st.warning("👈 Please enter your Gemini API Key in the sidebar to start.")
else:
    client = genai.Client(api_key=user_api_key)
    MODEL_ID = "gemini-2.0-flash-lite"

    uploaded_files = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

    if uploaded_files and st.button("🚀 Run Deep Extraction"):
        st.session_state.rfp_data_list = [] # Clear old data for new run
        
        for file in uploaded_files:
            with st.status(f"Analysing {file.name}...") as status:
                # Temporary file handling
                temp_name = f"temp_{file.name}"
                with open(temp_name, "wb") as f:
                    f.write(file.getbuffer())
                
                # Upload to Google Cloud (Gemini)
                g_file = client.files.upload(file=temp_name)
                while g_file.state == "PROCESSING":
                    time.sleep(2)
                    g_file = client.files.get(name=g_file.name)
                
                # THE 8 CONDITIONS PROMPT
                prompt = """
                Extract these 8 conditions from the RFP and return ONLY a valid JSON object:
                1. Customer Name
                2. Tender ID
                3. EMD Amount & Mode
                4. Minimum Annual Turnover Required
                5. Technical Eligibility / Experience
                6. Bid Validity Period
                7. Performance Bank Guarantee (PBG) %
                8. Penalty / Liquidated Damages Summary
                """
                
                try:
                    # Exponential Backoff for Rate Limits (429 Error)
                    response = None
                    for attempt in range(3):
                        try:
                            response = client.models.generate_content(model=MODEL_ID, contents=[g_file, prompt])
                            break
                        except Exception as e:
                            if "429" in str(e):
                                wait_time = (attempt + 1) * 15
                                st.warning(f"Rate limit hit. Retrying in {wait_time}s...")
                                time.sleep(wait_time)
                            else: raise e
                    
                    if response:
                        # Clean JSON formatting
                        clean_json = response.text.replace('```json', '').replace('```', '').strip()
                        extracted_dict = json.loads(clean_json)
                        extracted_dict['Source File'] = file.name
                        st.session_state.rfp_data_list.append(extracted_dict)
                        status.update(label=f"✅ {file.name} Extracted", state="complete")
                
                except Exception as e:
                    st.error(f"Error processing {file.name}: {e}")
                
                finally:
                    os.remove(temp_name)
                    time.sleep(5) # Standard gap to avoid 429
        
        st.session_state.processing_done = True

# --- 5. OUTPUT DISPLAY (Table) ---
if st.session_state.rfp_data_list:
    st.divider()
    st.subheader("📋 Extracted RFP Conditions Table")
    
    df = pd.DataFrame(st.session_state.rfp_data_list)
    # Ensure 'Source File' is the first column
    cols = ['Source File'] + [c for c in df.columns if c != 'Source File']
    st.dataframe(df[cols], use_container_width=True)
    
    # Download Option
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Download Report (CSV)", csv, "RFP_Analysis.csv", "text/csv")

    # --- 6. CHAT BOX (Analysis) ---
    st.divider()
    st.subheader("💬 Hack-A-Mpions Intelligence Chat")
    st.caption("Ask specific questions or compare the extracted files.")

    # Show Chat History
    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    # Chat Input
    if user_input := st.chat_input("Ex: Which company has the strictest penalty clause?"):
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("AI is thinking..."):
                # We feed the table data into the AI so it can "read" the results
                context = f"Here is the RFP extraction table: {df.to_string()}"
                chat_response = client.models.generate_content(
                    model=MODEL_ID, 
                    contents=[context, user_input]
                )
                st.markdown(chat_response.text)
                st.session_state.chat_history.append({"role": "assistant", "content": chat_response.text})
