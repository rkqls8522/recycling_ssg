from pydantic import BaseModel

class CandidateScore(BaseModel):
    class_id: int
    category: str
    score: float

class UserRegion(BaseModel):
    region_id: int
    sido_name: str
    sgg_name: str

class ClassificationResult(BaseModel):
    status: str                              # 분류 성공 여부 ("SUCCESS" 등, 1번 노드가 채움)
    major_category: str                      # 대분류
    minor_category: str                      # 소분류
    candidate_scores: list[CandidateScore]   # 1위 외에 모델이 고려한 후보 클래스들 + 확률
    user_region: UserRegion
    # Backend 의 배출요일 조회는 best-effort 라 실패하면 None 을 보낸다(섹션 15.1).
    # 필수 str 로 두면 그 경우 422 가 나서, 무관한 기능인 배출방법 조회까지 함께
    # 실패한다. 이 값은 여기서 쓰이지 않고 응답에 그대로 되돌려주기만 한다.
    disposal_day: str | None = None
    image_id: int
    feedback_id: int
    warnings: list[str] = []                 # 분류 과정에서 발생한 경고 메시지 (없으면 빈 리스트)

class NationalRule(BaseModel):
    source: str
    method: str | None = None


class RegionRule(BaseModel):
    region: str
    source_url: str
    exception_type: str
    method: str | None = None


class DisposalResult(BaseModel):
    item: str | None = None
    major_category: str
    minor_category: str
    national_rule: NationalRule | None = None
    region_rule: RegionRule | None = None
    has_region_exception: bool


class ClassificationResultWithDisposal(ClassificationResult):
    disposal_result: DisposalResult    

class ReclassifyRequest(BaseModel):
    img_url: str
    user_region: UserRegion


class ReclassifyResponse(BaseModel):
    major_category: str | None = None
    minor_category: str | None = None
    disposal_result: DisposalResult | None = None
    needs_retake: bool


class ChatNodeRequest(BaseModel):
    message: str
    major_category: str
    minor_category: str
    user_region: UserRegion


class ChatNodeResponse(BaseModel):
    answer: str
