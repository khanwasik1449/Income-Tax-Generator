import os
import re
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from number_to_words import number_to_words_bdt
from csv_parser import Employee, TaxRecord
from typing import List


def fmt_bdt(val) -> str:
    if val is None:
        return "0"
    try:
        num = int(round(float(val)))
    except (ValueError, TypeError):
        return "0"
    if num == 0:
        return "0"
    is_neg = num < 0
    s = str(abs(num))
    if len(s) <= 3:
        return f"-{s}" if is_neg else s
    last_three = s[-3:]
    other_digits = s[:-3]
    formatted_other = re.sub(r'\B(?=(\d{2})+(?!\d))', ',', other_digits)
    res = f"{formatted_other},{last_three}"
    return f"-{res}" if is_neg else res


def determine_fiscal_year(employee: Employee = None, tax_records: List[TaxRecord] = None,
                          start_year: int = None, end_year: int = None):
    if start_year is not None:
        if end_year is None:
            end_year = start_year + 1
        return start_year, end_year

    if employee and getattr(employee, "start_year", None):
        s_yr = int(employee.start_year)
        e_yr = int(getattr(employee, "end_year", None) or (s_yr + 1))
        return s_yr, e_yr

    if tax_records:
        years = []
        for tr in tax_records:
            for text in [tr.month, tr.challan_date]:
                if not text:
                    continue
                m4 = re.search(r'\b(20\d\d)\b', text)
                if m4:
                    yr = int(m4.group(1))
                    mon_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', text, re.IGNORECASE)
                    if mon_match:
                        mon_str = mon_match.group(1).lower()
                        if mon_str in ['jul', 'aug', 'sep', 'oct', 'nov', 'dec']:
                            years.append(yr)
                        else:
                            years.append(yr - 1)
                    else:
                        years.append(yr)
                m2 = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[-_](\d{2})\b', text, re.IGNORECASE)
                if m2:
                    mon_str = m2.group(1).lower()
                    yr = 2000 + int(m2.group(2))
                    if mon_str in ['jul', 'aug', 'sep', 'oct', 'nov', 'dec']:
                        years.append(yr)
                    else:
                        years.append(yr - 1)
        if years:
            from collections import Counter
            s_yr = Counter(years).most_common(1)[0][0]
            return s_yr, s_yr + 1

    return 2025, 2026


def generate_pdf(employee: Employee, tax_records: List[TaxRecord],
                 output_path: str, name: str = "", designation: str = "",
                 start_year: int = None, end_year: int = None,
                 use_letterhead: bool = False, letterhead_path: str = None):
    top_m = 36 * mm if use_letterhead else 20 * mm
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=top_m, bottomMargin=20 * mm,
    )

    def draw_bg(canvas, doc_obj):
        lh_file = letterhead_path
        if not lh_file or not os.path.exists(lh_file):
            lh_file = os.path.join("data", "custom_letterhead.png")
        if not os.path.exists(lh_file):
            lh_file = os.path.join("data", "default_letterhead.png")

        if use_letterhead and os.path.exists(lh_file):
            canvas.saveState()
            canvas.drawImage(lh_file, 0, 0, width=A4[0], height=A4[1], preserveAspectRatio=False)
            canvas.restoreState()

    styles = getSampleStyleSheet()
    title_s = ParagraphStyle("TitleCert", parent=styles["Title"],
                             fontSize=9, spaceAfter=8, alignment=TA_CENTER,
                             fontName="Helvetica-Bold")
    body_s = ParagraphStyle("BodyCert", parent=styles["Normal"],
                            fontSize=9, alignment=TA_JUSTIFY,
                            leading=12, spaceAfter=4)
    small_s = ParagraphStyle("SmallCert", parent=styles["Normal"],
                             fontSize=9, alignment=TA_LEFT, leading=11)
    footer_s = ParagraphStyle("FooterCert", parent=styles["Normal"],
                              fontSize=9, alignment=TA_CENTER)

    elements = []

    elements.append(Paragraph("TO WHOM IT MAY CONCERN", title_s))

    disp_name = name.strip() if name else "___________________________"
    disp_desg = designation.strip() if designation else "___________________________"
    tin = employee.tin if employee.tin else "N/A"
    net_total = employee.net_total

    s_yr, e_yr = determine_fiscal_year(employee, tax_records, start_year, end_year)

    cert_text = (
        f"This is to certify that <b>{disp_name}</b>, "
        f"Designation: <b>{disp_desg}</b> of BRAC Institute of Educational Development "
        f"(BRAC IED), BRAC University, TIN no: <b>{tin}</b> has been paid total salary of "
        f"<b>BDT {fmt_bdt(net_total)}</b> ({number_to_words_bdt(net_total)}) "
        f"during the period from 1 July {s_yr} to 30 June {e_yr}, the breakdown of the amount "
        f"is as follows:"
    )
    elements.append(Paragraph(cert_text, body_s))
    elements.append(Spacer(1, 6))

    breakdown = [
        ["Particulars", "Amount"],
        ["Basic Salary", fmt_bdt(employee.basic)],
        ["House Rent", fmt_bdt(employee.house_rent)],
        ["Medical Allowance", fmt_bdt(employee.medical_allowance)],
        ["Conveyance Allowance", fmt_bdt(employee.conveyance_allowance)],
        ["Festival Bonus", fmt_bdt(employee.festival_bonus)],
        ["Arrears", fmt_bdt(employee.arrears)],
        ["Others", fmt_bdt(employee.others)],
        ["Total", fmt_bdt(net_total)],
    ]

    bt = Table(breakdown, colWidths=[200, 120])
    bt.hAlign = "CENTER"
    bt.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(bt)
    elements.append(Spacer(1, 6))

    total_tax = sum(r.total_challan_amount for r in tax_records) if tax_records else 0
    total_claim = sum(r.claim_amount for r in tax_records) if tax_records else 0

    tax_text = (
        f"It is also certified that BDT <b>{fmt_bdt(total_claim)}</b> "
        f"({number_to_words_bdt(total_claim)}) "
        f"has been deducted as Income Tax from his/her salary during the period of "
        f"July {s_yr} to June {e_yr} and the Financial Year {s_yr}-{e_yr} through the "
        f"following A-Challans:"
    )
    elements.append(Paragraph(tax_text, body_s))
    elements.append(Spacer(1, 6))

    if tax_records:
        challan_data = [["S/N", "A-Challan No", "Challan Date", "Claim Amount", "Total Amount", "Bank Information"]]
        for i, tr in enumerate(tax_records, 1):
            challan_data.append([
                str(i),
                tr.challan_no,
                tr.challan_date,
                fmt_bdt(tr.claim_amount),
                fmt_bdt(tr.total_challan_amount),
                tr.bank_info or "-",
            ])
        challan_data.append(["", "", "Total", fmt_bdt(total_claim), fmt_bdt(total_tax), ""])

        ct = Table(challan_data, colWidths=[25, 90, 65, 60, 60, 85])
        ct.hAlign = "CENTER"
        ct.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (3, 0), (4, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(ct)
    else:
        elements.append(Paragraph("<i>No tax challan records found.</i>", small_s))

    elements.append(Spacer(1, 6))
    elements.append(Paragraph(
        "*SBL - Sonali Bank Limited &nbsp;&nbsp;&nbsp; *BBL - BRAC Bank Limited",
        ParagraphStyle("BankRef", parent=small_s, fontSize=9)
    ))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("This is a System Generated Statement", footer_s))

    if use_letterhead:
        doc.build(elements, onFirstPage=draw_bg, onLaterPages=draw_bg)
    else:
        doc.build(elements)
    return output_path
