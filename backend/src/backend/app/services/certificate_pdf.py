"""PDF generation service for official No-Dues Clearance Certificates using ReportLab and qrcode."""
import io
from datetime import datetime
import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
)


def generate_clearance_certificate_pdf(
    university_name: str,
    student_name: str,
    registration_number: str,
    programme_name: str,
    department_name: str,
    faculty_name: str,
    certificate_code: str,
    issued_at: datetime,
    approvals_data: list[tuple[str, str, str]],  # (dept_name, status, date_str)
    hod_name: str,
    verify_url: str,
) -> bytes:
    """
    Generates a professional clearance certificate PDF document on demand.
    Contains:
    - University title & Faculty header
    - Student credentials (Name, Reg No, Programme, Department)
    - Certificate UUID & Issue Date
    - Department clearance sign-off table
    - Chairperson / HoD authorization footer
    - Verification QR code pointing to public verification URL
    - Disclaimer note
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        alignment=1,  # Center
        textColor=colors.HexColor("#1A365D"),
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        alignment=1,
        textColor=colors.HexColor("#2B6CB0"),
    )
    doc_type_style = ParagraphStyle(
        "CertDocType",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        alignment=1,
        textColor=colors.HexColor("#742A2A"),
    )
    normal_style = ParagraphStyle(
        "CertNormal",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#2D3748"),
    )
    bold_style = ParagraphStyle(
        "CertBold",
        parent=normal_style,
        fontName="Helvetica-Bold",
    )
    footer_note_style = ParagraphStyle(
        "CertFooterNote",
        parent=styles["Italic"],
        fontName="Helvetica-Oblique",
        fontSize=8,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#718096"),
    )

    story = []

    # 1. Header
    story.append(Paragraph(university_name, title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(faculty_name, subtitle_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph("OFFICIAL NO-DUES CLEARANCE CERTIFICATE", doc_type_style))
    story.append(Spacer(1, 14))

    # 2. Student Info & Meta (left: details, right: QR code)
    # Generate QR Code image in memory
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=1,
    )
    qr.add_data(verify_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format="PNG")
    qr_buffer.seek(0)

    qr_platypus_img = Image(qr_buffer, width=1.3 * inch, height=1.3 * inch)

    issued_date_str = issued_at.strftime("%B %d, %Y (%H:%M UTC)") if issued_at else "N/A"

    info_text = f"""
    <b>Student Name:</b> {student_name}<br/>
    <b>Registration Number:</b> {registration_number}<br/>
    <b>Programme:</b> {programme_name}<br/>
    <b>Department:</b> {department_name}<br/>
    <b>Certificate Code:</b> {certificate_code}<br/>
    <b>Date of Issue:</b> {issued_date_str}
    """
    info_paragraph = Paragraph(info_text, normal_style)

    meta_table_data = [
        [info_paragraph, qr_platypus_img]
    ]
    meta_table = Table(meta_table_data, colWidths=[4.8 * inch, 1.8 * inch])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 14))

    # 3. Department Clearance Table
    story.append(Paragraph("<b>Departmental Clearances Summary</b>", bold_style))
    story.append(Spacer(1, 6))

    table_data = [
        ["Department / Section", "Clearance Status", "Date of Approval"]
    ]
    for dept_name_item, status_item, date_str in approvals_data:
        table_data.append([dept_name_item, status_item, date_str])

    dept_table = Table(table_data, colWidths=[3.6 * inch, 1.5 * inch, 1.5 * inch])
    dept_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF2F7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1A202C")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
    ]))
    story.append(dept_table)
    story.append(Spacer(1, 20))

    # 4. Signatures / Endorsement
    sign_text = f"""
    <b>Approved and Issued by:</b><br/>
    {hod_name}<br/>
    Chairperson, {department_name}<br/>
    {faculty_name}
    """
    sign_para = Paragraph(sign_text, normal_style)
    sign_table = Table([[sign_para]], colWidths=[6.6 * inch])
    sign_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 16))

    # 5. Security & Verification Disclaimer
    disclaimer_text = (
        "Note: This is a system-generated document and is valid only if the QR verification page "
        f"confirms it ({verify_url}). Any unauthorized alteration renders this certificate void."
    )
    story.append(Paragraph(disclaimer_text, footer_note_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
