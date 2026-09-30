"""Idempotent Master-data seeding for ``regions`` and ``waste_classes``.

Runs automatically at startup when ``settings.auto_seed_master_data`` is
True (see main.py). Safe to call multiple times: existing rows are updated
in place, missing rows are inserted, nothing is deleted.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from db.taxonomy_loader import load_regions, load_waste_classes
from models.region import Region
from models.waste_class import WasteClass

logger = logging.getLogger(__name__)


def seed_regions(db: Session) -> None:
    existing = {r.region_id: r for r in db.query(Region).all()}
    for row in load_regions():
        region = existing.get(row["region_id"])
        if region is None:
            db.add(
                Region(
                    region_id=row["region_id"],
                    sido_name=row["sido_name"],
                    sgg_name=row["sgg_name"],
                )
            )
        else:
            region.sido_name = row["sido_name"]
            region.sgg_name = row["sgg_name"]
    db.commit()
    logger.info("regions master data seeded (%d rows)", len(load_regions()))


def seed_waste_classes(db: Session) -> None:
    """(major_category, minor_category)에 UNIQUE 제약이 걸려 있어서, 그냥
    class_id 순서대로 한 줄씩 UPDATE 치면 두 경우에 실패할 수 있다:

    1. taxonomy(waste_classes.json)가 바뀌면서 두 class_id가 서로 값을
       주고받는(swap) 경우 -- 중간 상태에서 일시적으로 값이 겹친다.
    2. 지금 taxonomy에는 없는 class_id(예: 예전 86개 세부 클래스 체계 시절
       잔재. feedback/feedback_candidates 가 class_id로 참조 중일 수 있어
       행 자체는 지우지 않는다)가 이미 그 값을 차지하고 있는 경우.

    그래서 실제 값을 넣기 전에, (a) taxonomy 밖 잔재 행은 자리표시자로 비우고
    (b) 관리 대상 행은 전부 고유한 임시값을 거치게 해서, 최종 값을 넣는 순서와
    무관하게 항상 유니크 제약을 만족하도록 2단계로 나눠 처리한다.
    """
    classes = load_waste_classes()
    existing = {c.class_id: c for c in db.query(WasteClass).all()}

    # 0단계: taxonomy 밖 잔재 행 -- 자리표시자로 비워서 슬롯을 반환한다.
    for class_id, wc in existing.items():
        if class_id not in classes:
            wc.major_category = f"__legacy_{class_id}__"
            wc.minor_category = f"__legacy_{class_id}__"
    if existing:
        db.flush()

    # 1단계: 관리 대상 행을 전부 고유한 임시값으로 밀어넣는다 (swap 대비).
    for class_id in classes:
        wc = existing.get(class_id)
        if wc is not None:
            wc.major_category = f"__seed_tmp_{class_id}__"
            wc.minor_category = f"__seed_tmp_{class_id}__"
    if existing:
        db.flush()

    # 2단계: 실제 값 반영.
    for class_id, (major, minor) in classes.items():
        wc = existing.get(class_id)
        if wc is None:
            db.add(WasteClass(class_id=class_id, major_category=major, minor_category=minor))
        else:
            wc.major_category = major
            wc.minor_category = minor
    db.commit()
    logger.info("waste_classes master data seeded (%d rows)", len(classes))


def seed_all(db: Session) -> None:
    seed_regions(db)
    seed_waste_classes(db)
