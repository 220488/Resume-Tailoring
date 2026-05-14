"""
Render a tailored-resume JSON dict into a polished PDF using reportlab.

Public API:
    tailored_resume_to_pdf(tailored: dict) -> bytes
"""

from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)


_ACCENT = HexColor("#1f3a5f")
_MUTED = HexColor("#666666")


def _escape(text: str) -> str:
    """Escape characters that would otherwise be parsed as reportlab markup."""
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "Name",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            alignment=TA_CENTER,
            textColor=_ACCENT,
            spaceAfter=4,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=_ACCENT,
            spaceBefore=10,
            spaceAfter=4,
            alignment=TA_LEFT,
        ),
        "role_header": ParagraphStyle(
            "RoleHeader",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceAfter=1,
        ),
        "role_meta": ParagraphStyle(
            "RoleMeta",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            leading=12,
            textColor=_MUTED,
            spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "Bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            leftIndent=14,
            bulletIndent=2,
            spaceAfter=1,
        ),
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=11,
            textColor=_MUTED,
            spaceAfter=2,
        ),
    }


def _hr():
    return HRFlowable(
        width="100%",
        thickness=0.5,
        color=_ACCENT,
        spaceBefore=2,
        spaceAfter=4,
    )


def _section(story: list, title: str, styles: dict) -> None:
    story.append(Paragraph(title.upper(), styles["section"]))
    story.append(_hr())


def _add_summary(story: list, summary: str, styles: dict) -> None:
    if not summary:
        return
    _section(story, "Professional Summary", styles)
    story.append(Paragraph(_escape(summary), styles["body"]))


def _add_skills(story: list, skills: list, styles: dict) -> None:
    if not skills:
        return
    _section(story, "Skills", styles)
    story.append(Paragraph(_escape(" · ".join(skills)), styles["body"]))


def _add_work(story: list, work: list, styles: dict) -> None:
    if not work:
        return
    _section(story, "Work Experience", styles)
    for role in work:
        end = role.get("end_date") or "Present"
        title = _escape(role.get("title", ""))
        company = _escape(role.get("company", ""))
        start = _escape(role.get("start_date", ""))
        end_e = _escape(end)
        story.append(
            Paragraph(f"<b>{title}</b> &mdash; {company}", styles["role_header"])
        )
        story.append(Paragraph(f"{start} – {end_e}", styles["role_meta"]))
        for b in role.get("bullets", []):
            story.append(Paragraph(_escape(b), styles["bullet"], bulletText="•"))
        story.append(Spacer(1, 4))


def _add_education(story: list, education: list, styles: dict) -> None:
    if not education:
        return
    _section(story, "Education", styles)
    for edu in education:
        degree = _escape(edu.get("degree", ""))
        inst = _escape(edu.get("institution", ""))
        year = edu.get("graduation_year")
        suffix = f" ({year})" if year else ""
        story.append(
            Paragraph(f"<b>{degree}</b> &mdash; {inst}{_escape(suffix)}", styles["role_header"])
        )
        gpa = edu.get("gpa")
        if gpa is not None:
            story.append(Paragraph(f"GPA: {gpa}", styles["caption"]))
        coursework = edu.get("relevant_coursework", [])
        if coursework:
            story.append(
                Paragraph(
                    "Relevant coursework: " + _escape(", ".join(coursework)),
                    styles["caption"],
                )
            )
        story.append(Spacer(1, 4))


def _add_projects(story: list, projects: list, styles: dict) -> None:
    if not projects:
        return
    _section(story, "Projects", styles)
    for p in projects:
        story.append(Paragraph(f"<b>{_escape(p.get('name', ''))}</b>", styles["role_header"]))
        techs = p.get("technologies", [])
        if techs:
            story.append(Paragraph("Tech: " + _escape(", ".join(techs)), styles["caption"]))
        for b in p.get("bullets", []):
            story.append(Paragraph(_escape(b), styles["bullet"], bulletText="•"))
        story.append(Spacer(1, 4))


def tailored_resume_to_pdf(tailored: dict) -> bytes:
    """Render the tailored-resume dict into PDF bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
        title=f"{tailored.get('candidate_name') or 'Resume'} — Tailored Resume",
    )
    styles = _styles()
    story: list = []

    name = tailored.get("candidate_name") or "Resume"
    story.append(Paragraph(_escape(name), styles["name"]))
    story.append(Spacer(1, 6))

    _add_summary(story, tailored.get("professional_summary", ""), styles)
    _add_skills(story, tailored.get("skills", []), styles)
    _add_work(story, tailored.get("work_experience", []), styles)
    _add_education(story, tailored.get("education", []), styles)
    _add_projects(story, tailored.get("projects", []), styles)

    doc.build(story)
    return buf.getvalue()
