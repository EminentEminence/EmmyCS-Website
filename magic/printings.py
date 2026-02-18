

class printings:
    def __init__(self):
        self.printings = []

    def getLength(self):
        return len(self.printings)
    
    def listPrintings(self):
        for printing in self.printings:
            print(printing.image)


class printing:
    def __init__(self, address:str):
        self.image = address.replace("\\", "/")



