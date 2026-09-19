from __future__ import annotations


def test_favorites_crud_flow(client, signup_and_login):
    headers, _ = signup_and_login()

    empty = client.get("/api/v1/favorites", headers=headers)
    assert empty.status_code == 200
    assert empty.json()["items"] == []

    unknown_class = client.post("/api/v1/favorites", json={"class_id": 999999}, headers=headers)
    assert unknown_class.status_code == 404
    assert unknown_class.json()["code"] == "CLASS_NOT_FOUND"

    created = client.post("/api/v1/favorites", json={"class_id": 14}, headers=headers)
    assert created.status_code == 201
    body = created.json()
    assert body["class_id"] == 14
    assert body["major_category"] == "플라스틱류"
    favorite_id = body["favorite_id"]

    duplicate = client.post("/api/v1/favorites", json={"class_id": 14}, headers=headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "FAVORITE_ALREADY_EXISTS"

    listed = client.get("/api/v1/favorites", headers=headers)
    assert len(listed.json()["items"]) == 1

    deleted = client.delete(f"/api/v1/favorites/{favorite_id}", headers=headers)
    assert deleted.status_code == 204

    delete_again = client.delete(f"/api/v1/favorites/{favorite_id}", headers=headers)
    assert delete_again.status_code == 404
    assert delete_again.json()["code"] == "FAVORITE_NOT_FOUND"


def test_favorites_are_scoped_per_user(client, signup_and_login):
    headers_a, _ = signup_and_login()
    headers_b, _ = signup_and_login()

    created = client.post("/api/v1/favorites", json={"class_id": 6}, headers=headers_a)
    favorite_id = created.json()["favorite_id"]

    other_users_delete = client.delete(f"/api/v1/favorites/{favorite_id}", headers=headers_b)
    assert other_users_delete.status_code == 404
