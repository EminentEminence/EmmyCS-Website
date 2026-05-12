import os
from flask import Flask, jsonify, url_for, request
from MSEImporter import MSEImport
from card import Card


def _printing_folder_sort_key(folder_name: str) -> tuple[int, str]:
  lower_name = folder_name.lower()
  if lower_name == "standard":
    return (0, lower_name)
  if lower_name == "masterpiece":
    return (2, lower_name)
  return (1, lower_name)


def getCards(set: str) -> list[Card]:
    print(f"Getting cards for set: {set}")
    card_data_path = os.path.join(os.path.dirname(__file__), "cards/sets/"+set, "cardData.txt")
    cards = MSEImport(card_data_path, set)
    return cards

def navBar():
    return """<header>
      <nav class="navbar navbar-expand-lg navbar-light bg-light ">
        <button class="navbar-toggler ms-auto" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
          <span class="navbar-toggler-icon"></span>
        </button>
        <div class="collapse navbar-collapse justify-content-center" id="navbarNav">
          <ul class="navbar-nav ">
            <li class="nav-item">
              <a class="nav-link" href="/sets">Sets</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="">Secret Lairs (Coming Soon) </a>
            </li>
          </ul>
          <a class="navbar-brand emmy-brand-right" href="/">Home</a>
        </div>
      </nav>
    </header>"""

def pageHeader():
    return "<html>" \
    "   <head>" \
  "       <title>Emmy - Magic: The Gathering</title>" \
  "       <meta charset=\"utf-8\">" \
    "       <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css\">" \
    "       <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js\"></script>" \
    "<style>" + CSS() + "</style>" \
    "   </head>" \
    "<body>"
def CSS():
    return open(os.path.join(os.path.dirname(__file__), "../css/style.css"), 'r').read()
def getCardByName(cardName, set) -> Card:
  cards = getCards(set)
  for card in cards:
    if card.name == cardName:
      return card
  print("No card found")
  exit()
   

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "cards/sets/"),
    static_url_path="/static"
    )


@app.route("/sets")
def displayWeb():
    #HTML Base CODE
    code = pageHeader() + navBar() + \
    "<div class=\"container\">" \
    "<h1>Custom Sets</h1>" \
    ""
    for set in os.listdir(os.path.join(os.path.dirname(__file__), "cards/sets")):
        code += f"<a href=\"{url_for('displaySetView', set=set)}\"><h2>{set}</h2></a><div class=\"row row-cols-1 row-cols-md-2 row-cols-lg-3 row-cols-xl-4 row-cols-xxl-5\">"
        cards = getCards(set)
        cardCounter = 0
        for card in cards:
            if cardCounter >= 12:
                break
            printing = card.frontPrintings.printings[0] if card.frontPrintings.getLength() > 0 else None
            if printing is not None:
                cardCounter += 1
                code += f"<div class=\"col\"><a href=\"{url_for('displayCardView', set=set, cardName=card.name, printingPath=printing.image)}\"><img class=\"img-fluid h-100 m-1\" src=\"{url_for('static', filename=f'{printing.image}')}\"></a></div>"
        code += "</div><hr>"
    return code + "</body></html>"

@app.route("/cardview/<set>/<cardName>")
def displayCardView(set, cardName):
    card = getCardByName(cardName, set)

    printingPath = request.args.get("printingPath")
    selected_printing = None
    if printingPath:
      normalized_path = printingPath.replace("\\", "/")
      for current_printing in card.frontPrintings.printings:
        if current_printing.image == normalized_path:
          selected_printing = current_printing
          break

    if selected_printing is None and card.frontPrintings.printings:
      selected_printing = card.frontPrintings.printings[0]

    selected_image_path = selected_printing.image if selected_printing is not None else ""
    selected_artist = selected_printing.artist if selected_printing is not None else "Unknown"
    rules_text_html = card.rulesText.replace("\\n", "</p><p>").replace("\n", "</p><p>")
    flavour_text_html = card.flavourText.replace("\\n", "<br>").replace("\n", "<br>")

    printingsCode = ""
    for printing in card.frontPrintings.printings:
       artist_label = printing.artist if printing.artist else "Unknown"
       printingsCode = printingsCode + f"<div class=\"row border border-black border-1 mt-1\"><a href=\"{url_for('displayCardView', set=set, cardName=cardName, printingPath=printing.image)}\"><p>{printing.type} - {artist_label}</p></a></div>"

    code = pageHeader() + navBar() + f"""
      <html>
        <body>
          <main class=\"container m-5 row\">
            <section class=\"col-5\">
              <img class=\"img-fluid shadow\" src=\"{url_for('static', filename=f'{selected_image_path}')}\"> 
            </section>
            <section class=\"col-4 border-top border-bottom border-black border-5 \">
              <h3>{card.name}</h3>
              <hr>
              <h4>{card.type}</h4>
              <hr>
              <p>{rules_text_html}</p>
              <br>
              <p><i>{flavour_text_html}</i></p>
              <hr>
              <p>Illustrated By {selected_artist}</p>
            </section>
            <section class=\"col-3 border border-black border-2\">
              <div class=\"row\"><h3>Prints</h3></div>
            {printingsCode}
            </section>
          </main>
        </body>
      </html>
      """
    return code

@app.route("/cardview/<set>")
def displaySetView(set):
    code = pageHeader() + navBar() + \
    "<div class=\"container\">" \
    f"<h1>Custom Set: {set}</h1>"
    cards = getCards(set)

    def getCodeForCardsOfType(type) -> str:
      cardsCode = ""
      for card in cards:
        for printing in card.frontPrintings.printings:
          if printing.type == type:
            cardsCode += f"<a href=\"{url_for('displayCardView', set=set, cardName=card.name, printingPath=printing.image)}\"><img class=\"img-fluid h-100 m-1\" src=\"{url_for('static', filename=f'{printing.image}')}\"></a>"
      if cardsCode != "":
         return f"<br><hr><br><h3>---{type}---</h3><br><section class=\"row row-cols-1 row-cols-sm-2 row-cols-md-3 row-cols-lg-4 row-cols-xl-6 row-cols-xxl-8\">" + cardsCode + "</section>"
      return ""
    
    
    available_printing_types = []
    printings_path = os.path.join(
      os.path.dirname(__file__),
      "cards",
      "sets",
      set,
      "cardData-files",
      "images"
    )

    if os.path.isdir(printings_path):
      available_printing_types = [
        folder
        for folder in sorted(os.listdir(printings_path), key=_printing_folder_sort_key)
        if os.path.isdir(os.path.join(printings_path, folder))
      ]

    for printing_type in available_printing_types:
      code += getCodeForCardsOfType(printing_type)
    
    code += "</div><hr>"
    return code + "</body></html>"
app.run(debug=True)