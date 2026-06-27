from datetime import datetime

from fastapi import APIRouter, Depends

from app.db import get_conn

router = APIRouter()

CATEGORY_TABLES = {
    'temperature': 'mesures_temperature',
    'atmosphere':  'mesures_atmosphere',
    'puissance':   'mesures_puissance',
}


@router.get("/consultation/tags")
def consultation_tags(stations: str, conn=Depends(get_conn)):
    ids = [int(x) for x in stations.split(',') if x.strip()]
    if not ids:
        return []
    placeholders = ','.join(['%s'] * len(ids))
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT id, name, variable, category, equip_id AS station
            FROM tags
            WHERE equip_type = 'four' AND equip_id IN ({placeholders})
              AND variable NOT LIKE %s
            ORDER BY category, equip_id, variable
        """, ids + ['%secu%'])
        return cur.fetchall()


@router.get("/consultation/series")
def consultation_series(
    tag_ids: str,
    start: datetime,
    end: datetime,
    conn=Depends(get_conn),
):
    ids = [int(x) for x in tag_ids.split(',') if x.strip()]
    if not ids:
        return {"start": start, "end": end, "categories": {}}

    span = (end - start).total_seconds()
    if span <= 2 * 3600:
        bucket = 30
    elif span <= 24 * 3600:
        bucket = 120
    elif span <= 7 * 86400:
        bucket = 600
    else:
        bucket = 1800

    categories: dict = {}

    with conn.cursor() as cur:
        for tag_id in ids:
            cur.execute("""
                SELECT id, name, variable, category, equip_id AS station
                FROM tags WHERE id = %s AND equip_type = 'four'
                  AND variable NOT LIKE %s
            """, [tag_id, '%secu%'])
            tag = cur.fetchone()
            if not tag:
                continue
            table = CATEGORY_TABLES.get(tag['category'])
            if not table:
                continue

            if bucket == 30:
                cur.execute(f"""
                    SELECT ts, ROUND(value, 1) AS value FROM {table}
                    WHERE tag_id = %s AND ts BETWEEN %s AND %s
                    ORDER BY ts
                """, [tag_id, start, end])
            else:
                cur.execute(f"""
                    SELECT MIN(ts) AS ts, ROUND(AVG(value), 1) AS value
                    FROM {table}
                    WHERE tag_id = %s AND ts BETWEEN %s AND %s
                    GROUP BY FLOOR(UNIX_TIMESTAMP(ts) / %s)
                    ORDER BY 1
                """, [tag_id, start, end, bucket])

            points = [(r['ts'], r['value']) for r in cur.fetchall()]
            categories.setdefault(tag['category'], []).append({
                'tag_id':   tag['id'],
                'name':     tag['name'],
                'variable': tag['variable'],
                'station':  tag['station'],
                'points':   points,
            })

    return {"start": start, "end": end, "bucket_seconds": bucket, "categories": categories}
