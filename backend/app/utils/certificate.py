"""
Génération des certificats de traitement thermique (PDF + ZIP).
Un certificat par OF, données communes à la charge précalculées une seule fois.

Normes de référence : AMS 2750 (pyrométrie), AMS 2759 (traitement thermique aciers),
EN 9102 (First Article Inspection), NADCAP HT.
"""

import io
import math
import zipfile
from datetime import datetime, timedelta

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
import os as _os
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether,
)

LOGO_SAFRAN = _os.path.normpath(
    _os.path.join(_os.path.dirname(__file__), '..', '..', '..', 'LOGO_SAFRAN_noir2.png')
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Charte graphique ────────────────────────────────────────────────
NAVY   = colors.HexColor('#0f172a')
BLUE   = colors.HexColor('#2563eb')
LIGHT  = colors.HexColor('#eff6ff')
GRAY   = colors.HexColor('#64748b')
RED    = colors.HexColor('#dc2626')
WHITE  = colors.white
BLACK  = colors.black

W, H = A4

STATION_LABELS = {
    3: 'C10-3', 4: 'Bac huile', 5: 'C10-5', 6: 'Lavage', 7: 'C6-7',
    95: 'Four 7', 96: 'Four 4', 97: '653', 98: 'Cuve trempe alu', 99: '36',
}

def station_label(sid):
    return STATION_LABELS.get(int(sid) if sid is not None else 0, f'Four {sid}')

_STAR_STATION_LABELS = {
     7: 'Revenu C6-7',
    95: 'Revenu Four 7',
    96: 'Revenu Four 4',
    97: 'Traitement air liquide',
    98: 'Trempe alu',
    99: 'Étuve — dégazage H₂',
}


def clean_cycle(cycle, station=None):
    """Remplace les cycles sans nom (***...) par un libellé lisible."""
    if not cycle:
        return 'Cycle non identifié'
    if set(cycle.strip()) <= {'*'}:
        if station is not None:
            lbl = _STAR_STATION_LABELS.get(int(station))
            if lbl:
                return lbl
        return 'Cycle non identifié'
    return cycle

def fmt_dt(dt):
    if dt is None: return '—'
    if isinstance(dt, str): dt = datetime.fromisoformat(dt.replace(' ', 'T'))
    return dt.strftime('%d/%m/%Y %H:%M')

def fmt_duration(sec):
    if sec is None or sec < 0: return '—'
    h, m = divmod(int(sec) // 60, 60)
    return f'{h}h{m:02d}' if h else f'{m}min'


# ── Styles ──────────────────────────────────────────────────────────
def _styles():
    base = getSampleStyleSheet()
    return {
        'h1': ParagraphStyle('h1', parent=base['Normal'], fontName='Helvetica-Bold',
                             fontSize=13, textColor=WHITE, alignment=TA_CENTER, spaceAfter=2),
        'h1_cert': ParagraphStyle('h1_cert', parent=base['Normal'], fontName='Helvetica-Bold',
                                  fontSize=9, textColor=WHITE, alignment=TA_CENTER, spaceAfter=0),
        'h2': ParagraphStyle('h2', parent=base['Normal'], fontName='Helvetica-Bold',
                             fontSize=9, textColor=NAVY, spaceAfter=3, spaceBefore=8),
        'body': ParagraphStyle('body', parent=base['Normal'], fontName='Helvetica',
                               fontSize=8, leading=11),
        'small': ParagraphStyle('small', parent=base['Normal'], fontName='Helvetica',
                                fontSize=7, textColor=GRAY),
        'center': ParagraphStyle('center', parent=base['Normal'], fontName='Helvetica',
                                 fontSize=8, alignment=TA_CENTER),
        'italic': ParagraphStyle('italic', parent=base['Normal'], fontName='Helvetica-Oblique',
                                 fontSize=7, textColor=GRAY, leading=10),
    }

TABLE_STYLE_BASE = TableStyle([
    ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE',      (0, 0), (-1, -1), 7.5),
    ('BACKGROUND',   (0, 0), (-1, 0), LIGHT),
    ('TEXTCOLOR',    (0, 0), (-1, 0), NAVY),
    ('GRID',         (0, 0), (-1, -1), 0.3, colors.HexColor('#e2e8f0')),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, colors.HexColor('#f8fafc')]),
    ('TOPPADDING',   (0, 0), (-1, -1), 3),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ('LEFTPADDING',  (0, 0), (-1, -1), 4),
    ('RIGHTPADDING', (0, 0), (-1, -1), 4),
])

def _section_header(title, S):
    return [
        Spacer(1, 3*mm),
        Table([[Paragraph(title, S['h1'])]],
              colWidths=[W - 30*mm],
              style=TableStyle([
                  ('BACKGROUND', (0, 0), (-1, -1), NAVY),
                  ('TOPPADDING', (0, 0), (-1, -1), 4),
                  ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                  ('LEFTPADDING', (0, 0), (-1, -1), 6),
              ])),
        Spacer(1, 2*mm),
    ]


# ── Calcul des paliers de température (≈ PassageDetailView.vue) ─────
PALIER_MIN_SEC    = 10 * 60
PALIER_MIN_VALUE  = 50
EXCLUDED          = {'mes_temp_secu_b', 'mes_temp_secu_m_h'}

def _matches(cycle: str, pattern: str) -> bool:
    import fnmatch
    if '*' not in pattern:
        return pattern in cycle
    return fnmatch.fnmatch(cycle, pattern)


def get_paliers_config(cycle, conn):
    """Retourne les consignes configurées pour ce cycle (liste de float) ou None."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT consignes FROM param_paliers_cycle WHERE cycle_pattern = %s", [cycle]
            )
            row = cur.fetchone()
            if row:
                return [float(x.strip()) for x in row['consignes'].split(',') if x.strip()]
            cur.execute("""
                SELECT cycle_pattern, consignes FROM param_paliers_cycle
                ORDER BY LENGTH(cycle_pattern) DESC
            """)
            for r in cur.fetchall():
                if _matches(cycle, r['cycle_pattern']):
                    return [float(x.strip()) for x in r['consignes'].split(',') if x.strip()]
    except Exception:
        pass
    return None   # détection automatique


def get_tolerance(cycle, conn):
    """Tolérance °C depuis la table param_seuils_temperature."""
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tolerance_c FROM param_seuils_temperature WHERE cycle_pattern = %s",
                [cycle],
            )
            row = cur.fetchone()
            if row:
                return row['tolerance_c']
            cur.execute("""
                SELECT cycle_pattern, tolerance_c
                FROM param_seuils_temperature
                WHERE cycle_pattern <> '*' AND cycle_pattern <> %s
                ORDER BY LENGTH(cycle_pattern) DESC
            """, [cycle])
            for r in cur.fetchall():
                if _matches(cycle, r['cycle_pattern']):
                    return r['tolerance_c']
            cur.execute(
                "SELECT tolerance_c FROM param_seuils_temperature WHERE cycle_pattern = '*'"
            )
            row = cur.fetchone()
            return row['tolerance_c'] if row else 10.0
    except Exception:
        return 10.0


def compute_paliers(tags_data, tps_fin, tolerance_c=10.0):
    """
    tags_data : dict { variable: [(ts, value), ...] }
    Retourne une liste de dicts {consigne, atteinte, duree_s, inter_s}
    """
    cons = tags_data.get('cons_temp', [])
    if not cons:
        return []

    measures = {k: v for k, v in tags_data.items()
                if k != 'cons_temp' and k not in EXCLUDED}
    if not measures:
        return []

    tps_fin_ts = tps_fin.timestamp() if tps_fin else None

    # Détecter les paliers dans cons_temp
    paliers_raw = []
    i, pts = 0, cons
    while i < len(pts):
        val = pts[i][1]
        tol = tolerance_c  # tolérance en degrés absolus
        j = i
        while j + 1 < len(pts) and abs(pts[j + 1][1] - val) <= tol:
            j += 1
        t_start = pts[i][0].timestamp() if hasattr(pts[i][0], 'timestamp') else pts[i][0]
        t_end   = pts[j][0].timestamp() if hasattr(pts[j][0], 'timestamp') else pts[j][0]
        if val >= PALIER_MIN_VALUE and (t_end - t_start) >= PALIER_MIN_SEC:
            paliers_raw.append({'value': val, 't_start': t_start})
        i = j + 1

    results = []
    for palier in paliers_raw:
        tol = tolerance_c
        t_att   = None
        all_ok  = True
        for mes_pts in measures.values():
            found = next(
                (p for p in mes_pts
                 if (p[0].timestamp() if hasattr(p[0], 'timestamp') else p[0]) >= palier['t_start']
                 and p[1] >= palier['value'] - tol),
                None,
            )
            if not found:
                all_ok = False
                break
            t = found[0].timestamp() if hasattr(found[0], 'timestamp') else found[0]
            if t_att is None or t > t_att:
                t_att = t

        duree = (tps_fin_ts - t_att) if (all_ok and t_att and tps_fin_ts) else None
        results.append({
            'consigne': round(palier['value']),
            'atteinte_ts': t_att if all_ok else None,
            'duree_s': duree,
        })

    # Calculer les inter-paliers
    for idx, p in enumerate(results):
        if idx > 0 and results[idx - 1]['atteinte_ts'] and p['atteinte_ts']:
            p['inter_s'] = p['atteinte_ts'] - results[idx - 1]['atteinte_ts']
        else:
            p['inter_s'] = None

    return results


# ── Graphiques matplotlib ────────────────────────────────────────────
CATEGORY_LABELS = {
    'temperature': 'Température (°C)',
    'puissance':   'Potentiel carbone',
    'atmosphere':  'Sondes à oxygène',
}
CATEGORY_COLORS = {
    'temperature': ['#2563eb', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6'],
    'puissance':   ['#0ea5e9', '#f97316'],
    'atmosphere':  ['#10b981', '#06b6d4'],
}

def make_chart(category, tags_data, tps_deb, paliers=None):
    """Génère un graphique matplotlib en mémoire (PNG bytes).
    paliers : liste de dicts {consigne, atteinte_ts} pour les lignes verticales.
    """
    fig, ax = plt.subplots(figsize=(6.5, 2.5))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('#f8fafc')
    colors_ = CATEGORY_COLORS.get(category, ['#2563eb'])

    ref_ts = tps_deb.timestamp() if tps_deb else 0

    plotted = False
    for idx, (var, pts) in enumerate(tags_data.items()):
        if not pts:
            continue
        xs_min = [((p[0].timestamp() if hasattr(p[0], 'timestamp') else p[0]) - ref_ts) / 60
                  for p in pts]
        ys     = [p[1] for p in pts]
        ax.plot(xs_min, ys, color=colors_[idx % len(colors_)],
                linewidth=1.0, label=var)
        plotted = True

    if not plotted:
        plt.close(fig)
        return None

    # Lignes verticales d'atteinte de palier (température uniquement)
    if paliers:
        for pal in paliers:
            ts = pal.get('atteinte_ts')
            if not ts:
                continue
            x_min = (ts - ref_ts) / 60
            ax.axvline(x=x_min, color='#dc2626', linestyle='--',
                       linewidth=1.0, alpha=0.8, zorder=5)
            ax.annotate(
                f"{pal['consigne']}°C",
                xy=(x_min, 0), xycoords=('data', 'axes fraction'),
                xytext=(3, 4), textcoords='offset points',
                fontsize=6, color='#dc2626', va='bottom', ha='left',
                annotation_clip=False,
            )

    ax.set_xlabel('Temps écoulé (min)', fontsize=7)
    ax.set_ylabel(CATEGORY_LABELS.get(category, category), fontsize=7)
    ax.tick_params(labelsize=6.5)
    ax.grid(True, alpha=0.3, linewidth=0.4)

    # Légende à droite, au meilleur endroit disponible
    n_series = sum(1 for pts in tags_data.values() if pts)
    ax.legend(fontsize=6, loc='best',
              framealpha=0.88, edgecolor='#e2e8f0',
              ncol=1 if n_series <= 4 else 2)
    fig.tight_layout(pad=0.8)

    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=130, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return buf


# ── Données communes à la fournée ────────────────────────────────────
def fetch_charge_data(charge, conn):
    """
    Récupère toutes les données partagées entre les OF d'une même charge :
    - métadonnées charge
    - passages + time series + paliers
    - NC
    - lot list (pour itération)
    """
    cur = conn.cursor()

    # Métadonnées charge
    cur.execute("""
        SELECT operateur, date_creat, numero, portique
        FROM sup_charge WHERE charge = %s ORDER BY id DESC LIMIT 1
    """, [charge])
    charge_meta = cur.fetchone() or {}

    # OF de la charge
    cur.execute("""
        SELECT DISTINCT h.lot, l.piece, l.nuance, l.denomination,
                        l.poids, l.tonnage, l.nbre
        FROM sup_histo h
        LEFT JOIN sup_lot l ON l.lot = h.lot
        WHERE h.charge = %s ORDER BY h.lot
    """, [charge])
    lots = cur.fetchall()

    # Passages (dédupliqués)
    cur.execute("""
        SELECT MIN(id) AS id, station, tps_deb, MAX(tps_fin) AS tps_fin, cycle
        FROM sup_histo WHERE charge = %s
          AND cycle IS NOT NULL AND cycle <> ''
        GROUP BY station, tps_deb, cycle ORDER BY tps_deb
    """, [charge])
    passages = cur.fetchall()

    # Plan d'exécution (recette)
    cur.execute("""
        SELECT recette, bloc, type, cycle, fait_ou_pas
        FROM sup_plt_gen WHERE charge = %s ORDER BY bloc
    """, [charge])
    plt_steps = cur.fetchall()

    # Time series pour tous les passages
    CATEGORY_TABLES = {
        'temperature': 'mesures_temperature',
        'atmosphere':  'mesures_atmosphere',
        'puissance':   'mesures_puissance',
    }
    passages_ts = {}   # passage_id -> {category -> {variable -> [(ts,val)]}}
    for p in passages:
        pid = p['id']
        cur.execute("""
            SELECT id, name, variable, category FROM tags
            WHERE equip_type='four' AND equip_id=%s
              AND variable NOT LIKE %s
            ORDER BY category, variable
        """, [p['station'], '%secu%'])
        tags = cur.fetchall()

        cat_data = {}
        for tag in tags:
            table = CATEGORY_TABLES.get(tag['category'])
            if not table: continue
            cur.execute(f"""
                SELECT ts, ROUND(value,1) AS value FROM {table}
                WHERE tag_id=%s AND ts BETWEEN %s AND %s ORDER BY ts
            """, [tag['id'], p['tps_deb'], p['tps_fin']])
            pts = [(r['ts'], r['value']) for r in cur.fetchall()]
            cat_data.setdefault(tag['category'], {})[tag['variable']] = pts

        passages_ts[pid] = {
            'tps_deb': p['tps_deb'],
            'tps_fin': p['tps_fin'],
            'station': p['station'],
            'cycle':   p['cycle'],
            'categories': cat_data,
        }

    # NC
    cur.execute("""
        SELECT id, lot, date_declaration, nature, description,
               operateur, statut, action_corrective
        FROM nc_declarations
        WHERE charge = %s COLLATE utf8mb4_unicode_ci
        ORDER BY date_declaration
    """, [charge])
    ncs = cur.fetchall()

    # Recette name
    recette_name = plt_steps[0]['recette'] if plt_steps else None
    if not recette_name and passages:
        # Chercher dans les passages un cycle nommé (hors *** et LAVAGE)
        named = next(
            (p['cycle'] for p in passages
             if p['cycle'] and set(p['cycle'].strip()) > {'*'}
             and p['cycle'] != 'LAVAGE_LONG'),
            None,
        )
        if named:
            cur.execute("SELECT recette FROM sup_recette WHERE recette LIKE %s LIMIT 1",
                        [f"%{named}%"])
            row = cur.fetchone()
            recette_name = row['recette'] if row else named
        else:
            recette_name = '—'

    return {
        'charge':       charge,
        'charge_meta':  charge_meta,
        'lots':         lots,
        'passages':     passages,
        'plt_steps':    plt_steps,
        'passages_ts':  passages_ts,
        'ncs':          ncs,
        'recette_name': recette_name,
    }


# ── Génération d'un PDF ──────────────────────────────────────────────
def build_pdf(lot_info, charge_data, cert_num, conn=None):
    """Génère un PDF pour un OF donné. Retourne les bytes du PDF."""
    S = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=15*mm, bottomMargin=20*mm,
        title=f"Certificat de traitement thermique — OF {lot_info['lot']}",
    )

    story = []
    cw = W - 30*mm   # largeur utile

    # ── En-tête document ──────────────────────────────────────────
    # Colonne logo : fond blanc, largeur fixe
    logo_w, logo_h = 38*mm, 11*mm
    try:
        logo_img = Image(LOGO_SAFRAN, width=logo_w, height=logo_h)
    except Exception:
        logo_img = Paragraph('SAFRAN', S['h1'])

    # 2 lignes : titre seul / N° seul — logo et date s'étendent sur 2 lignes
    header_data = [
        [logo_img,
         Paragraph('CERTIFICAT DE TRAITEMENT THERMIQUE', S['h1']),
         Paragraph(fmt_dt(datetime.now()), S['h1'])],
        ['',
         Paragraph(f'N° {cert_num}', S['h1_cert']),
         ''],
    ]
    story.append(Table(
        header_data,
        colWidths=[logo_w + 2*mm, cw - logo_w - 2*mm - 30*mm, 30*mm],
        style=TableStyle([
            # Logo : fond blanc, centré
            ('BACKGROUND',    (0, 0), (0, 1), WHITE),
            ('VALIGN',        (0, 0), (0, 1), 'MIDDLE'),
            ('ALIGN',         (0, 0), (0, 1), 'CENTER'),
            ('SPAN',          (0, 0), (0, 1)),
            # Titre + N° : fond navy
            ('BACKGROUND',    (1, 0), (2, 1), NAVY),
            ('VALIGN',        (1, 0), (2, 1), 'MIDDLE'),
            # Date : s'étend sur 2 lignes
            ('SPAN',          (2, 0), (2, 1)),
            ('ALIGN',         (2, 0), (2, 1), 'CENTER'),
            ('TOPPADDING',    (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING',   (0, 0), (-1, -1), 6),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
            # Séparateur entre titre et N°
            ('LINEBELOW',     (1, 0), (1, 0), 0.5, colors.HexColor('#1e3a5f')),
        ]),
    ))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        'Conforme aux exigences AMS 2750 / AMS 2759 — NADCAP Heat Treating',
        S['italic'],
    ))

    # ── Identification OF (spécifique) ───────────────────────────
    story += _section_header('IDENTIFICATION DE L\'ORDRE DE FABRICATION', S)
    piece = lot_info.get('piece') or '—'
    of_rows = [
        ['N° OF (Lot)', lot_info['lot'],           'Référence pièce', piece],
        ['Désignation', lot_info.get('denomination') or '—', 'Nuance matière', lot_info.get('nuance') or '—'],
        ['Quantité',   f"{lot_info.get('nbre') or '—'} pièce(s)", 'Poids unitaire', f"{lot_info.get('poids') or '—'} kg"],
        ['Poids total', f"{lot_info.get('tonnage') or '—'} kg", '', ''],
    ]
    story.append(Table(
        of_rows, colWidths=[cw*0.2, cw*0.3, cw*0.2, cw*0.3],
        style=TableStyle([
            *TABLE_STYLE_BASE._cmds,
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY),
            ('TEXTCOLOR', (2, 0), (2, -1), NAVY),
        ]),
    ))

    # ── Identification charge ────────────────────────────────────
    story += _section_header('IDENTIFICATION DE LA CHARGE', S)
    cm = charge_data['charge_meta']
    passages = charge_data['passages']
    tps_deb_global = passages[0]['tps_deb'] if passages else None
    tps_fin_global = passages[-1]['tps_fin'] if passages else None
    charge_rows = [
        ['N° charge',   charge_data['charge'],
         'Opérateur',   cm.get('operateur') or '—'],
        ['Date création', cm.get('date_creat') or '—',
         'Portique',    station_label(cm.get('portique'))],
        ['Début traitement', fmt_dt(tps_deb_global),
         'Fin traitement',   fmt_dt(tps_fin_global)],
        ['Recette',     charge_data['recette_name'] or '—', '', ''],
    ]
    story.append(Table(
        charge_rows, colWidths=[cw*0.2, cw*0.3, cw*0.2, cw*0.3],
        style=TableStyle([
            *TABLE_STYLE_BASE._cmds,
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (0, 0), (0, -1), NAVY),
            ('TEXTCOLOR', (2, 0), (2, -1), NAVY),
        ]),
    ))

    # ── Cycle d'exécution ────────────────────────────────────────
    recette_label = charge_data.get('recette_name') or '—'
    story += _section_header(f"CYCLE D'EXÉCUTION  —  {recette_label}", S)
    def _step_duration(tps_deb, tps_fin):
        if tps_deb and tps_fin:
            return fmt_duration(int((tps_fin - tps_deb).total_seconds()))
        return '—'

    STATUTS = {1: 'Exécuté', 0: 'En cours', -1: 'Non exécuté'}
    if charge_data['plt_steps']:
        step_rows = [['Bloc', 'Cycle', 'Équipement', 'Début', 'Fin', 'Durée', 'Statut']]
        pby = {}
        for p in passages:
            pby.setdefault(p['cycle'], []).append(p)
        for step in charge_data['plt_steps']:
            bucket = pby.get(step['cycle'], [])
            matched = bucket.pop(0) if bucket else None
            step_rows.append([
                str(step['bloc']),
                clean_cycle(step['cycle'], matched['station'] if matched else None),
                station_label(matched['station']) if matched else '—',
                fmt_dt(matched['tps_deb']) if matched else '—',
                fmt_dt(matched['tps_fin']) if matched else '—',
                _step_duration(matched['tps_deb'] if matched else None,
                               matched['tps_fin'] if matched else None),
                STATUTS.get(step['fait_ou_pas'], '—'),
            ])
    else:
        step_rows = [['Équipement', 'Cycle', 'Début', 'Fin', 'Durée']]
        for p in passages:
            step_rows.append([
                station_label(p['station']), clean_cycle(p['cycle'], p['station']),
                fmt_dt(p['tps_deb']), fmt_dt(p['tps_fin']),
                _step_duration(p['tps_deb'], p['tps_fin']),
            ])

    story.append(Table(
        step_rows,
        colWidths=[cw*0.06, cw*0.20, cw*0.15, cw*0.18, cw*0.18, cw*0.10, cw*0.13] if len(step_rows[0]) == 7
                  else [cw*0.2, cw*0.2, cw*0.22, cw*0.22, cw*0.16],
        style=TableStyle([
            *TABLE_STYLE_BASE._cmds,
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), NAVY),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ]),
    ))

    # ── Graphiques et paliers (un bloc par passage avec time series) ─
    ORDER = ['temperature', 'puissance', 'atmosphere']
    for pid, ts_data in charge_data['passages_ts'].items():
        if not ts_data['categories']:
            continue

        story += _section_header(
            f"PARAMÈTRES ENREGISTRÉS — {station_label(ts_data['station'])} "
            f"· {clean_cycle(ts_data['cycle'], ts_data.get('station'))} · {fmt_dt(ts_data['tps_deb'])}",
            S,
        )

        # Calculer les paliers en premier (nécessaires pour les lignes sur le graphique)
        temp_tags   = ts_data['categories'].get('temperature', {})
        cycle       = ts_data.get('cycle', '') or ''
        tol_c       = get_tolerance(cycle, conn)
        all_paliers = compute_paliers(temp_tags, ts_data['tps_fin'], tolerance_c=tol_c) if temp_tags else []
        # Filtrer sur les consignes configurées si applicable
        cfg_consignes = get_paliers_config(cycle, conn) if cycle else None
        if cfg_consignes:
            paliers = [p for p in all_paliers
                       if any(abs(c - p['consigne']) <= tol_c for c in cfg_consignes)]
        else:
            paliers = []   # pas de règle = pas de paliers dans le PV

        for cat in ORDER:
            cat_tags = ts_data['categories'].get(cat, {})
            if not cat_tags:
                continue
            chart_paliers = paliers if cat == 'temperature' else None
            img_buf = make_chart(cat, cat_tags, ts_data['tps_deb'], paliers=chart_paliers)
            if img_buf:
                story.append(Paragraph(CATEGORY_LABELS.get(cat, cat), S['h2']))
                story.append(Image(img_buf, width=cw, height=58*mm))
                story.append(Spacer(1, 2*mm))

            # Tableau des paliers directement sous la courbe température
            if cat == 'temperature' and paliers:
                pal_rows = [['Consigne (°C)', 'Atteinte le', 'Temps de maintien']]
                for pal in paliers:
                    att_str = fmt_dt(datetime.fromtimestamp(pal['atteinte_ts'])) if pal['atteinte_ts'] else 'Non atteint'
                    pal_rows.append([
                        f"{pal['consigne']} °C",
                        att_str,
                        fmt_duration(pal.get('duree_s')),
                    ])
                story.append(Table(
                    pal_rows, colWidths=[cw*0.2, cw*0.45, cw*0.35],
                    style=TableStyle([
                        *TABLE_STYLE_BASE._cmds,
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('BACKGROUND', (0, 0), (-1, 0), NAVY),
                        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                    ]),
                ))
                story.append(Spacer(1, 3*mm))

    # ── Non-conformités ──────────────────────────────────────────
    ncs_lot = [nc for nc in charge_data['ncs']
               if nc.get('lot') is None or nc.get('lot') == lot_info['lot']]
    if charge_data['ncs']:   # toutes les NC de la charge
        story += _section_header('DÉCLARATIONS DE NON-CONFORMITÉ', S)
        if not charge_data['ncs']:
            story.append(Paragraph('Aucune non-conformité déclarée.', S['body']))
        else:
            nc_rows = [['Date', 'Lot', 'Nature', 'Description', 'Statut']]
            for nc in charge_data['ncs']:
                nc_rows.append([
                    fmt_dt(nc.get('date_declaration')),
                    nc.get('lot') or 'Toute charge',
                    nc.get('nature') or '—',
                    (nc.get('description') or '—')[:80],
                    nc.get('statut') or '—',
                ])
            story.append(Table(
                nc_rows, colWidths=[cw*0.18, cw*0.12, cw*0.22, cw*0.36, cw*0.12],
                style=TableStyle([
                    *TABLE_STYLE_BASE._cmds,
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#fee2e2')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), RED),
                    ('FONTSIZE', (0, 0), (-1, -1), 7),
                ]),
            ))
    else:
        story += _section_header('DÉCLARATIONS DE NON-CONFORMITÉ', S)
        story.append(Paragraph('Aucune non-conformité déclarée pour cette charge.', S['body']))

    # ── Déclaration de conformité ────────────────────────────────
    story += _section_header('DÉCLARATION DE CONFORMITÉ', S)
    story.append(Paragraph(
        f'Le soussigné certifie que le traitement thermique de l\'OF <b>{lot_info["lot"]}</b> '
        f'(référence <b>{lot_info.get("piece") or "—"}</b>, charge <b>{charge_data["charge"]}</b>) '
        f'a été réalisé conformément aux spécifications applicables et aux paramètres enregistrés '
        f'dans le présent certificat.',
        S['body'],
    ))
    story.append(Spacer(1, 8*mm))

    sig_rows = [
        ['Opérateur', '',  'Contrôle qualité', ''],
        ['Nom :', '________________________', 'Nom :', '________________________'],
        ['Date :', '________________________', 'Date :', '________________________'],
        ['Visa :', '________________________', 'Visa :', '________________________'],
    ]
    story.append(Table(
        sig_rows, colWidths=[cw*0.12, cw*0.38, cw*0.12, cw*0.38],
        style=TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('SPAN', (0, 0), (1, 0)),
            ('SPAN', (2, 0), (3, 0)),
            ('BACKGROUND', (0, 0), (1, 0), LIGHT),
            ('BACKGROUND', (2, 0), (3, 0), LIGHT),
            ('TEXTCOLOR', (0, 0), (-1, 0), NAVY),
        ]),
    ))

    story.append(Spacer(1, 5*mm))
    story.append(HRFlowable(width=cw, thickness=0.5, color=GRAY))
    story.append(Paragraph(
        f'Document généré le {fmt_dt(datetime.now())} — '
        f'Portail Traitement Thermique — Conservation 25 ans (exigence NADCAP HT)',
        S['small'],
    ))

    doc.build(story)
    return buf.getvalue()


# ── PDF pour un seul OF ──────────────────────────────────────────────
def generate_single_pdf(charge, lot_id, conn):
    """Génère le PDF pour un OF unique. Retourne les bytes PDF."""
    data = fetch_charge_data(charge, conn)
    lot_info = next((l for l in data['lots'] if l['lot'] == lot_id), None)
    if not lot_info:
        raise ValueError(f"OF {lot_id} non trouvé dans la charge {charge}")
    cert_num = f"TTH-{charge}-{lot_id}-{datetime.now().strftime('%Y%m%d')}"
    return build_pdf(lot_info, data, cert_num, conn=conn)


# ── ZIP tous les OF ───────────────────────────────────────────────────
def generate_zip(charge, conn):
    """
    Génère un ZIP contenant un PDF par OF de la charge.
    Retourne les bytes du ZIP.
    """
    data = fetch_charge_data(charge, conn)
    if not data['lots']:
        raise ValueError(f"Aucun OF trouvé pour la charge {charge}")

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for idx, lot in enumerate(data['lots'], start=1):
            cert_num = f"TTH-{charge}-{lot['lot']}-{datetime.now().strftime('%Y%m%d')}"
            pdf_bytes = build_pdf(lot, data, cert_num, conn=conn)
            filename = f"Certificat_{charge}_{lot['lot']}.pdf"
            zf.writestr(filename, pdf_bytes)

    zip_buf.seek(0)
    return zip_buf.getvalue()
