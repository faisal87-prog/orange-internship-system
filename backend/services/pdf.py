from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ORANGE = colors.Color(1.0, 0.31, 0.0)  # approx brand orange
DARK = colors.Color(0.12, 0.12, 0.14)
MUTED = colors.Color(0.35, 0.35, 0.40)


def _brand_logo_path() -> Path | None:
    candidates = [
        Path(settings.BASE_DIR).parent / "frontend" / "public" / "branding" / "orange-logo.jpeg",
        Path(settings.BASE_DIR) / "static" / "branding" / "orange-logo.jpeg",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _safe_filename_part(value: str) -> str:
    cleaned = "".join(
        ch.lower() if ch.isalnum() else "-"
        for ch in (value or "").strip()
    )
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "intern"


def weekly_report_title(report) -> str:
    week = report.roadmap_week.week_number if report.roadmap_week else "?"
    intern_name = (report.intern.user.full_name or "Intern").strip()
    return f"Week {week} Report for {intern_name}"


def weekly_report_pdf_filename(report) -> str:
    week = report.roadmap_week.week_number if report.roadmap_week else "unknown"
    intern_slug = _safe_filename_part(report.intern.user.full_name or "intern")
    return f"week-{week}-report-{intern_slug}.pdf"


def _wrap_text(text: str) -> list[str]:
    value = (text or "").strip() or "—"
    return value.split("\n")


def _bullet_lines(items) -> list[str]:
    items = items or []
    if not items:
        return ["—"]
    return [f"• {item}" for item in items]


def generate_weekly_report_pdf(report, *, draft_watermark: bool = False):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "OrangeTitle",
        parent=styles["Heading1"],
        textColor=ORANGE,
        fontSize=16,
        spaceAfter=4,
        leading=20,
    )
    heading_style = ParagraphStyle(
        "OrangeHeading",
        parent=styles["Heading2"],
        textColor=ORANGE,
        fontSize=12,
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        textColor=DARK,
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "Meta",
        parent=styles["BodyText"],
        textColor=MUTED,
        fontSize=9,
        leading=12,
    )

    week = report.roadmap_week.week_number if report.roadmap_week else "?"
    report_title = weekly_report_title(report)
    week_dates = ""
    if report.roadmap_week and (report.roadmap_week.start_date or report.roadmap_week.end_date):
        start = report.roadmap_week.start_date.isoformat() if report.roadmap_week.start_date else "?"
        end = report.roadmap_week.end_date.isoformat() if report.roadmap_week.end_date else "?"
        week_dates = f" ({start} → {end})"
    score = (
        f"{report.overall_weekly_score} / 100"
        if report.overall_weekly_score is not None
        else "No scored tasks available for this week."
    )

    story = []
    logo_path = _brand_logo_path()
    header_cells = []
    if logo_path:
        header_cells.append(Image(str(logo_path), width=0.85 * inch, height=0.85 * inch))
    header_cells.append(
        [
            Paragraph(report_title, title_style),
            Paragraph("Weekly Performance Report", meta_style),
        ]
    )
    header = Table(
        [[header_cells[0], header_cells[1]]] if logo_path else [[header_cells[0]]],
        colWidths=[1.1 * inch, 5.5 * inch] if logo_path else [6.6 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, -1), 2, ORANGE),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 0.2 * inch))

    if draft_watermark or report.status != "APPROVED":
        story.append(Paragraph("<b>DRAFT — Mentor preview only</b>", meta_style))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph(f"<b>Program:</b> {report.program.title}", body_style))
    story.append(Paragraph(f"<b>Intern:</b> {report.intern.user.full_name}", body_style))
    story.append(Paragraph(f"<b>Week:</b> {week}{week_dates}", body_style))
    story.append(Paragraph(f"<b>Overall Weekly Score:</b> {score}", body_style))
    story.append(
        Paragraph(
            f"<b>Generated:</b> {timezone.localdate().isoformat()}",
            meta_style,
        )
    )

    sections = [
        ("Performance Summary", _wrap_text(report.performance_summary)),
        ("Achievements", _bullet_lines(report.achievements)),
        ("Learning Progress", _wrap_text(report.learning_progress)),
        ("Productivity Analysis", _wrap_text(report.productivity_analysis)),
        ("Mentor Focus Suggestions", _bullet_lines(report.mentor_focus_suggestions)),
        ("Recommended Next Focus", _wrap_text(report.recommended_next_focus)),
        ("Additional Mentor Notes", _wrap_text(report.additional_mentor_notes)),
    ]
    for title, lines in sections:
        story.append(Paragraph(title, heading_style))
        for line in lines:
            story.append(Paragraph(str(line).replace("\n", "<br/>"), body_style))

    def _footer(canvas_obj, _doc):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(ORANGE)
        canvas_obj.setLineWidth(1)
        canvas_obj.line(0.75 * inch, 0.55 * inch, letter[0] - 0.75 * inch, 0.55 * inch)
        canvas_obj.setFillColor(MUTED)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(
            0.75 * inch,
            0.35 * inch,
            "Orange",
        )
        canvas_obj.drawRightString(
            letter[0] - 0.75 * inch,
            0.35 * inch,
            f"Page {canvas_obj.getPageNumber()}",
        )
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    filename = weekly_report_pdf_filename(report)
    report.pdf_file.save(filename, ContentFile(buffer.read()), save=True)
    return report.pdf_file


def generate_final_summary_pdf(summary):
    """Preserve existing Final Summary PDF generation (unchanged AI scope)."""
    from reportlab.pdfgen import canvas

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    score = (
        f"{summary.final_score} / 100"
        if summary.final_score is not None
        else "N/A"
    )
    lines = [
        "Final Internship Summary",
        f"Intern: {summary.intern.user.full_name}",
        f"Program: {summary.program.title}",
        f"Final Score: {score}",
        "",
        "Overall Performance Summary",
        summary.overall_performance_summary or "—",
        "",
        "Learning Journey",
        summary.learning_journey or "—",
        "",
        "Main Achievements",
        *_bullet_lines(summary.main_achievements),
        "",
        "Goal Achievement",
        summary.goal_achievement or "—",
        "",
        "Final Performance Summary",
        summary.final_performance_summary or "—",
        "",
        "Mentor Comments",
        summary.mentor_comments or "—",
        "",
        "Additional Mentor Notes",
        summary.additional_mentor_notes or "—",
    ]
    y = 750
    for line in lines:
        if y < 60:
            pdf.showPage()
            y = 750
        pdf.drawString(50, y, str(line)[:110])
        y -= 18
    pdf.save()
    buffer.seek(0)
    filename = f"final-summary-{summary.id}.pdf"
    summary.pdf_file.save(filename, ContentFile(buffer.read()), save=True)
    return summary.pdf_file
