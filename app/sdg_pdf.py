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

# Brand colors
NAVY = colors.HexColor('#0b1f33')
SKY = colors.HexColor('#0ea5e9')
GREEN = colors.HexColor('#10b981')
GREEN_D = colors.HexColor('#059669')
BLUE = colors.HexColor('#3b82f6')
AMBER = colors.HexColor('#f59e0b')
RED = colors.HexColor('#ef4444')
VIOLET = colors.HexColor('#8b5cf6')
GREY = colors.HexColor('#64748b')
LIGHT = colors.HexColor('#f1f5f9')
LINE = colors.HexColor('#e2e8f0')

SDGS = [
    {"num": 6, "title": "Clean Water & Sanitation", "sub": "Water infrastructure", "color": "#0EA5E9", "progress": 82},
    {"num": 7, "title": "Affordable & Clean Energy", "sub": "Renewable capacity", "color": "#F59E0B", "progress": 71},
    {"num": 8, "title": "Decent Work & Economic Growth", "sub": "Employment & safety", "color": "#8B5CF6", "progress": 78},
    {"num": 9, "title": "Industry, Innovation & Infrastructure", "sub": "Core business", "color": "#EF4444", "progress": 88},
    {"num": 11, "title": "Sustainable Cities & Communities", "sub": "Community development", "color": "#10B981", "progress": 74},
    {"num": 13, "title": "Climate Action", "sub": "GHG reduction", "color": "#059669", "progress": 64},
    {"num": 16, "title": "Peace, Justice & Strong Institutions", "sub": "Governance & ethics", "color": "#3B82F6", "progress": 91},
    {"num": 17, "title": "Partnerships for the Goals", "sub": "Value chain engagement", "color": "#1D4ED8", "progress": 69},
]

CONTRIBUTIONS = [
    {"sdg": 6, "contribution": "Drinking water & irrigation projects", "indicator": "14,820 KL", "status": "On track", "cls": "complete"},
    {"sdg": 7, "contribution": "Renewable generation & procurement", "indicator": "9.5% share", "status": "Below target", "cls": "partial"},
    {"sdg": 8, "contribution": "79,159 employees & workers", "indicator": "LTIFR 0.41", "status": "On track", "cls": "complete"},
    {"sdg": 9, "contribution": "Core EPC business — 250+ projects", "indicator": "250 projects", "status": "Leader", "cls": "complete"},
    {"sdg": 11, "contribution": "CSR & community development", "indicator": "Rs 186.4 Cr", "status": "On track", "cls": "complete"},
    {"sdg": 13, "contribution": "Scope 1+2 emissions intensity", "indicator": "12.84 t/Rs Cr", "status": "Reduction needed", "cls": "partial"},
    {"sdg": 16, "contribution": "Anti-corruption & ethics", "indicator": "0 violations", "status": "Clean", "cls": "complete"},
    {"sdg": 17, "contribution": "Value chain & supplier engagement", "indicator": "28% coverage", "status": "Coverage gap", "cls": "partial"},
]


def _styles():
    s = getSampleStyleSheet()
    return {
        'cover_title': ParagraphStyle('cover_title', parent=s['Title'],
            fontSize=32, textColor=colors.white, alignment=1, spaceAfter=6, leading=36),
        'cover_sub': ParagraphStyle('cover_sub', parent=s['Normal'],
            fontSize=13, textColor=colors.HexColor('#bae6fd'), alignment=1, spaceAfter=4),
        'cover_label': ParagraphStyle('cover_label', parent=s['Normal'],
            fontSize=9, textColor=colors.HexColor('#94a3b8'), alignment=1),
        'h1': ParagraphStyle('h1', parent=s['Heading1'],
            fontSize=20, textColor=NAVY, spaceAfter=4, spaceBefore=4),
        'h2': ParagraphStyle('h2', parent=s['Heading2'],
            fontSize=14, textColor=NAVY, spaceAfter=6, spaceBefore=10),
        'body': ParagraphStyle('body', parent=s['BodyText'],
            fontSize=10, leading=14, textColor=colors.HexColor('#334155')),
        'small': ParagraphStyle('small', parent=s['BodyText'],
            fontSize=8.5, leading=11, textColor=GREY),
        'sdg_title': ParagraphStyle('sdg_title', parent=s['Normal'],
            fontSize=10, textColor=NAVY, leading=12, fontName='Helvetica-Bold'),
        'sdg_sub': ParagraphStyle('sdg_sub', parent=s['Normal'],
            fontSize=8, textColor=GREY, leading=10),
    }


def _page_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, A4[0] - 18 * mm, 15 * mm)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GREY)
    canvas.drawString(18 * mm, 10 * mm, 'MEIL SDG Report · FY 2025-26 · Confidential')
    canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f'Page {doc.page}')
    canvas.restoreState()


def _bar_chart(labels, values, chart_colors, width=460, height=180):
    d = Drawing(width, height)
    chart = VerticalBarChart()
    chart.x = 40
    chart.y = 30
    chart.height = height - 50
    chart.width = width - 60
    chart.data = [values]
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontSize = 7.5
    chart.valueAxis.labels.fontSize = 7.5
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = 100
    chart.bars[0].fillColor = GREEN
    chart.bars.strokeColor = None
    # Colour each bar differently
    for i, c in enumerate(chart_colors):
        try:
            chart.bars[(0, i)].fillColor = colors.HexColor(c)
        except Exception:
            pass
    d.add(chart)
    return d


def _pie_chart(data, labels, slice_colors, width=460, height=180):
    d = Drawing(width, height)
    pie = Pie()
    pie.x = 160
    pie.y = 10
    pie.width = 140
    pie.height = 140
    pie.data = data
    pie.labels = labels
    pie.slices.fontSize = 8
    pie.slices.fontColor = colors.white
    for i, c in enumerate(slice_colors):
        pie.slices[i].fillColor = colors.HexColor(c)
    d.add(pie)
    return d


def build_sdg_pdf(entity, user_name, user_role):
    """Build a 4-page SDG PDF report."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=22 * mm,
        title=f'MEIL SDG Report - {entity["name"]}',
        author='MEIL BRSR Portal',
    )
    st = _styles()
    story = []

    avg_score = round(sum(s['progress'] for s in SDGS) / len(SDGS))
    on_track = [s for s in SDGS if s['progress'] >= 70]
    needs_action = [s for s in SDGS if s['progress'] < 70]

    # ============================================================
    # PAGE 1 — COVER
    # ============================================================
    cover_data = [
        [Paragraph('SDG', ParagraphStyle('logo', fontSize=48, textColor=colors.white, alignment=1, leading=52))],
        [Spacer(1, 6)],
        [Paragraph('MEIL SDG Report', st['cover_title'])],
        [Paragraph('UN Sustainable Development Goals Alignment', st['cover_sub'])],
        [Paragraph('Financial Year 2025-26', st['cover_sub'])],
        [Spacer(1, 30)],
        [Paragraph(entity['name'], ParagraphStyle('ent', fontSize=18, textColor=colors.white, alignment=1, leading=22))],
        [Paragraph(f'{entity["type"]} · Code {entity["code"]}', st['cover_label'])],
        [Spacer(1, 60)],
        [Paragraph(f'SDG Alignment Score: {avg_score}%', ParagraphStyle('score', fontSize=14, textColor=colors.HexColor('#7dd3fc'), alignment=1))],
        [Spacer(1, 20)],
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
        f'This report presents the UN SDG alignment performance of <b>{entity["name"]}</b> '
        f'for FY 2025-26. Of the 8 prioritised goals, <b>{len(on_track)}</b> are on track '
        f'(≥ 70% alignment) and <b>{len(needs_action)}</b> require additional action. '
        f'Overall SDG alignment score is <b>{avg_score}%</b>.',
        st['body']))
    story.append(Spacer(1, 14))

    # Overall score card
    score_row = [[
        Paragraph(f'<font size=40 color="#0ea5e9"><b>{avg_score}%</b></font>', st['body']),
        Paragraph('<font size=11>Overall SDG Alignment<br/>'
                  f'<font color="#64748b">Average across 8 prioritised goals</font></font>', st['body']),
    ]]
    score_t = Table(score_row, colWidths=[55 * mm, 105 * mm])
    score_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(score_t)
    story.append(Spacer(1, 16))

    # KPI cards — Goals on track / needing action
    kpi_row = [[
        Paragraph(f'<font size=26 color="#10b981"><b>{len(on_track)}</b></font><br/>'
                  '<font size=9 color="#64748b">Goals On Track</font>', st['body']),
        Paragraph(f'<font size=26 color="#f59e0b"><b>{len(needs_action)}</b></font><br/>'
                  '<font size=9 color="#64748b">Needing Action</font>', st['body']),
        Paragraph(f'<font size=26 color="#0ea5e9"><b>8</b></font><br/>'
                  '<font size=9 color="#64748b">Goals Tracked</font>', st['body']),
    ]]
    kpi_t = Table(kpi_row, colWidths=[53 * mm, 53 * mm, 53 * mm])
    kpi_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('PADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, LINE),
    ]))
    story.append(kpi_t)
    story.append(Spacer(1, 18))

    # Alignment bar chart
    story.append(Paragraph('Alignment Score by Goal', st['h2']))
    labels = [f"SDG {s['num']}" for s in SDGS]
    values = [s['progress'] for s in SDGS]
    bar_colors = [s['color'] for s in SDGS]
    story.append(_bar_chart(labels, values, bar_colors, width=460, height=170))
    story.append(PageBreak())

    # ============================================================
    # PAGE 3 — SDG DETAILS
    # ============================================================
    story.append(Paragraph('2. Prioritised UN SDGs — Detail', st['h1']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Progress against each goal based on MEIL\'s material ESG indicators. '
        'The score reflects how well current operations align with each goal.',
        st['body']))
    story.append(Spacer(1, 12))

    # Pie of on-track vs needing-action
    story.append(Paragraph('Goal Status Distribution', st['h2']))
    story.append(_pie_chart(
        [len(on_track), len(needs_action)],
        ['On track', 'Needs action'],
        ['#10b981', '#f59e0b'],
        width=460, height=170,
    ))
    story.append(Spacer(1, 14))

    # SDG table
    sdg_rows = [['SDG', 'Goal', 'Focus Area', 'Alignment']]
    for s in SDGS:
        sdg_rows.append([
            f"SDG {s['num']}",
            s['title'],
            s['sub'],
            f"{s['progress']}%",
        ])
    sdg_t = Table(sdg_rows, colWidths=[18 * mm, 60 * mm, 50 * mm, 22 * mm])
    sdg_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), SKY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(sdg_t)
    story.append(PageBreak())

    # ============================================================
    # PAGE 4 — CONTRIBUTIONS + FOCUS
    # ============================================================
    story.append(Paragraph('3. SDG Contributions at a Glance', st['h1']))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        'Concrete business contributions toward each prioritised goal.',
        st['body']))
    story.append(Spacer(1, 10))

    contrib_rows = [['SDG', 'Contribution', 'Indicator', 'Status']]
    for c in CONTRIBUTIONS:
        contrib_rows.append([
            f"SDG {c['sdg']}",
            c['contribution'],
            c['indicator'],
            c['status'],
        ])
    contrib_t = Table(contrib_rows, colWidths=[18 * mm, 70 * mm, 42 * mm, 30 * mm])
    contrib_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(contrib_t)
    story.append(Spacer(1, 18))

    story.append(Paragraph('4. Focus Areas', st['h1']))
    story.append(Spacer(1, 6))

    sorted_sdgs = sorted(SDGS, key=lambda x: x['progress'], reverse=True)
    strongest = sorted_sdgs[:2]
    weakest = sorted_sdgs[-2:]

    focus_rows = [
        ['Category', 'Goal', 'Score'],
    ]
    for s in strongest:
        focus_rows.append(['✅ Strongest', f"SDG {s['num']} · {s['title']}", f"{s['progress']}%"])
    for s in weakest:
        focus_rows.append(['⚠ Needs work', f"SDG {s['num']} · {s['title']}", f"{s['progress']}%"])

    focus_t = Table(focus_rows, colWidths=[30 * mm, 110 * mm, 25 * mm])
    focus_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), GREEN_D),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('PADDING', (0, 0), (-1, -1), 7),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, LINE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT]),
        ('BOX', (0, 0), (-1, -1), 0.5, LINE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(focus_t)
    story.append(Spacer(1, 20))

    story.append(Paragraph(
        'This SDG report was auto-generated by the MEIL BRSR Portal. It maps the company\'s '
        'material ESG performance to the 8 priority UN Sustainable Development Goals identified '
        'by MEIL Group. For assurance-critical data, refer to the underlying BRSR submission.',
        st['small']))

    doc.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    buf.seek(0)
    return buf.getvalue()