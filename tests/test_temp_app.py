import json

import tempApp
from tempApp import ScryfallService, app, create_temp_app


def test_upload_page_is_accessible():
    client = app.test_client()
    response = client.get("/upload")

    assert response.status_code == 200
    assert b"Upload Set Data" in response.data


def test_card_requests_are_cached():
    service = ScryfallService(api_base="https://example.invalid")
    calls = {"count": 0}

    def fake_request_json(path, params=None):
        calls["count"] += 1
        return {"object": "card", "id": "card-123", "name": "Cached Card"}

    service.request_json = fake_request_json

    first = service.get_card_by_id("card-123")
    second = service.get_card_by_id("card-123")

    assert first["id"] == "card-123"
    assert second["id"] == "card-123"
    assert calls["count"] == 1


def test_search_results_proxy_remote_images(monkeypatch):
    custom_app = create_temp_app()

    def fake_search_cards(self, params):
        return {
            "data": [
                {
                    "name": "Dark Ritual",
                    "image_uris": {"normal": "https://cards.scryfall.io/normal/front/11e12a84-e7be-4afc-a230-c2e644743fa8.jpg?1783903013"},
                }
            ]
        }

    monkeypatch.setattr(ScryfallService, "search_cards", fake_search_cards)

    client = custom_app.test_client()
    response = client.get("/api/search?q=name:Dark+Ritual")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data"][0]["image_uris"]["normal"].startswith("https://magic.emmycs.co.uk/api/proxy-image?url=")


def test_scryfall_deck_export_is_proxied(monkeypatch):
    custom_app = create_temp_app()

    def fake_fetch_deck_export(self, deck_path, export_format):
        assert deck_path == "example-deck"
        assert export_format == "csv"
        return "1 Island\n2 Mountain\n"

    monkeypatch.setattr(ScryfallService, "fetch_deck_export", fake_fetch_deck_export)

    client = custom_app.test_client()
    response = client.get("/api/decks/example-deck/export/csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.data == b"1 Island\n2 Mountain\n"


def test_api_build_accepts_deck_text(monkeypatch):
    custom_app = create_temp_app()

    def fake_search_cards(self, params):
        q = params.get("q", "")
        if "Forest" in q:
            return {"data": [{"object": "card", "id": "forest-1", "name": "Forest", "image_uris": {"normal": "https://example.invalid/forest.jpg"}}]}
        if "Island" in q:
            return {"data": [{"object": "card", "id": "island-1", "name": "Island", "image_uris": {"normal": "https://example.invalid/island.jpg"}}]}
        return {"data": []}

    monkeypatch.setattr(ScryfallService, "search_cards", fake_search_cards)

    client = custom_app.test_client()
    response = client.post("/api/build", json={"data": "1 Forest\n2 Island\n"})

    assert response.status_code == 200
    lines = [line for line in response.get_data(as_text=True).splitlines() if line.strip()]
    assert len(lines) == 3
    first = json.loads(lines[0])
    assert first["Name"] == "Card"
    assert first["Nickname"] in {"Forest", "Island"}
    assert "CustomDeck" in first
    assert "ObjectStates" not in first
    assert any('"Name": "Card"' in line for line in lines)
    assert any('"Nickname": "Forest"' in line for line in lines)
    assert any('"Nickname": "Island"' in line for line in lines)
    assert any('"CustomDeck"' in line for line in lines)


def test_deck_card_resolution_accepts_dict_search_params():
    service = ScryfallService(api_base="https://example.invalid")

    def fake_search_cards(self, params):
        q = params.get("q", "") if isinstance(params, dict) else params.query
        assert 'name:"Forest"' in q
        return {"data": [{"object": "card", "id": "forest-1", "name": "Forest"}]}

    service.search_cards = fake_search_cards.__get__(service, ScryfallService)

    card = service.resolve_deck_entry_card("Forest")

    assert card is not None
    assert card["name"] == "Forest"


def test_tts_native_card_object_uses_cached_local_images():
    card = {
        "name": "Angelic Ascension",
        "image_uris": {"normal": "https://cards.scryfall.io/normal/front/abcd.jpg"},
    }

    obj = tempApp.tts_native_card_object(card, 1)
    face_url = obj["CustomDeck"]["1"]["FaceURL"]

    assert ("/api/images/" in face_url) or ("/static/images/" in face_url)
    assert face_url.endswith((".jpg", ".png", ".webp", ".gif"))
    assert "cards.scryfall.io" not in face_url


def test_deck_import_url_falls_back_to_card_by_card(monkeypatch):
    service = ScryfallService(api_base="https://example.invalid")

    def fake_fetch_deck_export_for_url(self, deck_url):
        raise RuntimeError("Scryfall bulk deck export failed.")

    def fake_fetch_uri_text(self, url):
        return '<html><body><a href="/cards/123">Sol Ring</a><a href="/cards/456">Counterspell</a></body></html>'

    monkeypatch.setattr(ScryfallService, "fetch_deck_export_for_url", fake_fetch_deck_export_for_url)
    monkeypatch.setattr(ScryfallService, "_fetch_uri_text", fake_fetch_uri_text)

    deck_text = service.fetch_deck_text_from_url("https://scryfall.com/decks/test-deck")

    assert "1 Sol Ring" in deck_text
    assert "1 Counterspell" in deck_text


def test_moxfield_deck_payload_with_dict_boards_is_parsed(monkeypatch):
    service = ScryfallService(api_base="https://example.invalid")
    payload = {
        "mainboard": {
            "Kaalia, Zenith Seeker": {"quantity": 1, "card": {"name": "Kaalia, Zenith Seeker"}},
            "Aegis Angel": {"quantity": 1, "card": {"name": "Aegis Angel"}},
        },
        "commanders": {
            "Kaalia of the Vast": {"quantity": 1, "card": {"name": "Kaalia of the Vast"}},
        },
        "sideboard": {},
        "maybeboard": {},
    }

    class FakeResponse:
        def __init__(self, body):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._body

    def fake_urlopen(request, timeout=12):
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(tempApp, "urlopen", fake_urlopen)

    deck_text = service.fetch_deck_text_from_url("https://moxfield.com/decks/OU_fnSOgH0-GPomJ_PlaTw")
    cards = service.normalize_deck_build_response("", deck_url="https://moxfield.com/decks/OU_fnSOgH0-GPomJ_PlaTw")

    assert "1 Kaalia, Zenith Seeker" in deck_text
    assert "1 Aegis Angel" in deck_text
    assert len(cards) == 3
    assert {card["name"] for card in cards} == {"Kaalia, Zenith Seeker", "Aegis Angel", "Kaalia of the Vast"}
    assert all(card.get("image_uris") for card in cards)


def test_normalize_deck_build_response_card_by_card_fallback(monkeypatch):
    service = ScryfallService(api_base="https://example.invalid")

    def fake_search_cards(self, params):
        q = params.get("q", "") if isinstance(params, dict) else params.query
        if 'set:invalid' in q:
            return {"data": []}
        if 'name:"Sol Ring"' in q:
            return {"data": [{"object": "card", "id": "sol-ring-1", "name": "Sol Ring"}]}
        return {"data": []}

    monkeypatch.setattr(ScryfallService, "search_cards", fake_search_cards)

    cards = service.normalize_deck_build_response("1 Sol Ring [INVALID] 999")

    assert len(cards) == 1
    assert cards[0]["name"] == "Sol Ring"
