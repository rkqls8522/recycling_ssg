from typing_extensions import List, TypedDict, Dict
from langchain_core.documents import Document
from typing import Optional

class UserRegion(TypedDict):
    region_id: int
    sido_name: str
    sgg_name: str

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

class AgentState(TypedDict):
    major_category: str
    minor_category: str
    item_list: List[Dict]      
    user_region: UserRegion
    img_url: str
    disposal_result: DisposalResult
    is_valid: bool
    failure_reason: str
    retry_count: int