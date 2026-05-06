# GitHub Pages Deployment Guide

This Flask app has been converted to use Frozen Flask for static site generation on GitHub Pages.

## Local Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Test the Flask app locally:
```bash
python app.py
```
Then visit http://localhost:5000

## Generate Static Site

To create the static files for deployment:

```bash
python freeze.py
```

This generates a `build/` directory with all static HTML, CSS, and JavaScript files.

## Deploy to GitHub Pages

### Option 1: Using GitHub Actions (Recommended)

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Generate static site
        run: python freeze.py
      
      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./build
```

### Option 2: Manual Deployment

1. Generate the static site:
   ```bash
   python freeze.py
   ```

2. Create a `build` branch (if not using Actions):
   ```bash
   git checkout --orphan build
   git rm -rf .
   cp -r build/* .
   git add .
   git commit -m "Deploy static site"
   git push origin build
   ```

3. In GitHub repo settings:
   - Go to Settings > Pages
   - Source: Deploy from a branch
   - Branch: `build` / root directory

### Option 3: Deploy from docs folder

1. Rename the `build` directory to `docs`:
   ```bash
   mv build docs
   ```

2. Push to main branch

3. In GitHub Settings > Pages:
   - Source: Deploy from a branch
   - Branch: `main` / `/docs` folder

## Troubleshooting

- **API endpoints not working**: JSON responses are frozen as static files
- **Routes returning 404**: Check `freeze.py` to ensure all routes are registered
- **Assets not loading**: Ensure relative URLs are used in templates

## Notes

- The simulation results are cached and frozen into static HTML
- API responses (`/api/metrics`, `/api/run`) are converted to static JSON files
- Dashboard is fully static - no backend required on GitHub Pages
