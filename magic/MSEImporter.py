from card import Card
from printings import printings, printing
import os


def _printing_folder_sort_key(folder_name: str) -> tuple[int, str]:
    lower_name = folder_name.lower()
    if lower_name == "standard":
        return (0, lower_name)
    if lower_name == "masterpiece":
        return (2, lower_name)
    return (1, lower_name)


def _normalize_card_name(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def _strip_duplicate_suffix(base_name: str) -> str:
    stem, maybe_number = base_name.rsplit("-", 1) if "-" in base_name else (base_name, "")
    if maybe_number.isdigit():
        return stem
    return base_name


def _parse_printing_file_name(file_name: str) -> tuple[str, str]:
    base_name, _ = os.path.splitext(file_name)
    parts = base_name.split("-")

    if len(parts) < 2:
        return "", ""

    # New exporter format: {cardname}-{artist}.png with optional -{n} suffix for duplicates.
    if parts[-1].isdigit() and len(parts) >= 3:
        artist = parts[-2].strip()
        card_name = "-".join(parts[:-2]).strip()
    else:
        artist = parts[-1].strip()
        card_name = "-".join(parts[:-1]).strip()

    if not card_name or not artist:
        return "", ""

    return card_name, artist


def MSEImport(MSECardData: str, cardSet: str) -> list[Card]:

    cardData = open(MSECardData, 'r', encoding="utf-8").read()

    #Create initial card object
    
    cards = []
    cardsByName = {}
    # Split MSE data into lines and strip optional metadata/header rows.
    lines = cardData.splitlines()

    if lines and lines[0].lstrip("\ufeff").startswith("Set: "):
        lines = lines[1:]

    if lines and lines[0].strip().lower().startswith("name ||"):
        lines = lines[1:]

    def _set_if_present(card: Card, fields: list[str], index: int, attribute: str, side: str = "front"):
        if index < len(fields) and fields[index] != "":
            card.set(attribute, fields[index], side=side)

    images_root = os.path.join(
        os.path.dirname(__file__), "cards", "sets", cardSet, "cardData-files", "images"
    )
    available_printings_by_folder = {}
    if os.path.isdir(images_root):
        for folder_name in sorted(os.listdir(images_root), key=_printing_folder_sort_key):
            folder_path = os.path.join(images_root, folder_name)
            if os.path.isdir(folder_path):
                available_printings_by_folder[folder_name] = sorted(os.listdir(folder_path))


    for line in lines:
        #Split the line into field and get the number of fields
        line = [field.strip() for field in line.split("||")]
        length = len(line)

        if length == 0:
            continue

        if not line[0] or line[0].startswith("."):
            continue

        card_name = line[0]
        is_new_card = card_name not in cardsByName

        if is_new_card:
            card = Card()
            cardsByName[card_name] = card
            cards.append(card)
        else:
            card = cardsByName[card_name]
        #Front fields
        _set_if_present(card, line, 0, "name")
        _set_if_present(card, line, 1, "manaCost")
        _set_if_present(card, line, 2, "type")
        _set_if_present(card, line, 3, "rarity")
        _set_if_present(card, line, 4, "rulesText")
        _set_if_present(card, line, 5, "flavourText")
        _set_if_present(card, line, 6, "power")
        _set_if_present(card, line, 7, "toughness")
        _set_if_present(card, line, 8, "loyalty")

        #Back fields
        _set_if_present(card, line, 13, "name", side="back")
        _set_if_present(card, line, 14, "manaCost", side="back")
        _set_if_present(card, line, 15, "type", side="back")
        _set_if_present(card, line, 16, "rulesText", side="back")
        _set_if_present(card, line, 17, "flavourText", side="back")
        _set_if_present(card, line, 18, "power", side="back")
        _set_if_present(card, line, 19, "toughness", side="back")
        _set_if_present(card, line, 20, "loyalty", side="back")
        # Printings are loaded from image files once per unique card.
        if not is_new_card:
            continue
        

        #get printings
        '''
        Folder Structure
        -Test Content
            -printings
                -default
                -borderless
                -extended-art
                -promo
                -showcase
        '''

        cardPrintings = printings()

        normalized_card_name = _normalize_card_name(card.name)
        for folder_name, folder_printings in available_printings_by_folder.items():
            for printing_file in folder_printings:
                base_name, _ = os.path.splitext(printing_file)
                base_name = _strip_duplicate_suffix(base_name)

                artist = ""
                matched = False

                # Prefer exact card-name prefix matching so artist names can contain hyphens.
                if base_name == card.name:
                    matched = True
                elif base_name.startswith(f"{card.name}-"):
                    artist = base_name[len(card.name) + 1 :].strip()
                    matched = True
                else:
                    printing_card_name, parsed_artist = _parse_printing_file_name(printing_file)
                    if (
                        printing_card_name
                        and _normalize_card_name(printing_card_name) == normalized_card_name
                    ):
                        artist = parsed_artist
                        matched = True

                if matched:
                    abs_path = os.path.join(
                        cardSet,
                        "cardData-files",
                        "images",
                        folder_name,
                        printing_file,
                    )
                    cardPrintings.printings.append(printing(abs_path, folder_name, artist))

        card.frontPrintings = cardPrintings

    return cards

