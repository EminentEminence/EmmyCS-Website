from printings import printings
class Card:
    #Initialization for the card class with default values
    def __init__(self):

        #Front Face
        self.name = "Empty Card"
        self.manaCost = "0"
        self.type = None
        self.rarity = "Special"
        self.rulesText = "No rules text."
        self.power = None
        self.toughness = None
        self.loyalty = None
        self.frontPrintings = printings()

        #Back Face (Optional)
        self.name2 = None
        self.manaCost2 = None
        self.type2 = None
        self.rarity2 = None
        self.rulesText2 = None
        self.power2 = None
        self.toughness2 = None
        self.loyalty2 = None

    
    #CMC Calculation
    def _calcCMC(self, manaCost: str) -> int:
        #Exit early for 0 cost cards
        if manaCost == "0":
            return 0
        #Declare 'cmc' and 'temp' variables.
        cmc = 0
        temp = ""
        
        #Iterate through each character in the mana cost string
        for char in manaCost:

            #Skip the '/' character used in hybrid mana costs then reduce the cmc by 1 since the next character will be counted as well
            if char == '/':
                cmc -= 1
                continue

            #Check if the character is a digit
            elif char.isdigit():
                cmc += int(char)

            #Check if the character is a valid mana symbol
            elif char.upper() in ['W','U','B','R','G','C']:
                    cmc += 1

            else:
                #Raise an error for invalid characters
                raise ValueError(f"Invalid character '{char}' in mana cost '{manaCost}'")
            
        #Return the calculated cmc
        return cmc

    def get(self,attribute: str,side="front") -> object:
        if not hasattr(self, attribute):
            raise AttributeError(f"'Card' object has no attribute '{attribute}'")
        elif attribute == "cmc":
            if side == "front":
                return Card._calcCMC(self, self.manaCost)
            elif side == "back":
                return Card._calcCMC(self, self.manaCost2) if self.manaCost2 is not None else None
            else:
                raise ValueError(f"Invalid side '{side}'")
        
        return getattr(self, attribute if side == "front" else attribute+"2")

    def set(self,attribute: str,value : object ,side="front"):
        if not hasattr(self, attribute):
            raise AttributeError(f"'Card' object has no attribute '{attribute}'")
        setattr(self, attribute if side == "front" else attribute+"2", value)
