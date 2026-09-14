"""Pure-logic unit tests for service helpers that don't require network
access (public data API key decoding/field extraction, Gemini response
parsing)."""

from __future__ import annotations

import pytest

from services import gemini_service, public_waste_client


def test_decoded_service_key_handles_url_encoded_and_plain(monkeypatch):
    monkeypatch.setattr(public_waste_client.settings, "public_waste_api_service_key", "a%2Bb%3Dc")
    assert public_waste_client._decoded_service_key() == "a+b=c"

    monkeypatch.setattr(public_waste_client.settings, "public_waste_api_service_key", "already-plain-key")
    assert public_waste_client._decoded_service_key() == "already-plain-key"

    monkeypatch.setattr(public_waste_client.settings, "public_waste_api_service_key", None)
    assert public_waste_client._decoded_service_key() == ""


def test_extract_disposal_fields_prefers_first_matching_candidate_key():
    item = {"EMISN_DOW_NM": "화,목", "EMISN_BEGIN_TIME": "18:00", "EMISN_END_TIME": "24:00"}
    fields = public_waste_client.extract_disposal_fields(item)
    assert fields["disposal_day"] == "화,목"
    assert fields["start_time"] == "18:00"
    assert fields["end_time"] == "24:00"
    assert fields["disposal_method"] is None


def test_pick_best_item_matches_minor_category_over_major():
    items = [
        {"ITEM_NM": "플라스틱류 일반"},
        {"ITEM_NM": "플라스틱류 욕실용품"},
    ]
    best = public_waste_client.pick_best_item(items, major_category="플라스틱류", minor_category="욕실용품")
    assert best["ITEM_NM"] == "플라스틱류 욕실용품"


def test_pick_best_item_falls_back_to_first_when_no_match():
    items = [{"ITEM_NM": "종이류"}, {"ITEM_NM": "캔류"}]
    best = public_waste_client.pick_best_item(items, major_category="유리병", minor_category="맥주병")
    assert best == items[0]


def test_gemini_parse_class_id_success_and_failure():
    assert gemini_service._parse_class_id('{"class_id": 22}') == 22

    with pytest.raises(gemini_service.GeminiBadResponseError):
        gemini_service._parse_class_id(None)

    with pytest.raises(gemini_service.GeminiBadResponseError):
        gemini_service._parse_class_id("not json")

    with pytest.raises(gemini_service.GeminiBadResponseError):
        gemini_service._parse_class_id('{"wrong_key": 1}')
