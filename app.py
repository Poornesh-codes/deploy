import os
import sys
import json
from pathlib import Path
from flask import Flask, render_template, jsonify

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.data_loader import load_all_data
from src.simulator import Simulator

app = Flask(__name__)

# Frozen Flask configuration
app.config['FREEZER_DESTINATION'] = 'build'
app.config['FREEZER_RELATIVE_URLS'] = True
app.config['FREEZER_STATIC_IGNORE_404'] = True

project_dir = Path(__file__).parent
data_dir = project_dir / 'data' / 'raw'
config_path = project_dir / 'config.json'

# Global variable to cache simulation results
simulation_results = None

def run_simulation_if_needed():
    global simulation_results
    if simulation_results is not None:
        return simulation_results

    config = Config()
    config.load_from_json(str(config_path))
    
    try:
        orders, agents, graph = load_all_data(str(data_dir), config)
    except Exception as e:
        print(f"Error loading data: {e}")
        return {"error": str(e)}

    simulator = Simulator(graph, config)
    simulator.setup(orders, agents)
    simulation_results = simulator.run()
    return simulation_results

@app.route('/')
def dashboard():
    """Serve the web dashboard UI."""
    return render_template('dashboard.html')

@app.route('/api/run')
def api_run():
    """Run simulation and return full results."""
    # Force re-run if needed, or just return cached for now
    global simulation_results
    simulation_results = None # Force re-run
    results = run_simulation_if_needed()
    return jsonify(results)

@app.route('/api/metrics')
def api_metrics():
    """Return latest metrics JSON."""
    results = run_simulation_if_needed()
    if "error" in results:
        return jsonify(results), 500
    
    summary = {
        "simulation": results.get('simulation', {}),
        "metrics": results.get('metrics', {}),
        "workload": results.get('workload', {})
    }
    return jsonify(summary)

if __name__ == '__main__':
    # Initial run to pre-populate data
    run_simulation_if_needed()
    app.run(host='0.0.0.0', port=5000, debug=True)
