from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class LocalSearchResult:
    data: list[dict[str, Any]]
    total_cards: int
    has_more: bool
    next_page: int | None


class CustomSetStore:
    """File-backed storage for local custom sets in Scryfall-like JSON format."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _set_path(self, set_code: str) -> Path:
        safe_code = (set_code or "").strip().lower()
        if not safe_code:
            raise ValueError("Set code is required.")
        return self.data_dir / safe_code / "set.json"

    def _legacy_set_path(self, set_code: str) -> Path:
        safe_code = (set_code or "").strip().lower()
        if not safe_code:
            raise ValueError("Set code is required.")
        return self.data_dir / f"{safe_code}.json"

    def _read_set_payload(self, set_code: str) -> dict[str, Any] | None:
        file_path = self._set_path(set_code)
        if not file_path.exists():
            legacy = self._legacy_set_path(set_code)
            if legacy.exists():
                file_path = legacy
            else:
                return None

        if not file_path.exists():
            return None

        with file_path.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        return self._normalize_payload(payload)

    def _write_set_payload(self, set_code: str, payload: dict[str, Any]) -> None:
        normalized = self._normalize_payload(payload)
        file_path = self._set_path(set_code)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=2, ensure_ascii=False)

        legacy_path = self._legacy_set_path(set_code)
        if legacy_path.exists():
            legacy_path.unlink()

    def _iter_payloads(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        candidate_paths: list[Path] = []

        for set_dir in sorted(path for path in self.data_dir.iterdir() if path.is_dir()):
            set_json = set_dir / "set.json"
            if set_json.exists():
                candidate_paths.append(set_json)

        for legacy_path in sorted(self.data_dir.glob("*.json")):
            code = legacy_path.stem.lower()
            if (self.data_dir / code / "set.json").exists():
                continue
            candidate_paths.append(legacy_path)

        for file_path in candidate_paths:
            try:
                with file_path.open("r", encoding="utf-8") as file:
                    payload = json.load(file)
                payloads.append(self._normalize_payload(payload))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return payloads

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Set payload must be a JSON object.")

        cards = payload.get("cards")
        if not isinstance(cards, list):
            cards_list = payload.get("cards_list", {})
            cards = cards_list.get("data", []) if isinstance(cards_list, dict) else []
        cards = [card for card in cards if isinstance(card, dict)]

        set_record = payload.get("set")
        if not isinstance(set_record, dict):
            sets = payload.get("sets", [])
            if isinstance(sets, list) and sets and isinstance(sets[0], dict):
                set_record = sets[0]
            else:
                set_record = {}

        set_code = str(set_record.get("code") or (cards[0].get("set") if cards else "")).strip().lower()
        if not set_code:
            raise ValueError("Could not determine set code from payload.")

        set_name = str(set_record.get("name") or set_code.upper()).strip() or set_code.upper()
        set_type = str(set_record.get("set_type") or "custom").strip() or "custom"
        released_at = str(set_record.get("released_at") or "").strip() or None

        for card in cards:
            card["set"] = str(card.get("set") or set_code).strip().lower() or set_code
            card["set_name"] = str(card.get("set_name") or set_name).strip() or set_name
            card["set_type"] = str(card.get("set_type") or set_type).strip() or set_type
            card["collector_number"] = str(card.get("collector_number") or "").strip()

        normalized_set = {
            "object": "set",
            "id": set_record.get("id"),
            "code": set_code,
            "name": set_name,
            "set_type": set_type,
            "released_at": released_at,
            "card_count": len(cards),
            "digital": False,
            "foil_only": False,
            "nonfoil_only": False,
            "scryfall_uri": set_record.get("scryfall_uri") or f"/set/{set_code}",
            "uri": set_record.get("uri") or f"/api/sets/{set_code}",
            "search_uri": set_record.get("search_uri") or f"/api/search?q=set:{set_code}",
            "icon_svg_uri": set_record.get("icon_svg_uri"),
        }

        return {
            "meta": payload.get("meta", {}),
            "set": normalized_set,
            "sets": [normalized_set],
            "cards": cards,
            "cards_list": {
                "object": "list",
                "has_more": False,
                "next_page": None,
                "total_cards": len(cards),
                "data": cards,
            },
        }

    def save_uploaded_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = self._normalize_payload(payload)
        set_code = normalized["set"]["code"]
        self._write_set_payload(set_code, normalized)
        return normalized

    def list_sets(self) -> list[dict[str, Any]]:
        set_records = [payload["set"] for payload in self._iter_payloads()]
        return sorted(set_records, key=lambda item: (item.get("name") or "", item.get("code") or ""))

    def get_set(self, set_code: str) -> dict[str, Any] | None:
        payload = self._read_set_payload(set_code)
        if not payload:
            return None
        return payload["set"]

    def get_cards_for_set(self, set_code: str) -> list[dict[str, Any]]:
        payload = self._read_set_payload(set_code)
        if not payload:
            return []
        return payload["cards"]

    def get_card_by_id(self, card_id: str) -> dict[str, Any] | None:
        for payload in self._iter_payloads():
            for card in payload["cards"]:
                if str(card.get("id")) == card_id:
                    return card
        return None

    def get_card_by_set_number(self, set_code: str, collector_number: str) -> dict[str, Any] | None:
        cards = self.get_cards_for_set(set_code)
        for card in cards:
            if str(card.get("collector_number")) == collector_number:
                return card
        return None

    def get_printings_for_oracle(self, oracle_id: str) -> list[dict[str, Any]]:
        normalized_oracle = str(oracle_id or "").strip()
        if not normalized_oracle:
            return []

        matches = [
            card
            for card in self.all_cards()
            if str(card.get("oracle_id", "")).strip() == normalized_oracle
        ]
        matches.sort(key=lambda card: (str(card.get("set", "")), str(card.get("collector_number", "")), str(card.get("name", ""))))
        return matches

    def all_cards(self) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for payload in self._iter_payloads():
            cards.extend(payload["cards"])
        return cards

    def has_set(self, set_code: str) -> bool:
        return self._set_path(set_code).exists() or self._legacy_set_path(set_code).exists()

    def update_set(self, set_code: str, updates: dict[str, str]) -> bool:
        payload = self._read_set_payload(set_code)
        if not payload:
            return False

        target_set = payload["set"]
        new_name = str(updates.get("name", target_set.get("name", ""))).strip() or target_set.get("name")
        new_type = str(updates.get("set_type", target_set.get("set_type", "custom"))).strip() or "custom"
        new_release = str(updates.get("released_at", target_set.get("released_at") or "")).strip() or None

        target_set["name"] = new_name
        target_set["set_type"] = new_type
        target_set["released_at"] = new_release

        for card in payload["cards"]:
            card["set_name"] = new_name
            card["set_type"] = new_type
            card["released_at"] = new_release

        self._write_set_payload(set_code, payload)
        return True

    def update_card(self, set_code: str, card_id: str, updates: dict[str, str]) -> bool:
        payload = self._read_set_payload(set_code)
        if not payload:
            return False

        target_card: dict[str, Any] | None = None
        for card in payload["cards"]:
            if str(card.get("id")) == card_id:
                target_card = card
                break

        if target_card is None:
            return False

        editable_fields = {
            "name",
            "mana_cost",
            "type_line",
            "oracle_text",
            "flavor_text",
            "collector_number",
            "rarity",
            "frame",
            "power",
            "toughness",
            "loyalty",
        }

        for field_name in editable_fields:
            if field_name not in updates:
                continue
            value = str(updates[field_name]).strip()
            target_card[field_name] = value if value else None

        if target_card.get("collector_number") is None:
            target_card["collector_number"] = ""

        self._write_set_payload(set_code, payload)
        return True

    def search_cards(self, query: str, page: int, per_page: int) -> LocalSearchResult:
        cards = self.all_cards()
        filtered = [card for card in cards if self._matches_query(card, query)]
        preferred = self._preferred_printings(filtered)
        preferred.sort(key=lambda card: (str(card.get("set", "")), str(card.get("collector_number", "")), str(card.get("name", ""))))

        page_number = max(page, 1)
        start = (page_number - 1) * per_page
        end = start + per_page
        page_items = preferred[start:end]

        has_more = end < len(preferred)
        return LocalSearchResult(
            data=page_items,
            total_cards=len(preferred),
            has_more=has_more,
            next_page=(page_number + 1) if has_more else None,
        )

    def _preferred_printings(self, cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for card in cards:
            oracle_key = str(card.get("oracle_id") or card.get("id") or "").strip()
            if not oracle_key:
                continue
            grouped.setdefault(oracle_key, []).append(card)

        selected: list[dict[str, Any]] = []
        for oracle_key in sorted(grouped.keys()):
            selected.append(
                min(
                    grouped[oracle_key],
                    key=lambda item: (
                        self._frame_rank(item),
                        str(item.get("collector_number", "")),
                        str(item.get("name", "")),
                    ),
                )
            )
        return selected

    def _frame_rank(self, card: dict[str, Any]) -> int:
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

    def _matches_query(self, card: dict[str, Any], query: str) -> bool:
        query_text = (query or "").strip()
        if not query_text:
            return True

        clauses = [part for part in query_text.split() if part]
        for clause in clauses:
            if ":" not in clause:
                if not self._contains_any(card, clause):
                    return False
                continue

            prefix, raw_value = clause.split(":", 1)
            value = raw_value.strip().strip('"')
            if not value:
                continue

            if prefix == "game":
                continue
            if prefix in {"set"} and str(card.get("set", "")).lower() != value.lower():
                return False
            if prefix in {"name"} and value.lower() not in str(card.get("name", "")).lower():
                return False
            if prefix in {"o", "oracle", "text"} and value.lower() not in str(card.get("oracle_text", "")).lower():
                return False
            if prefix in {"t", "type"} and value.lower() not in str(card.get("type_line", "")).lower():
                return False
            if prefix in {"r", "rarity"} and value.lower() not in str(card.get("rarity", "")).lower():
                return False
            if prefix in {"m", "mana"} and value.upper() not in str(card.get("mana_cost", "")).upper():
                return False
            if prefix in {"pow", "power"} and value != str(card.get("power", "")):
                return False
            if prefix in {"tou", "toughness"} and value != str(card.get("toughness", "")):
                return False
            if prefix in {"c", "color"} and not self._match_color_clause(card, value):
                return False

        return True

    def _contains_any(self, card: dict[str, Any], token: str) -> bool:
        normalized = token.lower()
        haystacks = [
            str(card.get("name", "")),
            str(card.get("oracle_text", "")),
            str(card.get("type_line", "")),
            str(card.get("set_name", "")),
        ]
        return any(normalized in value.lower() for value in haystacks)

    def _match_color_clause(self, card: dict[str, Any], value: str) -> bool:
        normalized = value.strip().upper()
        colors = [str(color).upper() for color in card.get("colors", [])]
        if normalized in {"C", "COLORLESS"}:
            return len(colors) == 0

        requested = re.findall(r"[WUBRG]", normalized)
        if not requested:
            return False

        return all(symbol in colors for symbol in requested)
