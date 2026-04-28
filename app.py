"""
Person 6 — Frontend / Prototype Integration & Testing

Streamlit UI:
- Two inputs: job description text area + resume PDF upload
- Calls the FastAPI backend at /analyze
- Displays the tailored resume and all intermediate outputs
"""

import json

import requests
import streamlit as st

API_URL = "http://localhost:8000"

# ── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Resume Tailoring Assistant",
    page_icon="📄",
    layout="wide",
)

st.title("AI Resume Tailoring Assistant")
st.caption("Paste a job description and upload your resume — get a tailored version in seconds.")

# ── Inputs ───────────────────────────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Job Description")
    jd_text = st.text_area(
        label="Paste the full job description here",
        height=320,
        placeholder="Copy and paste the job posting...",
        label_visibility="collapsed",
    )

with col_right:
    st.subheader("Your Resume")
    resume_file = st.file_uploader(
        label="Upload your resume (PDF only)",
        type=["pdf"],
    )

st.divider()

# ── Submit ────────────────────────────────────────────────────────────────────

submitted = st.button("Tailor My Resume", type="primary", use_container_width=True)

if submitted:
    # Validation
    if not jd_text.strip():
        st.error("Please enter a job description.")
        st.stop()
    if resume_file is None:
        st.error("Please upload your resume PDF.")
        st.stop()

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
            result = response.json()

        except requests.exceptions.ConnectionError:
            st.error("Cannot reach the backend. Make sure the FastAPI server is running on port 8000.")
            st.stop()
        except requests.exceptions.HTTPError as e:
            detail = response.json().get("detail", str(e))
            st.error(f"Backend error: {detail}")
            st.stop()
        except Exception as e:
            st.error(f"Unexpected error: {e}")
            st.stop()

    # ── Results ───────────────────────────────────────────────────────────────

    st.success("Done! See your tailored resume below.")

    tab_tailored, tab_alignment, tab_jd, tab_resume = st.tabs([
        "Tailored Resume",
        "Alignment Report",
        "JD Analysis",
        "Resume Parsed",
    ])

    # Tab 1 — Tailored resume (main output)
    with tab_tailored:
        raw = result.get("tailored_resume", "")
        try:
            tailored = json.loads(raw)

            st.subheader("Professional Summary")
            st.write(tailored.get("professional_summary", ""))

            st.subheader("Reordered Skills")
            skills = tailored.get("reordered_skills", [])
            st.write("  •  ".join(skills) if skills else "—")

            st.subheader("Rewritten Bullet Points")
            bullets = tailored.get("rewritten_bullets", [])
            if bullets:
                for i, b in enumerate(bullets, 1):
                    with st.expander(f"Bullet {i}"):
                        st.markdown(f"**Original:** {b.get('original', '')}")
                        st.markdown(f"**Revised:** {b.get('revised', '')}")
                        st.caption(f"Rationale: {b.get('rationale', '')}")
            else:
                st.info("No bullet rewrites generated.")

        except json.JSONDecodeError:
            # Fallback: render as plain text if the LLM returned non-JSON
            st.markdown(raw)

    # Tab 2 — Alignment report
    with tab_alignment:
        raw = result.get("alignment", "{}")
        try:
            alignment = json.loads(raw)

            matched      = alignment.get("matched", [])
            missing      = alignment.get("missing", [])
            weak_matches = alignment.get("weak_matches", [])

            c1, c2, c3 = st.columns(3)
            c1.metric("Matched",      len(matched))
            c2.metric("Missing",      len(missing))
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

    # Tab 3 — JD analysis (debug / transparency)
    with tab_jd:
        raw = result.get("jd_parsed", "{}")
        try:
            st.json(json.loads(raw))
        except json.JSONDecodeError:
            st.text(raw)

    # Tab 4 — Resume analysis (debug / transparency)
    with tab_resume:
        raw = result.get("resume_parsed", "{}")
        try:
            st.json(json.loads(raw))
        except json.JSONDecodeError:
            st.text(raw)
