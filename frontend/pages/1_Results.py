import json
import streamlit as st
from fpdf import FPDF
import io
import re


def generate_pdf(tailored_data=None, full_text=None):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Tailored Resume", ln=True, align="C")
    pdf.ln(10)

    if full_text:
        pdf.set_font("Helvetica", "", 10)
        lines = full_text.split('\n')
        usable_width = pdf.w - pdf.l_margin - pdf.r_margin

        for line in lines:
            pdf.set_x(pdf.l_margin)
            if line.strip():
                pdf.multi_cell(usable_width, 5, line)
            else:
                pdf.ln(3)

    else:
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Professional Summary", ln=True)
        pdf.set_font("Helvetica", "", 10)
        summary = tailored_data.get("professional_summary", "")
        pdf.multi_cell(0, 5, summary)
        pdf.ln(5)

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Skills", ln=True)
        pdf.set_font("Helvetica", "", 10)
        skills = tailored_data.get("reordered_skills", [])
        skills_text = " • ".join(skills) if skills else "—"
        pdf.multi_cell(0, 5, skills_text)
        pdf.ln(5)

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


st.set_page_config(
    page_title="Resume Tailoring Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

if "analysis_result" not in st.session_state or st.session_state.analysis_result is None:
    st.warning("No analysis result found yet.")
    if st.button("← Back to Input"):
        st.switch_page("app.py")
    st.stop()

if "show_modifications" not in st.session_state:
    st.session_state.show_modifications = False

st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1180px;
}
h1, h2, h3 {
    letter-spacing: -0.02em;
}
.stButton > button {
    border-radius: 14px;
    height: 3rem;
    font-weight: 600;
}
[data-testid="stMetric"] {
    background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
    border: 1px solid #e2e8f0;
    padding: 14px 16px;
    border-radius: 16px;
    box-shadow: 0 1px 2px rgba(0,0,0,0.03);
}
[data-testid="stMetricLabel"] {
    color: #475569;
}
[data-testid="stMetricValue"] {
    font-size: 2rem;
    color: #1e293b;
}
div[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid #e5e7eb !important;
}
div[data-testid="stVerticalBlockBorderWrapper"] {
    background: linear-gradient(180deg, #f8fbff 0%, #eef4ff 100%);
    border: 1px solid #dbeafe !important;
    border-radius: 16px !important;
    padding: 0.45rem 0.6rem;
}
</style>
""", unsafe_allow_html=True)

top1, top2 = st.columns([5, 2], vertical_alignment="center")
with top1:
    st.title("Tailored Resume Results")
    st.caption("Review the tailored resume, key changes, and matching summary.")
with top2:
    if st.button("← Back to Input", width="stretch"):
        st.switch_page("app.py")

result = st.session_state.analysis_result
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

st.markdown(
    f"""
    <div style="
        margin: 0.3rem 0 1rem 0;
        padding: 0.9rem 1rem;
        border-radius: 14px;
        background: linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%);
        border: 1px solid #bbf7d0;
        color: #166534;
        font-size: 0.95rem;
        font-weight: 500;
    ">
        Resume tailored successfully · Estimated fit: <strong>{fit_score}%</strong>
    </div>
    """,
    unsafe_allow_html=True
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Overall Fit", f"{fit_score}%")
m2.metric("Matched", len(matched_preview))
m3.metric("Missing", len(missing_preview))
m4.metric("Weak Matches", len(weak_preview))

st.divider()

raw = result.get("tailored_resume", "")
try:
    tailored = json.loads(raw)
except json.JSONDecodeError:
    st.error("Tailored resume output is not valid JSON.")
    st.stop()

full_resume_text = tailored.get("full_resume_text", "")
full_resume_text = re.sub(r"\n{3,}", "\n\n", full_resume_text).strip()

selected_view = st.segmented_control(
    "Results Navigation",
    ["Final Resume", "Match Summary", "Key Modifications"],
    default="Final Resume",
    width="stretch",
    label_visibility="collapsed",
)

if selected_view == "Final Resume":
    if full_resume_text:
        with st.container(border=True):
            st.subheader("Complete Tailored Resume")
            st.markdown(
                f"""
                <div style="
                    background: white;
                    border: 1px solid #e2e8f0;
                    border-radius: 16px;
                    padding: 20px 22px;
                    line-height: 1.8;
                    font-size: 16px;
                    color: #374151;
                    white-space: pre-wrap;
                ">
                {full_resume_text}
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        with st.container(border=True):
            st.subheader("Tailored Resume Preview")

            st.markdown("**Professional Summary**")
            st.write(tailored.get("professional_summary", "—"))

            st.markdown("**Skills**")
            skills = tailored.get("reordered_skills", [])
            st.write(" • ".join(skills) if skills else "—")

            st.markdown("**Updated Achievements**")
            bullets = tailored.get("rewritten_bullets", [])
            if bullets:
                for i, bullet in enumerate(bullets, 1):
                    revised = bullet.get("revised", "")
                    if revised.strip():
                        st.markdown(f"{i}. {revised}")
            else:
                st.write("—")

    st.divider()

    pdf_data = generate_pdf(
        full_text=full_resume_text if full_resume_text else None,
        tailored_data=tailored if not full_resume_text else None
    )

    plain_text = full_resume_text if full_resume_text else f"""TAILORED RESUME

Professional Summary:
{tailored.get('professional_summary', '')}

Skills:
{chr(10).join('• ' + skill for skill in tailored.get('reordered_skills', []))}

Updated Achievements:
{chr(10).join('• ' + b.get('revised', '') for b in tailored.get('rewritten_bullets', []) if b.get('revised', '').strip())}
"""

    with st.container(border=True):
        st.subheader("Export Resume")
        st.caption("Download the tailored resume in your preferred format.")

        dl_col1, dl_col2, dl_col3 = st.columns(3)

        with dl_col1:
            st.download_button(
                "PDF Resume",
                data=pdf_data,
                file_name="tailored_resume.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        with dl_col2:
            st.download_button(
               "Text Version",
               data=plain_text,
               file_name="tailored_resume.txt",
               mime="text/plain",
               use_container_width=True
            )
        with dl_col3:
            st.download_button(
                "JSON Output",
                data=json.dumps(tailored, indent=2),
                file_name="tailored_resume.json",
                mime="application/json",
                use_container_width=True
            )

elif selected_view == "Match Summary":
    c1, c2, c3 = st.columns(3)
    c1.metric("Matched", len(matched_preview))
    c2.metric("Missing", len(missing_preview))
    c3.metric("Weak Matches", len(weak_preview))

    if matched_preview:
        st.subheader("Matched")
        for m in matched_preview:
            st.markdown(f"- **{m.get('item')}** *(from {m.get('source')})*")

    if missing_preview:
        st.subheader("Missing")
        for m in missing_preview:
            importance = m.get("importance", "")
            colour = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(importance, "⚪")
            st.markdown(f"- {colour} **{m.get('item')}** *(from {m.get('source')})*")

    if weak_preview:
        st.subheader("Weakly Expressed")
        for w in weak_preview:
            with st.expander(w.get("jd_requirement", "")):
                st.markdown(f"**Resume bullet:** {w.get('resume_bullet', '')}")
                st.caption(w.get("reason", ""))

elif selected_view == "Key Modifications":
    with st.container(border=True):
        st.subheader("Professional Summary")
        st.write(tailored.get("professional_summary", "—"))

    with st.container(border=True):
        st.subheader("Reordered Skills")
        skills = tailored.get("reordered_skills", [])
        if skills:
            st.write("  •  ".join(skills))
        else:
            st.write("—")

    with st.container(border=True):
        st.subheader("Rewritten Bullet Points")
        bullets = tailored.get("rewritten_bullets", [])
        if bullets:
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