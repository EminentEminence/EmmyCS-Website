import sys
import os
from flask import Flask, jsonify, url_for
from MSEImporter import MSEImport

card_data_path = os.path.join(os.path.dirname(__file__), "TestContent", "cardData.txt")
cards = MSEImport(card_data_path)

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(__file__), "TestContent", "printings"),
    static_url_path="/static"
    )


@app.route("/")
def displayWeb():
    code = "<html><body><h1>Card Printings</h1>"
    for card in cards:
        code += f"<h2>{card.name}</h2>"
        for printing in card.frontPrintings.default:
            code += f'<img src="{url_for("static", filename=printing.image)}" style="width:200px; display:inline;"">'
        for printing in card.frontPrintings.borderless:
            code += f'<img src="{url_for("static", filename=printing.image)}" style="width:200px; display:inline;"">'
        for printing in card.frontPrintings.extendedArt:
            code += f'<img src="{url_for("static", filename=printing.image)}" style="width:200px; display:inline;"">'
        for printing in card.frontPrintings.promo:
            code += f'<img src="{url_for("static", filename=printing.image)}" style="width:200px; display:inline;"">'
        for printing in card.frontPrintings.showcase:
            code += f'<img src="{url_for("static", filename=printing.image)}" style="width:200px; display:inline;"">'
    return code + "</body></html>"



app.run()