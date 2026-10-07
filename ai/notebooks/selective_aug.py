"""특정 클래스(기본값: 신문지)의 이미지만 학습 중 증강에서 제외한다.

## 왜 필요한가

신문지는 원본 수량이 매우 적어 **오프라인에서 미리 4배로 증강해** 데이터셋에
넣어 두었다. 여기에 학습 중 증강(mosaic/mixup/cutmix/HSV/flip ...)까지 걸리면
같은 원본에 증강이 이중으로 쌓여 과증강이 된다. 그래서 신문지 이미지만
증강 파이프라인을 우회시키고, 나머지 클래스는 정상적으로 증강한다.

## 왜 노트북 셀이 아니라 별도 모듈 파일인가

DataLoader worker(`workers > 0`)는 dataset 객체를 **pickle 로** 건네받는데,
pickle 은 객체 내용이 아니라 클래스의 *모듈 경로* 를 저장한다. 따라서 worker
프로세스에서도 같은 클래스를 import 할 수 있어야 한다.

- 노트북 셀에서 정의하면 클래스의 모듈이 `__main__` 이 되고, worker 는 그
  `__main__`(= 노트북)을 다시 import 할 수 없어 실패한다.
- 또한 `__getitem__` 은 던더 메서드라 인스턴스에 꽂아도 무시된다.
  파이썬이 던더를 **타입에서** 찾기 때문이다. 그래서 서브클래스여야 한다.

Windows 는 fork 가 아니라 spawn 이므로 부모 프로세스에서 한 원숭이 패치는
worker 에 전달되지 않는다. 이 파일처럼 디스크에 있는 모듈의 서브클래스만이
worker 까지 확실히 전달된다.

## 사용법

    import selective_aug

    selective_aug.configure(class_ids=[10])          # 10 = 종이류/신문지
    model.train(trainer=selective_aug.SelectiveAugTrainer, **train_kwargs)
"""

from __future__ import annotations

import random

from ultralytics.cfg import get_cfg
from ultralytics.data import augment as _augment
from ultralytics.data.dataset import YOLODataset
from ultralytics.models.yolo.detect import DetectionTrainer

__all__ = [
    "DEFAULT_EXCLUDE_CLASS_IDS",
    "configure",
    "current_config",
    "SelectiveAugYOLODataset",
    "SelectiveAugTrainer",
]

# 종이류/신문지 (data/taxonomy/waste_classes.json 기준)
DEFAULT_EXCLUDE_CLASS_IDS = (10,)

# 이 값은 **부모 프로세스에서** dataset 을 만들 때 한 번 읽혀 인스턴스 속성으로
# 복사된다. worker 는 그 인스턴스를 pickle 로 받으므로 이 전역을 다시 읽지 않는다.
_CONFIG: dict = {
    "class_ids": set(DEFAULT_EXCLUDE_CLASS_IDS),
    # "all" : 이미지의 모든 박스가 제외 클래스일 때만 제외 (기본)
    # "any" : 제외 클래스 박스가 하나라도 있으면 제외
    "match": "all",
    # mosaic/mixup/cutmix 가 '다른 이미지'를 끌어올 때도 제외 클래스를 피할지
    "filter_mix_partners": True,
}


def configure(
    class_ids=DEFAULT_EXCLUDE_CLASS_IDS,
    match: str = "all",
    filter_mix_partners: bool = True,
) -> dict:
    """증강에서 제외할 클래스를 설정한다. 학습을 시작하기 전에 호출한다."""
    if match not in {"all", "any"}:
        raise ValueError("match 는 all 또는 any 여야 합니다: " + repr(match))

    _CONFIG["class_ids"] = {int(c) for c in class_ids}
    _CONFIG["match"] = match
    _CONFIG["filter_mix_partners"] = bool(filter_mix_partners)
    return current_config()


def current_config() -> dict:
    """현재 설정을 복사해서 돌려준다 (출력/기록용)."""
    return {
        "class_ids": sorted(_CONFIG["class_ids"]),
        "match": _CONFIG["match"],
        "filter_mix_partners": _CONFIG["filter_mix_partners"],
    }


# ---------------------------------------------------------------------------
# mosaic/mixup/cutmix 의 '상대 이미지' 선택에서 제외 클래스를 걸러낸다.
# ---------------------------------------------------------------------------
class _PartnerFilterMixin:
    """get_indexes() 가 고른 상대 이미지가 제외 대상이면 다시 뽑는다.

    제외 클래스 이미지가 다른 이미지의 mosaic 조각으로 들어가면, 결국 그
    이미지도 변형된 형태로 학습에 쓰이는 셈이다. 그래서 상대 후보에서도 뺀다.
    """

    # 재추첨 상한. 제외 클래스 비율이 아주 높은 극단적 경우에도 멈추게 한다.
    _MAX_RESAMPLE = 20

    def get_indexes(self, *args, **kwargs):
        indexes = super().get_indexes(*args, **kwargs)
        blocked = getattr(self.dataset, "no_aug_indices", None)

        if not blocked or not getattr(self.dataset, "filter_mix_partners", False):
            return indexes

        is_scalar = isinstance(indexes, int)
        picked = [indexes] if is_scalar else list(indexes)
        cleaned = [self._resample(index, blocked) for index in picked]

        return cleaned[0] if is_scalar else cleaned

    def _resample(self, index: int, blocked: set) -> int:
        if index not in blocked:
            return index

        size = len(self.dataset)
        for _ in range(self._MAX_RESAMPLE):
            candidate = random.randint(0, size - 1)
            if candidate not in blocked:
                return candidate

        # 여기까지 오면 데이터 대부분이 제외 대상이라는 뜻이다. 원래 값을 쓴다.
        return index


class FilteredMosaic(_PartnerFilterMixin, _augment.Mosaic):
    pass


class FilteredMixUp(_PartnerFilterMixin, _augment.MixUp):
    pass


class FilteredCutMix(_PartnerFilterMixin, _augment.CutMix):
    pass


# 원본 transform 인스턴스를 위 서브클래스로 갈아 끼우기 위한 대응표.
_FILTERED_BY_ORIGINAL = {
    _augment.Mosaic: FilteredMosaic,
    _augment.MixUp: FilteredMixUp,
    _augment.CutMix: FilteredCutMix,
}


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
class SelectiveAugYOLODataset(YOLODataset):
    """제외 클래스 이미지는 letterbox 만 거쳐 나가는 YOLODataset."""

    def __init__(self, *args, **kwargs):
        # build_transforms 가 __init__ 안에서 불리므로 먼저 자리를 잡아 둔다.
        self._plain_transforms = None

        super().__init__(*args, **kwargs)

        # BaseDataset 은 hyp 를 보관하지 않는다. 증강 없는 파이프라인을 나중에
        # 다시 만들려면 필요하므로 여기서 직접 들고 있는다.
        self.hyp_cfg = kwargs.get("hyp") or get_cfg()

        self.exclude_class_ids = set(_CONFIG["class_ids"])
        self.match_rule = _CONFIG["match"]
        self.filter_mix_partners = _CONFIG["filter_mix_partners"]
        self.no_aug_indices = self._collect_no_aug_indices()

        # 어떤 transform 이 교체됐는지 남겨 둔다. 노트북에서 검증용으로 출력한다.
        self.filtered_transform_names: list = []
        if self.no_aug_indices:
            self.filtered_transform_names = self._install_partner_filters()

    # -- 제외 대상 색인 ------------------------------------------------------
    def _collect_no_aug_indices(self) -> set:
        """제외 클래스에 해당하는 이미지의 index 집합."""
        # val/test 는 애초에 증강을 하지 않으므로 계산할 필요가 없다.
        if not self.augment or not self.exclude_class_ids:
            return set()

        hits = set()
        for index, label in enumerate(self.labels):
            cls = label.get("cls")
            if cls is None or len(cls) == 0:
                continue

            ids = {int(value) for value in cls.reshape(-1)}
            if self.match_rule == "any":
                matched = bool(ids & self.exclude_class_ids)
            else:
                matched = ids.issubset(self.exclude_class_ids)

            if matched:
                hits.add(index)

        return hits

    def _install_partner_filters(self) -> list:
        """이미 만들어진 mosaic/mixup/cutmix 인스턴스의 클래스를 갈아 끼운다.

        __class__ 만 바꾸면 기존 속성(p, imgsz, border ...)은 그대로 살아 있고,
        pickle 은 새 클래스의 모듈 경로를 저장하므로 worker 에도 그대로 전달된다.
        transform 을 새로 만들지 않으므로 Ultralytics 버전 변화에도 덜 민감하다.

        Mosaic 은 최상위 Compose 에 바로 있지 않다. Ultralytics 는
        `Compose([Mosaic, CopyPaste, RandomPerspective])` 를 pre_transform 으로
        묶은 뒤 그것을 다시 MixUp/CutMix 에 넘긴다. 그래서 중첩된 Compose 와
        pre_transform 속성까지 따라 들어가야 한다.

        Returns:
            (list): 실제로 교체한 클래스 이름들 (검증/로그용)
        """
        swapped: list = []
        seen: set = set()

        def walk(node) -> None:
            # pre_transform 은 상위 Compose 와 같은 객체를 다시 가리키므로
            # id 로 방문 표시를 해야 무한 재귀에 빠지지 않는다.
            if node is None or id(node) in seen:
                return
            seen.add(id(node))

            replacement = _FILTERED_BY_ORIGINAL.get(type(node))
            if replacement is not None:
                node.__class__ = replacement
                swapped.append(replacement.__name__)

            for child in getattr(node, "transforms", []) or []:
                walk(child)
            walk(getattr(node, "pre_transform", None))

        walk(self.transforms)
        return swapped

    # -- 증강 없는 파이프라인 ------------------------------------------------
    @property
    def plain_transforms(self):
        """augment=False 일 때 Ultralytics 가 쓰는 것과 같은 파이프라인.

        직접 조립하지 않고 부모의 build_transforms 를 augment 만 꺼서 부른다.
        그래야 버전이 올라가 전처리가 바뀌어도 val 경로와 항상 같은 모양이 된다.
        """
        if self._plain_transforms is None:
            was_augmenting = self.augment
            self.augment = False
            try:
                self._plain_transforms = self.build_transforms(hyp=self.hyp_cfg)
            finally:
                self.augment = was_augmenting

        return self._plain_transforms

    # -- 실제 분기 -----------------------------------------------------------
    def __getitem__(self, index):
        if index in self.no_aug_indices:
            return self.plain_transforms(self.get_image_and_label(index))
        return super().__getitem__(index)

    def load_image(self, i, rect_mode: bool = True, resize_short: bool = False):
        """제외 대상 이미지는 mosaic 용 buffer 에 남기지 않는다.

        Mosaic.get_indexes() 는 dataset.buffer(최근에 읽은 이미지들)에서 상대를
        고른다. buffer 에 들어가지 않으면 애초에 후보가 되지 않는다.
        _PartnerFilterMixin 과 역할이 겹치지만, buffer 를 쓰지 않는 경로까지
        양쪽에서 막아 두는 편이 안전하다.
        """
        image, hw0, hw = super().load_image(i, rect_mode=rect_mode, resize_short=resize_short)

        if i in getattr(self, "no_aug_indices", ()) and self.filter_mix_partners:
            if self.buffer and self.buffer[-1] == i:
                self.buffer.pop()
                # 캐시도 비워 둔다. 그대로 두면 eviction 대상에서 빠져 계속 쌓인다.
                self.ims[i] = None
                self.im_hw0[i] = None
                self.im_hw[i] = None

        return image, hw0, hw


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------
class SelectiveAugTrainer(DetectionTrainer):
    """train split 만 SelectiveAugYOLODataset 으로 만드는 DetectionTrainer."""

    def build_dataset(self, img_path, mode: str = "train", batch=None):
        if mode != "train":
            return super().build_dataset(img_path, mode=mode, batch=batch)

        # build_yolo_dataset 안의 pad/rect/fraction 계산 로직을 복사하지 않고,
        # 그 함수가 참조하는 이름만 잠깐 바꿔치기해서 우리 클래스를 만들게 한다.
        from ultralytics.data import build as build_module

        original = build_module.YOLODataset
        build_module.YOLODataset = SelectiveAugYOLODataset
        try:
            return super().build_dataset(img_path, mode=mode, batch=batch)
        finally:
            build_module.YOLODataset = original
