#!/usr/bin/env python3
"""Statistical MTG booster generators for play and collector packs.

This program models booster contents at the distribution level instead of relying on
any one card's identity. That is the key to supporting unknown sets and new
printings: the generator learns the set's overall rarity and printing mix, then
samples a pack from that distribution while preferring cards from a user-supplied
collection when they match the target slot.

It works with MTGJSON when available, and falls back to realistic priors when
network access or a brand new set prevents a live fetch.
"""

from __future__ import annotations

import argparse
import json
import random
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence


MTGJSON_API_BASE = "https://mtgjson.com/api/v5"
SCRYFALL_API_BASE = "https://api.scryfall.com"
DEFAULT_SET = "mkm"


def normalize_rarity(value: str | None) -> str:
    if value is None:
        return "common"
    rarity = value.strip().lower()
    mapping = {
        "c": "common",
        "common": "common",
        "u": "uncommon",
        "uncommon": "uncommon",
        "r": "rare",
        "rare": "rare",
        "m": "mythic",
        "mythic": "mythic",
        "mythic rare": "mythic",
    }
    return mapping.get(rarity, "common")


def finish_tokens_for(raw: dict[str, Any] | Any) -> list[str]:
    if not isinstance(raw, dict):
        return []
    finish_values = raw.get("finishes") or raw.get("finish") or []
    if isinstance(finish_values, str):
        tokens = [token.strip().lower() for token in finish_values.replace("_", " ").split()]
    elif isinstance(finish_values, (list, tuple, set)):
        tokens = [str(token).strip().lower().replace("_", " ") for token in finish_values]
    else:
        tokens = []
    return [token for token in tokens if token]


def card_has_foil_variant(raw: dict[str, Any] | Any) -> bool:
    tokens = finish_tokens_for(raw)
    if tokens:
        return "foil" in tokens
    return bool(raw.get("isFoil") or raw.get("hasFoil") or raw.get("foil") or raw.get("is_foil"))


def derive_printing_type(raw: dict[str, Any] | Any) -> str:
    if not isinstance(raw, dict):
        return "normal"

    frame_values = raw.get("frame_effects") or raw.get("frameEffects") or []
    if isinstance(frame_values, str):
        frame_tokens = [token.strip().lower() for token in frame_values.replace("_", " ").split()]
    elif isinstance(frame_values, (list, tuple, set)):
        frame_tokens = [str(token).strip().lower().replace("_", " ") for token in frame_values]
    else:
        frame_tokens = []
    frame_tokens = [token for token in frame_tokens if token]

    finish_values = raw.get("finishes") or raw.get("finish") or []
    if isinstance(finish_values, str):
        finish_tokens = [token.strip().lower() for token in finish_values.replace("_", " ").split()]
    elif isinstance(finish_values, (list, tuple, set)):
        finish_tokens = [str(token).strip().lower().replace("_", " ") for token in finish_values]
    else:
        finish_tokens = []
    finish_tokens = [token for token in finish_tokens if token]
    finish_text = " ".join(finish_tokens)
    frame_text = " ".join(frame_tokens)

    frame_value = str(raw.get("frame") or "").lower().strip()
    custom_premium_frame_map = {
        "borderless": "borderless",
        "showcase": "showcase",
        "extended": "extended",
        "etched": "etched",
        "fullart": "full_art",
        "full_art": "full_art",
        "cosmicon": "full_art",
    }
    if frame_value in custom_premium_frame_map:
        return custom_premium_frame_map[frame_value]

    if (
        raw.get("isBorderless")
        or raw.get("is_borderless")
        or raw.get("borderless")
        or raw.get("borderColor") == "borderless"
        or "borderless" in frame_text
        or "borderless" in finish_text
    ):
        return "borderless"
    if (
        raw.get("isFullArt")
        or raw.get("is_full_art")
        or raw.get("full_art")
        or raw.get("fullArt")
        or "fullart" in frame_text
        or "full art" in frame_text
        or "full_art" in frame_text
        or "cosmicon" in frame_text
    ):
        return "full_art"
    if (
        raw.get("isShowcase")
        or raw.get("is_showcase")
        or raw.get("showcase")
        or "showcase" in frame_text
    ):
        return "showcase"
    if (
        raw.get("isExtendedArt")
        or raw.get("is_extended")
        or raw.get("extended_art")
        or raw.get("extendedArt")
        or "extendedart" in frame_text
        or "extended art" in frame_text
    ):
        return "extended"
    if (
        raw.get("isEtched")
        or raw.get("is_etched")
        or raw.get("etched")
        or "etched" in frame_text
    ):
        return "etched"
    if raw.get("isPromo") or raw.get("promoTypes") or raw.get("promo_types"):
        return "promo"
    return "normal"


@dataclass(frozen=True)
class CardRecord:
    name: str
    set_code: str
    rarity: str
    printing_type: str
    foil: bool
    collector_number: str | None = None

    @classmethod
    def from_mapping(cls, raw: dict[str, Any], set_code: str | None = None) -> "CardRecord | None":
        name = (raw.get("name") or raw.get("faceName") or raw.get("title") or "").strip()
        if not name:
            return None
        finish_tokens = finish_tokens_for(raw)
        finish_text = " ".join(finish_tokens)

        explicit_foil = bool(
            raw.get("isFoil")
            or raw.get("hasFoil")
            or raw.get("isAlternative")
            or raw.get("foil")
            or str(raw.get("finish") or "").lower() == "foil"
        )
        if finish_tokens:
            token_set = set(finish_tokens)
            if "foil" in token_set:
                foil = True
            elif len(token_set) == 1:
                foil = "foil" in token_set
            else:
                foil = explicit_foil and "foil" in token_set
        else:
            foil = explicit_foil or "foil" in finish_text

        return cls(
            name=name,
            set_code=(set_code or str(raw.get("set") or "")).upper(),
            rarity=normalize_rarity(str(raw.get("rarity") or raw.get("rarityName") or "common")),
            printing_type=derive_printing_type(raw),
            foil=foil,
            collector_number=str(raw.get("collectorNumber") or raw.get("number") or "").strip() or None,
        )


@dataclass
class SetProfile:
    set_code: str
    rarity_weights: dict[str, float]
    printing_weights: dict[str, float]
    collector_printing_weights: dict[str, float]
    foil_by_rarity: dict[str, float]
    allowed_printings: dict[str, set[str]]

    def slot_weights(self, booster_type: str) -> dict[str, float]:
        if booster_type == "play":
            return {"common": 10.0, "uncommon": 3.0, "rare": 1.0, "mythic": 0.12}
        if booster_type == "collector":
            return {"common": 5.0, "uncommon": 3.0, "rare": 4.0, "mythic": 1.8}
        raise ValueError(f"Unsupported booster type: {booster_type}")

    @staticmethod
    def default_profile(set_code: str) -> "SetProfile":
        rarity_weights = {"common": 0.76, "uncommon": 0.18, "rare": 0.05, "mythic": 0.01}
        printing_weights = {"normal": 0.72, "foil": 0.14, "borderless": 0.05, "showcase": 0.04, "extended": 0.03, "etched": 0.01, "full_art": 0.01}
        collector_printing_weights = {"normal": 0.18, "foil": 0.16, "borderless": 0.22, "showcase": 0.17, "full_art": 0.15, "extended": 0.08, "etched": 0.04}
        foil_by_rarity = {"common": 0.10, "uncommon": 0.16, "rare": 0.20, "mythic": 0.30}
        return SetProfile(
            set_code=set_code.upper(),
            rarity_weights=rarity_weights,
            printing_weights=printing_weights,
            collector_printing_weights=collector_printing_weights,
            foil_by_rarity=foil_by_rarity,
            allowed_printings={
                "play": {"normal", "foil"},
                "collector": {"normal", "foil", "borderless", "showcase", "extended", "etched", "full_art"},
            },
        )


class MTGJSONClient:
    def __init__(self, base_url: str = MTGJSON_API_BASE) -> None:
        self.base_url = base_url.rstrip("/")

    def _local_set_data(self, set_code: str) -> dict[str, Any] | None:
        code = set_code.upper()
        root = Path(__file__).resolve().parent / "working" / "AllSetFiles"
        if not root.exists():
            return None

        candidates = [root / f"{code}.json", root / f"{code.lower()}.json"]
        for path in candidates:
            if not path.exists():
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
                return payload["data"]
        return None

    def _booster_key_to_printing(self, key: str) -> str:
        token = str(key).lower().replace("_", "").replace("-", "")
        if "fullart" in token:
            return "full_art"
        if "borderless" in token:
            return "borderless"
        if "showcase" in token:
            return "showcase"
        if "extended" in token:
            return "extended"
        if "etched" in token:
            return "etched"
        if "foil" in token:
            return "foil"
        return "normal"

    def _booster_weights_from_metadata(self, booster_meta: Any) -> dict[str, float]:
        if not isinstance(booster_meta, dict):
            return {}

        total = 0.0
        weighted: Counter[str] = Counter()
        for pack in booster_meta.get("boosters", []):
            if not isinstance(pack, dict):
                continue
            contents = pack.get("contents", {})
            if not isinstance(contents, dict):
                continue
            weight = float(pack.get("weight") or 0)
            if weight <= 0:
                continue
            for key, count in contents.items():
                try:
                    amount = float(count)
                except (TypeError, ValueError):
                    continue
                if amount <= 0:
                    continue
                printing = self._booster_key_to_printing(str(key))
                weighted[printing] += amount * weight
                total += amount * weight

        if total <= 0:
            return {}
        return {kind: count / total for kind, count in weighted.items()}

    def _fetch_json(self, url: str) -> Any:
        request = urllib.request.Request(url, headers={"User-Agent": "booster-model/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def fetch_set_cards(self, set_code: str) -> list[dict[str, Any]]:
        code = set_code.upper()
        local_data = self._local_set_data(code)
        if isinstance(local_data, dict):
            cards = local_data.get("cards")
            if isinstance(cards, list):
                return cards

        urls = [
            f"{self.base_url}/SetCode/{code}.json",
            f"{self.base_url}/SetCode.json?set={urllib.parse.quote(code)}",
        ]

        for url in urls:
            try:
                payload = self._fetch_json(url)
            except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError):
                continue

            if isinstance(payload, dict):
                data = payload.get("data")
                if isinstance(data, list):
                    if data and all(isinstance(card, dict) for card in data):
                        return data
                if isinstance(data, dict):
                    cards = data.get("cards") or data.get("items")
                    if isinstance(cards, list):
                        return cards
                if isinstance(payload.get("sets"), list):
                    for entry in payload["sets"]:
                        if isinstance(entry, dict) and str(entry.get("code") or "").upper() == code:
                            return self.fetch_set_cards(str(entry.get("code") or code))
        raise RuntimeError(f"Unable to load card data for {code} from MTGJSON.")

    def fetch_set_profile(self, set_code: str) -> SetProfile:
        code = set_code.upper()
        local_data = self._local_set_data(code)
        if isinstance(local_data, dict):
            cards = local_data.get("cards")
            if isinstance(cards, list):
                rarity_counts: Counter[str] = Counter()
                printing_counts: Counter[str] = Counter()
                foil_by_rarity: defaultdict[str, int] = defaultdict(int)
                booster_meta = local_data.get("booster")
                local_play_weights = self._booster_weights_from_metadata(booster_meta.get("play")) if isinstance(booster_meta, dict) else {}
                local_collector_weights = self._booster_weights_from_metadata(booster_meta.get("collector")) if isinstance(booster_meta, dict) else {}

                for item in cards:
                    card = CardRecord.from_mapping(item, set_code=code)
                    if card is None:
                        continue
                    rarity_counts[card.rarity] += 1
                    printing_counts[card.printing_type] += 1
                    if card.foil:
                        foil_by_rarity[card.rarity] += 1

                total_cards = max(sum(rarity_counts.values()), 1)
                rarity_weights = {rarity: count / total_cards for rarity, count in rarity_counts.items()}
                play_printing_weights = local_play_weights or {kind: count / total_cards for kind, count in printing_counts.items()}
                collector_printing_weights = local_collector_weights or {kind: count / total_cards for kind, count in printing_counts.items()}
                foil_by_rarity = {rarity: (foil_by_rarity.get(rarity, 0) / max(rarity_counts.get(rarity, 1), 1)) for rarity in rarity_counts}

                default_profile = SetProfile.default_profile(code)
                return SetProfile(
                    set_code=code,
                    rarity_weights=rarity_weights or default_profile.rarity_weights,
                    printing_weights=play_printing_weights or default_profile.printing_weights,
                    collector_printing_weights=collector_printing_weights or default_profile.collector_printing_weights,
                    foil_by_rarity=foil_by_rarity or default_profile.foil_by_rarity,
                    allowed_printings={
                        "play": {"normal", "foil"},
                        "collector": {"normal", "foil", "borderless", "showcase", "extended", "etched", "full_art"},
                    },
                )

        try:
            cards = self.fetch_set_cards(set_code)
        except RuntimeError:
            return SetProfile.default_profile(code)

        rarity_counts: Counter[str] = Counter()
        printing_counts: Counter[str] = Counter()
        collector_printing_counts: Counter[str] = Counter()
        foil_by_rarity: defaultdict[str, int] = defaultdict(int)

        for item in cards:
            card = CardRecord.from_mapping(item, set_code=set_code)
            if card is None:
                continue
            rarity_counts[card.rarity] += 1
            printing_counts[card.printing_type] += 1
            collector_printing_counts[card.printing_type] += 1
            if card.foil:
                foil_by_rarity[card.rarity] += 1

        total_cards = max(sum(rarity_counts.values()), 1)
        rarity_weights = {rarity: count / total_cards for rarity, count in rarity_counts.items()}
        printing_weights = {kind: count / total_cards for kind, count in printing_counts.items()}
        collector_total = max(sum(collector_printing_counts.values()), 1)
        collector_printing_weights = {kind: count / collector_total for kind, count in collector_printing_counts.items()}
        foil_by_rarity = {rarity: (foil_by_rarity.get(rarity, 0) / max(rarity_counts.get(rarity, 1), 1)) for rarity in rarity_counts}

        default_profile = SetProfile.default_profile(code)
        return SetProfile(
            set_code=code,
            rarity_weights=rarity_weights or default_profile.rarity_weights,
            printing_weights=printing_weights or default_profile.printing_weights,
            collector_printing_weights=collector_printing_weights or default_profile.collector_printing_weights,
            foil_by_rarity=foil_by_rarity or default_profile.foil_by_rarity,
            allowed_printings={
                "play": {"normal", "foil"},
                "collector": {"normal", "foil", "borderless", "showcase", "extended", "etched", "full_art"},
            },
        )


class BaseBoosterModel:
    def __init__(self, set_code: str, mtgjson_base: str = MTGJSON_API_BASE) -> None:
        self.set_code = set_code.upper()
        self.client = MTGJSONClient(mtgjson_base)
        self.profile = self.client.fetch_set_profile(self.set_code)

    def _weighted_choice(self, weights: dict[str, float], rng: random.Random) -> str:
        total = sum(weights.values())
        if total <= 0:
            raise ValueError("Empty weight distribution")
        target = rng.random() * total
        running = 0.0
        for key, weight in weights.items():
            running += weight
            if target <= running:
                return key
        return next(reversed(weights))

    def _make_card_id(self, rarity: str, printing_type: str, foil: bool, suffix: str | None = None) -> dict[str, Any]:
        label = printing_type.replace("_", " ").title()
        if foil and "foil" not in label.lower():
            label = f"{label} Foil"
        fallback_name = f"{self.set_code} {rarity.title()} {label}"
        if suffix:
            fallback_name = f"{fallback_name} {suffix}"
        return {
            "name": fallback_name,
            "set": self.set_code,
            "rarity": rarity,
            "printing_type": printing_type,
            "foil": foil,
            "source": "statistical fallback",
        }

    def _card_identity(self, card: dict[str, Any] | None) -> str:
        if not isinstance(card, dict):
            return ""
        oracle_id = str(card.get("oracle_id") or card.get("oracleId") or "").strip()
        if oracle_id:
            return oracle_id
        name = str(card.get("name") or "").strip().lower()
        if name:
            return name
        set_code = str(card.get("set") or self.set_code or "").strip().lower()
        collector_number = str(card.get("collector_number") or card.get("number") or "").strip()
        return f"{set_code}:{collector_number}" if set_code and collector_number else str(card.get("id") or repr(card))

    def _pick_matching_card(self, collection: Sequence[dict[str, Any]], rarity: str, printing_type: str, foil: bool, rng: random.Random, booster_type: str = "play", seen_identities: set[str] | None = None) -> dict[str, Any] | None:
        premium_order = ["borderless", "showcase", "full_art", "extended", "etched", "normal", "foil"]
        preferred_printings: list[str] = []
        used_identities = seen_identities or set()

        if printing_type in premium_order:
            preferred_printings.append(printing_type)
            for candidate in premium_order:
                if candidate != printing_type and candidate not in preferred_printings:
                    preferred_printings.append(candidate)
        else:
            preferred_printings = [printing_type, "normal", "foil", "borderless", "showcase", "full_art", "extended", "etched"]

        if booster_type == "collector" and printing_type in {"borderless", "showcase", "full_art", "extended", "etched"}:
            preferred_printings = [printing_type, "borderless", "showcase", "full_art", "extended", "etched", "normal", "foil"]

        def matches_foil(card: dict[str, Any], target_foil: bool) -> bool:
            tokens = finish_tokens_for(card)
            if not tokens:
                return True
            token_set = set(tokens)
            if "foil" in token_set and "nonfoil" in token_set:
                return True
            if target_foil:
                return "foil" in token_set
            return "nonfoil" in token_set

        def available_cards(cards: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
            result: list[dict[str, Any]] = []
            for card in cards:
                identity = self._card_identity(card)
                if identity and identity in used_identities:
                    continue
                result.append(card)
            return result

        for target_printing in preferred_printings:
            for target_foil in [foil, not foil, True, False]:
                matches: list[dict[str, Any]] = []
                for card in available_cards(collection):
                    record = CardRecord.from_mapping(card, set_code=self.set_code)
                    if record is None:
                        continue
                    if record.rarity != rarity:
                        continue
                    if record.printing_type != target_printing:
                        continue
                    if not matches_foil(card, target_foil):
                        continue
                    matches.append(card)
                if matches:
                    return rng.choice(matches)

        for target_foil in [foil, not foil, True, False]:
            matches = []
            for card in available_cards(collection):
                record = CardRecord.from_mapping(card, set_code=self.set_code)
                if record is None:
                    continue
                if record.rarity != rarity:
                    continue
                if not matches_foil(card, target_foil):
                    continue
                matches.append(card)
            if matches:
                return rng.choice(matches)

        if booster_type == "collector":
            premium_bucket = {"borderless", "showcase", "full_art", "extended", "etched"}
            for target_foil in [foil, not foil, True, False]:
                matches = []
                for card in available_cards(collection):
                    record = CardRecord.from_mapping(card, set_code=self.set_code)
                    if record is None:
                        continue
                    if record.rarity != rarity:
                        continue
                    if record.printing_type not in premium_bucket:
                        continue
                    if not matches_foil(card, target_foil):
                        continue
                    matches.append(card)
                if matches:
                    return rng.choice(matches)

        for card in available_cards(collection):
            record = CardRecord.from_mapping(card, set_code=self.set_code)
            if record is None:
                continue
            if record.rarity == rarity:
                return card
        return None

    def _choose_rarity(self, booster_type: str, rng: random.Random) -> str:
        weights = self.profile.slot_weights(booster_type)
        # Realistic boosted pack composition, with a mythic-rare skew only in the rare slot.
        if booster_type == "play":
            slot_roll = rng.random()
            if slot_roll < 0.714:
                return "common"
            if slot_roll < 0.952:
                return "uncommon"
            if rng.random() < 0.125:
                return "mythic"
            return "rare"
        # Collector boosters are far more likely to contain premium printing bucket hits.
        slot_roll = rng.random()
        if slot_roll < 0.45:
            return "common"
        if slot_roll < 0.72:
            return "uncommon"
        if rng.random() < 0.28:
            return "mythic"
        return "rare"

    def _choose_printing(self, booster_type: str, rarity: str, rng: random.Random) -> tuple[str, bool]:
        allowed = self.profile.allowed_printings[booster_type]

        default_weights = {
            "normal": 0.72,
            "foil": 0.14,
            "borderless": 0.05,
            "showcase": 0.04,
            "extended": 0.03,
            "etched": 0.01,
            "full_art": 0.01,
        }
        collector_default_weights = {
            "normal": 0.18,
            "foil": 0.16,
            "borderless": 0.22,
            "showcase": 0.17,
            "full_art": 0.15,
            "extended": 0.08,
            "etched": 0.04,
        }

        base_source = self.profile.collector_printing_weights if booster_type == "collector" else self.profile.printing_weights
        base_weights = {
            key: float(base_source.get(key, default_weights.get(key, collector_default_weights.get(key, 0.0))))
            for key in (collector_default_weights if booster_type == "collector" else default_weights)
            if key in allowed
        }
        if not base_weights:
            base_weights = {key: value for key, value in (collector_default_weights if booster_type == "collector" else default_weights).items() if key in allowed}
        if booster_type == "collector":
            premium_boosts = {
                "borderless": 1.3,
                "showcase": 1.25,
                "full_art": 1.2,
                "extended": 1.1,
                "etched": 0.9,
            }
            for key, boost in premium_boosts.items():
                if key in allowed:
                    base_weights[key] = base_weights.get(key, 0.0) * boost
            base_weights["normal"] = base_weights.get("normal", 0.0) * 0.75
            base_weights["foil"] = base_weights.get("foil", 0.0) * 1.05
        else:
            base_weights["normal"] = base_weights.get("normal", 0.0) * 1.0
            base_weights["foil"] = base_weights.get("foil", 0.0) * 1.0

        if rarity == "mythic":
            base_weights["showcase"] = base_weights.get("showcase", 0.0) + 0.06
            base_weights["full_art"] = base_weights.get("full_art", 0.0) + 0.05
            base_weights["foil"] = base_weights.get("foil", 0.0) + 0.05
        elif rarity == "rare":
            base_weights["showcase"] = base_weights.get("showcase", 0.0) + 0.04
            base_weights["full_art"] = base_weights.get("full_art", 0.0) + 0.03
            base_weights["foil"] = base_weights.get("foil", 0.0) + 0.03
        elif rarity == "common":
            base_weights["normal"] = base_weights.get("normal", 0.0) + 0.10
            base_weights["foil"] = max(base_weights.get("foil", 0.0) - 0.02, 0.0)

        for key in list(base_weights):
            if key not in allowed:
                base_weights.pop(key, None)

        filtered = {key: max(weight, 0.001) for key, weight in base_weights.items() if key in allowed}
        if not filtered:
            filtered = {"normal": 1.0}
        total = sum(filtered.values())
        printing = self._weighted_choice({k: v / total for k, v in filtered.items()}, rng)

        if booster_type == "play" and printing not in {"normal", "foil"}:
            printing = "normal"

        foil_probability = self.profile.foil_by_rarity.get(rarity, 0.12)
        if printing in {"borderless", "showcase", "extended", "etched", "full_art"}:
            foil_probability = max(foil_probability, 0.45 if booster_type == "collector" else 0.20)
        foil = rng.random() < foil_probability
        if booster_type == "play" and printing not in {"normal", "foil"}:
            foil = False
        return printing, foil

    def generate_booster(self, collection: Sequence[dict[str, Any]], booster_type: str = "play", seed: int | None = None) -> list[dict[str, Any]]:
        if booster_type not in {"play", "collector"}:
            raise ValueError("booster_type must be 'play' or 'collector'.")

        rng = random.Random(seed)
        pack_size = 14 if booster_type == "play" else 15
        pack: list[dict[str, Any]] = []
        seen_identities: set[str] = set()

        for _ in range(pack_size):
            selected: dict[str, Any] | None = None
            fallback: dict[str, Any] | None = None
            for _ in range(60):
                rarity = self._choose_rarity(booster_type, rng)
                printing_type, foil = self._choose_printing(booster_type, rarity, rng)
                candidate = self._pick_matching_card(collection, rarity, printing_type, foil, rng, booster_type=booster_type, seen_identities=seen_identities)
                if candidate is None:
                    unseen_collection_cards = [item for item in collection if isinstance(item, dict) and self._card_identity(item) and self._card_identity(item) not in seen_identities]
                    if unseen_collection_cards:
                        continue
                    fallback_name_suffix = len(seen_identities)
                    fallback = self._make_card_id(rarity, printing_type, foil, suffix=f"#{fallback_name_suffix}")
                    while self._card_identity(fallback) in seen_identities:
                        fallback_name_suffix += 1
                        fallback = self._make_card_id(rarity, printing_type, foil, suffix=f"#{fallback_name_suffix}")
                    selected = fallback
                    break
                identity = self._card_identity(candidate)
                if not identity or identity not in seen_identities:
                    selected = candidate
                    break
                if not any(self._card_identity(item) not in seen_identities for item in collection if isinstance(item, dict)):
                    selected = candidate
                    break
            if selected is None:
                selected = fallback or self._make_card_id("common", "normal", False, suffix=f"#{len(seen_identities)}")

            if isinstance(selected, dict):
                selected_payload = dict(selected)
                selected_payload["rarity"] = normalize_rarity(str(selected_payload.get("rarity") or "common"))
                selected_payload["printing_type"] = selected_payload.get("printing_type") or derive_printing_type(selected_payload)
                selected_payload["foil"] = bool(foil)
                if "printing_type" in selected_payload and selected_payload["printing_type"] == "foil":
                    selected_payload["foil"] = True
                if selected_payload.get("printing_type") in {"normal", "borderless", "showcase", "full_art", "extended", "etched"} and foil:
                    selected_payload["foil"] = True
                pack.append(selected_payload)
                identity = self._card_identity(selected_payload)
                if identity:
                    seen_identities.add(identity)
            else:
                pack.append(selected)
        return pack


class PlayBoosterModel(BaseBoosterModel):
    def __init__(self, set_code: str, mtgjson_base: str = MTGJSON_API_BASE) -> None:
        super().__init__(set_code, mtgjson_base)

    def generate(self, collection: Sequence[dict[str, Any]], count: int = 1, seed: int | None = None) -> list[list[dict[str, Any]]]:
        rng = random.Random(seed)
        return [self.generate_booster(collection, booster_type="play", seed=rng.randrange(1_000_000)) for _ in range(count)]


class CollectorBoosterModel(BaseBoosterModel):
    def __init__(self, set_code: str, mtgjson_base: str = MTGJSON_API_BASE) -> None:
        super().__init__(set_code, mtgjson_base)

    def generate(self, collection: Sequence[dict[str, Any]], count: int = 1, seed: int | None = None) -> list[list[dict[str, Any]]]:
        rng = random.Random(seed)
        return [self.generate_booster(collection, booster_type="collector", seed=rng.randrange(1_000_000)) for _ in range(count)]


def load_collection(path: str | None, collection_json: str | None) -> list[dict[str, Any]]:
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            return data["cards"]
        raise ValueError("collection file must be a list of cards or a dict with a 'cards' list.")
    if collection_json:
        data = json.loads(collection_json)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("cards"), list):
            return data["cards"]
        raise ValueError("collection JSON must be a list or a dict with a 'cards' list.")
    return []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate realistic MTG booster packs from a card collection.")
    parser.add_argument("--set", default=DEFAULT_SET, help="Set code to model, e.g. mkm, one, war.")
    parser.add_argument("--type", choices=("play", "collector"), default="play", help="Which booster model to generate.")
    parser.add_argument("--count", type=int, default=1, help="Number of packs to generate.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed to make output deterministic.")
    parser.add_argument("--collection-file", type=str, default=None, help="JSON file containing a collection list or {cards:[...]}.")
    parser.add_argument("--collection-json", type=str, default=None, help="Inline collection JSON string.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    collection = load_collection(args.collection_file, args.collection_json)
    if args.type == "play":
        model = PlayBoosterModel(args.set)
        packs = model.generate(collection, count=max(args.count, 1), seed=args.seed)
    else:
        model = CollectorBoosterModel(args.set)
        packs = model.generate(collection, count=max(args.count, 1), seed=args.seed)

    payload = {
        "set": args.set.upper(),
        "booster_type": args.type,
        "pack_count": len(packs),
        "model_profile": {
            "rarity_weights": model.profile.rarity_weights,
            "printing_weights": model.profile.printing_weights,
            "foil_by_rarity": model.profile.foil_by_rarity,
            "play_allowed_printings": sorted(model.profile.allowed_printings["play"]),
            "collector_allowed_printings": sorted(model.profile.allowed_printings["collector"]),
        },
        "packs": packs,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
