# Vehicle Evaluation Tool

A Django web app that evaluates and ranks vehicles from [Riyasewana](https://riyasewana.com) using user-defined filters and the **Groq LLM API** for scoring and recommendations.

## Features

- **User filters**: Max price (LKR), max mileage (km), min year, vehicle type (Hybrid / Non-Hybrid / Any).
- **Scraper**: Fetches listings from Riyasewana and filters by your criteria.
- **LLM scoring**: Each vehicle is scored by Groq on condition, features, ownership, maintenance, and value (1–10).
- **Ranking**: Top 10 by total score; Groq then picks the **Best 3** and explains why.
- **UI**: Simple dark-themed interface with a filter form and results table (Best 3 highlighted).

## Setup

1. **Create a virtual environment and install dependencies**

   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Set your Groq API key**

   Create a `.env` file in the project root with:

   ```
   GROQ_API_KEY=your_groq_api_key_here
   ```

   Get a key at [Groq Console](https://console.groq.com).

3. **Run migrations and start the server**

   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

4. Open **http://127.0.0.1:8000/** and use the form to run an evaluation.

## Flow

1. **User input** → Form: max price, max mileage, min year, vehicle type.
2. **Scraper** → Fetches vehicles from Riyasewana, applies filters, extracts name, price, mileage, year, description.
3. **LLM scoring** → Each vehicle (up to 20) is sent to Groq for scores (condition, features, ownership, maintenance, value).
4. **Ranking** → Top 10 by total score; Groq selects Best 3 and returns an explanation.
5. **Frontend** → Top 10 table with Best 3 highlighted and explanation shown.

## Deploy on Vercel

The project is set up to run on [Vercel](https://vercel.com) as a serverless Django app.

1. **Install Vercel CLI** (optional): `npm i -g vercel`
2. **Link and deploy**: From the project root run `vercel` and follow the prompts, or connect the repo in the Vercel dashboard.
3. **Environment variables** (set in Vercel project settings):
   - `GROQ_API_KEY` – required for LLM ranking.
   - `DJANGO_SECRET_KEY` – set a strong secret in production.
   - Optionally: `ALLOWED_HOSTS` (default includes `.vercel.app`), `DJANGO_DEBUG=False`.
4. **Build command** (in Vercel project settings):  
   `pip install -r requirements.txt && python manage.py collectstatic --noinput`  
   (If you don't use Django admin or app static files, you can use only `pip install -r requirements.txt`.)
5. **Limits**: Vercel serverless functions have a **time limit** (e.g. 10s on Hobby, 60s on Pro). A full run (scrape + LLM for many vehicles) can exceed this; use fewer filters or consider a plan with longer timeouts.

On Vercel, sessions use signed cookies (no database). Local development still uses SQLite and DB-backed sessions.

## Notes

- The scraper adapts to Riyasewana’s HTML; if the site structure changes, selectors in `evaluator/scraper.py` may need updating.
- Scoring is limited to 20 vehicles per run to keep API usage and response time reasonable.
- Results are stored in the session so you can open the results page again after a search.
