import streamlit as st
from google import genai
import pandas as pd
import json
import os
import time

# --- 1. PAGE SETUP ---
st.set_page_config(
    page_title="Hack-A-Mpions RFP Hub", 
    layout="wide", 
    page_icon="🏆",
    initial_sidebar_state="expanded"
)

# --- 2. SESSION STATE (MEMORY) ---
if 'request_count' not in st.session_state: st.session_state.request_count = 0
if 'last_request_time' not in st.session_state: st.session_state.last_request_time = 0
if 'extracted_results' not in st.session_state: st.session_state.extracted_results = []
if 'gemini_files' not in st.session_state: st.session_state.gemini_files = []
if 'chat_history' not in st.session_state: st.session_state.chat_history = []

# --- 3. SIDEBAR BRANDING & MONITOR ---
with st.sidebar:
    st.markdown("""
        <div style='margin-top: -30px;'>
            <h1 style='color: #FF4B4B; font-size: 28px; font-family: sans-serif;'>🏆 Hack-A-Mpions</h1>
            <p style='font-size: 13px; color: gray; margin-top: -15px;'>RFP Intelligence Hub v2026.3</p>
        </div>
        <hr style="margin-top: 5px; margin-bottom: 20px;">
    """, unsafe_allow_html=True)
    
    api_key = st.text_input("Gemini API Key", type="password")
    
    # Quota Gauge
    daily_limit = 200
    usage_per = min(st.session_state.request_count / daily_limit, 1.0)
    st.write(f"Requests Used: **{st.session_state.request_count}** / {daily_limit}")
    st.progress(usage_per)
    
    if st.button("🗑️ Clear All Data & Chat"):
        st.session_state.request_count = 0
        st.session_state.extracted_results = []
        st.session_state.chat_history = []
        st.session_state.gemini_files = []
        st.rerun()

# --- 4. MAIN EXTRACTION LOGIC ---
st.title("📄 RFP Deep Extractor & Chat")

if api_key:
    try:
        client = genai.Client(api_key=api_key)
        MODEL_ID = "gemini-2.0-flash-lite" 

        uploaded_files = st.file_uploader("Upload RFP PDFs", type="pdf", accept_multiple_files=True)

        if uploaded_files:
            if st.button("🚀 Run Deep Extraction"):
                temp_results = []
                st.session_state.gemini_files = [] # Reset file context for new uploads
                
                for index, file in enumerate(uploaded_files):
                    # Rate Limit Protection
                    if time.time() - st.session_state.last_request_time < 6:
                        time.sleep(6) 

                    with st.status(f"Analyzing {file.name}...") as status:
                        temp_path = f"temp_{file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(file.getbuffer())
                        
                        g_file = client.files.upload(file=temp_path)
                        while g_file.state == "PROCESSING":
                            time.sleep(2)
                            g_file = client.files.get(name=g_file.name)
                        
                        st.session_state.gemini_files.append(g_file)
                        st.session_state.request_count += 1
                        st.session_state.last_request_time = time.time()

                        prompt = """
                        Extract from this RFP:
                        1. Customer Name, 2. Tender ID, 3. EMD Amount & Mode, 
                        4. Min Annual Turnover, 5. Tech Eligibility, 6. Bid Validity, 
                        7. PBG %, 8. Penalty Summary.
                        Return ONLY valid JSON.
                        """
                        
                        response = client.models.generate_content(model=MODEL_ID, contents=[g_file, prompt])
                        try:
                            data = json.loads(response.text.replace('```json', '').replace('```', '').strip())
                            data['Filename'] = file.name
                            temp_results.append(data)
                            status.update(label=f"✅ {file.name} Done", state="complete")
                        except:
                            st.error(f"Failed to parse {file.name}")
                        os.remove(temp_path)
                
                st.session_state.extracted_results = temp_results

        # --- 5. DISPLAY TABLE ---
        if st.session_state.extracted_results:
            st.divider()
            df = pd.DataFrame(st.session_state.extracted_results)
            st.dataframe(df, use_container_width=True)

        # --- 6. CHAT BOX (THE "MISSING" PART) ---
        st.divider()
        st.subheader("💬 Chat with Hack-A-Mpions AI")
        st.caption("Ask specific questions about the clauses or compare the uploaded documents.")

        # Show Chat History
        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.markdown(chat["content"])

        # Chat Input
        if user_query := st.chat_input("Ask about the RFPs (e.g., 'List all deadlines')"):
            st.session_state.chat_history.append({"role": "user", "content": user_query})
            with st.chat_message("user"):
                st.markdown(user_query)

            with st.chat_message("assistant"):
                if not st.session_state.gemini_files:
                    st.warning("Please upload and extract files first!")
                else:
                    with st.spinner("Analyzing documents..."):
                        # Send the user query along with ALL uploaded file contexts
                        chat_response = client.models.generate_content(
                            model=MODEL_ID,
                            contents=st.session_state.gemini_files + [user_query]
                        )
                        st.markdown(chat_response.text)
                        st.session_state.chat_history.append({"role": "assistant", "content": chat_response.text})

    except Exception as e:
        if "429" in str(e): st.error("🛑 Free Limit Reached. Wait 60s.")
        else: st.error(f"Error: {e}")
else:
    st.info("👈 Enter API Key in the sidebar to start.")