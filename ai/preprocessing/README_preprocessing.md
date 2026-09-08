# 생활폐기물 객체 탐지 데이터 전처리

AI Hub 생활폐기물 이미지와 JSON 라벨을 검사·표준화하고, 학습에 사용할 COCO 형식으로 변환하는 실행 파일입니다.

팀원은 데이터 경로만 자신의 환경에 맞게 수정한 뒤 실행할 수 있습니다. 원본 이미지와 원본 JSON 파일은 수정하거나 삭제하지 않습니다.

## 1. 주요 기능

- Training·Validation 이미지와 JSON 라벨 연결
- EXIF 자동 회전을 무시하고 실제 저장 방향 기준으로 이미지 로딩
- `BOX` annotation 표준화
- `POLYGON` annotation을 Bounding Box로 변환
- 이미지 범위를 벗어나거나 면적이 0인 Bounding Box 제외
- 최종 클래스 정책 적용 및 클래스 ID 부여
- 정책 제외 객체의 클래스·사유·이미지 경로 출력
- 전처리 결과를 JSON·CSV로 저장
- Training·Validation COCO JSON 생성
- COCO ID, 참조 관계와 Bounding Box 유효성 검사

## 2. 필요한 데이터 구조

`data` 폴더는 다음 구조여야 합니다.

```text
data/
├── Training/
│   ├── images/
│   └── labels/
└── Validation/
    ├── images/
    └── labels/
```

이미지와 JSON은 `images`, `labels` 아래에서 동일한 상대경로와 파일명을 사용해야 합니다.

```text
Training/images/도기류/컵/group01/sample.jpg
Training/labels/도기류/컵/group01/sample.json
```

## 3. 실행 환경

필수 패키지는 다음과 같습니다.

- Python 3.10 이상
- NumPy
- OpenCV Python

uv 환경에 패키지가 없다면 프로젝트 폴더에서 설치합니다.

```powershell
uv pip install numpy opencv-python
```

## 4. 데이터 경로 설정

`preprocess_dataset_data.py` 상단의 `DATA_DIR`만 실제 데이터 경로로 변경합니다.

```python
DATA_DIR = Path(
    r"파일경로입력"
)
```

Windows 절대경로 앞에는 `r`을 붙여 역슬래시가 잘못 해석되지 않도록 합니다.

결과는 실행 파일과 같은 위치의 `outputs` 폴더에 저장됩니다.

## 5. 실행 방법

프로젝트 루트에서 실행하는 것을 권장합니다.

```powershell
uv run python ai/preprocessing/preprocess_dataset_data.py
```

가상환경의 Python을 직접 지정해도 됩니다.

```powershell
& .\.venv\Scripts\python.exe .\ai\preprocessing\preprocess_dataset_data.py
```

## 6. 최종 클래스 정책

- 최종 대분류: 12개
- 최종 세부 클래스: 78개
- 모델용 클래스 ID: `0~77`
- COCO `category_id`: `1~78`

다음 객체는 제외합니다.

- 대분류가 `전자제품`인 객체
- 대분류 또는 세부 품목이 `가구`, `가구류`인 객체
- 최종 분류표에 정의되지 않은 객체

다음 클래스명은 통합합니다.

| 원본 | 최종 클래스 |
|---|---|
| 나무, 나무류 | 나무 |
| 비닐, 비닐류 | 비닐 |
| 스티로폼, 스티로폼류 | 스티로폼 |
| 유리병, 유리병류 | 유리병 |
| 페트병, 페트병류 | 페트병 |
| 맥주캔·음료수캔·참기름캔·커피캔 | 캔류_캔 |
| LED전구·백열전구 | 형광등_전구 |
| 안정기내장형·직관형·콤팩트형·환형·기타 | 형광등_형광등 |

`기타`, `기타술병`, `기타의류`는 제외하지 않습니다. 원본 표기인 `포장제`, `장남감`도 그대로 유지합니다.

## 7. 객체 제외 방식

제외 정책은 이미지가 아니라 **객체 단위**로 적용됩니다.

한 이미지에 객체가 2개 있고 그중 전자제품 객체 하나만 제외 대상이라면:

- 전자제품 Bounding Box만 제외
- 나머지 정상 객체는 유지
- 정상 객체가 남아 있으므로 이미지도 COCO 데이터에 유지
- 이미지 안의 모든 객체가 제외된 경우에만 최종 COCO에서 이미지 제외

실행 화면에서 제외 객체의 데이터셋, 클래스, 세부 품목, 사유와 이미지 경로를 확인할 수 있습니다.

## 8. 생성 파일

```text
outputs/
├── preprocessed/
│   ├── final_annotations.json
│   ├── class_id_mapping.json
│   ├── class_id_mapping.csv
│   ├── excluded_objects.csv
│   ├── preprocessing_summary.json
│   └── preprocessing_errors.json
└── coco/
    ├── instances_train.json
    └── instances_val.json
```

| 파일 | 용도 |
|---|---|
| `final_annotations.json` | 최종 표준화 annotation 전체 정보 |
| `class_id_mapping.json` | 클래스 ID와 클래스명 매핑 |
| `class_id_mapping.csv` | 사람이 확인하기 쉬운 클래스 매핑표 |
| `excluded_objects.csv` | 제외 객체, 제외 사유와 이미지 경로 |
| `preprocessing_summary.json` | 입력 데이터와 처리 결과 요약 |
| `preprocessing_errors.json` | 이미지·JSON·좌표 처리 오류 목록 |
| `instances_train.json` | Training COCO annotation |
| `instances_val.json` | Validation COCO annotation |

## 9. data 실행 확인값

현재 확인한 `data` 샘플의 결과는 다음과 같습니다.

```text
표준화 객체: 1,040
표준화 오류: 0
정책 제외 객체: 3
최종 객체: 1,037
최종 대분류: 12
최종 세부 클래스: 78
Training COCO: 이미지 766, 객체 858
Validation COCO: 이미지 166, 객체 179
COCO 검증: True
```

다른 데이터셋에서는 이미지와 객체 수가 달라질 수 있습니다. 구조와 클래스 정책이 같다면 클래스 수는 동일하게 유지됩니다.

## 10. 모델 학습 시 사용 파일

COCO 형식을 지원하는 객체 탐지 모델에서는 다음 파일을 사용합니다.

| 구분 | 이미지 폴더 | Annotation |
|---|---|---|
| Training | `data/Training/images` | `outputs/coco/instances_train.json` |
| Validation | `data/Validation/images` | `outputs/coco/instances_val.json` |

COCO JSON에는 이미지가 들어 있지 않습니다. 팀원에게 전달할 때는 COCO 파일뿐 아니라 원본 이미지 폴더도 함께 제공하거나, 팀원이 같은 원본 데이터를 가지고 있어야 합니다.

YOLO 학습에는 COCO JSON을 그대로 사용하지 않고 YOLO 라벨 형식으로 추가 변환해야 합니다.

## 11. 주의사항

- 실행 전 `DATA_DIR`가 올바른 `data` 폴더인지 확인합니다.
- 원본 이미지와 JSON을 직접 수정하지 않습니다.
- 클래스 정책을 변경하면 기존 모델의 클래스 ID와 호환되지 않을 수 있습니다.
- Training과 Validation은 동일한 전체 클래스 매핑을 사용합니다.
- `final_annotations.json`의 절대경로는 다른 PC에서 달라지므로 팀 학습에는 COCO의 상대경로를 우선 사용합니다.
- `preprocessing_errors.json`에 항목이 있다면 학습 전에 원인을 확인합니다.

