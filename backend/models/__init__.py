"""Import every ORM model so ``Base.metadata`` is fully populated before
``create_all()`` / Alembic autogenerate runs."""

from models.favorite import Favorite
from models.feedback import Feedback
from models.feedback_candidate import FeedbackCandidate
from models.image import Image
from models.region import Region
from models.user import User
from models.waste_class import WasteClass

__all__ = [
    "Favorite",
    "Feedback",
    "FeedbackCandidate",
    "Image",
    "Region",
    "User",
    "WasteClass",
]
