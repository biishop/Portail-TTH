from fastapi import APIRouter, Depends

from app.db import get_conn
from app.models import Four

router = APIRouter()


@router.get("/fours", response_model=list[Four])
def list_fours(conn=Depends(get_conn)):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT t.equip_id AS station,
              (SELECT sa.nom_station FROM sup_atelier sa
                WHERE sa.station = t.equip_id ORDER BY sa.id LIMIT 1) AS nom_station
            FROM tags t
            WHERE t.equip_type = 'four'
            ORDER BY t.equip_id
        """)
        return cur.fetchall()
