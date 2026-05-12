import os
from functools import lru_cache
from flask import Flask


@lru_cache(maxsize=1)
def CSS():
  css_path = os.path.join(os.path.dirname(__file__), "../css/style.css")
  with open(css_path, "r", encoding="utf-8") as css_file:
    return css_file.read()

def pageHeader(title="EmmyCS - Professional"):
    return "<html>" \
    "   <head>" \
    f"       <title>{title}</title>" \
    "       <meta charset=\"utf-8\">" \
    "       <link rel=\"shortcut icon\" type=\"image/x-icon\" href=\"/css/Icon.jpg\">" \
    "       <link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css\">" \
    "       <script src=\"https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/js/bootstrap.min.js\"></script>" \
    "       <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">" \
    "       <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>" \
    "       <link href=\"https://fonts.googleapis.com/css2?family=Montserrat:ital,wght@0,100..900;1,100..900&display=swap\" rel=\"stylesheet\">" \
    "       <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">" \
    "       <style>" + CSS() + "</style>" \
    "   </head>" \
    "   <body>"

def navBar():
    return f"""<nav class="navbar navbar-expand-sm navbar-light bg-light sticky-top border-bottom border-dark shadow">
    <button class="navbar-toggler ms-auto" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav" aria-controls="navbarNav" aria-expanded="false" aria-label="Toggle navigation">
      <span class="navbar-toggler-icon"></span>
    </button>
    <div class="collapse navbar-collapse justify-content-center" id="navbarNav">
      <ul class="navbar-nav">
        <li class="nav-item">
            <a class="nav-link" href="/projects">Projects</a>
        </li>
        <li class="nav-item">
            <a class="nav-link" href="/qualifications">Qualifications</a>
        </li>
      </ul>
        <a class="navbar-brand emmy-brand-right font-monserrat" href="/">EmmyCS</a>
    </div>
  </nav>"""

def pageFooter():
    return """<footer class="container-fluid bg-dark text-light mt-4">
    <div class="row">
      <div class="col">
        <br>
        <h3>Footer</h3>
        <p>&#169; 2026 EmmyCS. All rights reserved.</p>
        <br>
      </div>
    </div>
  </footer>
  </body>
  </html>"""

app = Flask(__name__)

@app.route("/")
def displayIndex():
    code = pageHeader("EmmyCS - Professional") + navBar() + \
    """<br>
  <main class="container">
    <header>
      <div class="row">
        <img src="https://picsum.photos/1000/500" class="img-fluid" alt="Showcase Image">
      </div>
    </header>
    <br>
    <article class="row">
      <h2>About:</h2>
      <p>Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio atque consectetur officiis cumque
        laudantium culpa! Nobis fuga sequi, et alias dicta aperiam. Beatae nostrum eum minima quidem deleniti cumque
        voluptate.</p>
    </article>
    <br><hr><br>
    <div class="row">
        <h2>Recent News / Projects</h2>
    </div>
    <br><hr><br>
    <article class="row">
      <div class="col-sm-4">
        <img src="https://picsum.photos/1000" class="img-fluid" alt="Placeholder image">
      </div>
      <div class="col-8">
        <h2>Placeholder Title</h2>
        <p>Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio atque consectetur officiis cumque
          laudantium culpa! Nobis fuga sequi, et alias dicta aperiam. Beatae nostrum eum minima quidem deleniti cumque
          voluptate.</p>
      </div>
    </article>
    <br><hr><br>
    <article class="row">
      <div class="col-sm-4">
        <img src="https://picsum.photos/1000" class="img-fluid" alt="Placeholder image">
      </div>
      <div class="col-8">
        <h2>Placeholder Title</h2>
        <p>Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio atque consectetur officiis cumque
          laudantium culpa! Nobis fuga sequi, et alias dicta aperiam. Beatae nostrum eum minima quidem deleniti cumque
          voluptate.</p>
      </div>
    </article>
    <br><hr><br>
    <article class="row">
      <div class="col-sm-4">
        <img src="https://picsum.photos/1000" class="img-fluid" alt="Placeholder image">
      </div>
      <div class="col-8">
        <h2>Placeholder Title</h2>
        <p>Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio atque consectetur officiis cumque
          laudantium culpa! Nobis fuga sequi, et alias dicta aperiam. Beatae nostrum eum minima quidem deleniti cumque
          voluptate.</p>
      </div>
    </article>
    <br><hr><br>
    <article class="row">
      <div class="col-4">
        <img src="https://picsum.photos/1000" class="img-fluid" alt="Placeholder image">
      </div>
      <div class="col-8">
        <h2>Placeholder Title</h2>
        <p>Lorem ipsum dolor sit amet consectetur adipisicing elit. Distinctio atque consectetur officiis cumque
          laudantium culpa! Nobis fuga sequi, et alias dicta aperiam. Beatae nostrum eum minima quidem deleniti cumque
          voluptate.</p>
      </div>
    </article>
  </main>"""
    return code + pageFooter()

@app.route("/projects")
def displayProjects():
    code = pageHeader("EmmyCS - Professional | Projects") + navBar() + \
    """<main>
    <br>
    <header class="container">
      <h1>My Projects</h1>
      <p>Below are some of the projects I have worked on over the years. Highlighting the skills used and how involved i was in the project.</p>
    </header>
    <section class="container border border-black border-3 rounded-3 mt-4 p-3">
      <div class="row">
        <div class="col-sm-6">
          <img src="https://picsum.photos/500/500" class="img-fluid" alt="Placeholder image">
        </div>
        <div class="col-sm-6">
          <h2>EmmyCS Website</h2>
          <p>This is my own personal website, used for a variety of purposes such as the page you are seeing now and a
            platform to showcase some of my hobbies.</p>
          <p>It makes use of a standard html 5 structure with Bootstrap CSS Styling. It runs using a Cloudflare web
            tunnel to a private server which uses a python web server.</p>
          <p>It also takes advantage of python's flask library to create dynamic web pages.</p>
        </div>
      </div>
      <div class="row">
        <div class="col">
          <h4>Level of Involvement:</h4>
          <p>Solo Developer</p>
        </div>
        <div class="col">
          <h4>Skills Used:</h4>
          <p>Python, HTML/CSS, Bootstrap, Cloudflare web hosting.</p>
        </div>
      </div>
    </section>
    <section class="container border border-black border-3 rounded-3 mt-4 p-3">
      <div class="row">
        <div class="col-sm-6">
          <img src="https://picsum.photos/500/500" class="img-fluid" alt="Placeholder image">
        </div>
        <div class="col-sm-6">
          <h2>Project Name</h2>
          <p>Some content describing the project and maybe just a little Lorem ipsum dolor sit amet consectetur
            adipisicing elit. Distinctio vitae ducimus voluptatibus. At repudiandae aliquam neque autem consequatur
            ratione, quos, temporibus velit saepe adipisci eligendi aut, reiciendis non placeat eius.</p>
        </div>
      </div>
      <div class="row">
        <div class="col">
          <h4>Level of Involvement:</h4>
          <p>Contributer</p>
        </div>
        <div class="col">
          <h4>Skills Used:</h4>
          <p>Python, JavaScript, HTML/CSS</p>
        </div>
      </div>
    </section>"""
    return code + pageFooter()

@app.route("/qualifications")
def displayQualifications():
    code = pageHeader("EmmyCS - Professional | Qualifications") + navBar() + \
    """<main class="container">
    <br>
    <h1>Qualifications</h1>
    <p>Below is a list of my qualifications which I have earned, listing where I aquired them and the skills learnt as a part of the qualification.</p>
    <br>
    <section class="container border border-black border-3 rounded-3 mt-4 p-3">
      <h2>Dundee University</h2>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>Introduction to Generative AI</h4>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Basic Fundamental Understanding of Generative AI</li>
            <li>Knowledge of how to effectively use Generative AI tools</li>
            <li>Understanding of the ethical considerations and limitations of Generative AI</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>Introduction to Software Development</h4>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Basic programming skills in Java</li>
            <li>Understanding of Object Oriented Programming concepts</li>
          </ul>
        </div>
      </div>
    </section>
    <br>
    <hr><br>
    <section class="container border border-black border-3 rounded-3 mt-4 p-3">
      <h2>Dollar Academy</h2>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - ADV Higher Computer Science</h4>
          <h5> Grade: A</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - ADV Higher Mathematics </h4>
          <h5> Grade: B</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - ADV Higher Statistics</h4>
          <h5> Grade: B</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - Higher German</h4>
          <h5> Grade: A</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - Higher Engineering Science</h4>
          <h5> Grade: A</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - Higher Physics</h4>
          <h5> Grade: A</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - National 5 Economics</h4>
          <h5> Grade: A</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
      <br>
      <div class="row">
        <div class="col border-end border-black border-3">
          <h4>SQA - National 5 English </h4>
          <h5> Grade: A</h5>
        </div>
        <div class="col ps-5">
          <ul>
            <li>Placeholder A</li>
            <li>Placeholder B</li>
          </ul>
        </div>
      </div>
    </section>"""
    return code + pageFooter()

if __name__ == "__main__":
  app.run(debug=False, threaded=True, use_reloader=False)
