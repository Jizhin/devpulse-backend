# DevPulse AI

> AI-powered code review and developer analytics platform for engineering teams.

DevPulse connects to your GitHub or GitLab repositories and automatically reviews every Pull Request using Gemini AI — flagging security vulnerabilities, performance issues, logic errors, and bad practices. It also tracks developer analytics, repo health, and gives every engineer a quality score.

## Features

- **AI Code Reviews** — connects to GitHub/GitLab, select a PR, Gemini AI reviews it in seconds. Flags critical issues, warnings, and suggestions with code snippets and fix recommendations.
- **Re-Review** — developer updates their PR? Hit re-review and it re-runs the AI on the latest changes, updating the existing review instead of creating a new one.
- **Developer Leaderboard** — every developer gets a quality score (0–100) and grade (A+, A, B+...) based on issues found in their PRs. See who writes the cleanest code.
- **Developer Profile** — click any developer to see their full profile — commits, PRs, merged history, issue patterns, languages, all synced live from GitHub/GitLab.
- **Repository Analytics** — per-repo quality scores, issue breakdowns, PR stats.
- **Repo Scanner** — scans your entire codebase (not just PRs) for vulnerabilities, outdated dependencies, security holes across all files.
- **Vulnerability Scanner** — dedicated security scanning module.
- **Notifications** — real-time alerts for critical issues found in reviews.
- **GitHub + GitLab support** — works with both providers.

---

## Tech Stack

**Backend**
- Python / Django
- Django REST Framework
- SQLite (default) / PostgreSQL
- Google Gemini AI API
- GitHub API / GitLab API

**Frontend**
- React + Vite
- React Router
- Axios
- Custom design system (no UI library)

---

## Project Structure

```
devpulse-backend/
├── accounts/          # Auth — register, login, JWT
├── repositories/      # Connect GitHub/GitLab repos
├── pullrequests/      # Sync and manage PRs
├── reviews/           # AI code review engine
├── analytics/         # Developer and repo analytics
├── reposcanner/       # Full repo vulnerability scanner
├── vulnscanner/       # Security scanner
├── notifications/     # Notification system
├── core/              # Shared utilities
└── api/               # API configuration
```

---

## Getting Started

### Prerequisites
- Python 3.10+
- pip
- Google Gemini API key (free at https://aistudio.google.com)
- GitHub or GitLab account with a personal access token

### Installation

```bash
# Clone the repo
git clone https://github.com/YOURUSERNAME/devpulse-backend.git
cd devpulse-backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your keys

# Run migrations
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start server
python manage.py runserver
```

### Environment Variables

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
GEMINI_API_KEY=your-gemini-api-key
```

---

## Frontend

Frontend repo: [devpulse-frontend](https://github.com/YOURUSERNAME/devpulse-frontend)

```bash
git clone https://github.com/YOURUSERNAME/devpulse-frontend.git
cd devpulse-frontend
npm install
npm run dev
```

Set `VITE_API_URL=http://localhost:8000` in your `.env`.

---

## Contributing

This is a solo project and I'm actively looking for contributors who want to help build this into a real product.

**Areas where help is needed:**
- Frontend (React) — new features, UI improvements
- Backend (Django) — new integrations, performance
- AI/ML — improving review quality, prompt engineering
- DevOps — deployment, CI/CD setup
- Design — UI/UX improvements
- Testing — writing tests, finding bugs

**How to contribute:**
1. Fork the repo
2. Create a branch (`git checkout -b feature/your-feature`)
3. Make your changes
4. Open a Pull Request with a clear description

For bigger contributions or if you want to be a core collaborator, open an issue or reach out directly.

---

## Roadmap

- [ ] Webhook support for real-time PR detection
- [ ] Deploy to AWS / cloud
- [ ] Email digest of weekly code quality report
- [ ] Slack / Discord integration
- [ ] Support for Bitbucket
- [ ] PR review comments posted back to GitHub/GitLab
- [ ] Team management and roles
- [ ] Public API

---

## Status

Actively building. Core features are working. Not yet deployed — looking for contributors and early users.

---

## License

MIT License — free to use, modify, and distribute.

---

*Built solo. Looking for collaborators to make this a real product. If you find this interesting, open an issue or reach out.*
