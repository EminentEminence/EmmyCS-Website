from __future__ import annotations

import json
import os
import random
import re
import shutil
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, send_from_directory, url_for

from booster_model import CollectorBoosterModel, MTGJSONClient, PlayBoosterModel, derive_printing_type
from custom_set_store import CustomSetStore
from mse_xml_to_scryfall import convert_set_xml_to_scryfall_like

# Path to the AllSetFiles directory containing booster data
ALL_SET_FILES_PATH = Path(__file__).resolve().parent / "working" / "AllSetFiles"


SCRYFALL_API_BASE = "https://api.scryfall.com"
DEFAULT_CARD_QUERY = "game:paper"
DEFAULT_SORT_ORDER = "released"
DEFAULT_SORT_DIRECTION = "desc"
DEFAULT_RESULTS_PER_PAGE = 12
CUSTOM_SETS_STORAGE_ENV = "CUSTOM_SETS_STORAGE_DIR"


def custom_sets_storage_root() -> Path:
    configured_path = (os.environ.get(CUSTOM_SETS_STORAGE_ENV) or "").strip()
    if configured_path:
        root = Path(configured_path).expanduser()
    else:
        root = Path(__file__).resolve().parent / "data" / "custom_sets"

    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class SearchParameters:
    query: str
    page: int = 1
    order: str = DEFAULT_SORT_ORDER
    direction: str = DEFAULT_SORT_DIRECTION
    unique: str = "cards"
    include_extras: bool = False
    include_multilingual: bool = False
    include_variations: bool = False
    include_digital: bool = False


class ScryfallService:
    """Temporary API-backed service layer that can later be swapped for a local database."""

    CACHE_TTL_SECONDS = 60 * 60 * 12

    def __init__(self, api_base: str = SCRYFALL_API_BASE) -> None:
        self.api_base = api_base.rstrip("/")
        self.custom_store = CustomSetStore(custom_sets_storage_root())
        self.cache_root = Path(__file__).resolve().parent / "data" / "cache"
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.cache_root / "scryfall_cache.json"
        self._response_cache: dict[str, dict[str, Any]] = self._load_cache()

    def _load_cache(self) -> dict[str, dict[str, Any]]:
        try:
            if not self.cache_path.exists():
                return {}
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
        except (OSError, ValueError, TypeError):
            return {}
        return {}

    def _save_cache(self) -> None:
        try:
            self.cache_path.write_text(json.dumps(self._response_cache, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            pass

    def _cache_key(self, path: str, params: dict[str, Any] | None = None) -> str:
        if not params:
            return path
        normalized = {key: value for key, value in params.items() if value not in (None, "")}
        query_string = urlencode(normalized, doseq=True)
        return f"{path}?{query_string}" if query_string else path

    def _read_cache(self, key: str) -> dict[str, Any] | None:
        entry = self._response_cache.get(key)
        if not isinstance(entry, dict):
            return None
        timestamp = float(entry.get("cached_at", 0))
        if time.time() - timestamp > self.CACHE_TTL_SECONDS:
            self._response_cache.pop(key, None)
            self._save_cache()
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

    def _write_cache(self, key: str, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        self._response_cache[key] = {"cached_at": time.time(), "payload": payload}
        self._save_cache()

    def request_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        cache_key = self._cache_key(path, params)
        cached = self._read_cache(cache_key)
        if cached is not None:
            return cached

        url = f"{self.api_base}{path}"
        if params:
            query_string = urlencode({key: value for key, value in params.items() if value not in (None, "")}, doseq=True)
            if query_string:
                url = f"{url}?{query_string}"

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "WebsiteV2TempApp/1.0",
            },
        )

        try:
            with urlopen(request, timeout=12) as response:
                payload = json.loads(response.read().decode("utf-8"))
                self._write_cache(cache_key, payload)
                return payload
        except HTTPError as error:
            try:
                payload = error.read().decode("utf-8")
                raise RuntimeError(json.loads(payload).get("details", str(error))) from error
            except json.JSONDecodeError:
                raise RuntimeError(str(error)) from error
        except URLError as error:
            raise RuntimeError(str(error)) from error

    def normalize_search_parameters(self, args: dict[str, str]) -> SearchParameters:
        query = self.build_query(args)
        page = self._parse_page_number(args.get("page", "1"))
        order = args.get("order", DEFAULT_SORT_ORDER) or DEFAULT_SORT_ORDER
        direction = args.get("dir", DEFAULT_SORT_DIRECTION) or DEFAULT_SORT_DIRECTION
        unique = args.get("unique", "cards") or "cards"
        include_extras = args.get("include_extras") == "1"
        include_multilingual = args.get("include_multilingual") == "1"
        include_variations = args.get("include_variations") == "1"
        include_digital = args.get("include_digital") == "1"
        return SearchParameters(
            query=query,
            page=page,
            order=order,
            direction=direction,
            unique=unique,
            include_extras=include_extras,
            include_multilingual=include_multilingual,
            include_variations=include_variations,
            include_digital=include_digital,
        )

    def _parse_page_number(self, raw_page: str) -> int:
        try:
            return max(int(raw_page or "1"), 1)
        except (TypeError, ValueError):
            return 1

    def build_query(self, args: dict[str, str]) -> str:
        parts: list[str] = []
        free_text = args.get("q", "").strip()
        skip_default_game = False
        if free_text:
            parts.append(free_text)
            skip_default_game = True

        field_map = {
            "name": "name",
            "oracle": "o",
            "type": "t",
            "text": "o",
            "set": "set",
            "rarity": "r",
            "color": "c",
            "mana": "m",
            "power": "pow",
            "toughness": "tou",
        }

        for field_name, prefix in field_map.items():
            value = args.get(field_name, "").strip()
            if value:
                parts.append(self._format_query_clause(prefix, value))
                skip_default_game = True

        if not skip_default_game and args.get("game", "paper").strip():
            parts.append(f"game:{args.get('game', 'paper').strip()}")

        if not parts:
            return DEFAULT_CARD_QUERY
        return " ".join(parts)

    def _format_query_clause(self, prefix: str, value: str) -> str:
        if " " in value or ":" in value or '"' in value:
            safe_value = value.replace('"', "\\\"")
            return f'{prefix}:"{safe_value}"'
        return f"{prefix}:{value}"

    def _looks_like_name_query(self, value: str) -> bool:
        candidate = value.strip()
        if not candidate:
            return False
        if re.search(r'[:()]', candidate):
            return False
        lowered = candidate.lower()
        reserved = {
            "game",
            "name",
            "oracle",
            "type",
            "text",
            "set",
            "rarity",
            "color",
            "mana",
            "power",
            "toughness",
            "cmc",
            "is",
            "or",
            "and",
            "not",
            "from",
            "to",
            "lang",
        }
        if any(token in reserved for token in lowered.split()):
            return False
        return True

    def search_cards(self, params: SearchParameters) -> dict[str, Any]:
        local_search = self.custom_store.search_cards(params.query, page=params.page, per_page=DEFAULT_RESULTS_PER_PAGE)
        set_filters = self._extract_set_filters(params.query)
        if set_filters and all(self.custom_store.has_set(code) for code in set_filters):
            return {
                "object": "list",
                "has_more": local_search.has_more,
                "next_page": local_search.next_page,
                "total_cards": local_search.total_cards,
                "data": local_search.data,
            }

        query_params = {
            "q": params.query,
            "page": params.page,
            "order": params.order,
            "dir": params.direction,
            "unique": params.unique,
            "include_extras": str(params.include_extras).lower(),
            "include_multilingual": str(params.include_multilingual).lower(),
            "include_variations": str(params.include_variations).lower(),
            "include_digital": str(params.include_digital).lower(),
        }
        remote_results = self.request_json("/cards/search", query_params)
        remote_cards = remote_results.get("data", [])
        filtered_remote_cards = self._filter_name_matches(remote_cards, params.query)
        remote_results["data"] = filtered_remote_cards
        remote_results["total_cards"] = len(filtered_remote_cards)

        if params.page != 1 or not local_search.data:
            return remote_results

        seen_ids = {str(card.get("id")) for card in filtered_remote_cards if card.get("id")}
        merged_local = [card for card in local_search.data if str(card.get("id")) not in seen_ids]
        merged_cards = merged_local + filtered_remote_cards

        remote_total = int(remote_results.get("total_cards") or len(filtered_remote_cards))
        return {
            **remote_results,
            "data": merged_cards,
            "total_cards": remote_total + max(local_search.total_cards, len(merged_local)),
        }

    def _filter_name_matches(self, cards: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
        cleaned = (query or "").strip()
        if not cleaned:
            return cards

        lowered = cleaned.lower()
        if any(token in {"or", "and", "not"} for token in lowered.split()):
            return cards

        normalized_query = re.sub(r"\s+", " ", cleaned).strip().lower()
        if normalized_query.startswith("name:"):
            normalized_query = re.sub(r"^name:\s*", "", normalized_query).strip()
        elif ":" in normalized_query:
            field_prefix = normalized_query.split(":", 1)[0]
            if field_prefix in {"name", "oracle", "type", "text", "set", "rarity", "color", "mana", "power", "toughness", "game"}:
                normalized_query = normalized_query.split(":", 1)[1].strip()

        normalized_query = normalized_query.strip().strip('"').strip()
        if not normalized_query:
            return cards

        ranked_matches: list[tuple[int, int, str, dict[str, Any]]] = []
        for card in cards:
            if not isinstance(card, dict):
                continue
            name = str(card.get("name") or "").strip().lower()
            if not name:
                continue
            if name == normalized_query:
                score = 1000
            elif name.startswith(normalized_query):
                score = 500
            elif normalized_query in name:
                score = 200
            else:
                continue
            ranked_matches.append((score, len(name), name, card))

        if not ranked_matches:
            return cards

        ranked_matches.sort(key=lambda item: (-item[0], item[1], item[2]))
        best = ranked_matches[0][3]
        if ranked_matches[0][0] >= 1000:
            return [card for _, _, _, card in ranked_matches if str(card.get("name") or "").strip().lower() == normalized_query]
        return [best]

    def get_card_by_id(self, card_id: str) -> dict[str, Any]:
        local_card = self.custom_store.get_card_by_id(card_id)
        if local_card:
            return local_card
        return self.request_json(f"/cards/{card_id}")

    def get_card_by_set_number(self, set_code: str, collector_number: str) -> dict[str, Any]:
        local_card = self.custom_store.get_card_by_set_number(set_code, collector_number)
        if local_card:
            return local_card
        return self.request_json(f"/cards/{set_code}/{collector_number}")

    def get_random_card(self) -> dict[str, Any]:
        local_cards = self.custom_store.all_cards()
        if local_cards and random.random() < 0.35:
            return random.choice(local_cards)
        return self.request_json("/cards/random")

    def get_sets(self, page: int = 1) -> dict[str, Any]:
        remote_sets = self.request_json("/sets", {"page": page, "order": "released"})
        local_sets = self.custom_store.list_sets()

        if page != 1 or not local_sets:
            return remote_sets

        remote_data = remote_sets.get("data", [])
        local_codes = {str(item.get("code", "")).lower() for item in local_sets}
        merged = local_sets + [item for item in remote_data if str(item.get("code", "")).lower() not in local_codes]
        return {**remote_sets, "data": merged}

    def get_set(self, set_code: str) -> dict[str, Any]:
        local_set = self.custom_store.get_set(set_code)
        if local_set:
            return local_set
        return self.request_json(f"/sets/{set_code}")

    def get_cards_for_set(self, set_code: str, page: int = 1) -> dict[str, Any]:
        local_cards = self.custom_store.get_cards_for_set(set_code)
        if local_cards:
            preferred_cards = self._preferred_printings_for_set(local_cards)
            page_number = max(page, 1)
            start = (page_number - 1) * DEFAULT_RESULTS_PER_PAGE
            end = start + DEFAULT_RESULTS_PER_PAGE
            sliced_cards = preferred_cards[start:end]
            has_more = end < len(preferred_cards)
            return {
                "object": "list",
                "has_more": has_more,
                "next_page": page_number + 1 if has_more else None,
                "total_cards": len(preferred_cards),
                "data": sliced_cards,
            }

        return self.request_json(
            "/cards/search",
            {
                "q": f"set:{set_code}",
                "page": page,
                "order": "set",
                "dir": "asc",
                "unique": "cards",
            },
        )

    def get_printings_for_card(self, card: dict[str, Any]) -> list[dict[str, Any]]:
        oracle_id = str(card.get("oracle_id") or "").strip()
        if not oracle_id:
            return [card]

        local_printings = self.custom_store.get_printings_for_oracle(oracle_id)

        remote_printings: list[dict[str, Any]] = []
        try:
            remote_response = self.request_json(
                "/cards/search",
                {
                    "q": f"oracleid:{oracle_id}",
                    "unique": "prints",
                    "order": "set",
                    "dir": "asc",
                },
            )
            remote_printings = [item for item in remote_response.get("data", []) if isinstance(item, dict)]
        except RuntimeError:
            remote_printings = []

        merged: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for printing in [*local_printings, *remote_printings, card]:
            printing_id = str(printing.get("id") or "").strip()
            if not printing_id or printing_id in seen_ids:
                continue
            seen_ids.add(printing_id)
            merged.append(printing)

        merged.sort(key=lambda item: (str(item.get("set", "")), str(item.get("collector_number", "")), str(item.get("name", ""))))
        return merged

    def _preferred_printings_for_set(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for card in cards:
            oracle_key = str(card.get("oracle_id") or card.get("id") or "").strip()
            if not oracle_key:
                continue
            grouped.setdefault(oracle_key, []).append(card)

        preferred: list[dict[str, Any]] = []
        for oracle_key in sorted(grouped.keys()):
            candidates = grouped[oracle_key]
            chosen = min(
                candidates,
                key=lambda item: (
                    self._printing_frame_rank(item),
                    str(item.get("collector_number", "")),
                    str(item.get("name", "")),
                ),
            )
            preferred.append(chosen)

        preferred.sort(key=lambda item: (str(item.get("collector_number", "")), str(item.get("name", ""))))
        return preferred

    def _printing_frame_rank(self, card: dict[str, Any]) -> int:
        frame_value = str(card.get("frame") or "").strip().lower()
        premium_order = {
            "borderless": 0,
            "showcase": 1,
            "full_art": 2,
            "fullart": 2,
            "cosmicon": 2,
            "extended": 3,
            "etched": 4,
            "2015": 5,
            "$standard": 5,
            "standard": 5,
        }
        if bool(card.get("full_art") or card.get("isFullArt") or card.get("fullArt")):
            return premium_order.get(frame_value, 2)
        if bool(card.get("borderless") or card.get("isBorderless") or card.get("borderColor") == "borderless"):
            return premium_order.get(frame_value, 0)
        return premium_order.get(frame_value, 10)

    def _extract_set_filters(self, query: str) -> list[str]:
        return [
            match.strip().strip('"').lower()
            for match in re.findall(r'(?:^|\s)set:("[^"]+"|[^\s]+)', query or "")
            if match.strip().strip('"')
        ]


def create_temp_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-key")
    service = ScryfallService()
    custom_sets_root = custom_sets_storage_root()

    def dev_only(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            return view_func(*args, **kwargs)

        return wrapped

    def safe_call(callable_obj, fallback):
        try:
            return callable_obj()
        except RuntimeError as error:
            flash(str(error), "error")
            return fallback

    def proxied_image_url(image_url: str | None) -> str | None:
        if not image_url:
            return None
        image_url = str(image_url).strip()
        if not image_url:
            return None
        if image_url.startswith(("https://magic.emmycs.co.uk/", "http://magic.emmycs.co.uk/", "/")):
            return image_url
        if image_url.startswith(("http://", "https://")):
            return url_for("api_proxy_image", url=image_url, _external=True)
        return image_url

    def proxy_image_uris_for_card(card: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(card, dict):
            return card

        image_uris = card.get("image_uris")
        if isinstance(image_uris, dict):
            for key, value in list(image_uris.items()):
                if not value:
                    continue
                image_uris[key] = proxied_image_url(str(value)) or value

        for face in card.get("card_faces", []) or []:
            if not isinstance(face, dict):
                continue
            face_uris = face.get("image_uris")
            if isinstance(face_uris, dict):
                for key, value in list(face_uris.items()):
                    if not value:
                        continue
                    face_uris[key] = proxied_image_url(str(value)) or value

        return card

    def card_preview_image(card: dict[str, Any]) -> str | None:
        if card.get("image_uris"):
            image_uris = card.get("image_uris", {})
            candidate = image_uris.get("normal") or image_uris.get("large") or image_uris.get("png")
            return proxied_image_url(candidate) or candidate

        for face in card.get("card_faces", []) or []:
            if face.get("image_uris"):
                image_uris = face.get("image_uris", {})
                candidate = image_uris.get("normal") or image_uris.get("large") or image_uris.get("png")
                return proxied_image_url(candidate) or candidate
        return None

    def card_gallery_images(card: dict[str, Any]) -> list[dict[str, str]]:
        gallery: list[dict[str, str]] = []
        if card.get("image_uris"):
            image_uris = card.get("image_uris", {})
            candidate = image_uris.get("png") or image_uris.get("large") or image_uris.get("normal") or ""
            gallery.append({"label": "Front", "image": proxied_image_url(candidate) or candidate})
            return gallery

        for index, face in enumerate(card.get("card_faces", []) or []):
            image_uris = face.get("image_uris", {})
            candidate = image_uris.get("png") or image_uris.get("large") or image_uris.get("normal") or ""
            gallery.append({"label": face.get("name") or f"Face {index + 1}", "image": proxied_image_url(candidate) or candidate})
        return [item for item in gallery if item["image"]]

    def normalize_card_for_display(card: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(card, dict):
            return card

        card = proxy_image_uris_for_card(card)

        finish_values: list[str] = []
        raw_finishes = card.get("finishes") or card.get("finish") or []
        if isinstance(raw_finishes, str):
            finish_values = [token.strip().lower() for token in raw_finishes.replace("_", " ").split() if token.strip()]
        elif isinstance(raw_finishes, (list, tuple, set)):
            finish_values = [str(token).strip().lower().replace("_", " ") for token in raw_finishes if str(token).strip()]

        token_set = {token for token in finish_values if token}
        is_foil = bool(
            card.get("foil")
            or card.get("isFoil")
            or card.get("is_foil")
            or card.get("hasFoil")
            or card.get("has_foil")
            or str(card.get("finish") or "").strip().lower() == "foil"
            or "foil" in token_set
        )

        if not is_foil and "foil" in {str(value).strip().lower() for value in (card.get("finishes") or []) if value is not None}:
            is_foil = True

        card["foil"] = bool(is_foil)
        card["finishes"] = finish_values or (['foil'] if is_foil else ['nonfoil'])
        return card

    def paginated_args(page: int) -> dict[str, str]:
        query_args = request.args.to_dict(flat=True)
        query_args["page"] = str(page)
        return query_args

    @app.context_processor
    def inject_globals() -> dict[str, Any]:
        return {
            "current_year": datetime.now().year,
            "search_query": request.args.get("q", ""),
        }

    @app.get("/")
    def temp_home() -> str:
        if any(request.args.get(field) for field in ["q", "name", "oracle", "type", "text", "set", "rarity", "color", "mana", "power", "toughness"]):
            return redirect(url_for("temp_search", **request.args.to_dict(flat=True)))

        featured_card = normalize_card_for_display(safe_call(service.get_random_card, None))
        latest_sets = safe_call(lambda: service.get_sets(page=1), {"data": []}).get("data", [])[:6]
        return render_template(
            "temp_home.html",
            page_title="Arcana Vault",
            featured_card=featured_card,
            latest_sets=latest_sets,
        )

    @app.get("/search")
    def temp_search() -> str:
        params = service.normalize_search_parameters(request.args.to_dict(flat=True))
        results = safe_call(lambda: service.search_cards(params), {"data": [], "has_more": False, "next_page": None, "total_cards": 0})
        results["data"] = [normalize_card_for_display(card) for card in results.get("data", [])]
        current_args = request.args.to_dict(flat=True)
        previous_args = current_args | {"page": str(max(params.page - 1, 1))}
        next_args = current_args | {"page": str(params.page + 1)}
        return render_template(
            "temp_search.html",
            page_title=f"Search | {params.query}",
            search=params,
            results=results,
            previous_page=max(params.page - 1, 1),
            next_page=params.page + 1,
            previous_page_url=url_for("temp_search", **previous_args),
            next_page_url=url_for("temp_search", **next_args),
        )

    @app.get("/random")
    def temp_random() -> str:
        card = safe_call(service.get_random_card, None)
        if card and card.get("id"):
            return redirect(url_for("temp_card_by_id", card_id=card["id"]))
        return redirect(url_for("temp_home"))

    @app.get("/card/<card_id>")
    def temp_card_by_id(card_id: str) -> str:
        card = normalize_card_for_display(safe_call(lambda: service.get_card_by_id(card_id), None))
        if not card:
            abort(404)
        printings = [normalize_card_for_display(printing) for printing in safe_call(lambda: service.get_printings_for_card(card), [card])]
        return render_template(
            "temp_card.html",
            page_title=card.get("name", "Card"),
            card=card,
            printings=printings,
            gallery_images=card_gallery_images(card),
            preview_image=card_preview_image(card),
        )

    @app.get("/card/<set_code>/<collector_number>")
    def temp_card_by_set(set_code: str, collector_number: str) -> str:
        card = normalize_card_for_display(safe_call(lambda: service.get_card_by_set_number(set_code, collector_number), None))
        if not card:
            abort(404)
        printings = [normalize_card_for_display(printing) for printing in safe_call(lambda: service.get_printings_for_card(card), [card])]
        return render_template(
            "temp_card.html",
            page_title=card.get("name", "Card"),
            card=card,
            printings=printings,
            gallery_images=card_gallery_images(card),
            preview_image=card_preview_image(card),
        )

    @app.get("/sets")
    def temp_sets() -> str:
        sets_response = safe_call(lambda: service.get_sets(page=1), {"data": []})
        return render_template(
            "temp_sets.html",
            page_title="Sets",
            sets=sets_response.get("data", []),
        )

    @app.get("/set/<set_code>")
    def temp_set_detail(set_code: str) -> str:
        set_record = safe_call(lambda: service.get_set(set_code), None)
        if not set_record:
            abort(404)

        cards = safe_call(lambda: service.get_cards_for_set(set_code), {"data": [], "has_more": False, "next_page": None})
        cards["data"] = [normalize_card_for_display(card) for card in cards.get("data", [])]
        return render_template(
            "temp_set_detail.html",
            page_title=set_record.get("name", set_code.upper()),
            set_record=set_record,
            cards=cards,
            set_code=set_code,
        )

    @app.get("/api")
    def temp_api_docs() -> str:
        endpoints = [
            {"method": "GET", "path": "/api/search", "description": "Search cards using the same filters as the UI."},
            {"method": "GET", "path": "/api/cards/<card_id>", "description": "Fetch a card by Scryfall card ID."},
            {"method": "GET", "path": "/api/cards/<set_code>/<collector_number>", "description": "Fetch a card by set code and collector number."},
            {"method": "GET", "path": "/api/sets", "description": "List Scryfall sets."},
            {"method": "GET", "path": "/api/sets/<set_code>", "description": "Fetch a set and related cards."},
            {"method": "GET", "path": "/api/random", "description": "Return a random card."},
            {"method": "GET", "path": "/upload", "description": "Upload and edit local custom sets without requiring a password."},
            {"method": "GET", "path": "/custom-sets", "description": "Upload and edit local custom sets merged into search and set pages."},
        ]
        return render_template("temp_api.html", page_title="API", endpoints=endpoints)

    def build_pack_opener_context() -> dict[str, Any]:
        query_args = request.args.to_dict(flat=True)
        booster_type = (query_args.get("booster_type") or "play").strip().lower()
        if booster_type not in {"play", "collector"}:
            booster_type = "play"

        set_code = (query_args.get("set") or "").strip()
        if query_args.get("set") is None and booster_type == "collector":
            set_code = "MKM"
        selected_set = set_code.upper()

        filter_args = {key: value for key, value in query_args.items() if key not in {"booster_type", "seed", "ajax"}}

        if set_code:
            set_lookup = set_code.upper()
            raw_mtgj_cards: list[dict[str, Any]] = []
            mtgjson_path = ALL_SET_FILES_PATH / f"{set_lookup}.json"
            if mtgjson_path.exists():
                try:
                    raw_mtgj_cards = MTGJSONClient().fetch_set_cards(set_lookup)
                except Exception:
                    raw_mtgj_cards = []
            if raw_mtgj_cards:
                candidate_cards = raw_mtgj_cards
            else:
                candidate_cards = [card for card in service.custom_store.get_cards_for_set(set_code) if isinstance(card, dict)]
            if filter_args and any(value.strip() for key, value in filter_args.items() if key != "set"):
                filtered_cards: list[dict[str, Any]] = []
                for card in candidate_cards:
                    if not isinstance(card, dict):
                        continue
                    keep = True
                    for key, value in filter_args.items():
                        if key == "set" or not str(value or "").strip():
                            continue
                        target = str(value).strip().lower()
                        if key in {"name", "q"}:
                            if target not in str(card.get("name", "")).lower():
                                keep = False
                                break
                        elif key in {"oracle", "text"}:
                            if target not in str(card.get("oracle_text", "")).lower():
                                keep = False
                                break
                        elif key in {"type"}:
                            if target not in str(card.get("type_line", "")).lower():
                                keep = False
                                break
                        elif key in {"rarity"}:
                            if target not in str(card.get("rarity", "")).lower():
                                keep = False
                                break
                        elif key in {"color"}:
                            requested = re.findall(r"[WUBRG]", target.upper())
                            if not requested:
                                continue
                            card_colors = [str(color).upper() for color in card.get("colors", [])]
                            if not all(symbol in card_colors for symbol in requested):
                                keep = False
                                break
                        elif key in {"mana"}:
                            if target.upper() not in str(card.get("mana_cost", "")).upper():
                                keep = False
                                break
                        elif key in {"power"}:
                            if target != str(card.get("power", "")):
                                keep = False
                                break
                        elif key in {"toughness"}:
                            if target != str(card.get("toughness", "")):
                                keep = False
                                break
                    if keep:
                        filtered_cards.append(card)
                candidate_cards = filtered_cards
        else:
            pool_params = service.normalize_search_parameters(filter_args)
            pool_response = safe_call(lambda: service.search_cards(pool_params), {"data": []})
            candidate_cards = [card for card in pool_response.get("data", []) if isinstance(card, dict)]

        if not candidate_cards and set_code:
            candidate_cards = [card for card in service.custom_store.get_cards_for_set(set_code) if isinstance(card, dict)]

        if not candidate_cards:
            candidate_cards = safe_call(lambda: service.search_cards(service.normalize_search_parameters({"q": "game:paper"})), {"data": []}).get("data", [])

        if set_code:
            set_for_model = set_code.upper()
        elif candidate_cards:
            set_for_model = str(candidate_cards[0].get("set") or candidate_cards[0].get("set_name") or "mkm").upper()
        else:
            set_for_model = "MKM"

        model_cls = PlayBoosterModel if booster_type == "play" else CollectorBoosterModel
        model = model_cls(set_for_model)
        seed_value = int(query_args.get("seed") or random.randint(1, 10_000_000))
        generated = model.generate(candidate_cards, count=1, seed=seed_value)
        pack_cards = generated[0] if generated else []

        def resolve_visual_card(card: dict[str, Any]) -> dict[str, Any]:
            if not isinstance(card, dict):
                return card

            target_printing = str(card.get("printing_type") or derive_printing_type(card) or "normal").lower()
            foil = bool(card.get("foil"))
            if card.get("image_uris") or card.get("card_faces"):
                resolved_card = dict(card)
                resolved_card["foil"] = foil
                resolved_card["printing_type"] = target_printing
                return resolved_card

            set_lookup_code = str(card.get("set") or set_for_model or "").lower()
            if not set_lookup_code:
                return card

            scryfall_id = ""
            for key in ["scryfall_id", "scryfallId", "id"]:
                value = str(card.get(key) or "").strip()
                if value:
                    scryfall_id = value
                    break
            if not scryfall_id and isinstance(card.get("identifiers"), dict):
                scryfall_id = str(card["identifiers"].get("scryfallId") or card["identifiers"].get("scryfall_id") or "").strip()
            if scryfall_id:
                try:
                    remote_card = service.request_json(f"/cards/{scryfall_id}")
                    if remote_card.get("image_uris") or remote_card.get("card_faces"):
                        resolved_card = dict(remote_card)
                        resolved_card["foil"] = foil
                        resolved_card["printing_type"] = target_printing
                        return resolved_card
                except RuntimeError:
                    pass

            name = str(card.get("name") or "").strip()
            oracle_id = str(card.get("oracle_id") or card.get("oracleId") or "").strip()

            candidates: list[dict[str, Any]] = []
            mtgjson_cards: list[dict[str, Any]] = []
            mtgjson_path = ALL_SET_FILES_PATH / f"{set_lookup_code.upper()}.json"
            if mtgjson_path.exists():
                try:
                    mtgjson_cards = MTGJSONClient().fetch_set_cards(set_lookup_code.upper())
                except Exception:
                    mtgjson_cards = []
            if mtgjson_cards:
                candidates = mtgjson_cards
            elif oracle_id:
                candidates = service.get_printings_for_card(card)
            else:
                local_set_cards = service.custom_store.get_cards_for_set(set_lookup_code)
                candidates = local_set_cards if local_set_cards else safe_call(lambda: service.get_cards_for_set(set_lookup_code), {"data": []}).get("data", [])
            candidates = [item for item in candidates if isinstance(item, dict)]

            filtered_candidates: list[dict[str, Any]] = []
            if name:
                filtered_candidates = [item for item in candidates if str(item.get("name") or "").strip() == name]
            if oracle_id and not filtered_candidates:
                filtered_candidates = [item for item in candidates if str(item.get("oracle_id") or item.get("oracleId") or "").strip() == oracle_id]
            if not filtered_candidates:
                filtered_candidates = candidates

            if target_printing:
                exact_printing_matches = [
                    item for item in filtered_candidates
                    if str(derive_printing_type(item)).lower() == target_printing and (item.get("image_uris") or item.get("card_faces"))
                ]
                if exact_printing_matches:
                    filtered_candidates = exact_printing_matches

            if target_printing in {"showcase", "borderless", "full_art", "extended", "etched"}:
                premium_matches = [
                    item for item in filtered_candidates
                    if str(derive_printing_type(item)).lower() == target_printing and (item.get("image_uris") or item.get("card_faces"))
                ]
                if premium_matches:
                    filtered_candidates = premium_matches
                else:
                    name_query = f'name:"{name}" set:{set_lookup_code} unique:prints'
                    try:
                        search_results = service.request_json("/cards/search", {"q": name_query, "unique": "prints", "order": "set", "dir": "asc"})
                        premium_matches = [item for item in search_results.get("data", []) if isinstance(item, dict) and str(derive_printing_type(item)).lower() == target_printing]
                        if premium_matches:
                            filtered_candidates = premium_matches
                    except RuntimeError:
                        pass

            for candidate in filtered_candidates:
                if candidate.get("image_uris") or candidate.get("card_faces"):
                    resolved_candidate = dict(candidate)
                    resolved_candidate["foil"] = foil
                    resolved_candidate["printing_type"] = target_printing or derive_printing_type(candidate)
                    return resolved_candidate
                candidate_id = str(candidate.get("scryfall_id") or candidate.get("scryfallId") or "").strip()
                if not candidate_id and isinstance(candidate.get("identifiers"), dict):
                    candidate_id = str(candidate["identifiers"].get("scryfallId") or candidate["identifiers"].get("scryfall_id") or "").strip()
                if candidate_id:
                    try:
                        remote_candidate = service.request_json(f"/cards/{candidate_id}")
                        if remote_candidate.get("image_uris") or remote_candidate.get("card_faces"):
                            resolved_candidate = dict(remote_candidate)
                            resolved_candidate["foil"] = foil
                            resolved_candidate["printing_type"] = target_printing or derive_printing_type(remote_candidate)
                            return resolved_candidate
                    except RuntimeError:
                        continue

            for candidate in candidates:
                candidate_id = str(candidate.get("scryfall_id") or candidate.get("scryfallId") or "").strip()
                if not candidate_id and isinstance(candidate.get("identifiers"), dict):
                    candidate_id = str(candidate["identifiers"].get("scryfallId") or candidate["identifiers"].get("scryfall_id") or "").strip()
                if candidate_id:
                    try:
                        remote_candidate = service.request_json(f"/cards/{candidate_id}")
                        if remote_candidate.get("image_uris") or remote_candidate.get("card_faces"):
                            resolved_candidate = dict(remote_candidate)
                            resolved_candidate["foil"] = foil
                            resolved_candidate["printing_type"] = target_printing or derive_printing_type(remote_candidate)
                            return resolved_candidate
                    except RuntimeError:
                        pass
                if candidate.get("image_uris") or candidate.get("card_faces"):
                    resolved_candidate = dict(candidate)
                    resolved_candidate["foil"] = foil
                    resolved_candidate["printing_type"] = target_printing or derive_printing_type(candidate)
                    return resolved_candidate

            return card

        pack_cards = [normalize_card_for_display(resolve_visual_card(card)) for card in pack_cards]
        selected_set_record = None
        if set_for_model:
            selected_set_record = safe_call(lambda: service.get_set(set_for_model.lower()), None)

        return {
            "booster_type": booster_type,
            "selected_set": selected_set,
            "selected_set_record": selected_set_record,
            "pool_count": len(candidate_cards),
            "pack_cards": pack_cards,
            "query_args": query_args,
            "current_filters": filter_args,
        }

    @app.get("/pack-opener")
    def temp_pack_opener() -> str:
        context = build_pack_opener_context()
        return render_template("temp_pack_opener.html", page_title="Pack Opener", **context)

    def render_custom_sets_page() -> str:
        sets = service.custom_store.list_sets()
        selected_set_code = (request.args.get("set") or "").strip().lower()
        selected_set = next((item for item in sets if str(item.get("code", "")).lower() == selected_set_code), None)

        if selected_set is None and sets:
            selected_set = sets[0]
            selected_set_code = str(selected_set.get("code", "")).lower()

        cards = service.custom_store.get_cards_for_set(selected_set_code) if selected_set else []

        selected_card_id = (request.args.get("card") or "").strip()
        selected_card = next((item for item in cards if str(item.get("id")) == selected_card_id), None)
        if selected_card is None and cards:
            selected_card = cards[0]

        return render_template(
            "temp_custom_sets.html",
            page_title="Custom Sets",
            custom_sets=sets,
            selected_set=selected_set,
            selected_cards=cards,
            selected_card=selected_card,
        )

    @app.get("/upload")
    def temp_upload() -> str:
        return render_custom_sets_page()

    @app.get("/custom-sets")
    def temp_custom_sets() -> str:
        return render_custom_sets_page()

    @app.post("/upload")
    @app.post("/custom-sets/upload")
    def temp_custom_sets_upload() -> Any:
        upload = request.files.get("set_file")
        if upload is None or not upload.filename:
            flash("Choose a JSON or ZIP file to upload.", "error")
            return redirect(url_for("temp_custom_sets"))

        upload_name = upload.filename.lower()

        if upload_name.endswith(".json"):
            try:
                payload = json.loads(upload.read().decode("utf-8"))
                normalized = service.custom_store.save_uploaded_payload(payload)
                set_code = normalized["set"]["code"]
                flash(f"Imported set {set_code.upper()} with {len(normalized['cards'])} cards.", "success")
                return redirect(url_for("temp_custom_sets", set=set_code))
            except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
                flash(f"Upload failed: {error}", "error")
                return redirect(url_for("temp_custom_sets"))

        if upload_name.endswith(".zip"):
            set_code_override = (request.form.get("set_code") or "").strip().lower() or None
            try:
                with tempfile.TemporaryDirectory(prefix="arcana-set-upload-") as temp_dir:
                    temp_path = Path(temp_dir)
                    zip_path = temp_path / "upload.zip"
                    zip_path.write_bytes(upload.read())

                    with zipfile.ZipFile(zip_path, "r") as archive:
                        archive.extractall(temp_path / "extracted")

                    extracted_root = temp_path / "extracted"
                    xml_candidates = list(extracted_root.rglob("setInfo.xml"))
                    if not xml_candidates:
                        raise ValueError("ZIP is missing setInfo.xml.")

                    xml_path = xml_candidates[0]
                    set_folder = xml_path.parent

                    payload = convert_set_xml_to_scryfall_like(
                        xml_path=xml_path,
                        images_root=set_folder,
                        output_path=temp_path / "converted.json",
                        set_code=set_code_override,
                        image_prefix="",
                    )

                    set_code = str(payload.get("set", {}).get("code", "")).strip().lower()
                    if not set_code:
                        raise ValueError("Could not infer set code from XML. Provide set code override.")

                    destination_set_root = custom_sets_root / set_code
                    if destination_set_root.exists():
                        shutil.rmtree(destination_set_root)
                    shutil.copytree(set_folder, destination_set_root)

                    for card in payload.get("cards", []):
                        image_uris = card.get("image_uris")
                        if isinstance(image_uris, dict):
                            for image_key, image_value in image_uris.items():
                                if not image_value:
                                    continue
                                image_uris[image_key] = url_for(
                                    "temp_custom_set_asset",
                                    set_code=set_code,
                                    asset_path=str(image_value).lstrip("/"),
                                    _external=True,
                                )

                        for face in card.get("card_faces", []) or []:
                            face_uris = face.get("image_uris")
                            if not isinstance(face_uris, dict):
                                continue
                            for image_key, image_value in face_uris.items():
                                if not image_value:
                                    continue
                                face_uris[image_key] = url_for(
                                    "temp_custom_set_asset",
                                    set_code=set_code,
                                    asset_path=str(image_value).lstrip("/"),
                                    _external=True,
                                )

                    normalized = service.custom_store.save_uploaded_payload(payload)
                    flash(f"Imported ZIP set {set_code.upper()} with {len(normalized['cards'])} cards.", "success")
                    return redirect(url_for("temp_custom_sets", set=set_code))
            except (OSError, zipfile.BadZipFile, ValueError) as error:
                flash(f"ZIP upload failed: {error}", "error")
                return redirect(url_for("temp_custom_sets"))

        flash("Only .json and .zip uploads are supported.", "error")
        return redirect(url_for("temp_custom_sets"))

    @app.get("/custom-sets/assets/<set_code>/<path:asset_path>")
    def temp_custom_set_asset(set_code: str, asset_path: str) -> Any:
        asset_root = (custom_sets_root / set_code).resolve()
        if not asset_root.exists() or not asset_root.is_dir():
            abort(404)

        try:
            requested = (asset_root / asset_path).resolve()
        except OSError:
            abort(404)

        if asset_root not in requested.parents and requested != asset_root:
            abort(404)

        if not requested.exists() or not requested.is_file():
            abort(404)

        return send_from_directory(asset_root, asset_path)

    @app.post("/custom-sets/<set_code>/update")
    def temp_custom_sets_update(set_code: str) -> Any:
        updated = service.custom_store.update_set(
            set_code,
            {
                "name": request.form.get("name", ""),
                "set_type": request.form.get("set_type", ""),
                "released_at": request.form.get("released_at", ""),
            },
        )
        if updated:
            flash(f"Updated set {set_code.upper()}.", "success")
        else:
            flash("Set not found.", "error")
            return redirect(url_for("temp_custom_sets"))
        return redirect(url_for("temp_custom_sets", set=set_code))

    @app.post("/custom-sets/<set_code>/cards/<card_id>/update")
    def temp_custom_set_card_update(set_code: str, card_id: str) -> Any:
        updated = service.custom_store.update_card(
            set_code,
            card_id,
            {
                "name": request.form.get("name", ""),
                "mana_cost": request.form.get("mana_cost", ""),
                "type_line": request.form.get("type_line", ""),
                "oracle_text": request.form.get("oracle_text", ""),
                "flavor_text": request.form.get("flavor_text", ""),
                "collector_number": request.form.get("collector_number", ""),
                "rarity": request.form.get("rarity", ""),
                "frame": request.form.get("frame", ""),
                "power": request.form.get("power", ""),
                "toughness": request.form.get("toughness", ""),
                "loyalty": request.form.get("loyalty", ""),
            },
        )
        if updated:
            flash("Card updated.", "success")
        else:
            flash("Card not found.", "error")
        return redirect(url_for("temp_custom_sets", set=set_code, card=card_id))

    def api_proxy_card_payload(payload: Any) -> Any:
        if isinstance(payload, dict):
            payload = dict(payload)
            for key, value in list(payload.items()):
                payload[key] = api_proxy_card_payload(value)

            image_uris = payload.get("image_uris")
            if isinstance(image_uris, dict):
                for key, value in list(image_uris.items()):
                    if not value:
                        continue
                    image_uris[key] = proxied_image_url(str(value)) or value

            for face in payload.get("card_faces", []) or []:
                if not isinstance(face, dict):
                    continue
                face_uris = face.get("image_uris")
                if isinstance(face_uris, dict):
                    for key, value in list(face_uris.items()):
                        if not value:
                            continue
                        face_uris[key] = proxied_image_url(str(value)) or value
            return payload

        if isinstance(payload, list):
            return [api_proxy_card_payload(item) for item in payload]

        return payload

    @app.get("/api/proxy-image")
    def api_proxy_image() -> Any:
        remote_url = (request.args.get("url") or "").strip()
        if not remote_url:
            abort(400)
        if not remote_url.startswith(("http://", "https://")):
            abort(400)
        if not remote_url.startswith(("https://cards.scryfall.io/", "https://api.scryfall.com/", "https://static.scryfall.io/")):
            abort(403)

        try:
            with urlopen(Request(remote_url, headers={"User-Agent": "Mozilla/5.0"}), timeout=25) as response:
                data = response.read()
                mime = response.headers.get_content_type() or "image/jpeg"
                return Response(data, mimetype=mime)
        except Exception:
            abort(502)

    @app.get("/api/search")
    def api_search() -> Any:
        params = service.normalize_search_parameters(request.args.to_dict(flat=True))
        try:
            return jsonify(api_proxy_card_payload(service.search_cards(params)))
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 502

    @app.get("/api/cards/<card_id>")
    def api_card_by_id(card_id: str) -> Any:
        try:
            return jsonify(api_proxy_card_payload(service.get_card_by_id(card_id)))
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 502

    @app.get("/api/cards/<set_code>/<collector_number>")
    def api_card_by_set(set_code: str, collector_number: str) -> Any:
        try:
            return jsonify(api_proxy_card_payload(service.get_card_by_set_number(set_code, collector_number)))
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 502

    @app.get("/api/sets")
    def api_sets() -> Any:
        try:
            page_arg = request.args.get("page", "1") or "1"
            page = max(int(page_arg), 1)
            return jsonify(api_proxy_card_payload(service.get_sets(page=page)))
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 502

    @app.get("/api/sets/<set_code>")
    def api_set_detail(set_code: str) -> Any:
        try:
            return jsonify({
                "set": api_proxy_card_payload(service.get_set(set_code)),
                "cards": api_proxy_card_payload(service.get_cards_for_set(set_code)),
            })
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 502

    @app.get("/api/random")
    def api_random() -> Any:
        try:
            return jsonify(api_proxy_card_payload(service.get_random_card()))
        except RuntimeError as error:
            return jsonify({"error": str(error)}), 502

    def api_compatibility_error(action: str) -> Any:
        return jsonify({
            "error": f"{action} is not available on this instance.",
            "details": "This server exposes the read-only Scryfall-compatible API only. Supported routes are /api/search, /api/cards/<id>, /api/cards/<set>/<number>, /api/sets, and /api/random.",
        }), 501

    @app.post("/api/build")
    def api_build() -> Any:
        return api_compatibility_error("Deck build")

    @app.post("/api/draft")
    def api_draft() -> Any:
        return api_compatibility_error("Draft generation")

    @app.post("/api/draftCube")
    def api_draft_cube() -> Any:
        return api_compatibility_error("Cube draft generation")

    return app


app = create_temp_app()


if __name__ == "__main__":
    app.run(debug=True)
