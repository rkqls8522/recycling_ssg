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
    classes = load_waste_classes()
    existing = {c.class_id: c for c in db.query(WasteClass).all()}
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
