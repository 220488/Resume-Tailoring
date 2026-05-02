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
from fpdf import FPDF
import io

API_URL = "http://localhost:8000"


def generate_pdf(tailored_data=None, full_text=None):
    """Generate PDF from tailored resume data or full text"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Tailored Resume", ln=True, align="C")
    pdf.ln(10)
    
    if full_text:
        # Generate from full text
        pdf.set_font("Helvetica", "", 10)
        lines = full_text.split('\n')
        for line in lines:
            if line.strip():
                pdf.multi_cell(0, 5, line)
            else:
                pdf.ln(3)
    else:
        # Generate from structured data
        # Professional Summary
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Professional Summary", ln=True)
        pdf.set_font("Helvetica", "", 10)
        summary = tailored_data.get("professional_summary", "")
        pdf.multi_cell(0, 5, summary)
        pdf.ln(5)
        
        # Skills
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Skills", ln=True)
        pdf.set_font("Helvetica", "", 10)
        skills = tailored_data.get("reordered_skills", [])
        skills_text = " • ".join(skills) if skills else "—"
        pdf.multi_cell(0, 5, skills_text)
        pdf.ln(5)
        
        # Updated Achievements
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Updated Achievements", ln=True)
        pdf.set_font("Helvetica", "", 10)
        bullets = tailored_data.get("rewritten_bullets", [])
        for i, bullet in enumerate(bullets, 1):
            revised = bullet.get("revised", "")
            if revised.strip():
                pdf.multi_cell(0, 5, f"{i}. {revised}")
    
    pdf_bytes = io.BytesIO()
    pdf_output = pdf.output()
    pdf_bytes.write(pdf_output)
    pdf_bytes.seek(0)
    return pdf_bytes.getvalue()


# Page config 
st.set_page_config(
    page_title="Resume Tailoring Assistant",
    page_icon="📄",
    layout="wide",
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
    padding-top: 2rem;
    padding-bottom: 2rem;
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
    height: 3.2rem;
    font-weight: 600;
}
[data-testid="stMetricValue"] {
    font-size: 2rem;
}
</style>
""", unsafe_allow_html=True)

# Header 
st.markdown("""
<div style="
    padding: 1.2rem 1.4rem;
    border-radius: 18px;
    background: linear-gradient(135deg, rgba(99,102,241,0.15), rgba(16,185,129,0.10));
    margin-bottom: 1.2rem;
">
    <h1 style="margin-bottom: 0.3rem;">AI Resume Tailoring Assistant</h1>
    <p style="margin: 0; opacity: 0.9;">
        Match your existing resume to a target role with structured analysis and controlled AI rewriting.
    </p>
</div>
""", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("### How to Use")
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
                height=300,
                disabled=True
            )

with col_right:
    with st.container(border=True):
        st.markdown("### Upload Your Resume")
        resume_file = st.file_uploader(
            label="Upload your resume (PDF only)",
            type=["pdf"],
        )

st.divider()

submitted = st.button("Tailor My Resume", type="primary", use_container_width=True)

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
    
if st.session_state.analysis_result:
    result = st.session_state.analysis_result
    st.success("Done! See your tailored resume below.")

    # Summary metrics preview
    raw_alignment = result.get("alignment", "{}")
    alignment_preview = {}

    try:
        alignment_preview = json.loads(raw_alignment)
    except json.JSONDecodeError:
        alignment_preview = {}

    matched_preview = alignment_preview.get("matched", [])
    missing_preview = alignment_preview.get("missing", [])
    weak_preview = alignment_preview.get("weak_matches", [])

    total_items = len(matched_preview) + len(missing_preview) + len(weak_preview)
    fit_score = round(((len(matched_preview) + 0.5 * len(weak_preview)) / total_items) * 100) if total_items > 0 else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Overall Fit", f"{fit_score}%")
    m2.metric("Matched", len(matched_preview))
    m3.metric("Missing", len(missing_preview))
    m4.metric("Weak Matches", len(weak_preview))

    st.divider()

    # Tabs

    tab_tailored, tab_alignment, tab_jd, tab_resume = st.tabs([
        "Final Resume",
        "Match Analysis",
        "Parsed JD",
        "Parsed Resume",
    ])

    # Tab 1 — Tailored resume
    with tab_tailored:
        raw = result.get("tailored_resume", "")
        try:
            tailored = json.loads(raw)

            # Check if full resume text is available
            full_resume_text = tailored.get("full_resume_text", "")
            if full_resume_text:
                # Display full resume
                with st.container(border=True):
                    st.subheader("Complete Tailored Resume")
                    st.text_area(
                        "Full Resume Content",
                        value=full_resume_text,
                        height=400,
                        disabled=True
                    )
                    
                # View modifications button
                if st.button("View Modifications", key="view_mods"):
                    st.session_state.show_modifications = not st.session_state.get("show_modifications", False)
                    
                if st.session_state.get("show_modifications", False):
                    with st.expander("Modifications Details", expanded=True):
                        with st.container(border=True):
                            st.subheader("Professional Summary")
                            summary_text = tailored.get("professional_summary", "—")
                            st.write(summary_text)
                            col_copy1, _ = st.columns([1, 4])
                            with col_copy1:
                                st.caption("Copy the text above manually (Ctrl+C)")

                        with st.container(border=True):
                            st.subheader("Reordered Skills")
                            skills = tailored.get("reordered_skills", [])
                            if skills:
                                skills_text = "  •  ".join(skills)
                                st.write(skills_text)
                                col_copy2, _ = st.columns([1, 4])
                                with col_copy2:
                                    st.caption("Copy the text above manually (Ctrl+C)")
                            else:
                                st.write("—")

                        with st.container(border=True):
                            st.subheader("Rewritten Bullet Points")
                            bullets = tailored.get("rewritten_bullets", [])

                            if bullets:
                                improved_count = len([b for b in bullets if b.get('revised', '').strip()])
                                st.metric("Bullets Optimized", f"{improved_count}/{len(bullets)}")
                                    
                                for i, b in enumerate(bullets, 1):
                                    with st.expander(f"Bullet {i}", expanded=(i == 1)):
                                        c1, c2 = st.columns(2)
                                        with c1:
                                            with st.container(border=True):
                                                st.markdown("**Original**")
                                                st.write(b.get("original", ""))
                                        with c2:
                                            with st.container(border=True):
                                                st.markdown("**Revised**")
                                                st.write(b.get("revised", ""))
                                        st.caption(f"Rationale: {b.get('rationale', '')}")
                            else:
                                st.info("No bullet rewrites generated.")
                
            else:
                # Fallback to original structure if no full text
                with st.container(border=True):
                    st.subheader("Professional Summary")
                    summary_text = tailored.get("professional_summary", "—")
                    st.write(summary_text)
                    col_copy1, _ = st.columns([1, 4])
                    with col_copy1:
                        st.caption("Copy the text above manually (Ctrl+C)")

                with st.container(border=True):
                    st.subheader("Reordered Skills")
                    skills = tailored.get("reordered_skills", [])
                    if skills:
                        skills_text = "  •  ".join(skills)
                        st.write(skills_text)
                        col_copy2, _ = st.columns([1, 4])
                        with col_copy2:
                            st.caption("Copy the text above manually (Ctrl+C)")
                    else:
                        st.write("—")

                with st.container(border=True):
                    st.subheader("Rewritten Bullet Points")
                    bullets = tailored.get("rewritten_bullets", [])

                    if bullets:
                        improved_count = len([b for b in bullets if b.get('revised', '').strip()])
                        st.metric("Bullets Optimized", f"{improved_count}/{len(bullets)}")
                            
                        for i, b in enumerate(bullets, 1):
                            with st.expander(f"Bullet {i}", expanded=(i == 1)):
                                c1, c2 = st.columns(2)
                                with c1:
                                    with st.container(border=True):
                                        st.markdown("**Original**")
                                        st.write(b.get("original", ""))
                                with c2:
                                    with st.container(border=True):
                                        st.markdown("**Revised**")
                                        st.write(b.get("revised", ""))
                                st.caption(f"Rationale: {b.get('rationale', '')}")
                    else:
                        st.info("No bullet rewrites generated.")

            st.divider()
            st.subheader("Download Complete Resume")
                
            # Generate PDF from full resume text if available
            if full_resume_text:
                pdf_data = generate_pdf(full_text=full_resume_text)
            else:
                # Fallback to original PDF generation
                pdf_data = generate_pdf(tailored_data=tailored)
                
            plain_text = full_resume_text if full_resume_text else f"""TAILORED RESUME

Professional Summary:
{tailored.get('professional_summary', '')}

Skills:
{chr(10).join('• ' + skill for skill in tailored.get('reordered_skills', []))}

Updated Achievements:
{chr(10).join('• ' + b.get('revised', '') for b in tailored.get('rewritten_bullets', []) if b.get('revised', '').strip())}
"""
                
            dl_col1, dl_col2, dl_col3 = st.columns(3)
                
            with dl_col1:
                st.download_button(
                    label="PDF",
                    data=pdf_data,
                    file_name="tailored_resume.pdf",
                    mime="application/pdf"
                )
                
            with dl_col2:
                st.download_button(
                    label="Text",
                    data=plain_text,
                    file_name="tailored_resume.txt",
                    mime="text/plain"
                )
                
            with dl_col3:
                st.download_button(
                    label="JSON",
                    data=json.dumps(tailored, indent=2),
                    file_name="tailored_resume.json",
                    mime="application/json"
                )

        except json.JSONDecodeError:
            st.markdown(raw)

    # Tab 2 — Alignment report
    with tab_alignment:
        raw = result.get("alignment", "{}")
        try:
            alignment = json.loads(raw)

            matched = alignment.get("matched", [])
            missing = alignment.get("missing", [])
            weak_matches = alignment.get("weak_matches", [])

            c1, c2, c3 = st.columns(3)
            c1.metric("Matched", len(matched))
            c2.metric("Missing", len(missing))
            c3.metric("Weak Matches", len(weak_matches))

            if matched:
                st.subheader("Matched")
                for m in matched:
                    st.markdown(f"- **{m.get('item')}** *(from {m.get('source')})*")

            if missing:
                st.subheader("Missing")
                for m in missing:
                    importance = m.get("importance", "")
                    colour = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(importance, "⚪")
                    st.markdown(f"- {colour} **{m.get('item')}** *(from {m.get('source')})*")

            if weak_matches:
                st.subheader("Weakly Expressed")
                for w in weak_matches:
                    with st.expander(w.get("jd_requirement", "")):
                        st.markdown(f"**Resume bullet:** {w.get('resume_bullet', '')}")
                        st.caption(w.get("reason", ""))

        except json.JSONDecodeError:
            st.json(raw)

    # Tab 3 — JD analysis
    with tab_jd:
        raw = result.get("jd_parsed", "{}")
        try:
            st.json(json.loads(raw))
        except json.JSONDecodeError:
            st.text(raw)

    # Tab 4 — Resume analysis
    with tab_resume:
        raw = result.get("resume_parsed", "{}")
        try:
            st.json(json.loads(raw))
        except json.JSONDecodeError:
            st.text(raw)
