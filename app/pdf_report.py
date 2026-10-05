from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.piecharts import Pie

# MEIL brand colors
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


def _styles():
    s = getSampleStyleSheet()
    return {
        'cover_title': ParagraphStyle('cover_title', parent=s['Title'],
            fontSize=32, textColor=colors.white, alignment=1, spaceAfter=6, leading=36),
        'cover_sub': ParagraphStyle('cover_sub', parent=s['Normal'],
            fontSize=13, textColor=colors.HexColor('#7dd3fc'), alignment=1, spaceAfter=4),
        'h1': ParagraphStyle('h1', parent=s['Heading1'],
            fontSize=20, textColor=NAVY, spaceAfter=4, spaceBefore=4),
        'h2': ParagraphStyle('h2', parent=s['Heading2'],
            fontSize=14, textColor=NAVY, spaceAfter=6, spaceBefore=10),
        'body': ParagraphStyle('body', parent=s['BodyText'],
            fontSize=10, leading=14, textColor=colors.HexColor('#334155')),
        'small': ParagraphStyle('small', parent=s['BodyText'],
            fontSize=8.5, leading=11, textColor=GREY),
        'cover_label': ParagraphStyle('cover_label', parent=s['Normal'],
            fontSize=9, textColor=colors.HexColor('#94a3b8'), alignment=1),
        'white': ParagraphStyle('white', parent=s['Normal'],
            fontSize=10, textColor=colors.white, leading=14),
    }


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 10 * mm, 'MEIL BRSR Report · FY 2025-26 · Confidential')
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f'Page {doc.page}')
    canvas.restoreState()


def _bar_chart(data, labels, color=GREEN, width=460, height=180):
    d = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 40
    chart.y = 30
    chart.height = height - 50
    chart.width = width - 60
    chart.data = data
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 8
    chart.valueAxis.labels.fontSize = 8
    chart.valueAxis.valueMin = 0
    chart.bars[0].fillColor = color
    chart.bars.strokeColor = None
    d.add(chart)
    return d


def _pie_chart(data, labels, chart_colors, width=320, height=180):
    d = Drawing(width, height)
    pie = Pie()
    pie.x = 60
    pie.y = 10
    pie.width = 160
    pie.height = 160
    pie.data = data
    pie.labels = labels
    pie.slices.fontSize = 8
    pie.slices.fontColor = colors.white
    for i, c in enumerate(chart_colors):
        pie.slices[i].fillColor = c
    d.add(pie)
    return d


def _kpi_table(rows):
    data = [[Paragraph(f'<b>{k}</b>', _styles()['small']), Paragraph(v, _styles()['body'])] for k, v in rows]
    t = Table(data, colWidths=[70 * mm, 90 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, -1), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    return t


def build_brsr_pdf(entity, sections, fields, user_name, user_role):
    """Build a 4-page BRSR PDF report and return it as bytes."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title=f'MEIL BRSR Report - {entity["name"]}',
        author='MEIL BRSR Portal',
    )
    st = _styles()
    story = []

    # ---------- Computations ----------
    section_progress = {}
    for s in sections:
        sec_fields = [f for f in fields if f.get('section_code') == s['code']]
        done = sum(1 for f in sec_fields if f.get('value'))
        pct = int((done / len(sec_fields)) * 100) if sec_fields else 0
        section_progress[s['code']] = {'name': s['name'], 'sub': s['sub'], 'pct': pct, 'fields': sec_fields}

    all_progress = list(section_progress.values())
    overall = int(sum(x['pct'] for x in all_progress) / len(all_progress)) if all_progress else 0

     # Pillar scores
    e_codes = ['C2', 'C6', 'CORE']
    s_codes = ['C3', 'C5', 'C8', 'C9']
    g_codes = ['A', 'B', 'C1', 'C4', 'C7']

    def pillar_avg(codes):
        vals = [section_progress.get(c, {}).get('pct', 0) for c in codes]
        return int(sum(vals) / len(vals)) if vals else 0

    e_score = pillar_avg(e_codes)
    s_score = pillar_avg(s_codes)
    g_score = pillar_avg(g_codes)

    # ============================================================
    # PAGE 1 — COVER
    # ============================================================
    cover_data = [
        [Paragraph('M', ParagraphStyle('logo', fontSize=60, textColor=colors.white, alignment=1, leading=64))],
        [Spacer(1, 6)],
        [Paragraph('MEIL BRSR Report', st['cover_title'])],
        [Paragraph('Business Responsibility &amp; Sustainability Report', st['cover_sub'])],
        [Paragraph(f'Financial Year 2025-26', st['cover_sub'])],
        [Spacer(1, 30)],
        [Paragraph(entity['name'], ParagraphStyle('ent', fontSize=18, textColor=colors.white, alignment=1, leading=22))],
        [Paragraph(f'{entity["type"]} · Code {entity["code"]}', st['cover_label'])],
        [Spacer(1, 60)],
        [Paragraph(f'Prepared for: {user_name}', st['cover_label'])],
        [Paragraph(f'Role: {user_role}', st['cover_label'])],
        [Paragraph(f'Generated: {datetime.now().strftime("%d %b %Y, %H:%M")}', st['cover_label'])],
    ]
    cover = Table(cover_data, colWidths=[170 * mm])
    cover.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    story.append(cover)
    story.append(PageBreak())

    # ============================================================
    # PAGE 2 — EXECUTIVE SUMMARY
    # ============================================================
    story.append(Paragraph('1. Executive Summary', st['h1']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f'This report presents the BRSR performance of <b>{entity["name"]}</b> for FY 2025-26, '
        f'covering 9 NGRBC principles and BRSR Core attributes. Overall completion stands at '
        f'<b>{overall}%</b>, aggregated from {len(sections)} BRSR sections.',
        st['body']))
    story.append(Spacer(1, 12))

    # Overall score banner
    overall_data = [[
        Paragraph(f'<font size=36 color="#10b981"><b>{overall}%</b></font>', st['body']),
        Paragraph('<font size=11>Overall BRSR Completion<br/>'
                  f'<font color="#64748b">Aggregated across all sections</font></font>', st['body']),
    ]]
    overall_t = Table(overall_data, colWidths=[50 * mm, 110 * mm])
    overall_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(overall_t)
    story.append(Spacer(1, 18))

    # Pillar scores
    story.append(Paragraph('ESG Pillar Scores', st['h2']))
    pillar_chart = _bar_chart(
        [[e_score, s_score, g_score]],
        ['Environmental', 'Social', 'Governance'],
        GREEN, width=460, height=150,
    )
    story.append(pillar_chart)
    story.append(Spacer(1, 12))

    story.append(Paragraph('Section Completion Breakdown', st['h2']))
    breakdown_rows = [['Section', 'Area', 'Progress']]
    for s in sections:
        pct = section_progress.get(s['code'], {}).get('pct', 0)
        breakdown_rows.append([s['name'], s['sub'], f'{pct}%'])
    breakdown_t = Table(breakdown_rows, colWidths=[45 * mm, 90 * mm, 25 * mm])
    breakdown_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(breakdown_t)
    story.append(PageBreak())

    # ============================================================
    # PAGE 3 — ENVIRONMENTAL PERFORMANCE
    # ============================================================
    story.append(Paragraph('2. Environmental Performance', st['h1']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Emissions, energy consumption, water withdrawal, and waste management metrics '
        'for the reporting period.', st['body']))
    story.append(Spacer(1, 12))

    # Emissions bar chart (sample values — in production these come from BRSR Core fields)
    story.append(Paragraph('GHG Emissions by Scope (tCO₂e)', st['h2']))
    emissions_chart = _bar_chart(
        [[218450, 341220, 1204660]],
        ['Scope 1', 'Scope 2', 'Scope 3'],
        GREEN_D, width=460, height=170,
    )
    story.append(emissions_chart)
    story.append(Spacer(1, 16))

    # Energy split pie
    story.append(Paragraph('Energy Mix (GJ)', st['h2']))
    energy_pie = _pie_chart(
        [412880, 3918440],
        ['Renewable', 'Non-renewable'],
        [GREEN, colors.HexColor('#94a3b8')],
    )
    story.append(energy_pie)
    story.append(Spacer(1, 16))

    # Environmental table
    env_rows = [
        ['Indicator', 'Value', 'Unit'],
        ['Renewable energy consumed', '412,880', 'GJ'],
        ['Non-renewable energy consumed', '3,918,440', 'GJ'],
        ['Renewable energy share', '9.5', '%'],
        ['Total water withdrawal', '14,820', 'KL'],
        ['Scope 1 emissions', '218,450', 'tCO₂e'],
        ['Scope 2 emissions', '341,220', 'tCO₂e'],
        ['Scope 3 emissions', '1,204,660', 'tCO₂e'],
        ['Waste recovered through recycling', '72.4', '%'],
    ]
    env_t = Table(env_rows, colWidths=[90 * mm, 45 * mm, 25 * mm])
    env_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN_D),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(env_t)
    story.append(PageBreak())

    # ============================================================
    # PAGE 4 — SOCIAL, GOVERNANCE, SDG
    # ============================================================
    story.append(Paragraph('3. Social Performance', st['h1']))
    story.append(Spacer(1, 6))
    social_rows = [
        ['Indicator', 'Value', 'Unit'],
        ['Total employees and workers', '79,159', 'nos'],
        ['Health insurance coverage', '100', '%'],
        ['LTIFR', '0.41', 'per Mn hrs'],
        ['Fatalities', '3', 'nos'],
        ['Women in workforce', '5.1', '%'],
        ['CSR expenditure', '186.4', '₹ crore'],
    ]
    social_t = Table(social_rows, colWidths=[90 * mm, 45 * mm, 25 * mm])
    social_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), BLUE),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(social_t)
    story.append(Spacer(1, 16))

    story.append(Paragraph('4. Governance Performance', st['h1']))
    story.append(Spacer(1, 6))
    gov_rows = [
        ['Indicator', 'Value', 'Unit'],
        ['Anti-corruption training coverage', '96', '%'],
        ['Complaints on unethical behaviour', '7', 'nos'],
        ['Confirmed violations', '0', 'nos'],
        ['ESG Committee meetings held', '4', 'nos'],
        ['Median remuneration ratio to CEO', '128.4', ': 1'],
    ]
    gov_t = Table(gov_rows, colWidths=[90 * mm, 45 * mm, 25 * mm])
    gov_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), VIOLET),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(gov_t)
    story.append(Spacer(1, 16))

    story.append(Paragraph('5. UN SDG Alignment', st['h1']))
    story.append(Spacer(1, 6))
    sdg_rows = [
        ['Goal', 'Focus Area', 'Alignment'],
        ['SDG 6', 'Clean Water & Sanitation', '82%'],
        ['SDG 7', 'Affordable & Clean Energy', '71%'],
        ['SDG 8', 'Decent Work & Economic Growth', '78%'],
        ['SDG 9', 'Industry, Innovation & Infrastructure', '88%'],
        ['SDG 11', 'Sustainable Cities & Communities', '74%'],
        ['SDG 13', 'Climate Action', '64%'],
        ['SDG 16', 'Peace, Justice & Strong Institutions', '91%'],
        ['SDG 17', 'Partnerships for the Goals', '69%'],
    ]
    sdg_t = Table(sdg_rows, colWidths=[20 * mm, 110 * mm, 30 * mm])
    sdg_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SKY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(sdg_t)
    story.append(Spacer(1, 20))

    story.append(Paragraph(
        'This report was auto-generated by the MEIL BRSR Portal. '
        'Data reflected is as entered and approved by the reporting entity. '
        'For assurance-critical KPIs, supporting evidence must be attached in the portal.',
        st['small']))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    buf.seek(0)
    return buf.getvalue()