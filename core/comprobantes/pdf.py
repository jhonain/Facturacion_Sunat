"""
pdf.py — Generación del comprobante en PDF (representación imprimible)
Usa ReportLab. Instalar: pip install reportlab
"""
from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)


def generar_pdf_comprobante(comprobante) -> bytes:
    buffer = BytesIO()
    doc    = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles  = getSampleStyleSheet()
    normal  = styles['Normal']
    bold    = ParagraphStyle('bold', parent=normal, fontName='Helvetica-Bold')
    center  = ParagraphStyle('center', parent=normal, alignment=1)
    center_bold = ParagraphStyle('center_bold', parent=bold, alignment=1, fontSize=13)
    small   = ParagraphStyle('small', parent=normal, fontSize=8)

    elements = []

    # ── Cabecera empresa ──────────────────────────────────────────────────────
    empresa = comprobante.empresa
    elements.append(Paragraph(empresa.razon_social.upper(), center_bold))
    elements.append(Paragraph(f'RUC: {empresa.ruc}', center))
    elements.append(Paragraph(empresa.direccion, center))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(HRFlowable(width='100%', thickness=1, color=colors.black))
    elements.append(Spacer(1, 0.3 * cm))

    # ── Tipo y número de comprobante ──────────────────────────────────────────
    numero_completo = f"{comprobante.serie.serie}-{comprobante.numero:08d}"
    elements.append(Paragraph(comprobante.get_tipo_display().upper(), center_bold))
    elements.append(Paragraph(numero_completo, center_bold))
    elements.append(Spacer(1, 0.4 * cm))

    # ── Datos del cliente ─────────────────────────────────────────────────────
    cliente = comprobante.cliente
    datos_cliente = [
        ['Fecha de emisión:', str(comprobante.fecha_emision)],
        ['Cliente:', cliente.razon_social],
        [f'{cliente.get_tipo_documento_display()}:', cliente.numero_documento],
        ['Dirección:', cliente.direccion or '—'],
    ]
    tabla_cliente = Table(datos_cliente, colWidths=[4 * cm, 13 * cm])
    tabla_cliente.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(tabla_cliente)
    elements.append(Spacer(1, 0.4 * cm))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 0.3 * cm))

    # ── Tabla de detalles ─────────────────────────────────────────────────────
    header = ['#', 'Descripción', 'Cant.', 'U.M.', 'P. Unit.', 'Desc.', 'IGV', 'Total']
    filas  = [header]

    for i, det in enumerate(comprobante.detalles.all(), start=1):
        filas.append([
            str(i),
            det.descripcion,
            f'{det.cantidad}',
            det.unidad_medida,
            f'S/ {det.precio_unitario:.2f}',
            f'S/ {det.descuento:.2f}',
            f'S/ {det.igv_linea:.2f}',
            f'S/ {det.total:.2f}',
        ])

    tabla_det = Table(
        filas,
        colWidths=[0.6*cm, 5.5*cm, 1.5*cm, 1.2*cm, 2.2*cm, 1.8*cm, 1.8*cm, 2.4*cm]
    )
    tabla_det.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, 0), colors.HexColor('#2E75B6')),
        ('TEXTCOLOR',    (0, 0), (-1, 0), colors.white),
        ('FONTNAME',     (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',     (0, 0), (-1, -1), 8),
        ('ALIGN',        (2, 0), (-1, -1), 'RIGHT'),
        ('GRID',         (0, 0), (-1, -1), 0.3, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
    ]))
    elements.append(tabla_det)
    elements.append(Spacer(1, 0.4 * cm))

    # ── Totales ───────────────────────────────────────────────────────────────
    moneda = comprobante.moneda
    totales = [
        ['Op. Gravadas:', f'{moneda} {comprobante.subtotal}'],
        ['IGV (18%):', f'{moneda} {comprobante.igv}'],
        ['TOTAL:', f'{moneda} {comprobante.total}'],
    ]
    tabla_tot = Table(totales, colWidths=[5 * cm, 3 * cm], hAlign='RIGHT')
    tabla_tot.setStyle(TableStyle([
        ('FONTNAME',  (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',  (0, 2), (-1, 2), 'Helvetica-Bold'),
        ('FONTSIZE',  (0, 0), (-1, -1), 9),
        ('FONTSIZE',  (0, 2), (-1, 2), 11),
        ('ALIGN',     (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, 2), (-1, 2), 1, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(tabla_tot)
    elements.append(Spacer(1, 0.5 * cm))

    # ── Estado SUNAT ──────────────────────────────────────────────────────────
    color_estado = {
        'ACEPTADO':  '#00AA00',
        'RECHAZADO': '#CC0000',
        'ENVIADO':   '#E6A817',
        'BORRADOR':  '#888888',
        'ANULADO':   '#CC0000',
    }.get(comprobante.estado, '#888888')

    estado_style = ParagraphStyle(
        'estado', parent=center_bold,
        textColor=colors.HexColor(color_estado),
        fontSize=10,
    )
    elements.append(Paragraph(f'Estado SUNAT: {comprobante.get_estado_display()}', estado_style))

    if comprobante.sunat_descripcion:
        elements.append(Paragraph(comprobante.sunat_descripcion, center))

    elements.append(Spacer(1, 0.3 * cm))
    elements.append(HRFlowable(width='100%', thickness=0.5, color=colors.grey))
    elements.append(Spacer(1, 0.2 * cm))
    elements.append(Paragraph('Representación impresa del Comprobante de Pago Electrónico', center))
    elements.append(Paragraph('Consulte su comprobante en: www.sunat.gob.pe', center))

    doc.build(elements)
    return buffer.getvalue()
