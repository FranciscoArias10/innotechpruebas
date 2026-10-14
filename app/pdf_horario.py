import io
import os
import subprocess
import tempfile
import unicodedata
from datetime import datetime
from django.db import connection

# Fallback imports ReportLab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def normalizar_texto(txt):
    if not txt:
        return ''
    return ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn').lower()

AREAS_MAP = [
    ('cultura fisica', 'DEPORTE', '#f59e0b', 'running'),
    ('educacion fisica', 'DEPORTE', '#f59e0b', 'running'),
    ('deport', 'DEPORTE', '#f59e0b', 'running'),
    ('ciencias naturales', 'CIENCIA', '#68c079', 'dna'),
    ('natural', 'CIENCIA', '#68c079', 'dna'),
    ('quimic', 'CIENCIA', '#a7bd39', 'flask'),
    ('biolog', 'CIENCIA', '#68c079', 'dna'),
    ('fisica', 'CIENCIA', '#12a79d', 'atom'),
    ('ciencia', 'CIENCIA', '#a7bd39', 'flask'),
    ('matematic', 'EXACTAS', '#0073bc', 'calculator'),
    ('estudios sociales', 'SOCIALES', '#c8874f', 'globe'),
    ('historia', 'SOCIALES', '#c8874f', 'globe'),
    ('social', 'SOCIALES', '#c8874f', 'globe'),
    ('ciudadan', 'SOCIALES', '#ea5455', 'landmark'),
    ('mentor', 'TUTORÍA', '#21d866', 'users'),
    ('tutoria', 'TUTORÍA', '#21d866', 'users'),
    ('eca', 'ARTÍSTICA', '#7c5cd6', 'palette'),
    ('artist', 'ARTÍSTICA', '#7c5cd6', 'palette'),
    ('financier', 'EMPRENDIMIENTO', '#13d896', 'coins'),
    ('emprendim', 'EMPRENDIMIENTO', '#692c87', 'coins'),
    ('lengua', 'LENGUAJE', '#90268f', 'book'),
    ('literat', 'LENGUAJE', '#90268f', 'book'),
    ('ingles', 'IDIOMAS', '#29b1e6', 'language'),
    ('idioma', 'IDIOMAS', '#29b1e6', 'language'),
    ('participacion', 'VALORES', '#f4b41a', 'award'),
    ('filosof', 'FILOSOFÍA', '#7c5cd6', 'book'),
]

ICONS_SVG = {
    'flask': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 2v7.527a2 2 0 0 1-.211.896L4.72 20.55a1 1 0 0 0 .9 1.45h12.76a1 1 0 0 0 .9-1.45l-5.069-10.127A2 2 0 0 1 14 9.527V2"/><path d="M8.5 2h7"/><path d="M7 16h10"/></svg>',
    'calculator': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="16" height="20" x="4" y="2" rx="2"/><line x1="8" x2="16" y1="6" y2="6"/><line x1="16" x2="16" y1="14" y2="18"/><path d="M16 10h.01"/><path d="M12 10h.01"/><path d="M8 10h.01"/><path d="M12 14h.01"/><path d="M8 14h.01"/><path d="M12 18h.01"/><path d="M8 18h.01"/></svg>',
    'globe': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>',
    'language': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m5 8 6 6"/><path d="m4 14 6-6 2-3"/><path d="M2 5h12"/><path d="M7 2h1"/><path d="m22 22-5-10-5 10"/><path d="M14 18h6"/></svg>',
    'users': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    'palette': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r=".5" fill="currentColor"/><circle cx="17.5" cy="10.5" r=".5" fill="currentColor"/><circle cx="8.5" cy="7.5" r=".5" fill="currentColor"/><circle cx="6.5" cy="12.5" r=".5" fill="currentColor"/><path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.563-2.512 5.563-5.563C22 6.5 17.5 2 12 2z"/></svg>',
    'running': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="17" cy="4" r="2"/><path d="m15 8-4.5 4.5 2 3.5 4.5-1.5"/><path d="M9 12.5 5 10l-2 5"/><path d="m12.5 16-2.5 6"/><path d="M7 21l3-5"/></svg>',
    'atom': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="2" fill="currentColor"/><ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(45 12 12)"/><ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(-45 12 12)"/></svg>',
    'dna': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 15c6.667-6 13.333 0 20-6"/><path d="M9 22c1.798-1.998 2.518-3.995 2.807-5.993"/><path d="M15 2c-1.798 1.998-2.518 3.995-2.807 5.993"/><path d="m17 6-2.5-2.5"/><path d="m14 8-1-1"/><path d="m7 18 2.5 2.5"/></svg>',
    'book': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>',
    'coins': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="6"/><path d="M18.09 10.37A6 6 0 1 1 10.34 18"/><path d="M7 6h1v4"/><path d="m16.71 13.88.7.71-2.82 2.82"/></svg>',
    'award': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="6"/><path d="M15.477 12.89 17 22l-5-3-5 3 1.523-9.11"/></svg>',
    'landmark': '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" x2="21" y1="22" y2="22"/><line x1="6" x2="6" y1="18" y2="11"/><line x1="10" x2="10" y1="18" y2="11"/><line x1="14" x2="14" y1="18" y2="11"/><line x1="18" x2="18" y1="18" y2="11"/><polygon points="12 2 20 7 4 7"/></svg>',
    'play-triangle': '<svg viewBox="0 0 24 24" width="7.5" height="7.5" fill="currentColor"><polygon points="6 3 20 12 6 21 6 3"/></svg>',
    'video': '<svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2"/></svg>',
    'doc': '<svg viewBox="0 0 24 24" width="10" height="10" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/></svg>'
}

def resolver_materia(nombre, color_def=''):
    txt_norm = normalizar_texto(nombre)
    for trozo, area, col, ico in AREAS_MAP:
        if trozo in txt_norm:
            return area, color_def or col, ico
    return 'ASIGNATURA', color_def or '#0073bc', 'book'

def generar_horario_html(persona_id, periodo_id, datos_horario):
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

    dias_base = [
        (1, 'LUNES'),
        (2, 'MARTES'),
        (3, 'MIÉRCOLES'),
        (4, 'JUEVES'),
        (5, 'VIERNES'),
        (6, 'SÁBADO')
    ]
    dia_hoy_num = datetime.now().isoweekday()

    clases_por_dia = {1: [], 2: [], 3: [], 4: [], 5: [], 6: []}
    for d in datos_horario.get('dias_visibles', []):
        idx = d.get('indice', 1)
        if idx in clases_por_dia:
            clases_por_dia[idx] = d.get('clases', [])

    # Solo incluir Sábado si el alumno tiene clases registradas ese día
    dias_info = [d for d in dias_base if d[0] <= 5 or len(clases_por_dia[d[0]]) > 0]
    total_dias = len(dias_info)

    horas_set = set()
    for d_idx, _ in dias_info:
        for c in clases_por_dia[d_idx]:
            ini = c.get('inicio', '')
            fin = c.get('fin', '')
            if ini and fin:
                horas_set.add((ini, fin))

    horas_ordenadas = sorted(list(horas_set), key=lambda x: x[0])

    css = f"""
    @page {{
        size: letter landscape;
        margin: 5mm 6mm;
    }}
    * {{
        box-sizing: border-box;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }}
    body {{
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background: #f8fafc;
        color: #0f172a;
    }}
    .horario-container {{
        width: 100%;
        background: #f4f7fa;
        border-radius: 14px;
        padding: 10px 14px 8px;
        box-sizing: border-box;
    }}
    .doc-header {{
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
        margin-bottom: 8px;
        padding-bottom: 5px;
        border-bottom: 1.5px solid #002B49;
    }}
    .doc-brand {{
        font-size: 7.5px;
        font-weight: 800;
        letter-spacing: 0.16em;
        text-transform: uppercase;
        color: #0073bc;
    }}
    .doc-title {{
        font-size: 14px;
        font-weight: 900;
        color: #002B49;
        margin: 1px 0 2px;
        text-transform: uppercase;
        letter-spacing: -0.01em;
    }}
    .doc-sub {{
        font-size: 8px;
        color: #64748b;
    }}
    .doc-badge {{
        background: #002B49;
        color: #ffffff;
        font-size: 7.5px;
        font-weight: 800;
        letter-spacing: 0.1em;
        padding: 3px 8px;
        border-radius: 5px;
        text-transform: uppercase;
    }}
    .tabla-grid {{
        width: 100%;
        display: grid;
        grid-template-columns: 84px repeat({total_dias}, 1fr);
        gap: 7px 6px;
        align-items: stretch;
    }}
    .th-col {{
        padding: 2px 3px 5px;
        border-bottom: 2px solid #cbd5e1;
        display: flex;
        justify-content: space-between;
        align-items: flex-end;
    }}
    .th-col.th-hora {{
        font-size: 8px;
        font-weight: 800;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: #94a3b8;
    }}
    .th-dia {{
        font-size: 10px;
        font-weight: 800;
        letter-spacing: 0.08em;
        color: #334155;
        text-transform: uppercase;
        display: flex;
        align-items: center;
        gap: 4px;
    }}
    .th-dia.es-hoy {{
        color: #0073bc;
    }}
    .th-count {{
        font-size: 7.5px;
        color: #94a3b8;
        font-weight: 600;
    }}
    .th-hoy-badge {{
        background: #e0f2fe;
        color: #0284c7;
        font-size: 6px;
        font-weight: 800;
        padding: 1px 4px;
        border-radius: 999px;
        letter-spacing: 0.08em;
    }}
    .turno-cell {{
        display: flex;
        flex-direction: column;
        justify-content: center;
        padding: 3px 2px;
        border-bottom: 1px solid #e2e8f0;
    }}
    .turno-tag {{
        font-size: 7px;
        font-weight: 800;
        letter-spacing: 0.08em;
        color: #94a3b8;
        text-transform: uppercase;
    }}
    .turno-tipo {{
        font-size: 6.5px;
        font-weight: 700;
        color: #cbd5e1;
        margin-bottom: 2px;
    }}
    .turno-hora-inicio {{
        font-size: 13px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.1;
        font-variant-numeric: tabular-nums;
    }}
    .turno-hora-fin {{
        font-size: 8.5px;
        color: #64748b;
        font-variant-numeric: tabular-nums;
    }}
    .clase-card {{
        border-radius: 12px;
        border: 1px solid var(--borde-color);
        background: var(--bg-pastel);
        padding: 6px 8px;
        display: flex;
        flex-direction: column;
        gap: 5px;
        justify-content: space-between;
        width: 100%;
        box-sizing: border-box;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .clase-top {{
        display: flex;
        align-items: flex-start;
        gap: 7px;
    }}
    .clase-ico-squircle {{
        width: 34px;
        height: 34px;
        min-width: 34px;
        border-radius: 9px;
        background: #ffffff;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
        display: flex;
        align-items: center;
        justify-content: center;
        color: var(--accent-color);
    }}
    .clase-meta {{
        flex: 1;
        min-width: 0;
    }}
    .clase-area {{
        font-size: 7px;
        font-weight: 800;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        line-height: 1.1;
        margin-bottom: 1.5px;
        color: var(--accent-color);
        opacity: 0.9;
    }}
    .clase-title-row {{
        display: flex;
        align-items: center;
        gap: 4px;
        flex-wrap: wrap;
    }}
    .clase-nombre {{
        font-size: 9.5px;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.15;
    }}
    .clase-badge {{
        display: inline-flex;
        align-items: center;
        gap: 2.5px;
        padding: 1.5px 5px;
        border-radius: 4px;
        font-size: 6.5px;
        font-weight: 700;
        color: #ffffff;
        background: var(--accent-color);
        white-space: nowrap;
    }}
    .clase-inner {{
        background: #ffffff;
        border-radius: 8px;
        padding: 3.5px 6px;
        border: 1px solid rgba(15, 23, 42, 0.06);
        display: flex;
        flex-direction: column;
        gap: 1px;
    }}
    .inner-modalidad {{
        display: flex;
        align-items: center;
        gap: 3px;
        font-size: 7px;
        font-weight: 700;
        color: #475569;
    }}
    .inner-subtexto {{
        font-size: 6.5px;
        color: #94a3b8;
        line-height: 1.1;
    }}
    .inner-docente {{
        font-size: 7.5px;
        font-weight: 600;
        color: #334155;
        margin-top: 1px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }}
    .celda-libre {{
        border-radius: 10px;
        border: 1px dashed #cbd5e1;
        background: #ffffff;
        width: 100%;
        min-height: 64px;
        display: flex;
        align-items: center;
        justify-content: center;
    }}
    .texto-libre {{
        font-size: 8px;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #cbd5e1;
    }}
    .vacio-box {{
        grid-column: 1 / -1;
        background: #ffffff;
        border: 1px dashed #cbd5e1;
        border-radius: 12px;
        padding: 36px 20px;
        text-align: center;
        color: #64748b;
        font-size: 11px;
        font-weight: 600;
    }}
    .doc-footer {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-top: 5px;
        font-size: 6.5px;
        color: #94a3b8;
    }}
    """

    html_parts = []
    html_parts.append('<!DOCTYPE html><html><head><meta charset="utf-8"><style>')
    html_parts.append(css)
    html_parts.append('</style></head><body>')
    html_parts.append('<div class="horario-container">')

    # Header
    html_parts.append(f"""
    <div class="doc-header">
        <div>
            <div class="doc-brand">SISTEMA INTEGRADO DE GESTIÓN EDUCATIVA · UNIEBEC</div>
            <div class="doc-title">Horario Oficial de Clases · {periodo_nombre}</div>
            <div class="doc-sub">Estudiante: <b>{nombre_est}</b> · Fecha de emisión: {datetime.now().strftime("%d/%m/%Y %H:%M")}</div>
        </div>
        <div class="doc-badge">HORARIO OFICIAL</div>
    </div>
    """)

    # Table grid
    html_parts.append('<div class="tabla-grid">')

    # Column Headers
    html_parts.append('<div class="th-col th-hora">HORA</div>')
    for d_idx, d_nom in dias_info:
        c_count = len(clases_por_dia[d_idx])
        es_hoy = (d_idx == dia_hoy_num) or (dia_hoy_num not in (1, 2, 3, 4, 5) and d_idx == 3)
        hoy_badge = '<span class="th-hoy-badge">HOY</span>' if es_hoy else ''
        clase_dia_estilo = 'th-dia es-hoy' if es_hoy else 'th-dia'
        html_parts.append(f"""
        <div class="th-col">
            <div class="{clase_dia_estilo}">{d_nom} {hoy_badge}</div>
            <div class="th-count">{c_count} clases</div>
        </div>
        """)

    # Grid Rows
    if not horas_ordenadas:
        html_parts.append("""
        <div class="vacio-box">
            Sin clases programadas para este periodo académico lectivo.
        </div>
        """)
    else:
        for turn_idx, (ini, fin) in enumerate(horas_ordenadas, 1):
            html_parts.append(f"""
            <div class="turno-cell">
                <div class="turno-tag">TURNO CLASE {turn_idx}</div>
                <div class="turno-tipo">- ASINCRONA</div>
                <div class="turno-hora-inicio">{ini}</div>
                <div class="turno-hora-fin">a {fin}</div>
            </div>
            """)
            for d_idx, _ in dias_info:
                clases_en_turno = [c for c in clases_por_dia[d_idx] if c.get('inicio') == ini and c.get('fin') == fin]
                if clases_en_turno:
                    c = clases_en_turno[0]
                    nom = c.get('nombre', '')
                    col_raw = c.get('color', '')
                    area, color_oficial, ico_key = resolver_materia(nom, col_raw)
                    svg_icon = ICONS_SVG.get(ico_key, ICONS_SVG['book'])
                    es_en_vivo = bool(c.get('zoom_join_url'))
                    badge_texto = 'En vivo' if es_en_vivo else 'Clase grabada'
                    badge_icon = ICONS_SVG['video'] if es_en_vivo else ICONS_SVG['play-triangle']
                    
                    prof = c.get('profesor') or 'Docente titular'
                    doc_icon = ICONS_SVG['doc']
                    
                    nom_titulo = ' '.join(p.capitalize() for p in nom.split())
                    prof_titulo = ' '.join(p.capitalize() for p in prof.split())
                    
                    html_parts.append(f"""
                    <div class="clase-card" style="--accent-color: {color_oficial}; --bg-pastel: color-mix(in srgb, {color_oficial} 18%, #ffffff); --borde-color: color-mix(in srgb, {color_oficial} 34%, #ffffff);">
                        <div class="clase-top">
                            <div class="clase-ico-squircle">{svg_icon}</div>
                            <div class="clase-meta">
                                <div class="clase-area">{area}</div>
                                <div class="clase-title-row">
                                    <div class="clase-nombre">{nom_titulo}</div>
                                    <div class="clase-badge">{badge_icon} {badge_texto}</div>
                                </div>
                            </div>
                        </div>
                        <div class="clase-inner">
                            <div class="inner-modalidad">{doc_icon} Clase grabada</div>
                            <div class="inner-subtexto">Clase grabada pendiente</div>
                            <div class="inner-docente">{prof_titulo}</div>
                        </div>
                    </div>
                    """)
                else:
                    html_parts.append("""
                    <div class="celda-libre">
                        <span class="texto-libre">LIBRE</span>
                    </div>
                    """)

    html_parts.append('</div>') # end tabla-grid

    # Footer
    html_parts.append("""
    <div class="doc-footer">
        <span>UNIEBEC · Sistema de Gestión Educativa · Todos los derechos reservados.</span>
        <span>Documento oficial de control académico · Validez periódica</span>
    </div>
    """)

    html_parts.append('</div></body></html>')
    return ''.join(html_parts)

def generar_horario_pdf_reportlab_fallback(persona_id, periodo_id, datos_horario):
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
        'TituloDoc', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=15, leading=18,
        textColor=colors.HexColor('#002B49'), alignment=1
    )
    subtitulo_style = ParagraphStyle(
        'SubtituloDoc', parent=styles['Normal'],
        fontName='Helvetica', fontSize=8.5, leading=12,
        textColor=colors.HexColor('#475569'), alignment=1
    )
    cell_hora_style = ParagraphStyle(
        'CellHora', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8.5, leading=12,
        textColor=colors.HexColor('#0F172A'), alignment=1
    )
    cell_libre_style = ParagraphStyle(
        'CellLibre', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=8, leading=10,
        textColor=colors.HexColor('#CBD5E1'), alignment=1
    )

    elementos = []
    elementos.append(Paragraph('UNIDAD EDUCATIVA BOLIVARIANA', titulo_style))
    elementos.append(Spacer(1, 2))
    elementos.append(Paragraph(f'HORARIO OFICIAL DE CLASES · {periodo_nombre}', subtitulo_style))
    elementos.append(Paragraph(f'Estudiante: <b>{nombre_est}</b> · Fecha de emisión: {datetime.now().strftime("%d/%m/%Y %H:%M")}', subtitulo_style))
    elementos.append(Spacer(1, 8))

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
    header_col_style = ParagraphStyle(
        'HeaderCol', parent=styles['Normal'],
        fontName='Helvetica-Bold', fontSize=9, leading=12,
        textColor=colors.white, alignment=1
    )
    fila_hdr = [Paragraph(col, header_col_style) for col in dias_titulos]
    data_tabla.append(fila_hdr)

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#002B49')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    for row_idx, (ini, fin) in enumerate(horas_ordenadas, start=1):
        rango_str = f"<b>{ini}</b><br/><font color='#64748B' size='7'>a {fin}</font>"
        fila = [Paragraph(rango_str, cell_hora_style)]
        for col_idx, dia_idx in enumerate(range(1, 6), start=1):
            clases_hora = [c for c in clases_por_dia[dia_idx] if c.get('inicio') == ini and c.get('fin') == fin]
            if clases_hora:
                c = clases_hora[0]
                area, col_oficial, _ = resolver_materia(c.get('nombre', ''), c.get('color', ''))
                texto_celda = (
                    f"<font size='6' color='{col_oficial}'><b>{area}</b></font><br/>"
                    f"<font size='8' color='#0F172A'><b>{c.get('nombre', '').title()}</b></font><br/>"
                    f"<font size='6' color='{col_oficial}'><b>[ Clase grabada ]</b></font><br/>\""
                    f"<font size='6.5' color='#334155'>{c.get('profesor', '').title()}</font>"
                )
                cell_style = ParagraphStyle(
                    f'Cell_{row_idx}_{col_idx}', parent=styles['Normal'],
                    fontName='Helvetica', leading=9, alignment=1
                )
                fila.append(Paragraph(texto_celda, cell_style))
            else:
                fila.append(Paragraph('LIBRE', cell_libre_style))
        data_tabla.append(fila)

    col_widths = [72, 138, 138, 138, 138, 138]
    tabla = Table(data_tabla, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle(table_styles))
    elementos.append(tabla)
    doc.build(elementos)
    return buffer.getvalue()

def generar_horario_pdf(persona_id, periodo_id, datos_horario):
    chromium_path = '/usr/bin/chromium'
    if not os.path.exists(chromium_path):
        return generar_horario_pdf_reportlab_fallback(persona_id, periodo_id, datos_horario)

    try:
        html_content = generar_horario_html(persona_id, periodo_id, datos_horario)
        with tempfile.NamedTemporaryFile('w', suffix='.html', delete=False, encoding='utf-8') as f_html:
            f_html.write(html_content)
            html_path = f_html.name

        pdf_path = html_path.replace('.html', '.pdf')
        cmd = [
            chromium_path,
            '--headless=new',
            '--disable-gpu',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--no-pdf-header-footer',
            f'--print-to-pdf={pdf_path}',
            html_path
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=15)
        if res.returncode == 0 and os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as f_pdf:
                pdf_bytes = f_pdf.read()
            return pdf_bytes
        else:
            return generar_horario_pdf_reportlab_fallback(persona_id, periodo_id, datos_horario)
    except Exception:
        return generar_horario_pdf_reportlab_fallback(persona_id, periodo_id, datos_horario)
    finally:
        try:
            if 'html_path' in locals() and os.path.exists(html_path):
                os.remove(html_path)
            if 'pdf_path' in locals() and os.path.exists(pdf_path):
                os.remove(pdf_path)
        except Exception:
            pass
