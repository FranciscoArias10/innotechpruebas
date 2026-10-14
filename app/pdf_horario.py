import io
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from django.db import connection

AREAS_MAP = {
    'quimic': ('Ciencia', '#a7bd39'),
    'biolog': ('Ciencia', '#68c079'),
    'fisica': ('Ciencia', '#12a79d'),
    'matematic': ('Exactas', '#0073bc'),
    'historia': ('Sociales', '#c8874f'),
    'social': ('Sociales', '#c8874f'),
    'ciudadan': ('Sociales', '#ea5455'),
    'mentor': ('Tutoría', '#21d866'),
    'tutoria': ('Tutoría', '#21d866'),
    'eca': ('Artística', '#7c5cd6'),
    'artist': ('Artística', '#7c5cd6'),
    'deport': ('Deporte', '#f59e0b'),
    'cultura fisica': ('Deporte', '#f59e0b'),
    'educacion fisica': ('Deporte', '#f59e0b'),
    'financier': ('Emprendimiento', '#13d896'),
    'emprendim': ('Emprendimiento', '#13d896'),
    'lengua': ('Lenguaje', '#90268f'),
    'ingles': ('Idiomas', '#29b1e6'),
    'participacion': ('Valores', '#f4b41a'),
    'filosof': ('Filosofía', '#7c5cd6'),
}

def obtener_area_y_color(nombre_materia, color_default='#0073bc'):
    txt = (nombre_materia or '').lower()
    for trozo, (area, col) in AREAS_MAP.items():
        if trozo in txt:
            return area, color_default or col
    return 'General', color_default or '#0073bc'

def hex_to_soft(hex_color, percent=14):
    hex_clean = (hex_color or '#0073bc').lstrip('#')
    if len(hex_clean) != 6:
        hex_clean = '0073bc'
    try:
        r = int(hex_clean[0:2], 16)
        g = int(hex_clean[2:4], 16)
        b = int(hex_clean[4:6], 16)
    except Exception:
        r, g, b = 0, 115, 188
    p = percent / 100.0
    r_soft = int(r * p + 255 * (1 - p))
    g_soft = int(g * p + 255 * (1 - p))
    b_soft = int(b * p + 255 * (1 - p))
    return colors.HexColor(f'#{r_soft:02x}{g_soft:02x}{b_soft:02x}')

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
    periodo_nombre = 'Periodo Académico'
    if row:
        apellidos = f"{row[1] or ''} {row[2] or ''}".strip()
        nombre_est = f"{row[0] or ''} {apellidos}".strip() or 'Estudiante'
        periodo_nombre = row[3] or 'Periodo Académico'

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=24,
        rightMargin=24,
        topMargin=22,
        bottomMargin=22
    )

    styles = getSampleStyleSheet()
    titulo_style = ParagraphStyle(
        'TituloDoc',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#002B49'),
        alignment=1
    )
    subtitulo_style = ParagraphStyle(
        'SubtituloDoc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    header_col_style = ParagraphStyle(
        'HeaderCol',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.white,
        alignment=1
    )
    cell_hora_style = ParagraphStyle(
        'CellHora',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    cell_libre_style = ParagraphStyle(
        'CellLibre',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#CBD5E1'),
        alignment=1
    )

    elementos = []
    elementos.append(Paragraph('UNIDAD EDUCATIVA BOLIVARIANA', titulo_style))
    elementos.append(Spacer(1, 3))
    elementos.append(Paragraph(f'HORARIO OFICIAL DE CLASES · {periodo_nombre}', subtitulo_style))
    elementos.append(Paragraph(f'Estudiante: <b>{nombre_est}</b> · Fecha de emisión: {datetime.now().strftime("%d/%m/%Y %H:%M")}', subtitulo_style))
    elementos.append(Spacer(1, 10))

    dias_titulos = ['HORA', 'LUNES', 'MARTES', 'MIÉRCOLES', 'JUEVES', 'VIERNES']
    dias_visibles = datos_horario.get('dias_visibles', [])
    
    clases_por_dia = {1: [], 2: [], 3: [], 4: [], 5: []}
    for d in dias_visibles:
        idx = d.get('indice', 1)
        if idx in clases_por_dia:
            clases_por_dia[idx] = d.get('clases', [])

    horas_set = set()
    for d_clases in clases_por_dia.values():
        for c in d_clases:
            ini = c.get('inicio', '')
            fin = c.get('fin', '')
            if ini and fin:
                horas_set.add((ini, fin))

    horas_ordenadas = sorted(list(horas_set), key=lambda x: x[0])
    
    data_tabla = []
    fila_hdr = [Paragraph(col, header_col_style) for col in dias_titulos]
    data_tabla.append(fila_hdr)

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#002B49')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]

    if not horas_ordenadas:
        fila_vacia = [Paragraph('-', cell_hora_style)] + [Paragraph('LIBRE', cell_libre_style) for _ in range(5)]
        data_tabla.append(fila_vacia)
    else:
        for row_idx, (ini, fin) in enumerate(horas_ordenadas, start=1):
            rango_str = f"<b>{ini}</b><br/><font color='#64748B' size='7.5'>a {fin}</font>"
            fila = [Paragraph(rango_str, cell_hora_style)]
            
            for col_idx, dia_idx in enumerate(range(1, 6), start=1):
                clases_hora = [
                    c for c in clases_por_dia[dia_idx]
                    if c.get('inicio') == ini and c.get('fin') == fin
                ]
                if clases_hora:
                    c = clases_hora[0]
                    col_raw = c.get('color') or '#0073bc'
                    area_nombre, color_oficial = obtener_area_y_color(c.get('nombre', ''), col_raw)
                    bg_color = hex_to_soft(color_oficial, 16)
                    border_color = hex_to_soft(color_oficial, 45)
                    
                    table_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), bg_color))
                    table_styles.append(('BOX', (col_idx, row_idx), (col_idx, row_idx), 1, border_color))

                    texto_celda = (
                        f"<font size='6' color='{color_oficial}'><b>{area_nombre.upper()}</b></font><br/>"
                        f"<font size='8.5' color='#0F172A'><b>{c.get('nombre', '')}</b></font><br/>"
                        f"<font size='6.5' color='{color_oficial}'><b>[ Clase grabada ]</b></font><br/>"
                        f"<font size='7' color='#334155'>{c.get('profesor', '')}</font><br/>"
                        f"<font size='6.5' color='#64748B'>{c.get('aula', '')}</font>"
                    )
                    cell_style = ParagraphStyle(
                        f'Cell_{row_idx}_{col_idx}',
                        parent=styles['Normal'],
                        fontName='Helvetica',
                        leading=9.5,
                        alignment=1
                    )
                    fila.append(Paragraph(texto_celda, cell_style))
                else:
                    table_styles.append(('BACKGROUND', (col_idx, row_idx), (col_idx, row_idx), colors.HexColor('#F8FAFC')))
                    fila.append(Paragraph('LIBRE', cell_libre_style))

            data_tabla.append(fila)

    col_widths = [72, 138, 138, 138, 138, 138]
    tabla = Table(data_tabla, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle(table_styles))

    elementos.append(tabla)
    elementos.append(Spacer(1, 10))
    footer_style = ParagraphStyle(
        'FooterDoc',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )
    elementos.append(Paragraph('Sistema Integrado de Gestión Educativa · UNIEBEC · Colores y áreas según el catálogo institucional.', footer_style))

    doc.build(elementos)
    return buffer.getvalue()
