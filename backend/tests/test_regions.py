from __future__ import annotations


def test_list_all_regions_is_public(client):
    """지역 선택 UI 는 로그인 전에도 떠야 하므로 이 엔드포인트만 인증이 없다."""
    resp = client.get("/api/v1/regions", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 200


def test_list_all_regions(client):
    resp = client.get("/api/v1/regions")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 56
    assert {r["sido_name"] for r in items} == {"서울특별시", "경기도"}


def test_filter_regions_by_sido(client):
    resp = client.get("/api/v1/regions", params={"sido_name": "서울특별시"})
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 25
    assert all(r["sido_name"] == "서울특별시" for r in items)


def test_filter_regions_invalid_sido(client):
    resp = client.get("/api/v1/regions", params={"sido_name": "부산광역시"})
    assert resp.status_code == 422
    assert resp.json()["code"] == "REQUEST_VALIDATION_ERROR"


def test_update_my_region(client, signup_and_login):
    headers, _ = signup_and_login()

    not_found = client.patch("/api/v1/users/me/region", json={"region_id": 9999}, headers=headers)
    assert not_found.status_code == 404
    assert not_found.json()["code"] == "REGION_NOT_FOUND"

    ok = client.patch("/api/v1/users/me/region", json={"region_id": 23}, headers=headers)
    assert ok.status_code == 200
    assert ok.json()["region"]["sgg_name"] == "강남구"

    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["region"]["region_id"] == 23
