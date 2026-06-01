# Worn11

Worn11 is a social collecting platform for football shirt collectors.

The project combines a Django REST API backend with a React frontend to support collector profiles, kit collections, social interactions, comments, and direct messaging around football shirts.

## What the Project Covers

Based on the current repository, Worn11 supports:

- Collector profiles with avatars, bios, social links, marketplace links, country, favorite team, preferred size, and contact email
- Personal kit collections with multiple photos per kit
- Kit metadata such as season, kit type, shirt technology, size, condition, player name, and player number
- Automated valuation with manual value override
- Explore sections for trending, most liked, latest, and for-sale kits
- User search
- Likes on kits
- Comments on kits, including one-level threaded replies and likes on comments
- Kit reporting flow
- Follow and unfollow between users
- Direct kit links such as `/profile/:username/kits/:kitId`
- Share flow from the kit modal
- Private conversations and unread message counts
- History browsing by league, team, and kit variants

## Tech Stack

### Backend

- Python
- Django 5
- Django REST Framework
- `dj-rest-auth`
- `django-allauth`
- `djangorestframework-simplejwt`
- Pillow
- `python-dotenv`

### Frontend

- React 19
- Vite
- React Router
- Axios
- Bootstrap 5
- Bootstrap Icons via CDN in `frontend/index.html`
- SweetAlert2
- Google OAuth via `@react-oauth/google`

### Data / Local Infrastructure

- SQLite is the current default Django database in `main/core/settings.py`
- A PostgreSQL Docker Compose service exists at the repository root, but it is not the backend default today

## Project Structure

```text
worn11/
├── README.md
├── docker-compose.yml          # Optional local PostgreSQL container
├── frontend/                   # React + Vite frontend
│   ├── package.json
│   ├── index.html
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       └── styles/
└── main/                       # Django backend
    ├── manage.py
    ├── requirements.txt
    ├── core/                   # Django project config
    ├── kits/                   # Main domain app
    ├── templates/
    ├── media/
    ├── .env
    └── venv/
```

## How the App Is Organized

### Backend

The backend is centered around the `kits` Django app.

Main backend areas:

- `main/kits/models.py`
  - Core domain models such as `Profile`, `Follow`, `Country`, `League`, `Team`, `Kit`, `UserKit`, `UserKitImage`
  - Social and moderation models such as `KitComment`, `KitCommentLike`, `KitReport`
  - Messaging models such as `Conversation` and `Message`
- `main/kits/serializers.py`
  - API serializers for kits, comments, reports, conversations, messages, user details, and profile data
- `main/kits/views.py`
  - Collection CRUD
  - Public kit detail
  - Explore feed
  - Comments, replies, likes, and deletes
  - Reporting
  - Follow and search
  - Messaging and unread counts
  - History-related endpoints
- `main/kits/views_auth.py`
  - Google login handoff for the frontend
- `main/kits/tests.py`
  - Current automated test coverage for the `kits` app

### Frontend

The frontend is a single-page React app with route-driven pages and shared UI components.

Main frontend areas:

- `frontend/src/App.jsx`
  - Router setup and top-level auth/unread message state
- `frontend/src/services/api.js`
  - Central Axios client and API helpers
- `frontend/src/pages/CollectionPage.jsx`
  - Explore page and user search
- `frontend/src/pages/ProfilePage.jsx`
  - Collector profile, follow/unfollow, collection display, profile stats, and message entry point
- `frontend/src/pages/KitDetailPage.jsx`
  - Direct kit route that opens the comments/media modal
- `frontend/src/pages/MessagesPage.jsx`
  - Conversations list and message thread UI
- `frontend/src/pages/HistoryPage.jsx`
  - League → team → kit browsing flow
- `frontend/src/pages/KitVariantsPage.jsx`
  - Variant browsing for a selected team/season/type
- `frontend/src/components/comments/`
  - Comment modal and reply UI
- `frontend/src/components/profile/`
  - Profile and kit card presentation
- `frontend/src/components/history/`
  - Museum/history browsing UI

## Frontend Routes

Current routes defined in `frontend/src/App.jsx`:

- `/` - Explore page
- `/my-collection` - Logged-in user's profile/collection view
- `/profile/:username` - Public profile page
- `/profile/:username/kits/:kitId` - Direct kit detail modal route
- `/messages` - Conversations list
- `/messages/:conversationId` - Specific conversation
- `/profile/edit` - Profile editing
- `/add-kit` - Add kit form
- `/edit-kit/:id` - Edit kit form
- `/history` - Kit museum browsing
- `/history/team/:teamId/variants` - Kit variants page
- `/groups` - Placeholder page at the moment

## API Areas

The main API surface under `/api/` currently includes:

- Authentication and current-user endpoints
- Collection CRUD for the logged-in user
- Public user collection and public kit detail
- Explore kits
- Kit likes
- Kit comments, replies, likes, and deletes
- Kit reporting
- Team search, user search, and user stats
- Follow/following/followers endpoints
- Conversations, messages, and unread counts
- League/team/history endpoints

The detailed URL patterns live in:

- `main/core/urls.py`
- `main/kits/urls.py`

## Local Development Setup

### Prerequisites

- Python 3
- Node.js and npm
- Optional: Docker and Docker Compose

### 1. Backend dependencies

The repository currently includes a local virtual environment at `main/venv`, and the rough project workflow assumes using it.

If that environment already exists:

```bash
cd main
source venv/bin/activate
pip install -r requirements.txt
```

If you prefer to recreate it:

```bash
cd main
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Frontend dependencies

```bash
cd frontend
npm install
```

### 3. Environment variables

The backend loads variables from:

```text
main/.env
```

Based on `main/core/settings.py`, the backend currently reads:

- `SECRET_KEY`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_SECRET`

If Google login is needed locally, those values must be set correctly.

## Running the Project

### Backend

```bash
cd main
source venv/bin/activate
python manage.py migrate
python manage.py runserver
```

The backend runs on Django's default development server:

```text
http://127.0.0.1:8000/
```

### Frontend

```bash
cd frontend
npm run dev
```

The frontend API client is currently hardcoded to:

```text
http://127.0.0.1:8000/api
```

That value is defined in `frontend/src/services/api.js`.

## Database and Migrations

### Current default database

The current Django settings use SQLite:

- Database file: `main/db.sqlite3`
- Config source: `main/core/settings.py`

That means the standard local workflow today is:

```bash
cd main
source venv/bin/activate
python manage.py makemigrations
python manage.py migrate
```

### PostgreSQL Docker service

A PostgreSQL container definition exists at the repository root:

```bash
docker-compose up -d
```

Important:

- This Postgres service is present in the repo
- The backend is not currently configured to use it by default
- `main/core/settings.py` still points to SQLite
- `main/requirements.txt` also does not currently include a PostgreSQL driver

So treat the Docker Compose database as available infrastructure, not as the active default backend database configuration.

## Tests and Checks

### Backend

Run Django checks:

```bash
cd main
source venv/bin/activate
python manage.py check
```

Run the `kits` test suite:

```bash
cd main
source venv/bin/activate
python manage.py test kits
```

### Frontend

Build the production bundle:

```bash
cd frontend
npm run build
```

Optional lint command:

```bash
cd frontend
npm run lint
```

## Configuration Notes

Current configuration details worth knowing:

- Backend secrets are loaded from `main/.env`
- Django `DEBUG` is currently hardcoded to `True` in `main/core/settings.py`
- Django currently allows all CORS origins in local settings
- Frontend API base URL is hardcoded in `frontend/src/services/api.js`
- The Google OAuth client ID is currently hardcoded in `frontend/src/main.jsx`

These are useful to know before changing auth or local environment behavior.

## Development Workflow

Typical feature workflow:

```bash
git checkout main
git pull origin main
git checkout -b feature/my-feature

# make changes

git status
git diff
git add .
git commit -m "Describe change"
git push -u origin feature/my-feature
```

Before opening or merging a pull request:

- Run backend checks
- Run the relevant Django tests
- Run the frontend build
- Review the diff for accidental config or generated-file changes

## Working on Features Safely

For changes that touch product behavior, it helps to think in terms of backend + frontend + data flow:

1. Update the Django model, serializer, view, and tests if the change affects API behavior
2. Update `frontend/src/services/api.js` if the frontend request/response contract changes
3. Update the relevant page/components
4. Re-run checks and tests
5. Review direct-link flows such as profile kit routes, comments modal behavior, and messaging

Areas that are easy to regress in this project:

- Authentication and current-user loading
- Kit modal behavior
- Likes/comments interaction
- Messaging unread counts
- Profile collection rendering
- History browsing routes

## README Maintenance

Update this README when:

- setup commands change
- new environment variables are added
- frontend build or backend test commands change
- database configuration changes
- major backend modules or API areas are introduced
- major frontend pages or routes are added, removed, or renamed
- local development assumptions change
- authentication flow changes

## Current Gaps / Follow-Up Candidates

These are not promises or committed roadmap items, just practical follow-ups suggested by the current codebase:

- Move hardcoded frontend configuration into environment-based settings
- Wire Django to PostgreSQL if Postgres is intended to become the default local database
- Add broader frontend and integration test coverage
- Flesh out the current placeholder `Groups` page
- Document key API contracts in more detail if the project grows further
