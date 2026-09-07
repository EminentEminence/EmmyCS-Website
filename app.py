import json
import os
import re
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import abort, Flask, flash, redirect, render_template, request, session, url_for


DEFAULT_CONTENT = {
    "hero": {
        "name": "Your Name",
        "role": "Software Developer",
        "tagline": "I build performant, delightful software products.",
    },
    "skills": [
        "Python & Flask",
        "TypeScript",
        "API Design",
        "Cloud Deployments",
        "Automation",
    ],
    "projects": [
        {
            "slug": "realtime-team-dashboard",
            "title": "Realtime Team Dashboard",
            "summary": "A web dashboard that visualizes product metrics with live updates.",
            "stack": "Flask, Redis, WebSockets",
            "details": "Built for cross-functional product teams to monitor release health, conversion funnel metrics, and service latency trends in one place.",
            "images": [],
        },
        {
            "slug": "ci-health-bot",
            "title": "CI Health Bot",
            "summary": "An automation bot that reports failing pipelines and ownership details.",
            "stack": "Python, GitHub API, Docker",
            "details": "Created to shorten incident response time by posting failure context, likely owners, and historical build reliability in team channels.",
            "images": [],
        },
        {
            "slug": "personal-knowledge-search",
            "title": "Personal Knowledge Search",
            "summary": "Semantic search over local engineering notes and architecture docs.",
            "stack": "FastAPI, PostgreSQL, Embeddings",
            "details": "Designed as a private assistant for technical notes with vector search, metadata filters, and quick citation previews.",
            "images": [],
        },
    ],
    "hobbies": [
        {
            "name": "Photography",
            "description": "Street and nature photography focused on composition and light.",
        },
        {
            "name": "Coffee Craft",
            "description": "Dialing in pourover recipes and exploring single-origin beans.",
        },
        {
            "name": "Trail Hiking",
            "description": "Weekend hikes to reset and study map-based route planning.",
        },
    ],
}


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-secret-key")

    data_file = Path(app.root_path) / "data" / "content.json"

    def slugify(value: str) -> str:
        """Convert text into a URL-safe slug."""
        cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return cleaned or "project"

    def ensure_unique_slug(existing_projects: list[dict], requested_slug: str, skip_index: int | None = None) -> str:
        """Make sure each project slug is unique across all projects."""
        base_slug = slugify(requested_slug)
        used_slugs = {
            str(project.get("slug", "")).strip()
            for index, project in enumerate(existing_projects)
            if skip_index is None or index != skip_index
        }

        if base_slug not in used_slugs:
            return base_slug

        suffix = 2
        while f"{base_slug}-{suffix}" in used_slugs:
            suffix += 1
        return f"{base_slug}-{suffix}"

    def normalize_project(raw_project: dict, all_projects: list[dict], project_index: int) -> dict:
        """Normalize a project entry to include required detail-page fields."""
        title = str(raw_project.get("title", "Untitled Project")).strip() or "Untitled Project"
        summary = str(raw_project.get("summary", "")).strip()
        stack = str(raw_project.get("stack", "")).strip()

        raw_details = raw_project.get("details", summary)
        details = str(raw_details).strip() or summary

        raw_images = raw_project.get("images", [])
        if not isinstance(raw_images, list):
            raw_images = []
        images = [str(image).strip() for image in raw_images if str(image).strip()]

        requested_slug = str(raw_project.get("slug", "")).strip() or title
        slug = ensure_unique_slug(all_projects, requested_slug, skip_index=project_index)

        return {
            "slug": slug,
            "title": title,
            "summary": summary,
            "stack": stack,
            "details": details,
            "images": images,
        }

    def parse_images(raw_images: str) -> list[str]:
        """Parse newline-separated image URLs into a clean list."""
        return [line.strip() for line in raw_images.splitlines() if line.strip()]

    def normalize_content(raw: dict) -> dict:
        """Normalize loaded JSON content and backfill missing sections."""
        raw_projects = raw.get("projects", DEFAULT_CONTENT["projects"])
        if not isinstance(raw_projects, list):
            raw_projects = DEFAULT_CONTENT["projects"]

        projects = [
            normalize_project(raw_project, raw_projects, project_index)
            for project_index, raw_project in enumerate(raw_projects)
            if isinstance(raw_project, dict)
        ]

        hero = raw.get("hero", DEFAULT_CONTENT["hero"])
        if not isinstance(hero, dict):
            hero = DEFAULT_CONTENT["hero"]

        raw_skills = raw.get("skills", DEFAULT_CONTENT["skills"])
        if not isinstance(raw_skills, list):
            raw_skills = DEFAULT_CONTENT["skills"]
        skills = [str(skill).strip() for skill in raw_skills if str(skill).strip()]

        raw_hobbies = raw.get("hobbies", DEFAULT_CONTENT["hobbies"])
        if not isinstance(raw_hobbies, list):
            raw_hobbies = DEFAULT_CONTENT["hobbies"]
        hobbies = [
            {
                "name": str(hobby.get("name", "")).strip(),
                "description": str(hobby.get("description", "")).strip(),
            }
            for hobby in raw_hobbies
            if isinstance(hobby, dict)
            and str(hobby.get("name", "")).strip()
            and str(hobby.get("description", "")).strip()
        ]

        return {
            "hero": {
                "name": str(hero.get("name", DEFAULT_CONTENT["hero"]["name"]))
                .strip()
                or DEFAULT_CONTENT["hero"]["name"],
                "role": str(hero.get("role", DEFAULT_CONTENT["hero"]["role"]))
                .strip()
                or DEFAULT_CONTENT["hero"]["role"],
                "tagline": str(hero.get("tagline", DEFAULT_CONTENT["hero"]["tagline"]))
                .strip()
                or DEFAULT_CONTENT["hero"]["tagline"],
            },
            "skills": skills,
            "projects": projects,
            "hobbies": hobbies,
        }

    def load_content() -> dict:
        """Load site content from disk, creating a default file if missing."""
        if not data_file.exists():
            content = normalize_content(DEFAULT_CONTENT)
            save_content(content)
            return content

        with data_file.open("r", encoding="utf-8") as file:
            return normalize_content(json.load(file))

    def save_content(content: dict) -> None:
        """Persist site content to disk in JSON format."""
        data_file.parent.mkdir(parents=True, exist_ok=True)
        normalized = normalize_content(content)
        with data_file.open("w", encoding="utf-8") as file:
            json.dump(normalized, file, indent=2)

    def dev_password() -> str:
        """Read the developer page password from environment settings."""
        return os.environ.get("DEV_PAGE_PASSWORD", "change-this-password")

    def dev_only(view_func):
        """Protect a route so only authenticated dev users can access it."""

        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not session.get("dev_authenticated"):
                return redirect(url_for("dev_login"))
            return view_func(*args, **kwargs)

        return wrapped

    def parse_index(index_text: str) -> int | None:
        """Safely parse an integer index from form values."""
        try:
            return int(index_text)
        except (TypeError, ValueError):
            return None

    @app.context_processor
    def inject_current_year() -> dict[str, int]:
        """Provide the current year to all templates for footer rendering."""
        return {"current_year": datetime.now().year}

    @app.get("/")
    def home() -> str:
        """Render the portfolio homepage."""
        content = load_content()
        return render_template(
            "index.html",
            page_title="Software Developer | Portfolio",
            hero=content["hero"],
            skills=content["skills"],
            projects=content["projects"],
            hobbies=content["hobbies"],
        )

    @app.get("/projects/<slug>")
    def project_detail(slug: str) -> str:
        """Render a dedicated subpage for an individual project."""
        content = load_content()
        project = next((item for item in content["projects"] if item.get("slug") == slug), None)
        if project is None:
            abort(404)

        return render_template(
            "project_detail.html",
            page_title=f"{project['title']} | Project",
            project=project,
        )

    @app.route("/dev/login", methods=["GET", "POST"])
    def dev_login() -> str:
        """Handle authentication for the developer control panel."""
        if request.method == "POST":
            submitted_password = request.form.get("password", "")
            if submitted_password == dev_password():
                session["dev_authenticated"] = True
                flash("Signed in to developer dashboard.", "success")
                return redirect(url_for("dev_dashboard"))

            flash("Invalid password.", "error")

        return render_template("dev_login.html", page_title="Developer Login")

    @app.post("/dev/logout")
    @dev_only
    def dev_logout():
        """Clear dev session and return to the login page."""
        session.pop("dev_authenticated", None)
        flash("Signed out.", "success")
        return redirect(url_for("dev_login"))

    @app.get("/dev")
    @dev_only
    def dev_dashboard() -> str:
        """Render the protected dashboard for editing portfolio content."""
        return render_template(
            "dev_dashboard.html",
            page_title="Developer Dashboard",
            content=load_content(),
        )

    @app.post("/dev/projects")
    @dev_only
    def manage_projects():
        """Add, update, or delete project items in persistent content."""
        action = request.form.get("action")
        content = load_content()
        projects = content["projects"]

        if action == "add":
            title = request.form.get("title", "").strip()
            summary = request.form.get("summary", "").strip()
            stack = request.form.get("stack", "").strip()
            details = request.form.get("details", "").strip()
            slug_value = request.form.get("slug", "").strip()
            images = parse_images(request.form.get("images", ""))
            if title and summary and stack:
                projects.append(
                    {
                        "slug": ensure_unique_slug(projects, slug_value or title),
                        "title": title,
                        "summary": summary,
                        "stack": stack,
                        "details": details or summary,
                        "images": images,
                    }
                )
                flash("Project added.", "success")
            else:
                flash("Title, summary, and stack are required.", "error")

        if action == "update":
            index = parse_index(request.form.get("index"))
            title = request.form.get("title", "").strip()
            summary = request.form.get("summary", "").strip()
            stack = request.form.get("stack", "").strip()
            details = request.form.get("details", "").strip()
            slug_value = request.form.get("slug", "").strip()
            images = parse_images(request.form.get("images", ""))
            if index is not None and 0 <= index < len(projects) and title and summary and stack:
                projects[index] = {
                    "slug": ensure_unique_slug(projects, slug_value or title, skip_index=index),
                    "title": title,
                    "summary": summary,
                    "stack": stack,
                    "details": details or summary,
                    "images": images,
                }
                flash("Project updated.", "success")
            else:
                flash("Unable to update project.", "error")

        if action == "delete":
            index = parse_index(request.form.get("index"))
            if index is not None and 0 <= index < len(projects):
                projects.pop(index)
                flash("Project removed.", "success")
            else:
                flash("Unable to remove project.", "error")

        save_content(content)
        return redirect(url_for("dev_dashboard"))

    @app.post("/dev/skills")
    @dev_only
    def manage_skills():
        """Add, update, or delete skill items in persistent content."""
        action = request.form.get("action")
        content = load_content()
        skills = content["skills"]

        if action == "add":
            value = request.form.get("value", "").strip()
            if value:
                skills.append(value)
                flash("Skill added.", "success")
            else:
                flash("Skill value is required.", "error")

        if action == "update":
            index = parse_index(request.form.get("index"))
            value = request.form.get("value", "").strip()
            if index is not None and 0 <= index < len(skills) and value:
                skills[index] = value
                flash("Skill updated.", "success")
            else:
                flash("Unable to update skill.", "error")

        if action == "delete":
            index = parse_index(request.form.get("index"))
            if index is not None and 0 <= index < len(skills):
                skills.pop(index)
                flash("Skill removed.", "success")
            else:
                flash("Unable to remove skill.", "error")

        save_content(content)
        return redirect(url_for("dev_dashboard"))

    @app.post("/dev/hobbies")
    @dev_only
    def manage_hobbies():
        """Add, update, or delete hobby items in persistent content."""
        action = request.form.get("action")
        content = load_content()
        hobbies = content["hobbies"]

        if action == "add":
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            if name and description:
                hobbies.append({"name": name, "description": description})
                flash("Hobby added.", "success")
            else:
                flash("Hobby name and description are required.", "error")

        if action == "update":
            index = parse_index(request.form.get("index"))
            name = request.form.get("name", "").strip()
            description = request.form.get("description", "").strip()
            if index is not None and 0 <= index < len(hobbies) and name and description:
                hobbies[index] = {"name": name, "description": description}
                flash("Hobby updated.", "success")
            else:
                flash("Unable to update hobby.", "error")

        if action == "delete":
            index = parse_index(request.form.get("index"))
            if index is not None and 0 <= index < len(hobbies):
                hobbies.pop(index)
                flash("Hobby removed.", "success")
            else:
                flash("Unable to remove hobby.", "error")

        save_content(content)
        return redirect(url_for("dev_dashboard"))

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
