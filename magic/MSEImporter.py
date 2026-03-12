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
    cardNames = []
    #Split the MSE data into lines
    lines = cardData.splitlines()

    #Remove top Line
    lines = lines[1:]

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

        if line[0] in cardNames:
            continue
        else:
            cardNames.append(line[0])

        card = Card()
        #Front fields
        card.set("name", line[0]) if length > 0 else None
        card.set("manaCost", line[1]) if length > 1 else None
        card.set("type", line[2]) if length > 2 else None
        card.set("rarity", line[3]) if length > 3 else None
        card.set("rulesText", line[4]) if length > 4 else None
        card.set("flavourText", line[5]) if length > 5 else None
        card.set("power", line[6]) if length > 6 else None
        card.set("toughness", line[7]) if length > 7 else None
        card.set("loyalty", line[8]) if length > 8 else None

        #Back fields
        card.set("name", line[13], side="back") if length > 13 else None
        card.set("manaCost", line[14], side="back") if length > 14 else None
        card.set("type", line[15], side="back") if length > 15 else None
        card.set("rulesText", line[16], side="back") if length > 16 else None
        card.set("flavourText", line[17], side="back") if length > 17 else None
        card.set("power", line[18], side="back") if length > 18 else None
        card.set("toughness", line[19], side="back") if length > 19 else None
        card.set("loyalty", line[20], side="back") if length > 20 else None
        cards.append(card)
        

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
                printing_card_name, artist = _parse_printing_file_name(printing_file)
                if (
                    printing_card_name
                    and _normalize_card_name(printing_card_name) == normalized_card_name
                ):
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

