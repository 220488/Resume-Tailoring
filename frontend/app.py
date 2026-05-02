"""
Person 6 — Frontend / Prototype Integration & Testing

Streamlit UI:
- Accepts two inputs: job description text and resume PDF upload
- Calls the FastAPI backend at /analyze
- Displays the tailored resume and intermediate analysis outputs
- Supports complete tailored resume preview when full resume text is returned
- Allows users to view key modifications and export results in PDF, text, or JSON format
"""

import json
import requests
import streamlit as st

API_URL = "http://localhost:8000"

# Page config 
st.set_page_config(
    page_title="Resume Tailoring Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Session state initialization
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "show_modifications" not in st.session_state:
    st.session_state.show_modifications = False

# Light styling

st.markdown("""
<style>
.block-container {
    padding-top: 0.8rem;
    padding-bottom: 1.2rem;
    max-width: 1180px;
}
h1, h2, h3 {
    letter-spacing: -0.02em;
}
[data-testid="stTextArea"] textarea {
    border-radius: 14px;
}
[data-testid="stFileUploader"] {
    border-radius: 14px;
}
.stButton > button {
    border-radius: 14px;
    height: 3rem;
    font-weight: 600;
}
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    padding: 14px 16px;
    border-radius: 16px;
}
[data-testid="stMetricValue"] {
    font-size: 2rem;
}
div[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid #e5e7eb !important;
}
button[kind="secondary"] {
    border-radius: 12px !important;
}
</style>
""", unsafe_allow_html=True)

# Header 
st.markdown("""
<div style="
    padding: 1.1rem 1.4rem;
    border-radius: 20px;
    background: linear-gradient(135deg, #eef2ff 0%, #ecfeff 100%);
    border: 1px solid rgba(0,0,0,0.06);
    margin-bottom: 1rem;
">
    <h1 style="margin: 0; font-size: 2.1rem; line-height: 1.05;">AI Resume Tailoring Assistant</h1>
    <p style="margin: 0.45rem 0 0 0; font-size: 0.98rem; color: #4b5563;">
        Match your existing resume to a target role with structured analysis and controlled AI rewriting.
    </p>
</div>
""", unsafe_allow_html=True)

with st.expander("How to Use", expanded=False):
    st.markdown("""
1. Paste a target job description or choose a sample role  
2. Upload your existing resume in PDF format  
3. Click **Tailor My Resume**  
4. Review the matched, missing, and weakly expressed items  
5. Check the revised summary, reordered skills, and rewritten bullet points
""")

# Sample JDs 

sample_jds = {
    "Graduate Data Analyst": """
We are looking for a Graduate Data Analyst to support data-driven decision making across the business.
You will analyse structured datasets, build dashboards, generate reports, and communicate insights to stakeholders.

Required skills:
- Python
- SQL
- Data analysis
- Data visualisation
- Communication skills

Preferred skills:
- Tableau or Power BI
- Excel
- Dashboard development
- Experience with business reporting

Qualifications:
- Bachelor or Master degree in data analytics, commerce, statistics, information systems, or related field
- Internship, coursework, or project experience in analytics is desirable
""",

    "Junior Data Scientist": """
We are seeking a Junior Data Scientist to support predictive modelling and data-driven product decisions.
You will work with structured and unstructured data, develop machine learning solutions, and present findings clearly.

Required skills:
- Python
- SQL
- Machine learning
- Statistics
- Data preprocessing

Preferred skills:
- scikit-learn
- Pandas / NumPy
- Data visualisation
- Model evaluation
- Communication and teamwork

Qualifications:
- Bachelor or Master degree in data science, computer science, mathematics, or related field
- University projects or internship experience in machine learning is preferred
""",

    "BI / Analytics Intern": """
We are hiring a BI / Analytics Intern to assist with dashboard reporting, KPI tracking, and business insight generation.
You will support teams by cleaning data, producing reports, and identifying trends.

Required skills:
- SQL
- Excel
- Data analysis
- Reporting
- Attention to detail

Preferred skills:
- Tableau or Power BI
- Python
- Stakeholder communication
- Experience with dashboards

Qualifications:
- Current university student in analytics, business, information systems, or related discipline
- Prior project experience in reporting or dashboard work is a plus
""",

    "AI / ML Intern": """
We are looking for an AI / ML Intern to support model experimentation and intelligent document processing tasks.
You will help prepare data, test model outputs, evaluate performance, and document findings.

Required skills:
- Python
- Machine learning
- Data preprocessing
- Problem solving
- Communication

Preferred skills:
- NLP
- Deep learning
- PyTorch or TensorFlow
- Model evaluation
- Experience with LLM applications

Qualifications:
- Current university student in computer science, artificial intelligence, data science, or related field
- Coursework or project experience in AI / ML is desirable
"""
}

# Inputs

st.markdown("## Input")

col_left, col_right = st.columns(2)

with col_left:
    with st.container(border=True):
        st.markdown("### Target Job Description")

        input_mode = st.radio(
            "Choose JD input method",
            ["Paste text", "Use sample JD"],
            horizontal=True,
        )

        if input_mode == "Paste text":
            jd_text = st.text_area(
                label="Paste the full job description here",
                height=300,
                placeholder="Copy and paste the job posting...",
                label_visibility="collapsed",
            )
        else:
            selected_jd = st.selectbox(
                "Choose a sample JD",
                list(sample_jds.keys())
            )
            jd_text = sample_jds[selected_jd]
            st.text_area(
                "Sample JD Preview",
                value=jd_text,
                height=220,
                disabled=True
            )

with col_right:
    with st.container(border=True):
        st.markdown("### Upload Your Resume")
        resume_file = st.file_uploader(
            label="Upload your resume (PDF only)",
            type=["pdf"],
        )
        
        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        submitted = st.button(
            "Tailor My Resume",
            type="primary",
            use_container_width=True
        )

# Main action
if submitted:
    # Validation first
    if not jd_text.strip():
        st.error("Please enter or select a job description.")
        st.stop()

    if resume_file is None:
        st.error("Please upload your resume PDF.")
        st.stop()

    # Only reset after validation passes
    st.session_state.analysis_result = None
    st.session_state.show_modifications = False

    with st.spinner("Analysing your resume against the job description…"):
        try:
            response = requests.post(
                f"{API_URL}/analyze",
                data={"jd_text": jd_text},
                files={
                    "resume_pdf": (
                        resume_file.name,
                        resume_file.getvalue(),
                        "application/pdf",
                    )
                },
                timeout=300,
            )
            response.raise_for_status()
            st.session_state.analysis_result = response.json()
            st.switch_page("pages/1_Results.py")

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the backend. Make sure the FastAPI server is running on port 8000.")
            st.stop()

        except requests.exceptions.HTTPError as e:
            try:
                detail = response.json().get("detail", str(e))
            except Exception:
                detail = str(e)
            st.error(f"Backend error: {detail}")
            st.stop()

        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()
