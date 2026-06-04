"""
SRG - Générateur de Factures PDF
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

SRG_RED = colors.HexColor("#C0392B")
SRG_DARK = colors.HexColor("#1A1A1A")
SRG_LIGHT = colors.HexColor("#F8F8F8")
SRG_GRAY = colors.HexColor("#888888")


def generer_facture_pdf(facture, lignes, output_dir=None):
    """
    Génère un PDF de facture.
    facture: dict avec keys (id, numero, client_nom, client_tel, date_facture, total_ht, remise, total_ttc)
    lignes: list de dicts (piece_nom, piece_ref, quantite, prix_unitaire, total_ligne)
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "exports")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"Facture_{facture['numero']}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath,
        pagesize=A4,
        rightMargin=1.5*cm,
        leftMargin=1.5*cm,
        topMargin=1.5*cm,
        bottomMargin=1.5*cm
    )

    styles = getSampleStyleSheet()
    story = []

    # ── HEADER ──
    header_data = [[
        Paragraph(
            '<font size="28" color="#C0392B"><b>SRG</b></font><br/>'
            '<font size="9" color="#555555">Société de Rechange et Garniture</font>',
            ParagraphStyle('h', fontName='Helvetica', fontSize=10)
        ),
        Paragraph(
            f'<font size="18" color="#1A1A1A"><b>FACTURE</b></font><br/>'
            f'<font size="10" color="#C0392B"><b>N° {facture["numero"]}</b></font>',
            ParagraphStyle('h2', fontName='Helvetica', fontSize=10, alignment=TA_RIGHT)
        )
    ]]
    header_table = Table(header_data, colWidths=[10*cm, 7.5*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(header_table)
    story.append(HRFlowable(width="100%", thickness=2, color=SRG_RED, spaceAfter=10))

    # ── INFOS CLIENT & DATE ──
    try:
        date_str = datetime.fromisoformat(facture["date_facture"]).strftime("%d/%m/%Y %H:%M")
    except Exception:
        date_str = facture["date_facture"]

    info_data = [[
        Paragraph(
            f'<b>Client:</b> {facture["client_nom"]}<br/>'
            f'<b>Tél:</b> {facture["client_tel"] or "—"}',
            ParagraphStyle('client', fontName='Helvetica', fontSize=10, leading=16)
        ),
        Paragraph(
            f'<b>Date:</b> {date_str}',
            ParagraphStyle('date', fontName='Helvetica', fontSize=10, alignment=TA_RIGHT)
        )
    ]]
    info_table = Table(info_data, colWidths=[10*cm, 7.5*cm])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(info_table)

    # ── TABLEAU DES ARTICLES ──
    col_headers = ['Réf.', 'Désignation', 'Qté', 'Prix U. (TND)', 'Total (TND)']
    table_data = [col_headers]

    for ligne in lignes:
        table_data.append([
            ligne.get("piece_ref", ""),
            ligne["piece_nom"],
            str(ligne["quantite"]),
            f'{ligne["prix_unitaire"]:,.2f}',
            f'{ligne["total_ligne"]:,.2f}',
        ])

    col_widths = [2.5*cm, 7*cm, 1.5*cm, 3*cm, 3.5*cm]
    articles_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    articles_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), SRG_RED),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        # Body rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, SRG_LIGHT]),
        ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ('LINEBELOW', (0, 0), (-1, 0), 1, SRG_RED),
    ]))
    story.append(articles_table)
    story.append(Spacer(1, 0.5*cm))

    # ── TOTAUX ──
    remise = facture.get("remise", 0) or 0
    total_ht = facture.get("total_ht", 0) or 0
    total_ttc = facture.get("total_ttc", 0) or 0

    totaux_data = []
    totaux_data.append(["Sous-total HT", f'{total_ht:,.2f} TND'])
    if remise > 0:
        totaux_data.append([f'Remise ({remise:.0f}%)', f'-{(total_ht * remise / 100):,.2f} TND'])
    totaux_data.append(['TOTAL TTC', f'{total_ttc:,.2f} TND'])

    totaux_table = Table(totaux_data, colWidths=[5*cm, 3.5*cm],
                         hAlign='RIGHT')
    style = [
        ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -2), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        # Total row
        ('BACKGROUND', (0, -1), (-1, -1), SRG_RED),
        ('TEXTCOLOR', (0, -1), (-1, -1), colors.white),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 11),
        ('TOPPADDING', (0, -1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, -1), (-1, -1), 8),
    ]
    totaux_table.setStyle(TableStyle(style))
    story.append(totaux_table)

    # ── FOOTER ──
    story.append(Spacer(1, 1*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=SRG_GRAY, spaceAfter=6))
    story.append(Paragraph(
        '<font size="8" color="#888888">SRG — Merci pour votre confiance | Ce document est généré automatiquement</font>',
        ParagraphStyle('footer', fontName='Helvetica', fontSize=8, alignment=TA_CENTER)
    ))

    doc.build(story)
    return filepath