#!/usr/bin/env python3
"""Create sample annual report PDFs for testing."""

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

def create_sample_annual_report(company, filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    title = Paragraph(f'<b>{company} Limited</b><br/>Annual Report 2023-24', styles['Title'])
    story.append(title)
    story.append(Spacer(1, 0.5*inch))

    story.append(Paragraph('<b>Financial Highlights</b>', styles['Heading1']))
    if company == 'RELIANCE':
        content = 'Revenue: Rs 9,50,000 crores (up 12% YoY)<br/>Net Profit: Rs 75,000 crores (up 8% YoY)<br/>EBITDA: Rs 1,25,000 crores (margin: 13.2%)<br/>Total Assets: Rs 15,00,000 crores<br/>Debt-to-Equity Ratio: 0.45<br/>Return on Equity: 9.5%'
    else:
        content = 'Total Income: Rs 2,10,000 crores (up 15% YoY)<br/>Net Profit: Rs 52,000 crores (up 18% YoY)<br/>Total Assets: Rs 28,00,000 crores<br/>Net NPA Ratio: 0.28%<br/>Capital Adequacy Ratio: 18.5%<br/>Return on Assets: 1.9%'
    story.append(Paragraph(content, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph('<b>Business Model and Operations</b>', styles['Heading1']))
    if company == 'RELIANCE':
        content = 'Reliance Industries operates across three primary segments: Oil to Chemicals (O2C), Digital Services (Jio), and Retail. Jio Platforms has 450 million subscribers. Reliance Retail operates 18,000+ stores. Strategic focus on new energy initiatives including solar manufacturing and green hydrogen.'
    else:
        content = 'HDFC Bank is India largest private sector bank with comprehensive banking services. Operations through Retail Banking (60%), Wholesale Banking (35%), and Treasury (5%). With 8,300+ branches serving 85 million customers. Digital banking has 95% of transactions. CASA ratio of 42%.'
    story.append(Paragraph(content, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph('<b>Key Risk Factors</b>', styles['Heading1']))
    if company == 'RELIANCE':
        content = '<b>Market Risks:</b> Crude oil price volatility impacts O2C profitability. Economic slowdown affects all segments.<br/><br/><b>Operational Risks:</b> Technology disruption in telecom. Regulatory changes in retail and digital.<br/><br/><b>Strategic Risks:</b> Large capital investments in new energy. Integration risks from acquisitions.'
    else:
        content = '<b>Credit Risk:</b> Asset quality deterioration from economic slowdown. Concentration in corporate and MSME lending.<br/><br/><b>Market Risk:</b> Interest rate fluctuations affect margins. Liquidity risk during stress.<br/><br/><b>Operational Risk:</b> Cybersecurity threats. Technology failures. Regulatory compliance challenges.'
    story.append(Paragraph(content, styles['Normal']))
    story.append(Spacer(1, 0.3*inch))

    story.append(Paragraph('<b>Future Outlook and Strategy</b>', styles['Heading1']))
    if company == 'RELIANCE':
        content = 'Focused on new energy transformation. Key initiatives: (1) 100 GW renewable energy by 2030, (2) 10 GW solar manufacturing, (3) Green hydrogen at $1/kg by 2030, (4) Jio 5G nationwide by 2024, (5) 25,000 retail stores. Expected 15% revenue CAGR.'
    else:
        content = 'Strategic priorities: (1) Deepen retail relationships, (2) Grow corporate and SME market share, (3) 1,000 new branches in 3 years, (4) Technology investments, (5) Maintain best-in-class asset quality. Targeting 15-18% loan growth and 17-18% ROE by FY26.'
    story.append(Paragraph(content, styles['Normal']))

    doc.build(story)
    print(f'Created {filename}')

if __name__ == '__main__':
    create_sample_annual_report('RELIANCE', 'data/filings/RELIANCE/annual_report_2023-24.pdf')
    create_sample_annual_report('HDFCBANK', 'data/filings/HDFCBANK/annual_report_2023-24.pdf')
