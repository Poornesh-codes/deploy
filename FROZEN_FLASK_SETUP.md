# Frozen Flask Deployment - Quick Start

Your Flask app has been converted to **Frozen Flask** for deployment on GitHub Pages!

## What Changed?

✅ Added `frozen-flask>=1.0` to `requirements.txt`
✅ Created `freeze.py` script to generate static files
✅ Updated `app.py` with Frozen Flask configuration
✅ Created `.gitignore` for build artifacts

## Quick Deployment Steps

### Step 1: Install Updated Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Generate Static Site
```bash
python freeze.py
```
This creates a `build/` folder with all static files (HTML, JSON, CSS, JS).

### Step 3: Push to GitHub
```bash
git add .
git commit -m "Add Frozen Flask and build directory"
git push origin main
```

### Step 4: Enable GitHub Pages
1. Go to your GitHub repo settings
2. Navigate to **Pages** (in the left sidebar under "Code and automation")
3. Set **Source** to "Deploy from a branch"
4. Select **Branch: main, Folder: /build**
5. Click Save

Your site will be live at: `https://yourusername.github.io/repo-name`

## How It Works

- **dashboard.html** → Served as static HTML at `/`
- **api/metrics** → Cached as `api/metrics/index.json`
- **api/run** → Cached as `api/run/index.json`
- Dashboard JavaScript fetches static JSON files automatically

## Troubleshooting

| Problem | Solution |
|---------|----------|
| 404 on `/api/metrics` | Make sure `freeze.py` generated the files |
| Assets not loading | Check browser console for 404 errors |
| Page looks broken | Ensure GitHub Pages is enabled in Settings |
| Want to regenerate | Delete `build/` folder and run `python freeze.py` again |

## For Continuous Deployment

See [GITHUB_PAGES_SETUP.md](GITHUB_PAGES_SETUP.md) for GitHub Actions workflow to auto-deploy on every push.

---

**Your app is now ready for GitHub Pages! 🚀**
