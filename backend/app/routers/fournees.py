from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from app.db import get_conn
from app.models import AlarmeItem, FourneeDetail, FourneeListResponse, NcCreate, NcDeclaration, RecettePlan, SeriesResponse, SeriesTag

router = APIRouter()

CATEGORY_TABLES = {
    'temperature': 'mesures_temperature',
    'atmosphere': 'mesures_atmosphere',
    'puissance': 'mesures_puissance',
}


@router.get("/fournees", response_model=FourneeListResponse)
def list_fournees(
    station: Optional[int] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    q: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    conn=Depends(get_conn),
):
    # Une "fournee" correspond a une charge : un ensemble d'OF (lot) places
    # ensemble dans le four, eventuellement repasses plusieurs fois (passages).
    having = []
    having_params: list = []

    if station is not None:
        having.append("MAX(h.station = %s) = 1")
        having_params.append(station)
    if date_from is not None:
        having.append("MAX(h.tps_deb >= %s) = 1")
        having_params.append(date_from)
    if date_to is not None:
        having.append("MAX(h.tps_deb < %s) = 1")
        having_params.append(date_to + timedelta(days=1))
    if q:
        like = f"%{q}%"
        having.append("MAX(h.lot LIKE %s OR h.piece LIKE %s OR h.cycle LIKE %s OR h.charge LIKE %s) = 1")
        having_params.extend([like, like, like, like])

    having_sql = f"HAVING {' AND '.join(having)}" if having else ""

    # Requête légère : agrégations pures, AUCUNE sous-requête corrélée
    # COUNT et fetch des IDs sur les 10k+ charges → rapide
    light_sql = f"""
        SELECT h.charge,
               MIN(h.tps_deb) AS tps_deb,
               MAX(h.tps_fin) AS tps_fin,
               COUNT(DISTINCT h.station, h.tps_deb, h.cycle) AS nb_passages,
               GROUP_CONCAT(DISTINCT h.station ORDER BY h.station SEPARATOR ', ') AS stations,
               COUNT(DISTINCT h.lot) AS nb_of,
               GROUP_CONCAT(DISTINCT h.lot ORDER BY h.lot SEPARATOR ', ') AS lots,
               SUM(CASE WHEN h.tps_fin IS NULL AND h.cycle <> 'LAVAGE_LONG' THEN 1 ELSE 0 END)
                   AS open_non_lavage,
               SUM(CASE WHEN h.tps_fin IS NULL AND h.cycle = 'LAVAGE_LONG' THEN 1 ELSE 0 END)
                   AS open_lavage
        FROM sup_histo h
        GROUP BY h.charge
        {having_sql}
    """

    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) AS total FROM ({light_sql}) g", having_params)
        total = cur.fetchone()['total']

        cur.execute(f"{light_sql} ORDER BY tps_fin DESC LIMIT %s OFFSET %s",
                    having_params + [limit, offset])
        items = list(cur.fetchall())

        # Enrichissement ciblé sur la page courante uniquement
        if items:
            charges = [i['charge'] for i in items]
            ph = ','.join(['%s'] * len(charges))

            # ── Statut et cycle en cours (50 charges max) ──────────
            cur.execute(f"""
                SELECT pg.charge,
                       MAX(CASE WHEN pg.fait_ou_pas = 0 AND pg.cycle <> 'LAVAGE_LONG' THEN 1 ELSE 0 END)
                           AS pg_open_non_lav,
                       MAX(CASE WHEN pg.fait_ou_pas = 0 AND pg.cycle = 'LAVAGE_LONG' THEN 1 ELSE 0 END)
                           AS pg_open_lav,
                       MIN(CASE WHEN pg.fait_ou_pas = 0 THEN pg.cycle END) AS pg_cycle_en_cours
                FROM sup_plt_gen pg WHERE pg.charge IN ({ph})
                GROUP BY pg.charge
            """, charges)
            plt_info: dict = {r['charge']: r for r in cur.fetchall()}

            # cycle_en_cours fallback depuis sup_histo (si pas dans plt_gen)
            missing_cycle = [c for c in charges
                             if not plt_info.get(c, {}).get('pg_cycle_en_cours')]
            histo_cycle: dict = {}
            if missing_cycle:
                mch = ','.join(['%s'] * len(missing_cycle))
                cur.execute(f"""
                    SELECT charge, cycle FROM sup_histo
                    WHERE charge IN ({mch}) AND tps_fin IS NULL
                    GROUP BY charge ORDER BY MAX(tps_deb) DESC
                """, missing_cycle)
                histo_cycle = {r['charge']: r['cycle'] for r in cur.fetchall()}

            # Portique (une ligne par charge)
            cur.execute(f"""
                SELECT charge, portique FROM sup_charge
                WHERE charge IN ({ph}) AND portique IS NOT NULL AND portique > 0
                GROUP BY charge ORDER BY id DESC
            """, charges)
            portique_by_charge = {r['charge']: r['portique'] for r in cur.fetchall()}

            # NC (rapide)
            cur.execute(
                f"SELECT charge COLLATE utf8mb4_unicode_ci AS charge FROM nc_declarations"
                f" WHERE charge IN ({ph}) GROUP BY charge",
                charges,
            )
            nc_set = {r['charge'] for r in cur.fetchall()}

            # Recette : sup_plt_gen d'abord, sinon sup_piece via lots
            cur.execute(f"""
                SELECT pg.charge, pg.recette
                FROM sup_plt_gen pg
                WHERE pg.charge IN ({ph}) AND pg.recette IS NOT NULL AND pg.recette <> ''
                GROUP BY pg.charge, pg.recette
            """, charges)
            recette_by_charge = {r['charge']: r['recette'] for r in cur.fetchall()}

            # Fallback 2 : sup_piece.recette via les lots
            missing = [c for c in charges if c not in recette_by_charge]
            if missing:
                mph = ','.join(['%s'] * len(missing))
                cur.execute(f"""
                    SELECT sh.charge, MIN(p.recette) AS recette
                    FROM sup_histo sh
                    JOIN sup_lot l ON l.lot = sh.lot
                    JOIN sup_piece p ON p.piece = l.piece
                    WHERE sh.charge IN ({mph})
                      AND p.recette IS NOT NULL AND p.recette <> ''
                    GROUP BY sh.charge
                """, missing)
                for r in cur.fetchall():
                    recette_by_charge[r['charge']] = r['recette']

            # Fallback 3 : cycle de cémentation (sup_cement) utilisé dans la charge
            missing = [c for c in charges if c not in recette_by_charge]
            if missing:
                mph = ','.join(['%s'] * len(missing))
                cur.execute(f"""
                    SELECT h.charge, h.cycle
                    FROM sup_histo h
                    WHERE h.charge IN ({mph})
                      AND EXISTS (
                          SELECT 1 FROM sup_cement sc
                          WHERE sc.cycle = h.cycle AND sc.fin_valid IS NULL
                      )
                    GROUP BY h.charge, h.cycle
                    ORDER BY h.charge
                """, missing)
                for r in cur.fetchall():
                    if r['charge'] not in recette_by_charge:
                        recette_by_charge[r['charge']] = r['cycle']

            # Séquence de cycles pour les recettes trouvées
            recettes = list(set(recette_by_charge.values()))
            recette_cycles: dict = {}
            if recettes:
                rph = ','.join(['%s'] * len(recettes))
                cur.execute(f"""
                    SELECT recette,
                           GROUP_CONCAT(DISTINCT cycle ORDER BY bloc SEPARATOR ' | ') AS cycles
                    FROM sup_recette
                    WHERE recette IN ({rph}) AND fin_valid IS NULL
                      AND cycle NOT LIKE '%%*%%'
                    GROUP BY recette
                """, recettes)
                recette_cycles = {r['recette']: r['cycles'] for r in cur.fetchall()}

            def _statut(i):
                pg = plt_info.get(i['charge'], {})
                if i['open_non_lavage'] or pg.get('pg_open_non_lav'):
                    return 'en_cours'
                if i['open_lavage'] or pg.get('pg_open_lav'):
                    return 'lavage'
                return 'termine'

            def _cycle_en_cours(i):
                pg = plt_info.get(i['charge'], {})
                return pg.get('pg_cycle_en_cours') or histo_cycle.get(i['charge'])

            items = [
                {**i,
                 'statut':         _statut(i),
                 'cycle_en_cours': _cycle_en_cours(i),
                 'has_nc':         i['charge'] in nc_set,
                 'portique':       portique_by_charge.get(i['charge']),
                 'recette':        recette_by_charge.get(i['charge']),
                 'recette_cycles': recette_cycles.get(recette_by_charge.get(i['charge']) or '', None)}
                for i in items
            ]

    return {"total": total, "items": items}


@router.get("/fournees/{charge}", response_model=FourneeDetail)
def get_fournee(charge: str, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        # Historique des passages de cette charge dans les fours.
        cur.execute("""
            SELECT MIN(id) AS id, station, tps_deb, MAX(tps_fin) AS tps_fin, cycle
            FROM sup_histo
            WHERE charge = %s
            GROUP BY station, tps_deb, cycle
            ORDER BY tps_deb
        """, [charge])
        passages = cur.fetchall()
        if not passages:
            raise HTTPException(status_code=404, detail="fournee introuvable")

        # OF (lot) attaches a cette charge, invariants sur tous les passages.
        cur.execute("""
            SELECT DISTINCT h.lot, l.piece, l.nuance, l.denomination, l.poids, l.tonnage, l.nbre,
                   p.recette AS piece_recette
            FROM sup_histo h
            LEFT JOIN sup_lot l ON l.lot = h.lot
            LEFT JOIN sup_piece p ON p.piece = l.piece
            WHERE h.charge = %s
            ORDER BY h.lot
        """, [charge])
        of_list = cur.fetchall()

        cur.execute("""
            SELECT operateur, date_creat, numero, portique, nbre
            FROM sup_charge WHERE charge = %s ORDER BY id DESC LIMIT 1
        """, [charge])
        charge_row = cur.fetchone() or {}

        first_recette = next((o['piece_recette'] for o in of_list if o['piece_recette']), None)
        if first_recette:
            cur.execute("""
                SELECT recette, bloc, type, cycle, deb_valid, fin_valid
                FROM sup_recette WHERE recette = %s ORDER BY bloc
            """, [first_recette])
            recette_steps = cur.fetchall()
        else:
            recette_steps = []

        # Plan d'execution de la recette pour cette charge (avec statut fait_ou_pas),
        # rapproche des passages four reels (rapprochement sequentiel par cycle,
        # car un meme cycle peut apparaitre plusieurs fois dans une recette).
        cur.execute("""
            SELECT recette, bloc, type, cycle, fait_ou_pas
            FROM sup_plt_gen WHERE charge = %s ORDER BY bloc
        """, [charge])
        plt_gen_steps = cur.fetchall()

        recette_plan = None
        if plt_gen_steps:
            passages_by_cycle: dict[str, list] = {}
            for p in passages:
                passages_by_cycle.setdefault(p['cycle'], []).append(p)

            # Si une etape ulterieure est marquee "fait" alors qu'une etape
            # plus tot ne l'est pas (incoherence MES), on considere les
            # etapes precedentes comme faites egalement (on ne peut pas
            # avoir avance dans la recette sans avoir termine les etapes
            # anterieures).
            effective_fait = [s['fait_ou_pas'] for s in plt_gen_steps]
            any_done_after = False
            for i in range(len(effective_fait) - 1, -1, -1):
                if any_done_after:
                    effective_fait[i] = 1
                if effective_fait[i] == 1:
                    any_done_after = True

            steps = []
            for step, fait_ou_pas in zip(plt_gen_steps, effective_fait):
                bucket = passages_by_cycle.get(step['cycle'])
                matched = bucket.pop(0) if bucket else None
                steps.append({
                    'bloc': step['bloc'],
                    'type': step['type'],
                    'cycle': step['cycle'],
                    'fait_ou_pas': fait_ou_pas,
                    'tps_deb': matched['tps_deb'] if matched else None,
                    'tps_fin': matched['tps_fin'] if matched else None,
                })

            # La charge est consideree terminee d'apres la fin de traitement
            # (tps_fin) de la derniere phase operatoire de la recette (hors
            # LAVAGE_LONG, qui n'est pas representatif de l'avancement du
            # traitement), les etapes etant realisees en sequence.
            operational_steps = [s for s in steps if s['cycle'] != 'LAVAGE_LONG']
            if operational_steps:
                terminee = operational_steps[-1]['tps_fin'] is not None
            else:
                terminee = plt_gen_steps[-1]['fait_ou_pas'] == 1

            recette_plan = RecettePlan(
                recette=plt_gen_steps[0]['recette'],
                terminee=terminee,
                steps=steps,
            )

    return {
        "charge": charge,
        "charge_operateur": charge_row.get('operateur'),
        "charge_date_creat": charge_row.get('date_creat'),
        "charge_numero": charge_row.get('numero'),
        "charge_portique": charge_row.get('portique'),
        "charge_nbre": charge_row.get('nbre'),
        "of_list": of_list,
        "passages": passages,
        "recette_steps": recette_steps,
        "recette_plan": recette_plan,
    }


@router.get("/fournees/{charge}/passages/{passage_id}/series", response_model=SeriesResponse)
def get_passage_series(charge: str, passage_id: int, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT station, tps_deb, tps_fin, cycle FROM sup_histo WHERE id = %s AND charge = %s
        """, [passage_id, charge])
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="passage introuvable")
        if row['station'] is None or row['tps_deb'] is None or row['tps_fin'] is None:
            raise HTTPException(status_code=404, detail="passage sans plage temporelle")

        station, tps_deb, tps_fin, cycle = row['station'], row['tps_deb'], row['tps_fin'], row.get('cycle')

        cur.execute("""
            SELECT id, name, variable, category FROM tags
            WHERE equip_type = 'four' AND equip_id = %s
              AND variable NOT LIKE %s
            ORDER BY category, variable
        """, [station, '%secu%'])
        tags = cur.fetchall()

        categories: dict[str, list[SeriesTag]] = {}
        for tag in tags:
            table = CATEGORY_TABLES.get(tag['category'])
            if table is None:
                continue
            cur.execute(f"""
                SELECT ts, ROUND(value, 1) AS value FROM {table}
                WHERE tag_id = %s AND ts BETWEEN %s AND %s
                ORDER BY ts
            """, [tag['id'], tps_deb, tps_fin])
            points = [(r['ts'], r['value']) for r in cur.fetchall()]
            categories.setdefault(tag['category'], []).append({
                'tag_id': tag['id'],
                'name': tag['name'],
                'variable': tag['variable'],
                'points': points,
            })

    return {"station": station, "tps_deb": tps_deb, "tps_fin": tps_fin,
            "cycle": cycle, "categories": categories}


# ── Non-conformités ────────────────────────────────────────────────

@router.get("/fournees/{charge}/meta")
def get_charge_meta(charge: str, conn=Depends(get_conn)):
    """Métadonnées légères d'une charge (sans passages ni séries)."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT operateur, date_creat, numero, portique
            FROM sup_charge WHERE charge = %s ORDER BY id DESC LIMIT 1
        """, [charge])
        row = cur.fetchone() or {}
        return {
            "charge":    charge,
            "operateur": row.get("operateur"),
            "date_creat": row.get("date_creat"),
            "numero":    row.get("numero"),
            "portique":  row.get("portique"),
        }


@router.get("/fournees/{charge}/nc", response_model=list[NcDeclaration])
def list_nc(charge: str, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, charge, lot, date_declaration, nature,
                   description, operateur, statut,
                   action_corrective, date_cloture
            FROM nc_declarations
            WHERE charge = %s
            ORDER BY date_declaration DESC
        """, [charge])
        return cur.fetchall()


@router.post("/fournees/{charge}/nc", response_model=NcDeclaration, status_code=201)
def create_nc(charge: str, body: NcCreate, conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO nc_declarations (charge, lot, nature, description, operateur)
            VALUES (%s, %s, %s, %s, %s)
        """, [charge, body.lot or None, body.nature,
              body.description or None, body.operateur or None])
        conn.commit()
        nc_id = cur.lastrowid
        cur.execute("""
            SELECT id, charge, lot, date_declaration, nature,
                   description, operateur, statut,
                   action_corrective, date_cloture
            FROM nc_declarations WHERE id = %s
        """, [nc_id])
        return cur.fetchone()


@router.get("/fournees/{charge}/alarmes", response_model=list[AlarmeItem])
def get_charge_alarmes(charge: str, conn=Depends(get_conn)):
    """Alarmes CITECT survenues pendant la periode d'execution de la charge."""
    from datetime import datetime as dt
    with conn.cursor() as cur:
        cur.execute("""
            SELECT MIN(tps_deb) AS tps_deb, MAX(tps_fin) AS tps_fin
            FROM sup_histo WHERE charge = %s
        """, [charge])
        row = cur.fetchone()
        if not row or not row['tps_deb']:
            return []
        tps_deb = row['tps_deb']
        tps_fin = row['tps_fin'] or dt.now()

        cur.execute("""
            SELECT id, code, description,
                   tps_apparition, tps_disparition, duree_s, type_alarme
            FROM alarmes
            WHERE tps_apparition BETWEEN %s AND %s
              AND type_alarme = 'CiAdvancedAlarmState'
            ORDER BY tps_apparition
        """, [tps_deb, tps_fin])
        return cur.fetchall()


@router.get("/fournees/{charge}/certificat/{lot_id}")
def download_certificat_lot(charge: str, lot_id: str, conn=Depends(get_conn)):
    """Génère et retourne le PDF (inline) pour un OF spécifique."""
    from app.utils.certificate import generate_single_pdf
    try:
        pdf_bytes = generate_single_pdf(charge, lot_id, conn)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type='application/pdf',
        headers={
            'Content-Disposition':
                f'inline; filename="Certificat_{charge}_{lot_id}.pdf"',
            'Content-Length': str(len(pdf_bytes)),
        },
    )


@router.get("/fournees/{charge}/certificats")
def download_certificats(charge: str, conn=Depends(get_conn)):
    """Génère un ZIP contenant un certificat PDF par OF de la charge."""
    from app.utils.certificate import generate_zip
    try:
        zip_bytes = generate_zip(charge, conn)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="Certificats_charge_{charge}.zip"',
            'Content-Length': str(len(zip_bytes)),
        },
    )
