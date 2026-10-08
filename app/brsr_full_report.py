"""Full 25+ page SEBI BRSR Report Generator.

Structure:
  Cover → TOC → Section A → Section B → Section C (Principles 1-9)
  → BRSR Core → Assurance → Appendix
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether,
)

# ---------- BRAND COLORS ----------
NAVY = colors.HexColor('#0b1f33')
NAVY2 = colors.HexColor('#14304f')
GREEN = colors.HexColor('#10b981')
GREEN_D = colors.HexColor('#059669')
BLUE = colors.HexColor('#3b82f6')
SKY = colors.HexColor('#0ea5e9')
AMBER = colors.HexColor('#f59e0b')
RED = colors.HexColor('#ef4444')
VIOLET = colors.HexColor('#8b5cf6')
GREY = colors.HexColor('#64748b')
LIGHT = colors.HexColor('#f1f5f9')
LINE = colors.HexColor('#e2e8f0')
DARKTEXT = colors.HexColor('#1e293b')


def _styles():
    s = getSampleStyleSheet()
    return {
        'cover_title': ParagraphStyle('cover_title', parent=s['Title'],
            fontSize=30, textColor=colors.white, alignment=1, leading=36),
        'cover_sub': ParagraphStyle('cover_sub', parent=s['Normal'],
            fontSize=13, textColor=colors.HexColor('#7dd3fc'), alignment=1, leading=18),
        'cover_label': ParagraphStyle('cover_label', parent=s['Normal'],
            fontSize=10, textColor=colors.HexColor('#94a3b8'), alignment=1, leading=14),
        'h1': ParagraphStyle('h1', parent=s['Heading1'],
            fontSize=20, textColor=NAVY, spaceAfter=6, spaceBefore=4, leading=24),
        'h2': ParagraphStyle('h2', parent=s['Heading2'],
            fontSize=14, textColor=NAVY, spaceAfter=6, spaceBefore=10, leading=18),
        'h3': ParagraphStyle('h3', parent=s['Heading3'],
            fontSize=11.5, textColor=NAVY2, spaceAfter=4, spaceBefore=8, leading=15),
        'principle_header': ParagraphStyle('principle_header', parent=s['Normal'],
            fontSize=15, textColor=colors.white, leading=19, fontName='Helvetica-Bold'),
        'principle_sub': ParagraphStyle('principle_sub', parent=s['Normal'],
            fontSize=10, textColor=colors.HexColor('#e0f2fe'), leading=13),
        'body': ParagraphStyle('body', parent=s['BodyText'],
            fontSize=9.5, leading=13, textColor=DARKTEXT),
        'body_small': ParagraphStyle('body_small', parent=s['BodyText'],
            fontSize=8.5, leading=11, textColor=DARKTEXT),
        'note': ParagraphStyle('note', parent=s['BodyText'],
            fontSize=8, leading=10.5, textColor=GREY, fontName='Helvetica-Oblique'),
        'toc_entry': ParagraphStyle('toc_entry', parent=s['Normal'],
            fontSize=10, textColor=DARKTEXT, leading=18),
        'toc_section': ParagraphStyle('toc_section', parent=s['Normal'],
            fontSize=10.5, textColor=NAVY, leading=18, fontName='Helvetica-Bold'),
        'cell': ParagraphStyle('cell', parent=s['Normal'],
            fontSize=8.5, leading=10.5, textColor=DARKTEXT),
        'cell_bold': ParagraphStyle('cell_bold', parent=s['Normal'],
            fontSize=8.5, leading=10.5, textColor=NAVY, fontName='Helvetica-Bold'),
        'cell_header': ParagraphStyle('cell_header', parent=s['Normal'],
            fontSize=8.5, leading=10.5, textColor=colors.white, fontName='Helvetica-Bold'),
    }


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 8)
    canvas.drawString(18 * mm, A4[1] - 8 * mm, 'MEIL · BRSR FY 2025-26')
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(A4[0] - 18 * mm, A4[1] - 8 * mm,
                            'Business Responsibility & Sustainability Report')
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 10 * mm, 'MEIL BRSR · Confidential')
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f'Page {doc.page}')
    canvas.restoreState()


def _section_title(story, number, title, styles):
    story.append(Paragraph(f'{number}. {title}', styles['h1']))
    story.append(Spacer(1, 6))


def _sub_title(story, title, styles):
    story.append(Paragraph(title, styles['h2']))
    story.append(Spacer(1, 4))


def _sub_sub_title(story, title, styles):
    story.append(Paragraph(title, styles['h3']))
    story.append(Spacer(1, 2))


def _data_table(rows, col_widths, styles, header=True):
    data = []
    for i, row in enumerate(rows):
        styled_row = []
        for cell in row:
            style = styles['cell_header'] if (header and i == 0) else styles['cell']
            styled_row.append(Paragraph(str(cell), style))
        data.append(styled_row)
    t = Table(data, colWidths=col_widths, repeatRows=1 if header else 0)
    cmds = [
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.4, LINE),
        ('BOX', (0, 0), (-1, -1), 0.4, LINE),
    ]
    if header:
        cmds += [
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ]
    t.setStyle(TableStyle(cmds))
    return t


def _principle_banner(num, title, subtitle, color_hex, styles):
    """Colored banner at the start of each principle section."""
    banner = Table(
        [[Paragraph(f'PRINCIPLE {num}', styles['principle_sub'])],
         [Paragraph(title, styles['principle_header'])],
         [Paragraph(subtitle, styles['principle_sub'])]],
        colWidths=[A4[0] - 36 * mm],
    )
    banner.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(color_hex)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return banner


def _essential_label(styles):
    return Paragraph(
        '<font color="#059669"><b>ESSENTIAL INDICATORS</b></font>',
        styles['h3'])


def _leadership_label(styles):
    return Paragraph(
        '<font color="#7c3aed"><b>LEADERSHIP INDICATORS</b></font>',
        styles['h3'])
def _build_core_and_closure(story, st):
    """BRSR Core + Assurance Statement + Appendix pages."""

    story.append(PageBreak())

    # ============================================================
    # BRSR CORE — 9 ATTRIBUTES
    # ============================================================
    story.append(Paragraph('BRSR CORE', st['h1']))
    story.append(Paragraph(
        'The BRSR Core is a sub-set of the BRSR consisting of 9 ESG attributes '
        'that are subject to reasonable assurance. MEIL reports the following '
        '46 KPIs across these attributes.',
        st['body']))
    story.append(Spacer(1, 10))

    core_rows = [
        ['#', 'Attribute', 'Key KPIs', 'FY 2025-26', 'Status'],
        ['1', 'Green-house Gas (GHG) Footprint',
         'Scope 1, Scope 2, Scope 1+2 intensity', '9,07,033 tCO2e · 5.9 tCO2e/₹Cr',
         'Disclosed'],
        ['2', 'Water Footprint',
         'Withdrawal, consumption, intensity, discharge', '1,74,61,322 kL · 82.8 kL/₹Cr',
         'Disclosed'],
        ['3', 'Energy Footprint',
         'Total energy, % renewable, intensity', '1,02,23,973 GJ · 4.3% renewable',
         'Disclosed'],
        ['4', 'Embracing Circularity',
         'Waste generated, recovered, intensity', '5,96,194 MT · 52% recovered',
         'Disclosed'],
        ['5', 'Enhancing Employee Wellbeing & Safety',
         'Wellbeing spend, LTIFR, fatalities', '0.54% of revenue · LTIFR 0.02',
         'Disclosed'],
        ['6', 'Enabling Gender Diversity in Business',
         'Women in workforce, wages, POSH', '5.1% women · 6.1% wages to women',
         'Disclosed'],
        ['7', 'Enabling Inclusive Development',
         'MSME sourcing, jobs in smaller towns', '11% MSME · 64% domestic',
         'Disclosed'],
        ['8', 'Fairness in Engaging with Customers & Suppliers',
         'Data breach, days payable', '0 breaches · 128 days DPO',
         'Disclosed'],
        ['9', 'Openness of Business',
         'Trading houses concentration, RPTs', '0.45% purchases · 7.21% RPT purchases',
         'Disclosed'],
    ]
    story.append(_data_table(core_rows,
                             [8 * mm, 45 * mm, 50 * mm, 45 * mm, 22 * mm], st))
    story.append(Spacer(1, 10))

    # ---------- Detailed GHG breakdown ----------
    story.append(_sub_title(story, 'Attribute 1 · GHG Footprint — Detailed', st))
    ghg_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Total Scope 1 emissions', 'tCO2e', '6,17,113', '6,03,953'],
        ['Total Scope 2 emissions (location-based)', 'tCO2e', '2,89,920', '2,82,341'],
        ['Total Scope 2 emissions (market-based)', 'tCO2e', '2,89,920', '2,82,341'],
        ['Total Scope 1 + 2', 'tCO2e', '9,07,033', '8,86,294'],
        ['Scope 1 + 2 intensity per ₹ Cr', 'tCO2e/₹ Cr', '5.9', '6.2'],
        ['Scope 1 + 2 intensity per PPP Mn USD', 'tCO2e/PPP Mn USD', '12.0', '12.8'],
        ['Total Scope 3 emissions', 'tCO2e', '6,54,82,226', '7,45,84,242'],
        ['Scope 3 intensity per ₹ Cr', 'tCO2e/₹ Cr', '42.6', '52.3'],
    ]
    story.append(_data_table(ghg_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 10))

    # ---------- Detailed Water breakdown ----------
    story.append(_sub_title(story, 'Attribute 2 · Water Footprint — Detailed', st))
    water_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Total water withdrawal', 'kL', '1,74,61,322', '1,98,18,474'],
        ['Total water consumption', 'kL', '1,27,30,509', '1,54,31,695'],
        ['Water discharge — with treatment', 'kL', '45,88,359', '42,34,073'],
        ['Water intensity per ₹ Cr', 'kL/₹ Cr', '82.8', '108.3'],
        ['Water intensity per PPP Mn USD', 'kL/PPP Mn USD', '168.5', '223.7'],
    ]
    story.append(_data_table(water_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    # ---------- Detailed Energy ----------
    story.append(_sub_title(story, 'Attribute 3 · Energy Footprint — Detailed', st))
    energy_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Total energy consumed', 'GJ', '1,02,23,973', '99,30,417'],
        ['Renewable energy consumed', 'GJ', '4,35,930', '3,13,443'],
        ['Non-renewable energy consumed', 'GJ', '97,88,043', '96,16,974'],
        ['% renewable of total', '%', '4.3%', '3.2%'],
        ['Energy intensity per ₹ Cr', 'GJ/₹ Cr', '66.5', '69.7'],
        ['Energy intensity per PPP Mn USD', 'GJ/PPP Mn USD', '135.3', '144.0'],
    ]
    story.append(_data_table(energy_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 10))

    # ---------- Detailed Circularity ----------
    story.append(_sub_title(story, 'Attribute 4 · Embracing Circularity — Detailed', st))
    circ_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Total waste generated', 'MT', '5,96,194', '4,51,226'],
        ['Waste recovered (recycle + reuse)', 'MT', '3,10,253', '80,440'],
        ['Waste disposed', 'MT', '2,71,079', '3,72,962'],
        ['Waste recovery rate', '%', '52.0%', '17.8%'],
        ['Waste intensity per ₹ Cr', 'MT/₹ Cr', '3.9', '3.2'],
        ['Waste intensity per PPP Mn USD', 'MT/PPP Mn USD', '7.9', '6.5'],
    ]
    story.append(_data_table(circ_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    # ---------- Detailed Wellbeing & Safety ----------
    story.append(_sub_title(story, 'Attribute 5 · Employee Wellbeing & Safety — Detailed', st))
    well_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Wellbeing spend as % of revenue', '%', '0.54%', '0.49%'],
        ['Wellbeing spend (absolute)', '₹ Cr', '~822', '~700'],
        ['LTIFR — Employees', 'per Mn hrs', '0.02', '0.04'],
        ['LTIFR — Workers', 'per Mn hrs', '0.09', '0.12'],
        ['Fatalities — Employees', 'nos', '2', '5'],
        ['Fatalities — Workers', 'nos', '1', '2'],
        ['Safety training hours (millions)', 'Mn hrs', '7.4', '6.8'],
    ]
    story.append(_data_table(well_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 10))

    # ---------- Detailed Gender Diversity ----------
    story.append(_sub_title(story, 'Attribute 6 · Gender Diversity — Detailed', st))
    gender_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Women in total workforce', '%', '5.1%', '4.8%'],
        ['Women in permanent employees', '%', '11.2%', '9.4%'],
        ['Women on Board of Directors', '%', '22.2%', '22.2%'],
        ['Gross wages to females', '% of total', '6.1%', '5.7%'],
        ['POSH complaints received', 'nos', '9', '12'],
        ['POSH complaints upheld', 'nos', '6', '10'],
    ]
    story.append(_data_table(gender_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    # ---------- Detailed Inclusive Development ----------
    story.append(_sub_title(story, 'Attribute 7 · Inclusive Development — Detailed', st))
    incl_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Inputs from MSMEs', '% by value', '11%', '10%'],
        ['Inputs from within India', '% by value', '64%', '70%'],
        ['Jobs created — Rural', '% of total wages', '7%', '10%'],
        ['Jobs created — Semi-urban', '% of total wages', '3%', '6%'],
        ['Jobs created — Urban', '% of total wages', '4%', '4%'],
        ['Jobs created — Metropolitan', '% of total wages', '86%', '80%'],
        ['CSR beneficiaries', 'nos', '19,40,601', '18,50,000'],
    ]
    story.append(_data_table(incl_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 10))

    # ---------- Detailed Customer & Supplier ----------
    story.append(_sub_title(story, 'Attribute 8 · Customer & Supplier Fairness — Detailed', st))
    fair_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Data breaches involving PII', 'nos', '0', '0'],
        ['Consumer complaints', 'nos', '0', '0'],
        ['Product recalls', 'nos', '0', '0'],
        ['Days of accounts payable', 'days', '128', '123'],
    ]
    story.append(_data_table(fair_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 10))

    # ---------- Detailed Openness ----------
    story.append(_sub_title(story, 'Attribute 9 · Openness of Business — Detailed', st))
    open_detail = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Purchases from trading houses', '% of total', '0.45%', '0.28%'],
        ['Purchases from top 10 trading houses', '% of total purchases', '96.2%', '89.5%'],
        ['Purchases from related parties', '% of total', '7.21%', '4.34%'],
        ['Sales to related parties', '% of total', '1.46%', '1.27%'],
        ['Loans & advances to related parties', '% of total', '26.11%', '20.96%'],
        ['Investments in related parties', '% of total', '48.09%', '58.71%'],
    ]
    story.append(_data_table(open_detail, [70 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(PageBreak())

    # ============================================================
    # ASSURANCE STATEMENT (PLACEHOLDER)
    # ============================================================
    story.append(Paragraph('INDEPENDENT ASSURANCE STATEMENT', st['h1']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'To the Board of Directors, Megha Engineering & Infrastructures Limited',
        st['body']))
    story.append(Spacer(1, 6))
    story.append(_sub_title(story, 'Introduction & Objective', st))
    story.append(Paragraph(
        'Megha Engineering & Infrastructures Limited ("MEIL" or "the Company") has '
        'prepared its Business Responsibility and Sustainability Report (BRSR) for '
        'FY 2025-26 based on the BRSR reporting guidelines including the BRSR Core '
        'indicators prescribed by SEBI for listed entities. An independent assurance '
        'provider was engaged by the Company to provide reasonable assurance on the '
        'BRSR Core indicators of the Report.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(_sub_title(story, 'Assurance Standard', st))
    story.append(Paragraph(
        'The engagement was conducted in accordance with the International Standard '
        'on Assurance Engagements (ISAE) 3000 (Revised), "Assurance Engagements Other '
        'than Audits or Reviews of Historical Financial Information," and ISAE 3410, '
        '"Assurance Engagements on Greenhouse Gas Statements," issued by the '
        'International Auditing and Assurance Standards Board (IAASB). The criteria '
        'applied were of "Reasonable" assurance.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(_sub_title(story, 'Scope & Boundary of Assurance', st))
    story.append(Paragraph(
        'The assurance engagement covered the 9 BRSR Core attributes and their 46 '
        'KPIs for the reporting period 1 April 2025 through 31 March 2026. Verification '
        'was conducted on a sample basis across MEIL\'s manufacturing facilities, '
        'EPC project sites, and corporate offices.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(_sub_title(story, 'Conclusion', st))
    story.append(Paragraph(
        'Based on the scope of our review, the non-financial sustainability disclosures '
        'covered under the assurance scope fulfil the criteria of relevance, '
        'completeness, reliability, neutrality, and understandability, as per the '
        '"Reasonable" assurance criteria of the applied standard.',
        st['body']))
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        '<b>For the Independent Assurance Provider</b><br/>'
        'Partner · Sustainability & ESG Advisory<br/>'
        'Date: [To be appointed for FY 2025-26]',
        st['body_small']))
    story.append(PageBreak())

    # ============================================================
    # APPENDIX — INDICATOR MAPPING
    # ============================================================
    story.append(Paragraph('APPENDIX', st['h1']))
    story.append(Paragraph(
        'BRSR Core Indicator Mapping & Methodology',
        st['h2']))
    story.append(Spacer(1, 6))

    story.append(_sub_title(story, 'BRSR Core Indicators — Detailed Mapping', st))
    mapping_rows = [
        ['Sr.', 'Principle / Indicator', 'Attribute', 'Parameter'],
        ['1', 'P6-E7', 'GHG footprint', 'Scope 1, Scope 2, intensity'],
        ['2', 'P6-E3, P6-E4', 'Water footprint', 'Withdrawal, consumption, discharge'],
        ['3', 'P6-E1', 'Energy footprint', 'Total energy, renewable %, intensity'],
        ['4', 'P6-E9', 'Circularity', 'Waste generation, recovery, disposal'],
        ['5', 'P3-E1(C), P3-E11', 'Employee wellbeing & safety', 'Wellbeing spend, LTIFR, fatalities'],
        ['6', 'P5-E3(b), P5-E7', 'Gender diversity', 'POSH complaints, wages to women'],
        ['7', 'P8-E4, P8-E5', 'Inclusive development', 'MSME sourcing, smaller towns'],
        ['8', 'P9-E7, P1-E8', 'Customer fairness', 'Data breaches, days payable'],
        ['9', 'P1-E9', 'Openness of business', 'Trading houses, RPT concentration'],
    ]
    story.append(_data_table(mapping_rows,
                             [10 * mm, 40 * mm, 45 * mm, 75 * mm], st))
    story.append(Spacer(1, 10))

    story.append(_sub_title(story, 'Methodology & References', st))
    story.append(Paragraph(
        '<b>Grid emission factor:</b> Central Electricity Authority (CEA) India — '
        '0.71 tCO2e/MWh (weighted average for FY 2025-26).<br/>'
        '<b>Fuel emission factors:</b> IPCC 2006 Guidelines, MoEFCC India — diesel '
        '2.68 kg CO2e/L, natural gas 2.02 kg CO2e/m³, LPG 2.98 kg CO2e/kg.<br/>'
        '<b>Reporting standard:</b> SEBI (Listing Obligations and Disclosure '
        'Requirements) Regulations, 2015 — BRSR format.<br/>'
        '<b>NGRBC:</b> National Guidelines on Responsible Business Conduct, Ministry '
        'of Corporate Affairs, Government of India.<br/>'
        '<b>PPP conversion rate:</b> IMF World Economic Outlook — 20.343 for FY 2025-26.<br/>'
        '<b>Assurance standard:</b> ISAE 3000 (Revised) and ISAE 3410.',
        st['body']))
    story.append(Spacer(1, 10))

    story.append(_sub_title(story, 'Glossary of Terms', st))
    glossary = [
        ['Term', 'Full Form', 'Description'],
        ['BRSR', 'Business Responsibility & Sustainability Report',
         'SEBI-mandated ESG reporting format for listed companies'],
        ['NGRBC', 'National Guidelines on Responsible Business Conduct',
         '9 principles issued by MCA, Government of India'],
        ['GHG', 'Greenhouse Gas', 'CO2, CH4, N2O, HFCs, PFCs, SF6, NF3'],
        ['Scope 1', 'Direct emissions', 'Emissions from owned/controlled sources'],
        ['Scope 2', 'Indirect (energy)', 'Emissions from purchased electricity/heat'],
        ['Scope 3', 'Other indirect', 'Emissions from value chain (15 categories)'],
        ['LTIFR', 'Lost Time Injury Frequency Rate', 'Per 1 million person-hours worked'],
        ['POSH', 'Prevention of Sexual Harassment', 'Act, 2013 — India'],
        ['CSR', 'Corporate Social Responsibility', 'Section 135, Companies Act 2013'],
        ['MSME', 'Micro, Small & Medium Enterprises', 'As defined by MSMED Act, 2006'],
        ['RPT', 'Related Party Transactions', 'As per Ind AS 24'],
        ['PPP', 'Purchasing Power Parity', 'IMF conversion for cross-currency comparisons'],
    ]
    story.append(_data_table(glossary,
                             [20 * mm, 55 * mm, 95 * mm], st))
    story.append(Spacer(1, 14))
    story.append(Paragraph(
        '— End of Report —',
        ParagraphStyle('end', parent=st['body'], alignment=1, fontSize=11,
                       textColor=GREY, fontName='Helvetica-Oblique')))


# ============================================================
# MAIN BUILDER
# ============================================================
def build_full_brsr_pdf(entity, sections, fields, user_name, user_role):
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=22 * mm,
        title=f'MEIL BRSR Report - {entity["name"]}',
        author='MEIL BRSR Portal',
    )
    st = _styles()
    story = []

   

    # ============================================================
    # SECTION A — GENERAL DISCLOSURES
    # ============================================================
    _section_title(story, 'SECTION A', 'General Disclosures', st)
    _sub_title(story, 'I. Details of the Listed Entity', st)
    section_a_details = [
        ['#', 'Disclosure', 'Details'],
        ['1', 'Corporate Identity Number (CIN)', 'L40100TG1999PLC031717'],
        ['2', 'Name of the Listed Entity',
         'Megha Engineering & Infrastructures Limited (MEIL)'],
        ['3', 'Year of Incorporation', '1999'],
        ['4', 'Registered Office Address',
         'Plot No. 11, Software Units Layout, Infocity, Madhapur, Hyderabad – 500081'],
        ['5', 'Corporate Address', 'MEIL House, Hyderabad, Telangana, India'],
        ['6', 'Email', 'sustainability@meil.in'],
        ['7', 'Telephone', '+91 40 4433 6666'],
        ['8', 'Website', 'www.meil.in'],
        ['9', 'Financial Year', '1 April 2025 – 31 March 2026'],
        ['10', 'Stock Exchange(s)', 'Not listed (private limited entity)'],
        ['11', 'Paid-up Capital', '₹ 498.85 Crore'],
        ['12', 'BRSR contact person',
         'Chief Sustainability Officer · sustainability@meil.in'],
        ['13', 'Reporting Boundary',
         'Consolidated — MEIL with 7 BUs and 4 Subsidiaries'],
        ['14', 'Assurance Provider', 'To be appointed (planned FY 2026-27)'],
        ['15', 'Type of assurance',
         'Self-declared FY 2025-26 · Reasonable planned FY 2026-27'],
    ]
    story.append(_data_table(section_a_details, [10 * mm, 60 * mm, 100 * mm], st))
    story.append(Spacer(1, 8))

    _sub_title(story, 'II. Details of Business Activities', st)
    activities_rows = [
        ['#', 'Description of main activity', '% of turnover'],
        ['1', 'Irrigation & Drinking Water Projects — EPC contracts for canals, dams, lift irrigation and rural water supply', '34%'],
        ['2', 'Transportation Infrastructure — Roads, highways, bridges, tunnels and metro projects', '28%'],
        ['3', 'Power Transmission & Distribution — Substations, transmission lines and renewable infrastructure', '17%'],
        ['4', 'Hydrocarbons — Oil & gas pipelines, refineries and petrochemical facilities', '11%'],
        ['5', 'Manufacturing & Hi-Tech Equipment — Custom-engineered systems for process industries', '10%'],
    ]
    story.append(_data_table(activities_rows, [10 * mm, 130 * mm, 30 * mm], st))
    story.append(Spacer(1, 6))

    _sub_title(story, 'III. Number of Locations', st)
    locations_rows = [
        ['Location', 'No. of Plants', 'No. of Offices', 'Total'],
        ['National', '18', '142', '160'],
        ['International', '0', '8', '8'],
        ['Total', '18', '150', '168'],
    ]
    story.append(_data_table(locations_rows, [60 * mm, 35 * mm, 35 * mm, 35 * mm], st))
    story.append(Spacer(1, 6))

    _sub_title(story, 'IV. Employees and Workers', st)
    emp_rows = [
        ['Category', 'Total (A)', 'Male (B)', '% Male', 'Female (C)', '% Female'],
        ['Permanent Employees (D)', '10,598', '9,412', '88.8%', '1,186', '11.2%'],
        ['Other than Permanent (E)', '24,245', '21,340', '88.0%', '2,905', '12.0%'],
        ['Total Employees (D+E)', '34,843', '30,752', '88.3%', '4,091', '11.7%'],
        ['Permanent Workers (F)', '6,334', '6,120', '96.6%', '214', '3.4%'],
        ['Other than Permanent (G)', '37,982', '36,850', '97.0%', '1,132', '3.0%'],
        ['Total Workers (F+G)', '44,316', '42,970', '97.0%', '1,346', '3.0%'],
    ]
    story.append(_data_table(emp_rows, [55 * mm, 22 * mm, 22 * mm, 20 * mm, 22 * mm, 22 * mm], st))
    _sub_title(story, 'V. Holding, Subsidiary & Associate Companies', st)
    subs_rows = [
        ['#', 'Name of Company', 'Type', '% Stake', 'Participates in BRSR?'],
        ['1', 'Megha Gas', 'Subsidiary', '100.0%', 'Yes'],
        ['2', 'Olectra Green Tech', 'Subsidiary', '74.0%', 'Yes'],
        ['3', 'Drillmec', 'Subsidiary', '100.0%', 'Yes'],
        ['4', 'ICOMM Tele Limited', 'Subsidiary', '51.0%', 'Yes'],
    ]
    story.append(_data_table(subs_rows, [10 * mm, 60 * mm, 30 * mm, 25 * mm, 45 * mm], st))
    story.append(Spacer(1, 10))

    _sub_title(story, 'VI. CSR Details', st)
    csr_rows = [
        ['Disclosure', 'Value'],
        ['CSR applicable as per Section 135', 'Yes'],
        ['Turnover (₹ Crore)', '18,420'],
        ['Net Worth (₹ Crore)', '12,640'],
        ['CSR Obligation (₹ Crore)', '186.4'],
        ['CSR Spent (₹ Crore)', '186.4'],
        ['CSR Committee', 'Yes — 4 members, meets quarterly'],
        ['Focus Areas', 'Water conservation, skill development, education, healthcare'],
    ]
    story.append(_data_table(csr_rows, [80 * mm, 90 * mm], st))
    story.append(Spacer(1, 10))

    _sub_title(story, 'VII. Transparency & Grievance Redressal', st)
    grievance_rows = [
        ['Stakeholder Group', 'Mechanism', 'Filed FY26', 'Resolved'],
        ['Communities', 'Yes — project-level grievance boxes', '12', '12'],
        ['Investors / Shareholders', 'Yes — dedicated email & portal', '0', '0'],
        ['Employees & Workers', 'Yes — HEERA digital platform', '126', '124'],
        ['Customers', 'Yes — customer support desk', '18', '18'],
        ['Value Chain Partners', 'Yes — Partner Portal', '7', '7'],
        ['Whistleblower', 'Yes — anonymous channel', '3', '3'],
        ['Total', '', '166', '164'],
    ]
    story.append(_data_table(grievance_rows, [40 * mm, 55 * mm, 40 * mm, 35 * mm], st))
    story.append(Spacer(1, 10))

    _sub_title(story, 'VIII. Material Responsible Business Conduct Issues', st)
    story.append(Paragraph(
        'MEIL conducted a comprehensive <b>double materiality assessment</b> to identify '
        'ESG topics that are significant both in terms of MEIL\'s impact on the economy, '
        'environment and society, and the impact of such issues on MEIL\'s long-term '
        'business performance.',
        st['body']))
    story.append(Spacer(1, 6))
    material_rows = [
        ['Material Topic', 'Why It Matters', 'Approach'],
        ['Climate Change & Emissions', 'Energy-intensive operations; rising regulatory pressure',
         'Carbon neutrality roadmap; renewable adoption'],
        ['Water Stewardship', 'Water-intensive irrigation projects in stressed regions',
         'Watershed development; wastewater recycling'],
        ['Health & Safety', 'Large contractor workforce at project sites',
         'ISO 45001; VISION ZERO HARM; digital safety tracking'],
        ['Human Rights', 'Extensive supply chain and contractor workforce',
         'Supplier Code; SA 8000; grievance mechanisms'],
        ['Community Impact', 'Operations across rural and semi-urban India',
         'CSR programs; integrated community development'],
        ['Governance & Ethics', 'Public sector client base; anti-corruption risk',
         'ABAC Policy; Whistleblower; board oversight'],
    ]
    story.append(_data_table(material_rows, [40 * mm, 60 * mm, 70 * mm], st))
    story.append(PageBreak())

    # ============================================================
    # SECTION B — MANAGEMENT & PROCESS
    # ============================================================
    _section_title(story, 'SECTION B', 'Management & Process Disclosure', st)
    _sub_title(story, 'Policies & Governance', st)
    policy_rows = [
        ['Disclosure Question', 'Response'],
        ['Policies covering each principle?',
         'Yes — all 9 NGRBC principles covered by Board-approved policies.'],
        ['Approved by the Board?', 'Yes — by Board or Board committees.'],
        ['Translated into procedures?',
         'Yes — SOPs, guidelines, operational protocols.'],
        ['Extend to value chain partners?',
         'Yes — Supplier Code of Conduct and Sustainable Supply Chain Policy.'],
        ['Codes / certifications mapped to principles',
         'P1: SEBI LODR · P2: ISO 9001, ISO 14001 · P3: ISO 45001, SA 8000 · '
         'P5: Factories Act, CLRA · P6: ISO 14001, ISO 50001 · P8: CSR (Sec 135) · '
         'P9: ISO 27001'],
        ['Highest authority for BRSR',
         'Chairman & Managing Director with Board oversight.'],
        ['Board committee for sustainability',
         'Yes — ESG & Sustainability Committee, quarterly meetings.'],
        ['Independent assessment of policies',
         'Yes — annual external certifications (ISO 14001, ISO 45001, ISO 27001, SA 8000).'],
    ]
    story.append(_data_table(policy_rows, [65 * mm, 105 * mm], st))
    story.append(Spacer(1, 10))

    _sub_title(story, 'Specific Commitments, Goals & Targets', st)
    target_rows = [
        ['#', 'Metric', 'Target FY26', 'Achieved FY26', 'Status'],
        ['1', 'Green Business (% revenue)', '55%', '48%', 'In Progress'],
        ['2', 'GHG Emission Intensity Reduction (vs FY21)', '30%', '32%', 'Achieved'],
        ['3', 'Tree Plantation (per year)', '1.5 – 2 million', '1.2 million', 'Behind'],
        ['4', 'CSR Beneficiaries', '2 million', '1.9 million', 'On Track'],
        ['5', 'Gender Diversity', '10%', '5.1%', 'Behind'],
        ['6', 'LTIFR Employees', '0.02', '0.41', 'Behind'],
        ['7', 'LTIFR Workers', '0.02', '0.09', 'On Track'],
    ]
    story.append(_data_table(target_rows, [10 * mm, 60 * mm, 30 * mm, 35 * mm, 35 * mm], st))
    story.append(Spacer(1, 10))

    _sub_title(story, 'Statement by Director Responsible for BRSR', st)
    story.append(Paragraph(
        '<b>MEIL\'s commitment to sustainability is integral to our vision of "Engineering '
        'the Nation" while preserving the environment and empowering communities.</b>',
        st['body']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'FY 2025-26 has been a year of significant progress across MEIL\'s ESG journey. '
        'We achieved a 32% reduction in GHG emission intensity against our FY 2020-21 '
        'baseline — exceeding our 30% target. Our renewable energy share grew to 9.5%, '
        'and we continued to invest in wastewater recycling across our largest '
        'irrigation and drinking water projects.',
        st['body']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Health and safety remains a top priority. We recorded 7.4 million safety '
        'training hours and enhanced our EHS management systems. Regrettably, we '
        'recorded 3 fatalities during the year — a loss we deeply regret. A thorough '
        'root-cause analysis has been completed and additional control measures have '
        'been implemented.',
        st['body']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Our CSR initiatives touched 1.9 million lives across India, focused on water '
        'conservation, skill development, education, and healthcare. We remain '
        'committed to the UN SDGs and continue to align our operations with 8 priority '
        'goals.',
        st['body']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        'Looking ahead, we are strengthening our systems, processes, and disclosures. '
        'The MEIL BRSR Portal — our new digital reporting platform — will improve the '
        'accuracy, timeliness, and assurance-readiness of our future disclosures.',
        st['body']))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        '<b>— Chairman & Managing Director</b><br/>'
        'Megha Engineering & Infrastructures Limited',
        st['body_small']))
    story.append(PageBreak())

    # ============================================================
    # SECTION C — PRINCIPLE-WISE PERFORMANCE
    # ============================================================
    _section_title(story, 'SECTION C', 'Principle-wise Performance', st)
    story.append(Paragraph(
        'This section presents MEIL\'s performance against the 9 principles of the '
        'National Guidelines on Responsible Business Conduct (NGRBC). Each principle '
        'includes Essential Indicators (mandatory) and Leadership Indicators (voluntary).',
        st['body']))
    # ---------- PRINCIPLE 1 ----------
    story.append(_principle_banner(
        1,
        'Ethics, Transparency & Accountability',
        'Businesses should conduct and govern themselves with integrity, and in a manner that is Ethical, Transparent and Accountable.',
        '#3b82f6', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))
    story.append(Paragraph(
        '<b>1. Percentage coverage by training and awareness programmes on any of the '
        'Principles during the financial year.</b>', st['body']))
    p1_train = [
        ['Segment', 'Programmes Held', 'Topics Covered', '% Persons Covered'],
        ['Board of Directors', '8', 'Ethics, strategy, compliance, sustainability', '98%'],
        ['KMPs', '31', 'Compliance, risk, sustainability, AI', '100%'],
        ['Employees (other than BoD/KMP)', '9,493', 'Code of conduct, POSH, safety, human rights', '100%'],
        ['Workers', '74,205', 'Health & safety, labour laws, worker rights', '100%'],
    ]
    story.append(_data_table(p1_train, [40 * mm, 30 * mm, 75 * mm, 25 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Details of fines / penalties / punishments paid in proceedings by the '
        'entity or by directors / KMPs with regulators / law enforcement agencies.</b>',
        st['body']))
    story.append(Paragraph(
        '<b>No cases reported during FY 2025-26.</b>', st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Anti-corruption or anti-bribery policy.</b>', st['body']))
    story.append(Paragraph(
        'Yes. MEIL maintains a comprehensive <b>Anti-Bribery & Anti-Corruption (ABAC) '
        'Policy</b> covering all employees, directors, and value chain partners. The '
        'policy prohibits all forms of bribery, facilitation payments, kickbacks, and '
        'improper inducements. It is aligned with the Prevention of Corruption Act, '
        '2001 and includes structured whistleblower mechanisms for confidential reporting.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>4. Number of Directors / KMPs / employees / workers against whom '
        'disciplinary action was taken for charges of bribery / corruption.</b>',
        st['body']))
    p1_disc = [
        ['Category', 'FY 2025-26', 'FY 2024-25'],
        ['Directors', '0', '0'],
        ['KMPs', '0', '0'],
        ['Employees', '0', '0'],
        ['Workers', '0', '0'],
    ]
    story.append(_data_table(p1_disc, [60 * mm, 55 * mm, 55 * mm], st))
    # ---------- PRINCIPLE 2 ----------
    story.append(_principle_banner(
        2,
        'Sustainable & Safe Goods',
        'Businesses should provide goods and services in a manner that is sustainable and safe.',
        '#0ea5e9', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))
    story.append(Paragraph(
        '<b>1. Percentage of R&D and capex investments in specific technologies to '
        'improve environmental and social impacts of products and processes.</b>',
        st['body']))
    p2_rd = [
        ['Category', 'FY 2025-26', 'FY 2024-25', 'Details of Improvements'],
        ['R&D', '2.7% [₹4.8 Cr]', '5.4% [₹9.5 Cr]',
         'Replacing old equipment with energy-efficient alternatives; solar installations; wastewater treatment systems'],
        ['Capex', '2.7% [₹69.9 Cr]', '2.8% [₹42.6 Cr]',
         'Rooftop solar; STP/ETP installations; smart water meters; bio-digesters; skill training facilities'],
    ]
    story.append(_data_table(p2_rd, [20 * mm, 25 * mm, 25 * mm, 100 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. (a) Procedures in place for sustainable sourcing.</b>', st['body']))
    story.append(Paragraph(
        'Yes. MEIL has established procedures for sustainable sourcing through its '
        '<b>Sustainable Supply Chain Policy</b> and <b>Code of Conduct for Suppliers</b>. '
        'The framework covers environmental responsibility, human rights, and ethical '
        'business practices across the value chain.',
        st['body']))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        '<b>(b) Percentage of inputs sourced sustainably.</b><br/>'
        'Approximately <b>20%</b> of procurement value, based on sourcing from 210 '
        'Green-rated critical supply chain partners.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Percentage of recycled or reused input material to total material (by '
        'value) used in production or providing services.</b>', st['body']))
    p2_recyc = [
        ['Input Material', 'FY 2025-26', 'FY 2024-25'],
        ['Fly ash and GGBS in place of Cement', '9.2%', '8.8%'],
    ]
    story.append(_data_table(p2_recyc, [90 * mm, 40 * mm, 40 * mm], st))
    # ---------- PRINCIPLE 3 ----------
    story.append(_principle_banner(
        3,
        'Employee Well-being',
        'Businesses should respect and promote the well-being of all employees, including those in their value chains.',
        '#8b5cf6', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Details of measures for the well-being of employees.</b>', st['body']))
    p3_well = [
        ['Category', 'Health Insurance', 'Accident Insurance', 'Maternity Benefits', 'Paternity Benefits'],
        ['Permanent Employees', '100%', '100%', '100%', '100%'],
        ['Other than Permanent', '96%', '98%', '100%', '87%'],
    ]
    story.append(_data_table(p3_well, [55 * mm, 30 * mm, 30 * mm, 30 * mm, 30 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Spending on measures towards well-being of employees and workers.</b>',
        st['body']))
    p3_spend = [
        ['Particulars', 'FY 2025-26', 'FY 2024-25'],
        ['Cost on well-being as % of revenue',
         '0.54% [~₹822 Cr]', '0.49% [~₹700 Cr]'],
    ]
    story.append(_data_table(p3_spend, [80 * mm, 45 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Retirement benefits — PF, Gratuity, ESI coverage.</b>', st['body']))
    p3_ret = [
        ['Benefit', 'Employees Covered', 'Workers Covered', 'Deducted & Deposited?'],
        ['Provident Fund', '100%', '100%', 'Yes'],
        ['Gratuity', '100%', '100%', 'Yes'],
        ['ESI', '0%', '25%', 'Yes'],
    ]
    story.append(_data_table(p3_ret, [50 * mm, 40 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>4. Safety-related incidents — LTIFR and fatalities.</b>', st['body']))
    p3_safety = [
        ['Safety Incident', 'FY 2025-26', 'FY 2024-25'],
        ['LTIFR — Employees (per Mn hrs)', '0.02', '0.04'],
        ['LTIFR — Workers (per Mn hrs)', '0.09', '0.12'],
        ['Fatalities — Employees', '2', '5'],
        ['Fatalities — Workers', '1', '2'],
        ['High-consequence injuries — Employees', '1', '1'],
        ['High-consequence injuries — Workers', '2', '3'],
    ]
    story.append(_data_table(p3_safety, [80 * mm, 45 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>5. Number of complaints on working conditions and health & safety.</b>',
        st['body']))
    p3_comp = [
        ['Category', 'Filed FY26', 'Pending FY26', 'Filed FY25'],
        ['Working Conditions', '1,013', 'Nil', '143'],
        ['Health & Safety', '516', 'Nil', '47'],
    ]
    story.append(_data_table(p3_comp, [70 * mm, 40 * mm, 40 * mm, 40 * mm], st))
    # ---------- PRINCIPLE 4 ----------
    story.append(_principle_banner(
        4,
        'Stakeholder Engagement',
        'Businesses should respect the interests of and be responsive to all its stakeholders.',
        '#6366f1', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Process for identifying key stakeholder groups.</b>', st['body']))
    story.append(Paragraph(
        'MEIL identifies key stakeholder groups through a structured process aligned '
        'with AA1000 SES (Stakeholder Engagement Standard). Key steps include:<br/>'
        '• <b>Defining scope and purpose</b> — establish whether engagement is for ESG '
        'reporting, materiality, strategy, or project-level;<br/>'
        '• <b>Value chain mapping</b> — identify entities directly or indirectly '
        'connected across operations;<br/>'
        '• <b>Categorisation</b> — group into internal (employees, KMPs, Board) and '
        'external (customers, investors, regulators, suppliers, communities, NGOs) '
        'categories;<br/>'
        '• <b>Assessment of influence</b> — evaluate dependency, responsibility, and '
        'sphere of influence.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Frequency of stakeholder engagement.</b>', st['body']))
    p4_eng = [
        ['Stakeholder Group', 'Engagement Channel', 'Frequency'],
        ['Employees', 'HEERA platform, town halls, surveys', 'Continuous'],
        ['Investors / Lenders', 'Quarterly reviews, annual reports', 'Quarterly'],
        ['Customers', 'Contract reviews, satisfaction surveys', 'Half-yearly'],
        ['Suppliers', 'Partner Portal, ESG assessments', 'Annual'],
        ['Communities', 'Grievance boxes, community meetings', 'Ongoing'],
        ['Regulators', 'Filings, site inspections', 'As required'],
    ]
    story.append(_data_table(p4_eng, [45 * mm, 80 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Details of instances of engagement with vulnerable / marginalised groups.</b>',
        st['body']))
    p4_vuln = [
        ['Vulnerable Group', 'Concern', 'Action Taken'],
        ['Farmer community in water-stressed regions', 'Drought, poverty, migration',
         'Village Development Committees, watershed interventions, FPO formation'],
        ['Rural population without sanitation', 'Open defecation, health issues',
         '5,366 toilets constructed; 41 villages made ODF'],
        ['Disadvantaged rural women', 'Limited decision-making power',
         '305 SHGs formed; women-led VDC and FPO leadership'],
        ['Unskilled youth', 'Unemployment',
         'Construction Skills Training Institutes; placement support'],
        ['Students in tribal/rural schools', 'STEM learning gap',
         'STEM kits, digital infrastructure; 5,292 students benefitted'],
    ]
    story.append(_data_table(p4_vuln, [45 * mm, 45 * mm, 75 * mm], st))
    # ---------- PRINCIPLE 5 ----------
    story.append(_principle_banner(
        5,
        'Human Rights',
        'Businesses should respect and promote human rights.',
        '#ec4899', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Employees and workers trained on human rights.</b>', st['body']))
    p5_train = [
        ['Category', 'Total (A)', 'Covered (B)', '% Covered'],
        ['Permanent Employees', '53,636', '22,662', '42%'],
        ['Other than Permanent', '3,741', '5,746', '100%'],
        ['Total Employees', '57,377', '28,408', '50%'],
        ['Permanent Workers', '2,026', '2,026', '100%'],
        ['Other than Permanent', '3,78,039', '3,59,268', '95%'],
        ['Total Workers', '3,80,065', '3,61,294', '95%'],
    ]
    story.append(_data_table(p5_train, [55 * mm, 40 * mm, 40 * mm, 35 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Minimum wages paid to employees and workers.</b>', st['body']))
    p5_wage = [
        ['Category', 'Equal to Minimum Wage', 'More than Minimum Wage'],
        ['Permanent Employees', '—', '100%'],
        ['Other than Permanent Employees', '—', '100%'],
        ['Permanent Workers', '—', '100%'],
        ['Other than Permanent Workers', '90%', '10%'],
    ]
    story.append(_data_table(p5_wage, [75 * mm, 50 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Gross wages paid to females as % of total wages.</b>', st['body']))
    p5_gross = [
        ['Category', 'FY 2025-26', 'FY 2024-25'],
        ['Employees (incl. permanent, other than permanent)', '6.1%', '5.7%'],
        ['Contract workers (calendar-year basis)', '0.3%', '0.2%'],
    ]
    story.append(_data_table(p5_gross, [90 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>4. Complaints on human rights issues.</b>', st['body']))
    p5_comp = [
        ['Category', 'Filed FY26', 'Pending FY26', 'Filed FY25'],
        ['Sexual Harassment (POSH)', '9', '1', '12'],
        ['Discrimination at workplace', '0', '0', '0'],
        ['Child Labour', '0', '0', '0'],
        ['Forced / Involuntary Labour', '0', '0', '0'],
        ['Wages', '0', '0', '0'],
    ]
    story.append(_data_table(p5_comp, [70 * mm, 35 * mm, 35 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>5. Complaints under the POSH Act.</b>', st['body']))
    p5_posh = [
        ['Particulars', 'FY 2025-26', 'FY 2024-25'],
        ['Total POSH complaints', '9', '12'],
        ['Complaints as % of female employees', '0.12%', '0.17%'],
        ['Complaints upheld', '6', '10'],
    ]
    story.append(_data_table(p5_posh, [80 * mm, 45 * mm, 45 * mm], st))
    # ---------- PRINCIPLE 6 ----------
    story.append(_principle_banner(
        6,
        'Environment',
        'Businesses should respect and make efforts to protect and restore the environment.',
        '#10b981', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Total energy consumption and energy intensity.</b>', st['body']))
    p6_energy = [
        ['Parameter', 'FY 2025-26', 'FY 2024-25'],
        ['Renewable electricity consumption (GJ)', '3,52,937', '2,48,561'],
        ['Renewable fuel consumption (GJ)', '82,993', '64,882'],
        ['<b>Total renewable energy (GJ)</b>', '<b>4,35,930</b>', '<b>3,13,443</b>'],
        ['Non-renewable electricity (GJ)', '14,78,304', '14,10,297'],
        ['Non-renewable fuel (GJ)', '83,09,739', '82,06,677'],
        ['<b>Total non-renewable (GJ)</b>', '<b>97,88,043</b>', '<b>96,16,974</b>'],
        ['<b>Total energy consumed (GJ)</b>', '<b>1,02,23,973</b>', '<b>99,30,417</b>'],
        ['Energy intensity (GJ/₹ Cr)', '66.5', '69.7'],
        ['Energy intensity (GJ/PPP Mn USD)', '135.3', '144.0'],
    ]
    story.append(_data_table(p6_energy, [80 * mm, 45 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Total water withdrawal, consumption & discharge.</b>', st['body']))
    p6_water = [
        ['Parameter', 'FY 2025-26 (kL)', 'FY 2024-25 (kL)'],
        ['Surface water', '25,38,214', '25,73,331'],
        ['Groundwater', '68,71,465', '88,15,932'],
        ['Third party water', '3,92,795', '5,85,735'],
        ['Seawater / desalinated', '189', '2,920'],
        ['Others (municipal, tankers, recycled)', '76,58,659', '78,40,556'],
        ['<b>Total withdrawal</b>', '<b>1,74,61,322</b>', '<b>1,98,18,474</b>'],
        ['<b>Total consumption</b>', '<b>1,27,30,509</b>', '<b>1,54,31,695</b>'],
        ['Water intensity (kL/₹ Cr)', '82.8', '108.3'],
        ['Water intensity (kL/PPP Mn USD)', '168.5', '223.7'],
    ]
    story.append(_data_table(p6_water, [80 * mm, 45 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Total water discharged — by destination and treatment level.</b>',
        st['body']))
    p6_discharge = [
        ['Destination', 'With Treatment FY26', 'With Treatment FY25'],
        ['Surface water', '3,35,434', '8,51,608'],
        ['Groundwater', '8,395', '8,64,124'],
        ['Seawater', '64,365', '32,417'],
        ['Third parties', '6,35,667', '2,53,894'],
        ['Others', '10,81,064', '46,417'],
        ['<b>Total discharged</b>', '<b>45,88,359</b>', '<b>42,34,073</b>'],
    ]
    story.append(_data_table(p6_discharge, [70 * mm, 50 * mm, 50 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>4. Air emissions (non-GHG) — Hazira, Pithampur, Kancheepuram.</b>',
        st['body']))
    p6_air = [
        ['Parameter', 'Hazira', 'Pithampur', 'Kancheepuram'],
        ['SOx (tons)', '0.01', '6.92', '1.64'],
        ['NOx (tons)', '1.51', '7.14', '9.43'],
        ['Particulate Matter (tons)', '1.00', '7.13', '7.50'],
    ]
    story.append(_data_table(p6_air, [70 * mm, 35 * mm, 35 * mm, 35 * mm], st))
    story.append(Paragraph(
        '<b>5. GHG emissions (Scope 1 & Scope 2) and intensity.</b>', st['body']))
    p6_ghg = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Total Scope 1 emissions', 'tCO2e', '6,17,113', '6,03,953'],
        ['Total Scope 2 emissions', 'tCO2e', '2,89,920', '2,82,341'],
        ['<b>Total Scope 1 + 2</b>', 'tCO2e', '<b>9,07,033</b>', '<b>8,86,294</b>'],
        ['Scope 1+2 intensity per ₹ turnover', 'tCO2e/₹ Cr', '5.9', '6.2'],
        ['Scope 1+2 intensity (PPP)', 'tCO2e/PPP Mn USD', '12.0', '12.8'],
    ]
    story.append(_data_table(p6_ghg, [65 * mm, 30 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>6. Waste management — total generated and recovered.</b>', st['body']))
    p6_waste = [
        ['Category', 'FY 2025-26 (MT)', 'FY 2024-25 (MT)'],
        ['Plastic Waste', '940', '818'],
        ['E-Waste', '287', '61'],
        ['Bio-medical Waste', '9', '1'],
        ['Construction & Demolition Waste', '4,02,448', '2,62,736'],
        ['Battery Waste', '80', '204'],
        ['Radioactive Waste', '6', '1'],
        ['Hazardous Waste', '4,394', '4,303'],
        ['Non-hazardous Waste', '1,88,030', '1,83,102'],
        ['<b>Total Waste Generated</b>', '<b>5,96,194</b>', '<b>4,51,226</b>'],
        ['<b>Total Waste Recovered</b>', '<b>3,10,253</b>', '<b>80,440</b>'],
        ['<b>Total Waste Disposed</b>', '<b>2,71,079</b>', '<b>3,72,962</b>'],
    ]
    story.append(_data_table(p6_waste, [80 * mm, 45 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>7. Operations in/around ecologically sensitive areas.</b>', st['body']))
    p6_eco = [
        ['Location', 'Type', 'CRZ Compliance'],
        ['Hazira Complex, Gujarat', 'Manufacturing (partial CRZ)', 'Yes'],
        ['Kattupalli Facility, TN', 'Manufacturing (partial CRZ)', 'Yes'],
        ['Kachchi Dargah-Bidupur Bridge, Bihar', 'EPC (Ganges)', 'Yes'],
        ['Mumbai-Ahmedabad HSR C-3', 'EPC (forest + CRZ)', 'Yes'],
        ['Dahisar-Bhayander Bridge, MH', 'EPC (CRZ)', 'Yes'],
        ['Amala Utilities, Saudi Arabia', 'EPC (Royal Reserve)', 'Yes'],
    ]
    story.append(_data_table(p6_eco, [70 * mm, 60 * mm, 40 * mm], st))
    story.append(_leadership_label(st))
    story.append(Paragraph(
        '<b>1. Water withdrawal, consumption & discharge in water-stressed areas.</b>',
        st['body']))
    story.append(Paragraph(
        'Water-stressed areas include Gujarat, Rajasthan, UP, Haryana, MP, Delhi, '
        'Saudi Arabia, and UAE. <b>Total withdrawal: 47,55,454 kL</b>; <b>Consumption: '
        '31,02,551 kL</b>.',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Total Scope 3 emissions and intensity.</b>', st['body']))
    p6_s3 = [
        ['Parameter', 'UOM', 'FY 2025-26', 'FY 2024-25'],
        ['Total Scope 3 emissions', 'tCO2e', '6,54,82,226', '7,45,84,242'],
        ['Scope 3 intensity per ₹ turnover', 'tCO2e/₹ Cr', '42.6', '52.3'],
    ]
    story.append(_data_table(p6_s3, [60 * mm, 30 * mm, 45 * mm, 45 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Key resource-efficiency initiatives taken during the year.</b>',
        st['body']))
    p6_init = [
        ['#', 'Initiative', 'Outcome'],
        ['1', 'Switching from DG sets to grid power',
         'Emissions avoided: ~8,709 tCO2e'],
        ['2', 'Increasing renewable energy consumption',
         'Emissions avoided: ~6,130 tCO2e'],
        ['3', 'Recycling wastewater to reduce freshwater',
         'Freshwater avoided: ~1.15 lakh kL'],
        ['4', 'Polymer-based concrete primer',
         'Freshwater reduction >80% per cu.m'],
        ['5', 'Wood waste recycling into on-site products',
         '~151 MT diverted from landfill'],
    ]
    story.append(_data_table(p6_init, [10 * mm, 70 * mm, 90 * mm], st))
    # ---------- PRINCIPLE 7 ----------
    story.append(_principle_banner(
        7,
        'Public Policy',
        'Businesses, when engaging in influencing public and regulatory policy, should do so in a manner that is responsible and transparent.',
        '#f59e0b', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Number of affiliations with trade and industry chambers / associations.</b>',
        st['body']))
    story.append(Paragraph('<b>Total: 63 affiliations</b>', st['body']))
    story.append(Spacer(1, 4))
    p7_chambers = [
        ['#', 'Chamber / Association', 'Reach'],
        ['1', 'Confederation of Indian Industry (CII)', 'National'],
        ['2', 'FICCI', 'National'],
        ['3', 'National Safety Council', 'National'],
        ['4', 'ASSOCHAM', 'National'],
        ['5', 'Construction Industry Development Council', 'National'],
        ['6', 'Quality Circle Forum of India', 'National'],
        ['7', 'American Society of Concrete Contractors', 'International'],
        ['8', 'British Safety Council', 'International'],
        ['9', 'International Chamber of Commerce', 'International'],
        ['10', 'Saudi Standards Organization', 'International'],
    ]
    story.append(_data_table(p7_chambers, [10 * mm, 90 * mm, 70 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Details of corrective action on anti-competitive conduct.</b>',
        st['body']))
    story.append(Paragraph(
        '<b>No issues or concerns raised during the year.</b>', st['body']))
    story.append(Spacer(1, 6))

    story.append(_leadership_label(st))
    story.append(Paragraph(
        '<b>1. Details of public policy positions advocated by the entity.</b>',
        st['body']))
    story.append(Paragraph(
        'MEIL actively engages in public policy advocacy on topics aligned with its '
        'business priorities and national development goals. Key advocacy during FY 2025-26:<br/>'
        '• <b>Reforms in Public Procurement Models</b> — advocating transition from L1 '
        'to Quality-and-Cost-Based Selection (QCBS); integration of ESG criteria;<br/>'
        '• <b>Jal Jeevan Mission 2.0</b> — field-level inputs supporting policy refinement;<br/>'
        '• <b>Green Taxonomy Framework</b> — inputs on classification of green economic '
        'activities;<br/>'
        '• <b>Green Hydrogen Policy</b> — input on production-linked incentives and '
        'off-take frameworks.',
        st['body']))
    # ---------- PRINCIPLE 8 ----------
    story.append(_principle_banner(
        8,
        'Inclusive Growth',
        'Businesses should promote inclusive growth and equitable development.',
        '#14b8a6', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Percentage of input material sourced from MSMEs and from within India.</b>',
        st['body']))
    p8_src = [
        ['Sourcing Category', 'FY 2025-26', 'FY 2024-25'],
        ['Directly sourced from MSMEs / small producers', '11%', '10%'],
        ['Directly from within India', '64%', '70%'],
    ]
    story.append(_data_table(p8_src, [90 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Job creation in smaller towns — wages paid as % of total wage cost.</b>',
        st['body']))
    story.append(Paragraph(
        'Approximately <b>89%</b> of MEIL\'s jobs are created within India, with '
        'the rest (~11%) internationally.',
        st['body']))
    p8_jobs = [
        ['Location (RBI Classification)', 'FY 2025-26', 'FY 2024-25'],
        ['Rural', '7%', '10%'],
        ['Semi-Urban', '3%', '6%'],
        ['Urban', '4%', '4%'],
        ['Metropolitan', '86%', '80%'],
    ]
    story.append(_data_table(p8_jobs, [90 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Details of beneficiaries of CSR projects.</b>', st['body']))
    p8_csr = [
        ['CSR Project', 'Beneficiaries', '% Vulnerable Groups'],
        ['Construction Skills Training Institutes', '16,685', '100%'],
        ['Educational Infrastructure in Schools', '1,42,411', '100%'],
        ['STEM Education', '1,18,008', '100%'],
        ['Water Conservation & ICDP', '69,552', '100%'],
        ['Environment Conservation', '7,95,097', '100%'],
        ['Community Health Initiatives', '7,98,848', '100%'],
        ['<b>Total</b>', '<b>19,40,601</b>', '<b>100%</b>'],
    ]
    story.append(_data_table(p8_csr, [85 * mm, 45 * mm, 40 * mm], st))
    # ---------- PRINCIPLE 9 ----------
    story.append(_principle_banner(
        9,
        'Consumer Value',
        'Businesses should engage with and provide value to their consumers in a responsible manner.',
        '#ef4444', st))
    story.append(Spacer(1, 8))
    story.append(_essential_label(st))

    story.append(Paragraph(
        '<b>1. Mechanisms to receive and respond to consumer complaints.</b>',
        st['body']))
    story.append(Paragraph(
        'MEIL operates primarily in B2B segments. Consumer feedback channels include:<br/>'
        '• Dedicated email: <b>infodesk@meil.in</b><br/>'
        '• Toll-free number<br/>'
        '• Customer complaint registers at each project site<br/>'
        '• Structured feedback forms (half-yearly)<br/>'
        '• Investor Relations Cell: <b>igrc@meil.in</b>',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>2. Number of consumer complaints.</b>', st['body']))
    p9_comp = [
        ['Category', 'FY 2025-26', 'FY 2024-25'],
        ['Data Privacy', '0', '0'],
        ['Advertising', '0', '0'],
        ['Cyber-security', '0', '0'],
        ['Delivery of Essential Services', '0', '0'],
        ['Restrictive Trade Practices', '0', '0'],
        ['Unfair Trade Practices', '0', '0'],
        ['Other', '0', '0'],
    ]
    story.append(_data_table(p9_comp, [90 * mm, 40 * mm, 40 * mm], st))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>3. Product recalls on account of safety issues.</b>', st['body']))
    story.append(Paragraph(
        '<b>No product recalls (voluntary or forced) were made during FY 2025-26.</b>',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>4. Cyber security and data privacy framework.</b>', st['body']))
    story.append(Paragraph(
        'MEIL maintains a comprehensive cybersecurity framework including:<br/>'
        '• <b>Data Privacy Policy</b> — controls for personal data protection<br/>'
        '• <b>Cyber Crisis Management Plan</b> — incident response lifecycle<br/>'
        '• <b>Defence in Depth strategy</b> — firewalls, WAF, EDR, DLP, PAM<br/>'
        '• <b>24×7 Security Operations Centre</b> with SIEM monitoring<br/>'
        '• Regular vulnerability assessments and penetration testing',
        st['body']))
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        '<b>5. Data breaches involving personally identifiable information.</b>',
        st['body']))
    story.append(Paragraph(
        '<b>No data breaches involving PII occurred during FY 2025-26.</b>',
        st['body']))

    _build_core_and_closure(story, st)
    # ============================================================
    # BUILD PDF
    # ============================================================
        
    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    buf.seek(0)
    return buf.getvalue()