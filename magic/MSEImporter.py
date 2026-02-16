from card import Card
from printings import printings, printing
import os
def MSEImport(MSECardData: str, cardSet: str) -> list[Card]:

    cardData = open(MSECardData, 'r', encoding="utf-8").read()

    #Create initial card object
    
    cards = []
    cardNames = []
    #Split the MSE data into lines
    lines = cardData.splitlines()

    #Remove top Line
    lines = lines[1:]

    availablePrintingsDefault = os.listdir(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "default")) if os.path.exists(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "default")) else []
    availablePrintingsBorderless = os.listdir(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "borderless")) if os.path.exists(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "borderless")) else []
    availablePrintingsExtendedArt = os.listdir(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "extended-art")) if os.path.exists(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "extended-art")) else []
    availablePrintingsPromo = os.listdir(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "promo")) if os.path.exists(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "promo")) else []
    availablePrintingsShowcase = os.listdir(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "showcase")) if os.path.exists(os.path.join(os.path.dirname(__file__), "cards\\sets\\"+cardSet, "printings", "showcase")) else []


    for line in lines:
        #Split the line into field and get the number of fields
        line = line.split("\t")
        length = len(line)

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
        card.set("power", line[5]) if length > 5 else None
        card.set("toughness", line[6]) if length > 6 else None
        card.set("loyalty", line[7]) if length > 7 else None

        #Back fields
        card.set("name", line[8], side="back") if length > 8 else None
        card.set("manaCost", line[9], side="back") if length > 9 else None
        card.set("type", line[10], side="back") if length > 10 else None
        card.set("rarity", line[11], side="back") if length > 11 else None
        card.set("rulesText", line[12], side="back") if length > 12 else None
        card.set("power", line[13], side="back") if length > 13 else None
        card.set("toughness", line[14], side="back") if length > 14 else None
        card.set("loyalty", line[15], side="back") if length > 15 else None
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

        cardName = card.name
        cardName = cardName.replace("'", "").replace(",", "").replace(":", "")
        for printingVar in availablePrintingsDefault:
            abs_path = os.path.join(cardSet, "printings", "default", printingVar)
            if printingVar.startswith(cardName):   
                cardPrintings.printings.append(printing(abs_path))
        for printingVar in availablePrintingsBorderless:
            abs_path = os.path.join(cardSet, "printings", "borderless", printingVar)
            if printingVar.startswith(cardName):
                cardPrintings.printings.append(printing(abs_path))
        for printingVar in availablePrintingsExtendedArt:
            abs_path = os.path.join(cardSet, "printings", "extended-art", printingVar)
            if printingVar.startswith(cardName):
                cardPrintings.printings.append(printing(abs_path))
        for printingVar in availablePrintingsPromo:
            abs_path = os.path.join(cardSet, "printings", "promo", printingVar)
            if printingVar.startswith(cardName):
                cardPrintings.printings.append(printing(abs_path))
        for printingVar in availablePrintingsShowcase:
            abs_path = os.path.join(cardSet, "printings", "showcase", printingVar)
            if printingVar.startswith(cardName):
                cardPrintings.printings.append(printing(abs_path))

        card.frontPrintings = cardPrintings

    return cards

