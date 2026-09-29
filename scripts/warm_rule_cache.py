"""RAG 배출규정 캐시 프리워밍.

rag/src/agents/rule_lookup.py 의 조회 캐시는 RAG 프로세스 메모리에만 있어서
서버를 재시작하면 비워진다. 시연 직전에 이 스크립트를 한 번 돌려두면 첫 방문자부터
캐시 적중(~2ms)으로 응답한다. 채우지 않으면 물건 종류마다 첫 1회가 0.5~1초 걸린다.

무엇을 채우면 되는지:
  - national_rule 은 지역 인자가 없다(전국 공통 규정). 17개 클래스를 1회씩만 돌면
    모든 지역 사용자가 캐시를 공유한다.
  - region_rule 은 find_region_rule() 이 "경기도"가 아니면 조회 없이 None 을
    반환하므로, 경기도 시군구 조합만 채우면 된다. 서울 등 다른 시도는 채울 것이 없다.

사용법:
    uv run python scripts/warm_rule_cache.py                  # 전체 (경기도 포함)
    uv run python scripts/warm_rule_cache.py --national-only  # 17개만, 약 15초
    uv run python scripts/warm_rule_cache.py --workers 8      # 더 빠르게 (API 제한 주의)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_DIR = REPO_ROOT / "data" / "taxonomy"

# region_rule 조회가 실제로 일어나는 유일한 시도. rule_lookup.find_region_rule() 의
# 게이트 조건과 반드시 같아야 한다.
REGION_RULE_SIDO = "경기도"


def load_classes() -> list[tuple[str, str]]:
    raw = json.loads((TAXONOMY_DIR / "waste_classes.json").read_text(encoding="utf-8"))
    return [(major, minor) for major, minor in raw.values()]


def load_regions() -> list[dict]:
    return json.loads((TAXONOMY_DIR / "regions.json").read_text(encoding="utf-8"))


def build_payload(major: str, minor: str, region: dict) -> dict:
    return {
        "status": "SUCCESS",
        "major_category": major,
        "minor_category": minor,
        "candidate_scores": [],
        "user_region": {
            "region_id": region["region_id"],
            "sido_name": region["sido_name"],
            "sgg_name": region["sgg_name"],
        },
        "disposal_day": "월요일",
        "image_id": 0,
        "feedback_id": 0,
        "warnings": [],
    }


# 527건을 한꺼번에 몰아치면 Upstage/Pinecone 쪽에서 일시적으로 거부해 500 이나
# 커넥션 리셋이 섞여 나온다(실측). 조회 자체는 멀쩡하므로 잠깐 쉬었다 다시 보내면
# 대부분 통과한다. 이미 캐시된 조합은 재시도해도 API 를 타지 않으므로 비용도 없다.
def warm_one(
    session: requests.Session, url: str, payload: dict, retries: int
) -> tuple[bool, str]:
    delay = 1.0
    last_error = "unknown"
    for attempt in range(retries + 1):
        try:
            r = session.post(url, json=payload, timeout=40)
            if r.status_code == 200:
                return True, ""
            last_error = f"HTTP {r.status_code} {r.text[:120]}"
        except requests.RequestException as exc:
            last_error = str(exc)
        if attempt < retries:
            time.sleep(delay)
            delay *= 2
    return False, last_error


def run_phase(name: str, jobs: list[dict], url: str, workers: int, retries: int) -> int:
    if not jobs:
        return 0
    print(f"\n[{name}] {len(jobs)}건 (동시 {workers})")
    started = time.perf_counter()
    failures = 0
    done = 0
    with requests.Session() as session, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(warm_one, session, url, p, retries): p for p in jobs}
        for future in as_completed(futures):
            ok, err = future.result()
            done += 1
            if not ok:
                failures += 1
                p = futures[future]
                print(
                    f"  실패 {p['major_category']}/{p['minor_category']} "
                    f"{p['user_region']['sgg_name']}: {err}"
                )
            if done % 25 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}", end="\r", flush=True)
    elapsed = time.perf_counter() - started
    print(f"\n  완료 {len(jobs) - failures}/{len(jobs)}  ({elapsed:.1f}초)")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001", help="RAG 서비스 주소")
    parser.add_argument(
        "--workers", type=int, default=3, help="동시 요청 수 (높이면 외부 API 거부 위험)"
    )
    parser.add_argument(
        "--retries", type=int, default=3, help="실패 시 재시도 횟수 (1초부터 2배씩 대기)"
    )
    parser.add_argument(
        "--national-only",
        action="store_true",
        help="전국 공통 규정 17건만 채운다 (경기도 시군구별 예외는 건너뜀)",
    )
    args = parser.parse_args()

    rule_url = f"{args.url.rstrip('/')}/rule_node"
    classes = load_classes()
    regions = load_regions()

    gyeonggi = [r for r in regions if r["sido_name"] == REGION_RULE_SIDO]
    others = [r for r in regions if r["sido_name"] != REGION_RULE_SIDO]
    if not others:
        print("경기도 외 지역이 없어 national 예열에도 경기도 지역을 사용합니다.")
    national_region = (others or gyeonggi)[0]

    print(f"RAG  : {rule_url}")
    print(f"클래스: {len(classes)}개")
    print(f"지역  : 전체 {len(regions)}개 중 경기도 {len(gyeonggi)}개")
    print(
        f"        (경기도 외 {len(others)}개 지역은 region_rule 조회 자체가 없어 예열 불필요)"
    )

    try:
        requests.get(f"{args.url.rstrip('/')}/health", timeout=5).raise_for_status()
    except requests.RequestException as exc:
        print(f"\nRAG 서비스에 연결할 수 없습니다: {exc}")
        print("먼저 실행하세요:  uv run uvicorn rag.main:app --host 127.0.0.1 --port 8001")
        return 1

    failures = run_phase(
        "1/2 전국 공통 규정",
        [build_payload(major, minor, national_region) for major, minor in classes],
        rule_url,
        args.workers,
        args.retries,
    )

    if not args.national_only:
        failures += run_phase(
            f"2/2 {REGION_RULE_SIDO} 지자체 예외",
            [
                build_payload(major, minor, region)
                for region in gyeonggi
                for major, minor in classes
            ],
            rule_url,
            args.workers,
            args.retries,
        )

    try:
        info = requests.get(f"{args.url.rstrip('/')}/cache_info", timeout=5).json()
        print("\n캐시 현황")
        for scope, stat in info.items():
            print(
                f"  {scope:9s} 적재 {stat['currsize']:4d}건  "
                f"적중 {stat['hits']}  미적중 {stat['misses']}"
            )
    except requests.RequestException:
        print("\n(cache_info 조회 실패 — RAG 서비스를 재시작했는지 확인하세요)")

    if failures:
        print(f"\n{failures}건 실패. 위 메시지를 확인하세요.")
        return 1
    print("\n프리워밍 완료.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
