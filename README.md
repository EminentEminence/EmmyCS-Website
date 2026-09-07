# Flask Portfolio Website

Modern Flask-based personal website template for advertising software development work and side hobbies.

## Features
- Responsive modern layout
- Light and dark themes with a manual toggle
- Hero, projects, skills, and hobbies sections
- Password-protected developer dashboard for add/edit/delete content
- Dedicated per-project detail subpages
- Optional project image gallery support (managed in dev dashboard)
- Reusable base template structure

## Run Locally
1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the app:
   ```bash
   export DEV_PAGE_PASSWORD="your-strong-password"
   export FLASK_SECRET_KEY="replace-this-secret"
   flask --app app run --debug
   ```
4. Open the local URL shown by Flask.

## Developer Dashboard
- Visit `/dev/login` and sign in with `DEV_PAGE_PASSWORD`.
- Edit projects, skills, and hobbies from the dashboard UI.
- For each project, manage:
   - `slug` (used in `/projects/<slug>` URLs)
   - summary and detailed overview text
   - optional image URLs (one per line)
- Changes are persisted in `data/content.json`.

## Customize
- Replace placeholder name/role/tagline in `data/content.json`.
- Add or update projects, skills, and hobbies in `data/content.json` or from `/dev`.
- Adjust theme colors and spacing in `static/css/styles.css`.

## Temporary Card Search Prototype
- The Scryfall-style prototype lives in `tempApp.py`.
- Run it separately while layout work is in progress, then merge the route/service layer into `app.py` later.
