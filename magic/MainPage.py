from email import header
import sys
import os
from flask import Flask, jsonify, url_for, request
from MSEImporter import MSEImport
from card import Card


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
              <a class="nav-link" href="/professional/projects.html">Projects</a>
            </li>
            <!--<li class="nav-item">
              <a class="nav-link" href="/professional/experience.html">Experience</a>
            </li> -->
            <li class="nav-item">
              <a class="nav-link" href="/professional/qualifications.html">Qualifications</a>
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
    "       <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css\">" \
    "       <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js\"></script>" \
    "   </head>" \
    "<body>"

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
    printingPath = request.args.get("printingPath")
    return f"<html><body><h1>{cardName} - {set}</h1><img src=\"{url_for('static', filename=f'{printingPath}')}\"></body></html>"

@app.route("/cardview/<set>")
def displaySetView(set):
    code = pageHeader() + navBar() + \
    "<div class=\"container\">" \
    f"<h1>Custom Set: {set}</h1>"
    code += "<div class=\"row row-cols-1 row-cols-md-2 row-cols-lg-3 row-cols-xl-4 row-cols-xxl-5\">"
    cards = getCards(set)
    for card in cards:
        for printing in card.frontPrintings.printings:
            code += f"<div class=\"col\"><a href=\"{url_for('displayCardView', set=set, cardName=card.name, printingPath=printing.image)}\"><img class=\"img-fluid h-100 m-1\" src=\"{url_for('static', filename=f'{printing.image}')}\"></a></div>"
    code += "</div><hr>"
    return code + "</body></html>"
app.run(debug=True)