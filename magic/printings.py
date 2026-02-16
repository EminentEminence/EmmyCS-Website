

class printings:
    def __init__(self):
        self.default = []
        self.borderless = []
        self.extendedArt = []
        self.promo = []
        self.showcase = []

    def getLength(self):
        return len(self.default) + len(self.borderless) + len(self.extendedArt) + len(self.promo) + len(self.showcase)
    
    def listPrintings(self):
        print("Default Printings:")
        for printing in self.default:
            print(printing.image)
        print("Borderless Printings:")
        for printing in self.borderless:
            print(printing.image)
        print("Extended Art Printings:")
        for printing in self.extendedArt:
            print(printing.image)
        print("Promo Printings:")
        for printing in self.promo:
            print(printing.image)
        print("Showcase Printings:")
        for printing in self.showcase:
            print(printing.image)


class printing:
    def __init__(self, address:str):
        self.image = address.replace("\\", "/")



