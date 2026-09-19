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


def test_extract_disposal_fields_always_reads_recycling_group_regardless_of_class():
    # Real API shape: one row per region, "+"-joined day abbreviations, one
    # column group per waste category (섹션 15.1). Every one of our 17
    # classes is treated as recyclable, so only RCYCL_* is ever read --
    # other groups on the same row (e.g. LF_WST_*) must be ignored.
    item = {
        "RCYCL_EMSN_DOW": "화+목",
        "RCYCL_EMSN_BGNG_TM": "19:00",
        "RCYCL_EMSN_END_TM": "21:00",
        "RCYCL_EMSN_MTHD": "투명 봉투에 담아 배출",
        "LF_WST_EMSN_DOW": "월+수+금",
    }
    fields = public_waste_client.extract_disposal_fields(item)
    assert fields["disposal_day"] == "화, 목"
    assert fields["start_time"] == "19:00"
    assert fields["end_time"] == "21:00"
    assert fields["disposal_method"] == "투명 봉투에 담아 배출"


def test_extract_disposal_fields_missing_recycling_columns_returns_all_none():
    item = {"LF_WST_EMSN_DOW": "화+목"}
    fields = public_waste_client.extract_disposal_fields(item)
    assert fields == {"disposal_day": None, "start_time": None, "end_time": None, "disposal_method": None}


def test_pick_best_item_returns_the_single_region_row():
    items = [{"SGG_NM": "종로구"}]
    assert public_waste_client.pick_best_item(items) == items[0]


def test_gemini_parse_class_id_success_and_failure():
    assert gemini_service._parse_class_id('{"class_id": 22}') == 22

    with pytest.raises(gemini_service.GeminiBadResponseError):
        gemini_service._parse_class_id(None)

    with pytest.raises(gemini_service.GeminiBadResponseError):
        gemini_service._parse_class_id("not json")

    with pytest.raises(gemini_service.GeminiBadResponseError):
        gemini_service._parse_class_id('{"wrong_key": 1}')
