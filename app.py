import streamlit as st
import pdfplumber
from groq import Groq
from duckduckgo_search import DDGS
import json

# Setup direct search engine wrapper (Bypasses the Python 3.14 LangChain bug)
def direct_web_search(query_text):
    try:
        with DDGS() as ddgs:
            results = [r['body'] for r in ddgs.text(query_text, max_results=2)]
            return " ".join(results) if results else "No direct web tracking matches found."
    except Exception as e:
        return "Search temporary unavailable, assessing via primary base logic."

# Securely pull the Groq Brain Key from the cloud settings
if "GROQ_API_KEY" in st.secrets:
    api_key = st.secrets["GROQ_API_KEY"]
else:
    st.error("⚠️ Setup Error: Please add your GROQ_API_KEY inside Streamlit Advanced Settings!")
    st.stop()

client = Groq(api_key=api_key)

# Configure the visual layout of your dashboard website
st.set_page_config(page_title="Fact-Check Agent", page_icon="🛡️", layout="wide")
st.title("🛡️ Automated Fact-Checking Agent Dashboard")
st.caption("Upload a marketing or data PDF. The AI Agent will read it and check live search data to catch lies.")

# Create a visual drag-and-drop file uploader button
uploaded_file = st.file_uploader("Drop your PDF document here", type="pdf")

if uploaded_file is not None:
    # Layer 1: Read the PDF file
    with st.spinner("⏳ Step 1: Extracting raw text from document..."):
        with pdfplumber.open(uploaded_file) as pdf:
            raw_text = "".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            
    if not raw_text.strip():
        st.error("❌ This PDF has no readable text. Please try another one.")
    else:
        # Layer 2: Extract individual statistical data strings
        with st.spinner("🧠 Step 2: LLM Brain is locating data claims..."):
            extraction_prompt = f"""
            Extract up to 3 major statistical, financial, or dated claims from this text.
            Return ONLY a valid, raw JSON array of strings. No conversational descriptions.
            Text: {raw_text[:3000]}
            """
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.1
            )
            try:
                claims = json.loads(completion.choices[0].message.content.strip())
            except:
                claims = [line.strip() for line in completion.choices[0].message.content.split("\n") if line.strip()][:3]

        st.subheader("📊 Automated Verification Audit Report")
        
        # Layer 3 & 4: Route claims to the live search tool and display visual results
        for claim in claims:
            if not claim: 
                continue
            with st.spinner(f"🔍 Searching live web for: '{claim}'..."):
                web_info = direct_web_search(claim)
                
                verification_prompt = f"""
                Compare the PDF Claim against the Live Web Info.
                Claim: {claim}
                Live Web Info: {web_info}
                
                Provide a structured report starting with either VERDICT: VERIFIED, VERDICT: INACCURATE, or VERDICT: FALSE. 
                Follow up with a brief 'REAL FACTS' section outlining the true historical data.
                """
                verdict_comp = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": verification_prompt}],
                    temperature=0.1
                )
                
                # Render results dynamically inside drop-down containers
                with st.expander(f"📋 Evaluated Statement: {claim}", expanded=True):
                    response_text = verdict_comp.choices[0].message.content
                    if "VERIFIED" in response_text.upper():
                        st.success("🟢 Verified Success")
                    elif "INACCURATE" in response_text.upper():
                        st.warning("🟡 Outdated or Inaccurate Info")
                    else:
                        st.error("🔴 False Statement Caught")
                    st.write(response_text)
                    
        st.success("🎉 Full Automated Analysis Complete!")
