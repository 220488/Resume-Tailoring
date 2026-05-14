"""
Results page: renders the tailored resume, alignment summary, and raw analysis,
plus PDF / Text / JSON downloads.
"""

import json
import re
import sys
from pathlib import Path

import streamlit as st

# Make sibling pdf_export.py importable when Streamlit runs this from /pages
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pdf_export import tailored_resume_to_pdf  # noqa: E402


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", (name or "resume").strip())
    return cleaned.strip("_") or "resume"


def _resume_to_plain_text(tailored: dict) -> str:
    lines: list[str] = []
    name = tailored.get("candidate_name") or ""
    if name:
        lines.append(name)
        lines.append("=" * len(name))
        lines.append("")

    summary = tailored.get("professional_summary", "")
    if summary:
        lines.append("PROFESSIONAL SUMMARY")
        lines.append(summary)
        lines.append("")

    skills = tailored.get("skills", [])
    if skills:
        lines.append("SKILLS")
        lines.append(" · ".join(skills))
        lines.append("")

    work = tailored.get("work_experience", [])
    if work:
        lines.append("WORK EXPERIENCE")
        for role in work:
            end = role.get("end_date") or "Present"
            lines.append(
                f"{role.get('title', '')} — {role.get('company', '')}  "
                f"({role.get('start_date', '')} – {end})"
            )
            for b in role.get("bullets", []):
                lines.append(f"  • {b}")
            lines.append("")

    education = tailored.get("education", [])
    if education:
        lines.append("EDUCATION")
        for edu in education:
            year = edu.get("graduation_year")
            suffix = f" ({year})" if year else ""
            lines.append(f"{edu.get('degree', '')} — {edu.get('institution', '')}{suffix}")
            gpa = edu.get("gpa")
            if gpa is not None:
                lines.append(f"  GPA: {gpa}")
            coursework = edu.get("relevant_coursework", [])
            if coursework:
                lines.append(f"  Relevant coursework: {', '.join(coursework)}")
            lines.append("")

    projects = tailored.get("projects", [])
    if projects:
        lines.append("PROJECTS")
        for p in projects:
            lines.append(p.get("name", ""))
            techs = p.get("technologies", [])
            if techs:
                lines.append(f"  Tech: {', '.join(techs)}")
            for b in p.get("bullets", []):
                lines.append(f"  • {b}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Resume Tailoring Assistant",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Guard: must have an analysis result ──────────────────────────────────────

if "analysis_result" not in st.session_state or st.session_state.analysis_result is None:
    st.warning("No analysis result found yet.")
    if st.button("← Back to Input"):
        st.switch_page("app.py")
    st.stop()

if "show_modifications" not in st.session_state:
    st.session_state.show_modifications = False

# ── Light styling ────────────────────────────────────────────────────────────

st.markdown("""
<style>
.block-container {
    padding-top: 5rem;
    padding-bottom: 2rem;
    max-width: 1180px;
}
header[data-testid="stHeader"] {
    background: rgba(255, 255, 255, 0.85);
    backdrop-filter: blur(6px);
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

# ── Top bar ──────────────────────────────────────────────────────────────────

top1, top2 = st.columns([5, 2], vertical_alignment="center")
with top1:
    st.title("Tailored Resume Results")
    st.caption("Review the tailored resume, key changes, and matching summary.")
with top2:
    if st.button("← Back to Input", use_container_width=True):
        st.switch_page("app.py")

# ── Parse results ────────────────────────────────────────────────────────────

result = st.session_state.analysis_result

raw_alignment = result.get("alignment", "{}")
try:
    alignment_preview = json.loads(raw_alignment)
except json.JSONDecodeError:
    alignment_preview = {}

matched_preview = alignment_preview.get("matched", [])
missing_preview = alignment_preview.get("missing", [])
weak_preview = alignment_preview.get("weak_matches", [])

total_items = len(matched_preview) + len(missing_preview) + len(weak_preview)
fit_score = (
    round(((len(matched_preview) + 0.5 * len(weak_preview)) / total_items) * 100)
    if total_items > 0
    else 0
)

# ── Success banner ───────────────────────────────────────────────────────────

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
    unsafe_allow_html=True,
)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Overall Fit", f"{fit_score}%")
m2.metric("Matched", len(matched_preview))
m3.metric("Missing", len(missing_preview))
m4.metric("Weak Matches", len(weak_preview))

st.divider()

# ── Tailored resume parsing ──────────────────────────────────────────────────

raw_tailored = result.get("tailored_resume", "")
try:
    tailored = json.loads(raw_tailored)
except json.JSONDecodeError:
    st.error("Tailored resume output is not valid JSON.")
    st.markdown(raw_tailored)
    st.stop()

# ── Segmented navigation ─────────────────────────────────────────────────────

selected_view = st.segmented_control(
    "Results Navigation",
    ["Final Resume", "Match Summary", "JD Analysis", "Resume Parsed"],
    default="Final Resume",
    width="stretch",
    label_visibility="collapsed",
)

# ── View 1: Final Resume ─────────────────────────────────────────────────────

if selected_view == "Final Resume":
    with st.container(border=True):
        name = tailored.get("candidate_name") or "—"
        st.markdown(f"# {name}")

        summary = tailored.get("professional_summary", "")
        if summary:
            st.markdown("### Professional Summary")
            st.write(summary)

        skills = tailored.get("skills", [])
        if skills:
            st.markdown("### Skills")
            st.write(" · ".join(skills))

        work = tailored.get("work_experience", [])
        if work:
            st.markdown("### Work Experience")
            for role in work:
                end = role.get("end_date") or "Present"
                st.markdown(
                    f"**{role.get('title', '')}** — {role.get('company', '')}  "
                    f"  *{role.get('start_date', '')} – {end}*"
                )
                for b in role.get("bullets", []):
                    st.markdown(f"- {b}")
                st.write("")

        education = tailored.get("education", [])
        if education:
            st.markdown("### Education")
            for edu in education:
                line = f"**{edu.get('degree', '')}** — {edu.get('institution', '')}"
                year = edu.get("graduation_year")
                if year:
                    line += f"  *({year})*"
                st.markdown(line)
                gpa = edu.get("gpa")
                if gpa is not None:
                    st.caption(f"GPA: {gpa}")
                coursework = edu.get("relevant_coursework", [])
                if coursework:
                    st.caption("Relevant coursework: " + ", ".join(coursework))

        projects = tailored.get("projects", [])
        if projects:
            st.markdown("### Projects")
            for p in projects:
                st.markdown(f"**{p.get('name', '')}**")
                techs = p.get("technologies", [])
                if techs:
                    st.caption("Tech: " + ", ".join(techs))
                for b in p.get("bullets", []):
                    st.markdown(f"- {b}")
                st.write("")

    st.divider()

    # ── Export ───────────────────────────────────────────────────────────────

    file_stem = _safe_filename(tailored.get("candidate_name", "resume"))
    plain_text = _resume_to_plain_text(tailored)

    try:
        pdf_bytes = tailored_resume_to_pdf(tailored)
        pdf_error: str | None = None
    except Exception as exc:
        pdf_bytes = b""
        pdf_error = str(exc)

    with st.container(border=True):
        st.subheader("Export Resume")
        st.caption("Download the tailored resume in your preferred format.")

        dl_col1, dl_col2, dl_col3 = st.columns(3)

        with dl_col1:
            if pdf_error:
                st.error(f"Could not build PDF: {pdf_error}")
            else:
                st.download_button(
                    "PDF Resume",
                    data=pdf_bytes,
                    file_name=f"{file_stem}_tailored.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        with dl_col2:
            st.download_button(
                "Text Version",
                data=plain_text,
                file_name=f"{file_stem}_tailored.txt",
                mime="text/plain",
                use_container_width=True,
            )

        with dl_col3:
            st.download_button(
                "JSON Output",
                data=json.dumps(tailored, indent=2),
                file_name=f"{file_stem}_tailored.json",
                mime="application/json",
                use_container_width=True,
            )

# ── View 2: Match Summary ────────────────────────────────────────────────────

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

# ── View 3: JD Analysis ──────────────────────────────────────────────────────

elif selected_view == "JD Analysis":
    raw_jd = result.get("jd_parsed", "{}")
    with st.container(border=True):
        st.subheader("Parsed Job Description")
        try:
            st.json(json.loads(raw_jd))
        except json.JSONDecodeError:
            st.text(raw_jd)

# ── View 4: Resume Parsed ────────────────────────────────────────────────────

elif selected_view == "Resume Parsed":
    raw_resume = result.get("resume_parsed", "{}")
    with st.container(border=True):
        st.subheader("Parsed Resume")
        try:
            st.json(json.loads(raw_resume))
        except json.JSONDecodeError:
            st.text(raw_resume)
