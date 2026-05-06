#!/usr/bin/env python3
"""
Freeze Flask app to static HTML for GitHub Pages deployment.
Run this script to generate the static site in the 'build' directory.
"""

import os
import sys
import json
from pathlib import Path
from flask_frozen import Freezer

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from app import app

def freeze_app():
    """Generate static files from Flask app."""
    # Configure app for freezing
    app.config['FREEZER_DESTINATION'] = 'build'
    app.config['FREEZER_RELATIVE_URLS'] = True
    app.config['FREEZER_REMOVE_EXTRA_FILES'] = False
    
    freezer = Freezer(app)
    
    @freezer.register_generator
    def url_generators():
        """Generate URLs for all routes that need to be frozen."""
        yield '/'
        # API endpoints are frozen as .json files
        yield '/api/metrics'
        yield '/api/run'
    
    print("🔨 Freezing Flask app to static HTML...")
    freezer.freeze()
    print("✅ Static site generated in 'build/' directory")
    print("\n📁 Generated files:")
    build_dir = Path('build')
    for file in sorted(build_dir.rglob('*')):
        if file.is_file():
            rel_path = file.relative_to(build_dir)
            size = file.stat().st_size
            print(f"   {rel_path} ({size} bytes)")
    
    print("\n📝 Next steps:")
    print("1. Commit the 'build' directory to your GitHub repo")
    print("2. In GitHub Settings > Pages:")
    print("   - Source: Deploy from a branch")
    print("   - Branch: main, folder: /build")
    print("   OR use GitHub Actions for automatic deployment")

if __name__ == '__main__':
    freeze_app()
