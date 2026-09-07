from __future__ import annotations

import argparse
import json
import re
import uuid
from datetime import UTC, datetime
from pathlib import Path
import xml.etree.ElementTree as ET

RARITY_MAP = {
    "C": "common",
    "U": "uncommon",
    "R": "rare",
    "M": "mythic",
    "S": "special",
    "B": "bonus",
}

COLOR_NAME_TO_SYMBOL = {
    "white": "W",
    "blue": "U",
    "black": "B",
    "red": "R",
    "green": "G",
}

COLOR_ORDER = ["W", "U", "B", "R", "G"]


FRAME_NAME_ALIASES = {
    "$STANDARD": "2015",
    "$BORDERLESS": "borderless",
}


def _clean_xml_text(raw_xml: str) -> str:
    """Normalize exporter quirks so the payload can be parsed as XML."""
    return raw_xml.replace("\x01", "<")


def _text(node: ET.Element | None, path: str, default: str = "") -> str:
    if node is None:
        return default
    value = node.findtext(path, default=default)
    return (value or default).strip()


def _float_or_zero(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _collector_suffix(index: int) -> str:
    """Convert 1-based occurrence index to alphabetical suffix (1 -> a, 27 -> aa)."""
    if index < 1:
        return ""

    value = index
    chars: list[str] = []
    while value > 0:
        value -= 1
        chars.append(chr(ord("a") + (value % 26)))
        value //= 26
    return "".join(reversed(chars))


def _derive_set_code(set_name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", set_name)
    initials = "".join(word[0] for word in words if word)
    if len(initials) >= 3:
        return initials[:5].lower()

    collapsed = "".join(words).lower()
    if len(collapsed) >= 3:
        return collapsed[:5]
    return "set"


def _normalize_mana_cost(cost: str) -> str:
    if not cost:
        return ""

    normalized = cost.strip().upper()
    tokens = re.findall(r"\{[^}]+\}|\d+|[WUBRGCXS]", normalized)
    if not tokens:
        return ""

    parts: list[str] = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token.startswith("{") and token.endswith("}"):
            parts.append(token)
        else:
            parts.append("{" + token + "}")
    return "".join(parts)


def _colors_from_mana(cost: str) -> list[str]:
    symbols = set(re.findall(r"[WUBRG]", cost.upper()))
    return [symbol for symbol in COLOR_ORDER if symbol in symbols]


def _normalize_colors(raw_colors: str, mana_cost: str) -> list[str]:
    if not raw_colors:
        return _colors_from_mana(mana_cost)

    tokens = [token.strip().lower() for token in raw_colors.split(",") if token.strip()]
    inferred: set[str] = set()

    for token in tokens:
        if token in COLOR_NAME_TO_SYMBOL:
            inferred.add(COLOR_NAME_TO_SYMBOL[token])
        elif token in {"w", "u", "b", "r", "g"}:
            inferred.add(token.upper())

    if not inferred:
        return _colors_from_mana(mana_cost)
    return [symbol for symbol in COLOR_ORDER if symbol in inferred]


def _image_url(relative_image_path: str, image_prefix: str) -> str:
    normalized = relative_image_path.replace("\\", "/").strip()
    if not image_prefix:
        return normalized

    return image_prefix.rstrip("/") + "/" + normalized.lstrip("/")


def _normalize_frame_name(raw_style_name: str) -> str:
    style_name = (raw_style_name or "").strip()
    if not style_name:
        return "2015"

    alias_value = FRAME_NAME_ALIASES.get(style_name.upper())
    if alias_value:
        return alias_value

    return style_name


def _canonical_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _oracle_identity_key(card_node: ET.Element, set_code_final: str) -> str:
    """Build a gameplay-identity fingerprint used to share oracle_id across printings."""
    name = _canonical_text(_text(card_node, "name"))
    mana_cost = _normalize_mana_cost(_text(card_node, "mana_cost"))
    type_line = _canonical_text(_text(card_node, "type_line"))
    oracle_text = _canonical_text(_text(card_node, "oracle_text"))
    layout = _canonical_text(_text(card_node, "layout", "normal") or "normal")

    stats = card_node.find("stats")
    power = _canonical_text(_text(stats, "power") if stats is not None else "")
    toughness = _canonical_text(_text(stats, "toughness") if stats is not None else "")
    loyalty = _canonical_text(_text(stats, "loyalty") if stats is not None else "")

    face_parts: list[str] = []
    faces_parent = card_node.find("faces")
    if faces_parent is not None:
        for face in faces_parent.findall("face"):
            face_parts.append(
                "|".join(
                    [
                        _canonical_text(face.attrib.get("side", "")),
                        _canonical_text(_text(face, "name")),
                        _normalize_mana_cost(_text(face, "mana_cost")),
                        _canonical_text(_text(face, "type_line")),
                        _canonical_text(_text(face, "oracle_text")),
                        _canonical_text(_text(face, "power")),
                        _canonical_text(_text(face, "toughness")),
                        _canonical_text(_text(face, "loyalty")),
                    ]
                )
            )

    return "::".join(
        [
            set_code_final,
            name,
            mana_cost,
            type_line,
            oracle_text,
            layout,
            power,
            toughness,
            loyalty,
            "||".join(face_parts),
        ]
    )


def _artist_from_image_file(image_file: str) -> str:
    basename = Path(image_file).name
    stem = basename[:-4] if basename.lower().endswith(".png") else basename
    segments = stem.split(".")
    if len(segments) >= 3:
        return segments[-1].strip()
    return ""


def _build_card_faces(card_node: ET.Element, card_image_uris: dict[str, str], fallback_colors: list[str]) -> list[dict]:
    faces: list[dict] = []
    faces_parent = card_node.find("faces")
    if faces_parent is None:
        return faces

    for face in faces_parent.findall("face"):
        face_name = _text(face, "name")
        face_mana = _text(face, "mana_cost")
        face_type = _text(face, "type_line")
        face_oracle = _text(face, "oracle_text")
        face_flavor = _text(face, "flavor_text")
        face_power = _text(face, "power")
        face_toughness = _text(face, "toughness")
        face_loyalty = _text(face, "loyalty")
        face_colors = _normalize_colors(_text(face, "colors"), face_mana)
        if not face_colors:
            face_colors = fallback_colors

        faces.append(
            {
                "name": face_name,
                "mana_cost": _normalize_mana_cost(face_mana),
                "type_line": face_type,
                "oracle_text": face_oracle,
                "flavor_text": face_flavor,
                "power": face_power or None,
                "toughness": face_toughness or None,
                "loyalty": face_loyalty or None,
                "colors": face_colors,
                "image_uris": card_image_uris,
            }
        )

    return faces


def convert_set_xml_to_scryfall_like(
    xml_path: Path,
    images_root: Path,
    output_path: Path,
    set_code: str | None = None,
    image_prefix: str = "",
    released_at: str = "",
) -> dict:
    raw_xml = xml_path.read_text(encoding="utf-8", errors="replace")
    root = ET.fromstring(_clean_xml_text(raw_xml))

    set_name = root.attrib.get("set", "Custom Set").strip() or "Custom Set"
    set_code_final = (set_code or _derive_set_code(set_name)).lower()

    partition_styles: dict[str, str] = {}
    for style_node in root.findall("style"):
        partition_code = _text(style_node, "partition")
        style_name = _text(style_node, "name")
        if partition_code:
            partition_styles[partition_code] = _normalize_frame_name(style_name)

    cards: list[dict] = []
    card_nodes = root.findall("card")
    collector_totals: dict[str, int] = {}
    for card_node in card_nodes:
        raw_collector = _text(card_node, "collector_number") or _text(card_node, "number") or "0"
        collector_totals[raw_collector] = collector_totals.get(raw_collector, 0) + 1

    collector_seen: dict[str, int] = {}

    for card_node in card_nodes:
        name = _text(card_node, "name")
        mana_cost_raw = _text(card_node, "mana_cost")
        mana_cost = _normalize_mana_cost(mana_cost_raw)
        cmc = _float_or_zero(_text(card_node, "mana_value", "0"))
        type_line = _text(card_node, "type_line")
        oracle_text = _text(card_node, "oracle_text")
        flavor_text = _text(card_node, "flavor_text")
        rarity = RARITY_MAP.get(_text(card_node, "rarity", "C").upper(), "common")
        collector_number = _text(card_node, "collector_number") or _text(card_node, "number") or "0"
        collector_seen[collector_number] = collector_seen.get(collector_number, 0) + 1
        collector_occurrence = collector_seen[collector_number]

        if collector_totals.get(collector_number, 0) > 1:
            collector_number_db = f"{collector_number}{_collector_suffix(collector_occurrence)}"
        else:
            collector_number_db = collector_number
        layout = _text(card_node, "layout", "normal") or "normal"
        image_file = _text(card_node, "image_file")
        partition = _text(card_node, "partition", "A")

        image_source_path = (images_root / image_file).resolve() if image_file else None
        image_ref = _image_url(image_file, image_prefix) if image_file else ""
        image_uris = {
            "small": image_ref,
            "normal": image_ref,
            "large": image_ref,
            "png": image_ref,
            "art_crop": image_ref,
            "border_crop": image_ref,
        }

        colors = _normalize_colors(_text(card_node, "colors"), mana_cost_raw)

        stats = card_node.find("stats")
        power = _text(stats, "power") if stats is not None else ""
        toughness = _text(stats, "toughness") if stats is not None else ""
        loyalty = _text(stats, "loyalty") if stats is not None else ""

        stable_key = f"{set_code_final}:{collector_number_db}:{partition}:{name}"
        card_id = str(uuid.uuid5(uuid.NAMESPACE_URL, stable_key))
        oracle_id = str(uuid.uuid5(uuid.NAMESPACE_URL, _oracle_identity_key(card_node, set_code_final)))

        card_faces = _build_card_faces(card_node, image_uris, colors)

        card_payload = {
            "object": "card",
            "id": card_id,
            "oracle_id": oracle_id,
            "multiverse_ids": [],
            "tcgplayer_id": None,
            "cardmarket_id": None,
            "name": name,
            "lang": "en",
            "released_at": released_at or None,
            "uri": f"/api/cards/{card_id}",
            "scryfall_uri": f"/card/{set_code_final}/{collector_number_db}",
            "layout": layout,
            "highres_image": bool(image_ref),
            "image_status": "highres_scan" if image_ref else "missing",
            "image_uris": image_uris if image_ref else None,
            "mana_cost": mana_cost,
            "cmc": cmc,
            "type_line": type_line,
            "oracle_text": oracle_text,
            "flavor_text": flavor_text or None,
            "power": power or None,
            "toughness": toughness or None,
            "loyalty": loyalty or None,
            "colors": colors,
            "color_identity": colors,
            "keywords": [],
            "legalities": {},
            "games": ["paper"],
            "reserved": False,
            "foil": True,
            "nonfoil": True,
            "finishes": ["nonfoil", "foil"],
            "oversized": False,
            "promo": False,
            "reprint": False,
            "variation": False,
            "set_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"set:{set_code_final}")),
            "set": set_code_final,
            "set_name": set_name,
            "set_type": "custom",
            "set_uri": f"/api/sets/{set_code_final}",
            "set_search_uri": f"/api/search?q=set:{set_code_final}",
            "collector_number": collector_number_db,
            "source_collector_number": collector_number,
            "rarity": rarity,
            "artist": _artist_from_image_file(image_file),
            "artist_ids": [],
            "border_color": "black",
            "frame": partition_styles.get(partition, "2015"),
            "full_art": partition.upper() in {"B", "C"},
            "textless": False,
            "booster": True,
            "story_spotlight": False,
            "edhrec_rank": None,
            "penny_rank": None,
            "prices": {},
            "related_uris": {},
            "purchase_uris": {},
            "source_image_file": str(image_source_path) if image_source_path else None,
        }

        if len(card_faces) > 1 or layout in {"transform", "modal_dfc", "adventure", "split", "flip"}:
            card_payload["card_faces"] = card_faces

        cards.append(card_payload)

    set_record = {
        "object": "set",
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"set:{set_code_final}")),
        "code": set_code_final,
        "mtgo_code": None,
        "arena_code": None,
        "tcgplayer_id": None,
        "name": set_name,
        "set_type": "custom",
        "released_at": released_at or None,
        "block_code": None,
        "block": None,
        "parent_set_code": None,
        "card_count": len(cards),
        "digital": False,
        "foil_only": False,
        "nonfoil_only": False,
        "scryfall_uri": f"/set/{set_code_final}",
        "uri": f"/api/sets/{set_code_final}",
        "search_uri": f"/api/search?q=set:{set_code_final}",
        "icon_svg_uri": None,
    }

    output_payload = {
        "meta": {
            "source_xml": str(xml_path),
            "images_root": str(images_root),
            "generated_at": datetime.now(UTC).isoformat(),
            "schema": "scryfall-like-local-v1",
        },
        "set": set_record,
        "sets": [set_record],
        "cards": cards,
        "cards_list": {
            "object": "list",
            "has_more": False,
            "next_page": None,
            "total_cards": len(cards),
            "data": cards,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert MSE XML set export into Scryfall-like local card JSON.")
    parser.add_argument(
        "--xml",
        default="data/Magic the Gathering/Sets/Honkai: Star Rail/setInfo.xml",
        help="Path to the XML set export file.",
    )
    parser.add_argument(
        "--images-root",
        default="data/Magic the Gathering/Sets/Honkai: Star Rail",
        help="Root folder where image paths from XML are resolved.",
    )
    parser.add_argument(
        "--out",
        default="data/Magic the Gathering/Sets/Honkai: Star Rail/scryfall_like_cards.json",
        help="Output JSON file path.",
    )
    parser.add_argument(
        "--set-code",
        default="",
        help="Optional explicit set code override (for example: hsr).",
    )
    parser.add_argument(
        "--image-prefix",
        default="",
        help="Optional URL/path prefix prepended to each image_file value.",
    )
    parser.add_argument(
        "--released-at",
        default="",
        help="Optional release date in YYYY-MM-DD format.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    payload = convert_set_xml_to_scryfall_like(
        xml_path=Path(args.xml),
        images_root=Path(args.images_root),
        output_path=Path(args.out),
        set_code=args.set_code or None,
        image_prefix=args.image_prefix,
        released_at=args.released_at,
    )

    print(
        "Converted",
        len(payload.get("cards", [])),
        "cards from",
        args.xml,
        "->",
        args.out,
    )


if __name__ == "__main__":
    main()
