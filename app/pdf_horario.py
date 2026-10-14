import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.db import connection

def generar_horario_pdf(persona_id, periodo_id, datos_horario):
    sql_est = """
        SELECT 
            p.nombres, p.apellido_1, p.apellido_2,
            per.nombre as periodo_nombre
        FROM ctr_persona p
        LEFT JOIN ctr_periodo per ON per.id = %s
        WHERE p.id = %s
    """
    with connection.cursor() as cur:
        cur.execute(sql_est, [periodo_id, persona_id])
        row = cur.fetchone()
    
    nombre_est = 'Estudiante'
    periodo_nombre = 'Periodo Academico'
    if row:
        apellidos = f"{row[1] or ''} {row[2] or ''}".strip()
        nombre_est = f"{row[0] or ''} {apellidos}".strip() or 'Estudiante'
        periodo_nombre = row[3] or 'Periodo Academico'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'TituloDoc',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#002B49'),
        alignment=1
    )
    subtitulo_style = ParagraphStyle(
        'SubtituloDoc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#555555'),
        alignment=1
    )
    header_col_style = ParagraphStyle(
        'HeaderCol',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=colors.white,
        alignment=1
    )
    cell_hora_style = ParagraphStyle(
        'CellHora',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#002B49'),
        alignment=1
    )
    cell_materia_style = ParagraphStyle(
        'CellMateria',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10,
        textColor=colors.HexColor('#1E293B'),
        alignment=1
    )
    cell_detalle_style = ParagraphStyle(
        'CellDetalle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#64748B'),
        alignment=1
    )

    elementos = []
    elementos.append(Paragraph('UNIDAD EDUCATIVA BOLIVARIANA', titulo_style))
    elementos.append(Spacer(1, 4))
    elementos.append(Paragraph(f'HORARIO OFICIAL DE CLASES · {periodo_nombre}', subtitulo_style))
    elementos.append(Paragraph(f'Estudiante: <b>{nombre_est}</b> · Fecha de emisión: {datetime.now().strftime("%d/%m/%Y %H:%M")}', subtitulo_style))
    elementos.append(Spacer(1, 14))

    # Recoger todas las clases por dia
    # Dias: 1: Lunes .. 5: Viernes
    dias_titulos = ['HORA', 'LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES']
    dias_visibles = datos_horario.get('dias_visibles', [])
    
    # Mapeo dia -> lista de clases
    clases_por_dia = {1: [], 2: [], 3: [], 4: [], 5: []}
    for d in dias_visibles:
        idx = d.get('indice', 1)
        if idx in clases_por_dia:
            clases_por_dia[idx] = d.get('clases', [])

    # Obtener todas las horas unicas (inicio - fin)
    horas_set = set()
    for d_clases in clases_por_dia.values():
        for c in d_clases:
            ini = c.get('inicio', '')
            fin = c.get('fin', '')
            if ini and fin:
                horas_set.add((ini, fin))

    horas_ordenadas = sorted(list(horas_set), key=lambda x: x[0])
    
    data_tabla = []
    # Fila cabecera
    fila_hdr = [Paragraph(col, header_col_style) for col in dias_titulos]
    data_tabla.append(fila_hdr)

    if not horas_ordenadas:
        fila_vacia = [
            Paragraph('-', cell_hora_style),
            Paragraph('Sin clases', cell_detalle_style),
            Paragraph('Sin clases', cell_detalle_style),
            Paragraph('Sin clases', cell_detalle_style),
            Paragraph('Sin clases', cell_detalle_style),
            Paragraph('Sin clases', cell_detalle_style),
        ]
        data_tabla.append(fila_vacia)
    else:
        for (ini, fin) in horas_ordenadas:
            rango_str = f"{ini}<br/>{fin}"
            fila = [Paragraph(rango_str, cell_hora_style)]
            for dia_idx in range(1, 6):
                clases_hora = [
                    c for c in clases_por_dia[dia_idx]
                    if c.get('inicio') == ini and c.get('fin') == fin
                ]
                if clases_hora:
                    c = clases_hora[0]
                    texto_celda = f"<b>{c.get('nombre', '')}</b><br/>{c.get('aula', '')}<br/>{c.get('profesor', '')}"
                    fila.append(Paragraph(texto_celda, cell_materia_style))
                else:
                    fila.append(Paragraph('-', cell_detalle_style))
            data_tabla.append(fila)

    col_widths = [75, 135, 135, 135, 135, 135]
    tabla = Table(data_tabla, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#002B49')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8FAFC')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elementos.append(tabla)
    elementos.append(Spacer(1, 14))
    footer_style = ParagraphStyle(
        'FooterDoc',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )
    elementos.append(Paragraph('Documento informativo generado por el Sistema Académico de la UE Bolivariana.', footer_style))

    doc.build(elementos)
    return buffer.getvalue()
