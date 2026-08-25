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


def _score_cell(value) -> str:
    if value is None:
        return "—"
    return str(value)


def _change_cell(value) -> str:
    from services.week_performance import format_signed_change

    return format_signed_change(value)


def _weekly_comparison_table_flowables(comparison: dict, heading_style, body_style):
    from services.week_performance import format_completed_tasks

    story = []
    story.append(Paragraph("Weekly Performance Comparison", heading_style))
    if not comparison.get("has_previous_weeks"):
        message = comparison.get("message") or "No previous week available for comparison."
        story.append(Paragraph(message, body_style))
        story.append(Spacer(1, 0.1 * inch))
        return story

    weeks = comparison.get("weeks") or []
    change = comparison.get("change") or {}
    week_count = len(weeks)
    font_size = 8 if week_count >= 6 else 9
    header = ["Metric"] + [f"Week {item['week_number']}" for item in weeks] + ["Change"]
    rows = [
        ["Weekly Score"]
        + [_score_cell(item.get("weekly_score")) for item in weeks]
        + [_change_cell(change.get("weekly_score"))],
        ["Completed Tasks"]
        + [
            format_completed_tasks(item["completed_tasks"], item["total_tasks"])
            for item in weeks
        ]
        + [_change_cell(change.get("completed_tasks"))],
        ["Needs Revision"]
        + [str(item["needs_revision"]) for item in weeks]
        + [_change_cell(change.get("needs_revision"))],
        ["On-Time Tasks"]
        + [str(item["on_time_tasks"]) for item in weeks]
        + [_change_cell(change.get("on_time_tasks"))],
    ]
    data = [header] + rows
    usable = 6.6 * inch
    metric_w = 1.25 * inch
    change_w = 0.7 * inch
    week_w = max(0.55 * inch, (usable - metric_w - change_w) / max(week_count, 1))
    col_widths = [metric_w] + [week_w] * week_count + [change_w]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 0), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, MUTED),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))
    return story


def _final_week_performance_table_flowables(payload: dict, heading_style, body_style):
    from services.week_performance import format_completed_tasks

    story = []
    story.append(Paragraph("Internship Performance by Week", heading_style))
    weeks = payload.get("weeks") or []
    if not weeks:
        story.append(Paragraph("No roadmap weeks available.", body_style))
        story.append(Spacer(1, 0.1 * inch))
        return story

    cell_style = ParagraphStyle(
        "WeekPerfCell",
        parent=body_style,
        fontSize=8,
        leading=10,
    )
    header = ["Week", "Score", "Completed Tasks", "Needs Revision", "Main Focus"]
    data = [header]
    for item in weeks:
        data.append(
            [
                f"Week {item['week_number']}",
                _score_cell(item.get("weekly_score")),
                format_completed_tasks(item["completed_tasks"], item["total_tasks"]),
                str(item["needs_revision"]),
                Paragraph(item.get("main_focus") or "—", cell_style),
            ]
        )
    table = Table(
        data,
        colWidths=[0.85 * inch, 0.7 * inch, 1.2 * inch, 1.1 * inch, 2.75 * inch],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ORANGE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
                ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
                ("ALIGN", (0, 0), (3, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("GRID", (0, 0), (-1, -1), 0.4, MUTED),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))
    return story


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

    from services.week_performance import build_weekly_report_comparison

    comparison = build_weekly_report_comparison(
        intern=report.intern,
        program=report.program,
        current_week=report.roadmap_week,
        current_weekly_score=report.overall_weekly_score,
    )
    story.extend(
        _weekly_comparison_table_flowables(comparison, heading_style, body_style)
    )

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
    if report.pdf_file:
        report.pdf_file.delete(save=False)
    target = report.pdf_file.field.generate_filename(report, filename)
    storage = report.pdf_file.storage
    if storage.exists(target):
        storage.delete(target)
    report.pdf_file.save(filename, ContentFile(buffer.read()), save=True)
    return report.pdf_file

def final_summary_title(summary) -> str:
    intern_name = (summary.intern.user.full_name or "Intern").strip()
    return f"Final Internship Summary for {intern_name}"


def final_summary_pdf_filename(summary) -> str:
    intern_slug = _safe_filename_part(summary.intern.user.full_name or "intern")
    return f"final-internship-summary-{intern_slug}.pdf"


def generate_final_summary_pdf(summary, *, draft_watermark: bool = False):
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
        "FinalOrangeTitle",
        parent=styles["Heading1"],
        textColor=ORANGE,
        fontSize=16,
        spaceAfter=4,
        leading=20,
    )
    heading_style = ParagraphStyle(
        "FinalOrangeHeading",
        parent=styles["Heading2"],
        textColor=ORANGE,
        fontSize=12,
        spaceBefore=12,
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "FinalBody",
        parent=styles["BodyText"],
        textColor=DARK,
        fontSize=10,
        leading=14,
        spaceAfter=2,
    )
    meta_style = ParagraphStyle(
        "FinalMeta",
        parent=styles["BodyText"],
        textColor=MUTED,
        fontSize=9,
        leading=12,
    )

    report_title = final_summary_title(summary)
    from services.final_summary_score import (
        format_final_summary_score_display,
        refresh_final_summary_score,
    )

    calculated_score = refresh_final_summary_score(summary)
    score = format_final_summary_score_display(calculated_score)
    internship_dates = ""
    if summary.program.start_date or summary.program.end_date:
        start = (
            summary.program.start_date.isoformat()
            if summary.program.start_date
            else "?"
        )
        end = (
            summary.program.end_date.isoformat() if summary.program.end_date else "?"
        )
        internship_dates = f"{start} → {end}"

    story = []
    logo_path = _brand_logo_path()
    header_cells = []
    if logo_path:
        header_cells.append(Image(str(logo_path), width=0.85 * inch, height=0.85 * inch))
    header_cells.append(
        [
            Paragraph(report_title, title_style),
            Paragraph("Final Performance Report", meta_style),
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

    if draft_watermark or summary.status != "APPROVED":
        story.append(Paragraph("<b>DRAFT — Mentor preview only</b>", meta_style))
        story.append(Spacer(1, 0.1 * inch))

    story.append(Paragraph(f"<b>Program:</b> {summary.program.title}", body_style))
    story.append(Paragraph(f"<b>Intern:</b> {summary.intern.user.full_name}", body_style))
    if internship_dates:
        story.append(Paragraph(f"<b>Internship dates:</b> {internship_dates}", body_style))
    story.append(Paragraph(f"<b>Final Score:</b> {score}", body_style))
    story.append(
        Paragraph(
            f"<b>Generated:</b> {timezone.localdate().isoformat()}",
            meta_style,
        )
    )

    sections = [
        ("Overall Performance Summary", _wrap_text(summary.overall_performance_summary)),
        ("Learning Journey", _wrap_text(summary.learning_journey)),
        ("Main Achievements", _bullet_lines(summary.main_achievements)),
        ("Goal Achievement", _wrap_text(summary.goal_achievement)),
        ("Final Performance Summary", _wrap_text(summary.final_performance_summary)),
        ("Mentor Comments", _wrap_text(summary.mentor_comments)),
        ("Additional Notes", _wrap_text(summary.additional_mentor_notes)),
    ]
    for title, lines in sections:
        story.append(Paragraph(title, heading_style))
        for line in lines:
            story.append(Paragraph(str(line).replace("\n", "<br/>"), body_style))

    from services.week_performance import build_final_summary_week_performance

    week_performance = build_final_summary_week_performance(
        intern=summary.intern,
        program=summary.program,
    )
    story.extend(
        _final_week_performance_table_flowables(
            week_performance, heading_style, body_style
        )
    )

    def _footer(canvas_obj, _doc):
        canvas_obj.saveState()
        canvas_obj.setStrokeColor(ORANGE)
        canvas_obj.setLineWidth(1)
        canvas_obj.line(0.75 * inch, 0.55 * inch, letter[0] - 0.75 * inch, 0.55 * inch)
        canvas_obj.setFillColor(MUTED)
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(0.75 * inch, 0.35 * inch, "Orange")
        canvas_obj.drawRightString(
            letter[0] - 0.75 * inch,
            0.35 * inch,
            f"Page {canvas_obj.getPageNumber()}",
        )
        canvas_obj.restoreState()

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buffer.seek(0)
    filename = final_summary_pdf_filename(summary)
    if summary.pdf_file:
        summary.pdf_file.delete(save=False)
    target = summary.pdf_file.field.generate_filename(summary, filename)
    storage = summary.pdf_file.storage
    if storage.exists(target):
        storage.delete(target)
    summary.pdf_file.save(filename, ContentFile(buffer.read()), save=True)
    return summary.pdf_file
