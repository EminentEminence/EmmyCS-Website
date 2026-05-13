import os
import html
from difflib import SequenceMatcher
from flask import Flask, jsonify, url_for, request, send_file
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
              <a class="nav-link" href="/search">Search</a>
            </li>
            <li class="nav-item">
              <a class="nav-link" href="">Secret Lairs (Coming Soon) </a>
            </li>
          </ul>
          <a class="navbar-brand emmy-brand-right" href="/">Home</a>
        </div>
      </nav>
    </header>"""

def pageHeader(style_file="style.css"):
    return "<html>" \
    "   <head>" \
  "       <title>Emmy - Magic: The Gathering</title>" \
  "       <meta charset=\"utf-8\">" \
  "       <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" \
    "       <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css\">" \
    "       <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js\"></script>" \
    "<style>" + CSS(style_file) + "</style>" \
    "   </head>" \
    "<body>"
def CSS(style_file="style.css"):
    return open(os.path.join(os.path.dirname(__file__), "../css", style_file), 'r').read()


def _extract_primary_type(type_line: str | None) -> str:
    if not type_line:
      return "Unknown"
    normalized = type_line.replace("—", "-")
    main_part = normalized.split("-")[0].strip()
    words = [word for word in main_part.split() if word]
    if not words:
      return "Unknown"

    candidates = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Land", "Planeswalker", "Battle"]
    for candidate in candidates:
      if candidate in words:
        return candidate
    return words[-1]


def _extract_color_identity(mana_cost: str | None) -> str:
    if not mana_cost:
      return "Colorless"
    colors = []
    for symbol, name in [("W", "White"), ("U", "Blue"), ("B", "Black"), ("R", "Red"), ("G", "Green")]:
      if symbol in mana_cost.upper():
        colors.append(name)
    if len(colors) == 0:
      return "Colorless"
    if len(colors) == 1:
      return colors[0]
    return "Multicolor"


def _safe_mana_value(mana_cost: str | None) -> int:
    if not mana_cost:
      return 0
    cmc = 0
    temp_number = ""
    for char in mana_cost.upper():
      if char.isdigit():
        temp_number += char
        continue

      if temp_number:
        cmc += int(temp_number)
        temp_number = ""

      if char in ["W", "U", "B", "R", "G", "C", "X"]:
        cmc += 1
    if temp_number:
      cmc += int(temp_number)
    return cmc


def _rarity_sort_value(rarity: str | None) -> int:
    rarity_map = {
      "common": 0,
      "uncommon": 1,
      "rare": 2,
      "mythic": 3,
      "special": 4,
    }
    return rarity_map.get((rarity or "").lower(), 5)
    
def _normalize_rarity_group(rarity: str | None) -> str:
    lower = (rarity or "").lower()
    if "mythic" in lower:
      return "Mythic"
    if "rare" in lower:
      return "Rare"
    if "uncommon" in lower:
      return "Uncommon"
    if "common" in lower:
      return "Common"
    if "special" in lower:
      return "Special"
    return "Special"


def _first_printing(card: Card):
  return card.frontPrintings.printings[0] if card.frontPrintings.getLength() > 0 else None


def getAllCardsFirstPrinting() -> list[dict]:
  all_cards = []
  sets_path = os.path.join(os.path.dirname(__file__), "cards/sets")
  for set_name in sorted(os.listdir(sets_path)):
    cards = getCards(set_name)
    for card in cards:
      printing = _first_printing(card)
      if printing is None:
        continue
      all_cards.append({
        "set": set_name,
        "card": card,
        "printing": printing,
      })
  return all_cards


def _safe_int(value: str | None):
  if value is None or value == "":
    return None
  try:
    return int(value)
  except ValueError:
    return None


def _build_api_record(entry: dict) -> dict:
  card = entry["card"]
  set_name = entry["set"]
  printing = entry["printing"]

  card_name = card.name or "Unknown"
  type_line = card.type or "Unknown"
  primary_type = _extract_primary_type(type_line)
  rarity = card.rarity or "Special"
  rarity_group = _normalize_rarity_group(rarity)
  mana_cost = card.manaCost or "0"
  mana_value = _safe_mana_value(mana_cost)
  rules_text = (card.rulesText or "").replace("\\n", "\n")
  flavour_text = (card.flavourText or "").replace("\\n", "\n")
  power = card.power if card.power is not None else ""
  toughness = card.toughness if card.toughness is not None else ""
  color_identity = _extract_color_identity(mana_cost)
  artist = printing.artist if printing.artist else "Unknown"

  image_rel_path = printing.image.replace("\\", "/")
  image_abs_path = os.path.join(
    os.path.dirname(__file__),
    "cards",
    "sets",
    image_rel_path.replace("/", os.sep),
  )

  return {
    "set": set_name,
    "name": card_name,
    "type_line": type_line,
    "primary_type": primary_type,
    "rarity": rarity,
    "rarity_group": rarity_group,
    "mana_cost": mana_cost,
    "mana_value": mana_value,
    "rules_text": rules_text,
    "flavour_text": flavour_text,
    "power": power,
    "toughness": toughness,
    "color": color_identity,
    "artist": artist,
    "printing_type": printing.type,
    "card_url": url_for("displayCardView", set=set_name, cardName=card_name, printingPath=printing.image),
    "image_url": url_for("static", filename=f"{printing.image}"),
    "image_abs_path": image_abs_path,
  }


def _search_score(query: str, card_name: str) -> float:
  if not query:
    return 1.0

  q = query.lower().strip()
  name = card_name.lower().strip()

  if q == name:
    return 1000.0

  score = 0.0
  if name.startswith(q):
    score += 700.0
  if q in name:
    score += 500.0

  q_tokens = [token for token in q.split() if token]
  name_tokens = [token for token in name.split() if token]
  token_hits = sum(1 for token in q_tokens if token in name_tokens)
  if q_tokens:
    score += (token_hits / len(q_tokens)) * 200.0

  score += SequenceMatcher(None, q, name).ratio() * 100.0
  return score


def _filter_api_records(records: list[dict], args) -> list[dict]:
  query = (args.get("q") or args.get("query") or "").strip()
  set_filter = (args.get("set") or "").strip().lower()
  type_filter = (args.get("type") or "").strip().lower()
  rarity_filter = (args.get("rarity") or "").strip().lower()
  color_filter = (args.get("color") or "").strip().lower()
  printing_filter = (args.get("printing") or "").strip().lower()
  min_mv = _safe_int(args.get("min_mv"))
  max_mv = _safe_int(args.get("max_mv"))

  filtered = []
  for record in records:
    if set_filter and record["set"].lower() != set_filter:
      continue
    if type_filter and type_filter not in record["type_line"].lower() and type_filter != record["primary_type"].lower():
      continue
    if rarity_filter and rarity_filter != record["rarity_group"].lower() and rarity_filter not in record["rarity"].lower():
      continue
    if color_filter and color_filter != record["color"].lower():
      continue
    if printing_filter and printing_filter != (record["printing_type"] or "").lower():
      continue
    if min_mv is not None and record["mana_value"] < min_mv:
      continue
    if max_mv is not None and record["mana_value"] > max_mv:
      continue
    filtered.append(record)

  filtered.sort(
    key=lambda record: (
      _search_score(query, record["name"]),
      -record["mana_value"],
      -len(record["name"]),
    ),
    reverse=True,
  )
  return filtered


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


@app.route("/search")
def displaySearchView():
    all_cards = getAllCardsFirstPrinting()
    set_names = sorted({entry["set"] for entry in all_cards})

    card_items_html = ""
    for index, entry in enumerate(all_cards):
      card = entry["card"]
      set_name = entry["set"]
      printing = entry["printing"]

      card_name = card.name or "Unknown"
      type_line = card.type or "Unknown"
      primary_type = _extract_primary_type(type_line)
      rarity = card.rarity or "Special"
      rarity_group = _normalize_rarity_group(rarity)
      mana_cost = card.manaCost or "0"
      mana_value = _safe_mana_value(mana_cost)
      color_identity = _extract_color_identity(mana_cost)
      artist = printing.artist if printing.artist else "Unknown"
      card_url = url_for("displayCardView", set=set_name, cardName=card_name, printingPath=printing.image)
      image_url = url_for("static", filename=f"{printing.image}")

      rules_text = (card.rulesText or "").replace("\\n", " ").replace("\n", " ").strip()
      flavour_text = (card.flavourText or "").replace("\\n", " ").replace("\n", " ").strip()

      card_items_html += f"""
      <button
        type=\"button\"
        class=\"search-card\"
        data-index=\"{index}\"
        data-name=\"{html.escape(card_name)}\"
        data-set=\"{html.escape(set_name)}\"
        data-type=\"{html.escape(primary_type)}\"
        data-rarity=\"{html.escape(rarity)}\"
        data-raritygroup=\"{html.escape(rarity_group)}\"
        data-color=\"{html.escape(color_identity)}\"
        data-manavalue=\"{mana_value}\"
        data-cardurl=\"{html.escape(card_url)}\"
        data-image=\"{html.escape(image_url)}\"
        data-mana=\"{html.escape(mana_cost)}\"
        data-typeline=\"{html.escape(type_line)}\"
        data-rulestext=\"{html.escape(rules_text)}\"
        data-flavour=\"{html.escape(flavour_text)}\"
        data-artist=\"{html.escape(artist)}\"
      >
        <img src=\"{image_url}\" alt=\"{html.escape(card_name)}\">
        <span class=\"search-card-name\">{html.escape(card_name)}</span>
        <span class=\"search-card-meta\">{html.escape(set_name)} | {html.escape(rarity)}</span>
          <span class="search-card-type">{html.escape(type_line)}</span>
          <span class="search-card-extra">MV {mana_value} | {html.escape(color_identity)} | {html.escape(artist)}</span>
      </button>
      """

    set_options = "".join(
      f"<option value=\"{html.escape(set_name)}\">{html.escape(set_name)}</option>"
      for set_name in set_names
    )

    return pageHeader("newstyle.css") + navBar() + f"""
    <main class=\"search-page\">
      <section class=\"search-layout\">
        <aside class=\"detail-panel\">
          <a id=\"detailCardLink\" class=\"detail-image-link\" href=\"#\">
            <img id=\"detailImage\" class=\"detail-image\" src=\"\" alt=\"Selected card\">
          </a>
          <div class=\"detail-body\">
            <h2 id=\"detailName\">Select a card</h2>
            <p id=\"detailSet\" class=\"detail-sub\"></p>
            <p id=\"detailMana\"></p>
            <p id=\"detailType\"></p>
            <p id=\"detailRules\"></p>
            <p id=\"detailFlavour\" class=\"detail-flavour\"></p>
            <p id=\"detailArtist\" class=\"detail-sub\"></p>
          </div>
        </aside>

        <section class=\"results-panel\">
          <div class=\"controls-row\">
            <label>Sort
              <select id=\"sortSelect\">
                <option value=\"name_asc\">Name (A-Z)</option>
                <option value=\"name_desc\">Name (Z-A)</option>
                <option value=\"mv_asc\">Mana Value (Low-High)</option>
                <option value=\"mv_desc\">Mana Value (High-Low)</option>
                <option value=\"rarity_desc\">Rarity (High-Low)</option>
                <option value=\"rarity_asc\">Rarity (Low-High)</option>
              </select>
            </label>
            <label>Type
              <select id=\"typeFilter\">
                <option value=\"\">Any Type</option>
                <option value=\"Creature\">Creature</option>
                <option value=\"Instant\">Instant</option>
                <option value=\"Sorcery\">Sorcery</option>
                <option value=\"Artifact\">Artifact</option>
                <option value=\"Enchantment\">Enchantment</option>
                <option value=\"Land\">Land</option>
                <option value=\"Planeswalker\">Planeswalker</option>
                <option value=\"Battle\">Battle</option>
              </select>
            </label>
            <label>Rarity
              <select id=\"rarityFilter\">
                <option value=\"\">Any Rarity</option>
                <option value=\"Common\">Common</option>
                <option value=\"Uncommon\">Uncommon</option>
                <option value=\"Rare\">Rare</option>
                <option value=\"Mythic\">Mythic</option>
                <option value=\"Special\">Special</option>
              </select>
            </label>
            <label>Color
              <select id=\"colorFilter\">
                <option value=\"\">Any Color</option>
                <option value=\"White\">White</option>
                <option value=\"Blue\">Blue</option>
                <option value=\"Black\">Black</option>
                <option value=\"Red\">Red</option>
                <option value=\"Green\">Green</option>
                <option value=\"Colorless\">Colorless</option>
                <option value=\"Multicolor\">Multicolor</option>
              </select>
            </label>
            <label>Set
              <select id=\"setFilter\">
                <option value=\"\">All Sets</option>
                {set_options}
              </select>
            </label>
            <label>Search
              <input id=\"nameSearch\" type=\"search\" placeholder=\"Card name\">
            </label>
            <div class=\"view-toggle\" role=\"group\" aria-label=\"View mode\">
              <button type=\"button\" id=\"gridMode\" class=\"toggle-btn active\">Grid</button>
              <button type=\"button\" id=\"listMode\" class=\"toggle-btn\">List</button>
            </div>
          </div>

          <p id=\"resultsCount\" class=\"results-count\"></p>

          <div id=\"cardsContainer\" class=\"cards-grid\">
            {card_items_html}
          </div>
        </section>
      </section>
    </main>

    <script>
      const container = document.getElementById('cardsContainer');
      const cards = Array.from(container.querySelectorAll('.search-card'));
      const sortSelect = document.getElementById('sortSelect');
      const typeFilter = document.getElementById('typeFilter');
      const rarityFilter = document.getElementById('rarityFilter');
      const colorFilter = document.getElementById('colorFilter');
      const setFilter = document.getElementById('setFilter');
      const nameSearch = document.getElementById('nameSearch');
      const resultsCount = document.getElementById('resultsCount');
      const gridMode = document.getElementById('gridMode');
      const listMode = document.getElementById('listMode');

      const detailCardLink = document.getElementById('detailCardLink');
      const detailImage = document.getElementById('detailImage');
      const detailName = document.getElementById('detailName');
      const detailSet = document.getElementById('detailSet');
      const detailMana = document.getElementById('detailMana');
      const detailType = document.getElementById('detailType');
      const detailRules = document.getElementById('detailRules');
      const detailFlavour = document.getElementById('detailFlavour');
      const detailArtist = document.getElementById('detailArtist');

      function rarityRank(value) {{
        const map = {{ common: 0, uncommon: 1, rare: 2, mythic: 3, special: 4 }};
        return map[(value || '').toLowerCase()] ?? 5;
      }}

      function updateDetails(cardButton) {{
        if (!cardButton) return;
        detailImage.src = cardButton.dataset.image;
        detailCardLink.href = cardButton.dataset.cardurl;
        detailName.textContent = cardButton.dataset.name;
        detailSet.textContent = `${{cardButton.dataset.set}} | ${{cardButton.dataset.rarity}}`;
        detailMana.textContent = `Mana Cost: ${{cardButton.dataset.mana || '0'}} (${{cardButton.dataset.manavalue}})`;
        detailType.textContent = `Type: ${{cardButton.dataset.typeline || 'Unknown'}}`;
        detailRules.textContent = cardButton.dataset.rulestext ? `Rules: ${{cardButton.dataset.rulestext}}` : 'Rules: None';
        detailFlavour.textContent = cardButton.dataset.flavour ? `\"${{cardButton.dataset.flavour}}\"` : '';
        detailArtist.textContent = `Illustrated by ${{cardButton.dataset.artist || 'Unknown'}}`;
      }}

      function applyFiltersAndSort() {{
        const searchValue = nameSearch.value.trim().toLowerCase();

        const filtered = cards.filter((card) => {{
          const matchesName = card.dataset.name.toLowerCase().includes(searchValue);
          const matchesType = !typeFilter.value || card.dataset.type === typeFilter.value;
          const matchesRarity = !rarityFilter.value || card.dataset.raritygroup === rarityFilter.value;
          const matchesColor = !colorFilter.value || card.dataset.color === colorFilter.value;
          const matchesSet = !setFilter.value || card.dataset.set === setFilter.value;
          return matchesName && matchesType && matchesRarity && matchesColor && matchesSet;
        }});

        const sortMode = sortSelect.value;
        filtered.sort((a, b) => {{
          if (sortMode === 'name_asc') return a.dataset.name.localeCompare(b.dataset.name);
          if (sortMode === 'name_desc') return b.dataset.name.localeCompare(a.dataset.name);
          if (sortMode === 'mv_asc') return Number(a.dataset.manavalue) - Number(b.dataset.manavalue) || a.dataset.name.localeCompare(b.dataset.name);
          if (sortMode === 'mv_desc') return Number(b.dataset.manavalue) - Number(a.dataset.manavalue) || a.dataset.name.localeCompare(b.dataset.name);
          if (sortMode === 'rarity_asc') return rarityRank(a.dataset.raritygroup) - rarityRank(b.dataset.raritygroup) || a.dataset.name.localeCompare(b.dataset.name);
          if (sortMode === 'rarity_desc') return rarityRank(b.dataset.raritygroup) - rarityRank(a.dataset.raritygroup) || a.dataset.name.localeCompare(b.dataset.name);
          return 0;
        }});

        cards.forEach((card) => card.style.display = 'none');
        filtered.forEach((card) => {{
          card.style.display = '';
          container.appendChild(card);
        }});

        resultsCount.textContent = `${{filtered.length}} card${{filtered.length === 1 ? '' : 's'}} shown`;

        const activeCard = container.querySelector('.search-card.active');
        if (!activeCard || activeCard.style.display === 'none') {{
          cards.forEach((card) => card.classList.remove('active'));
          if (filtered.length > 0) {{
            filtered[0].classList.add('active');
            updateDetails(filtered[0]);
          }} else {{
            detailImage.src = '';
            detailCardLink.href = '#';
            detailName.textContent = 'No card found';
            detailSet.textContent = '';
            detailMana.textContent = '';
            detailType.textContent = '';
            detailRules.textContent = '';
            detailFlavour.textContent = '';
            detailArtist.textContent = '';
          }}
        }}
      }}

      cards.forEach((card) => {{
        card.addEventListener('click', () => {{
          cards.forEach((item) => item.classList.remove('active'));
          card.classList.add('active');
          updateDetails(card);
        }});
      }});

      [sortSelect, typeFilter, rarityFilter, colorFilter, setFilter, nameSearch].forEach((input) => {{
        input.addEventListener('input', applyFiltersAndSort);
        input.addEventListener('change', applyFiltersAndSort);
      }});

      gridMode.addEventListener('click', () => {{
        container.classList.remove('cards-list');
        container.classList.add('cards-grid');
        gridMode.classList.add('active');
        listMode.classList.remove('active');
      }});

      listMode.addEventListener('click', () => {{
        container.classList.remove('cards-grid');
        container.classList.add('cards-list');
        listMode.classList.add('active');
        gridMode.classList.remove('active');
      }});

      applyFiltersAndSort();
    </script>
    </body></html>
    """


@app.route("/api")
def displayApiSummary():
    return pageHeader() + navBar() + """
    <main class="container py-4">
      <h1>Magic Card API</h1>
      <p>This API searches across all card sets and returns the best matching card image.</p>
      <hr>
      <h2>Endpoint</h2>
      <p><b>GET /api/search</b></p>
      <h2>Required Query Parameter</h2>
      <ul>
        <li><b>q</b> (or <b>query</b>): card name text to search for.</li>
      </ul>
      <h2>Optional Filters</h2>
      <ul>
        <li><b>set</b>: exact set name.</li>
        <li><b>type</b>: matches card type line (example: Creature, Instant).</li>
        <li><b>rarity</b>: Common, Uncommon, Rare, Mythic, Special.</li>
        <li><b>color</b>: White, Blue, Black, Red, Green, Colorless, Multicolor.</li>
        <li><b>printing</b>: printing type name (example: Standard, Borderless).</li>
        <li><b>min_mv</b>: minimum mana value.</li>
        <li><b>max_mv</b>: maximum mana value.</li>
        <li><b>format</b>: image (default) or json.</li>
      </ul>
      <h2>Examples</h2>
      <p><a href="/api/search?q=Gojo">/api/search?q=Gojo</a></p>
      <p><a href="/api/search?q=Dragon&type=Creature&rarity=Rare&format=json">/api/search?q=Dragon&type=Creature&rarity=Rare&format=json</a></p>
      <p><a href="/api/search?q=Knight&set=Deadlock&color=White&min_mv=1&max_mv=4">/api/search?q=Knight&set=Deadlock&color=White&min_mv=1&max_mv=4</a></p>
      <hr>
      <p>If no card matches, the API returns HTTP 404 with JSON error details.</p>
    </main>
    </body></html>
    """


@app.route("/api/search")
def apiSearchCardImage():
    query = (request.args.get("q") or request.args.get("query") or "").strip()
    if query == "":
      return jsonify({
        "error": "Missing required query parameter 'q' (or 'query').",
        "example": "/api/search?q=Lightning",
      }), 400

    all_entries = getAllCardsFirstPrinting()
    records = [_build_api_record(entry) for entry in all_entries]
    filtered = _filter_api_records(records, request.args)

    if len(filtered) == 0:
      return jsonify({
        "error": "No card matched the provided query and filters.",
        "query": query,
        "filters": {
          "set": request.args.get("set"),
          "type": request.args.get("type"),
          "rarity": request.args.get("rarity"),
          "color": request.args.get("color"),
          "printing": request.args.get("printing"),
          "min_mv": request.args.get("min_mv"),
          "max_mv": request.args.get("max_mv"),
        },
      }), 404

    best = filtered[0]
    response_format = (request.args.get("format") or "image").strip().lower()

    if response_format == "json":
      return jsonify({
        "query": query,
        "match": {
          "name": best["name"],
          "set": best["set"],
          "type_line": best["type_line"],
          "rarity": best["rarity"],
          "mana_cost": best["mana_cost"],
          "mana_value": best["mana_value"],
          "rules_text": best["rules_text"],
          "flavour_text": best["flavour_text"],
          "power": best["power"],
          "toughness": best["toughness"],
          "color": best["color"],
          "artist": best["artist"],
          "printing_type": best["printing_type"],
          "image_url": best["image_url"],
          "card_url": best["card_url"],
        },
      })

    return send_file(best["image_abs_path"])


if __name__ == "__main__":
  app.run(debug=True)