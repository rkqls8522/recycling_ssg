from typing_extensions import List, TypedDict, Dict
from langchain_core.documents import Document
from typing import Optional

class NationalRule(TypedDict):
    source: str
    method: str

class RegionRule(TypedDict):
    region: str
    source_url: str
    exception_type: str
    method: str

class DisposalResult(TypedDict):
    item: Optional[str]
    major_category: str
    minor_category: str
    national_rule: Optional[NationalRule]
    region_rule: Optional[RegionRule]
    has_region_exception: bool

class VerificationSubState(TypedDict):
    category: str
    sub_item: str
    region: str
    img_url: str                    # classify judge용
    regulation_text: List[str]
    disposal_result: DisposalResult # generated_answer 대체
    is_valid: bool
    failure_reason: str
    retry_count: int