"""
CLI entry point for the Smart Delivery Dispatch System.
Loads data, runs simulation, outputs metrics.
"""

import os
import sys
import json
import time
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.data_loader import load_all_data
from src.simulator import Simulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def main():
    """Run the complete delivery dispatch simulation."""
    project_dir = Path(__file__).parent
    data_dir = project_dir / 'data' / 'raw'
    config_path = project_dir / 'config.json'
    output_dir = project_dir / 'output'

    # Create output directory
    output_dir.mkdir(exist_ok=True)

    print("\n" + "=" * 60)
    print("🚀 SMART DELIVERY DISPATCH SYSTEM")
    print("=" * 60 + "\n")

    # 1. Load configuration
    logger.info("Loading configuration...")
    config = Config()
    config.load_from_json(str(config_path))

    # 2. Load all data
    logger.info("Loading datasets...")
    start = time.time()
    try:
        orders, agents, graph = load_all_data(str(data_dir), config)
    except FileNotFoundError as e:
        logger.error(f"Data file missing: {e}")
        sys.exit(1)

    load_time = time.time() - start
    logger.info(f"Data loaded in {load_time:.2f}s")
    logger.info(f"  Orders: {len(orders)}")
    logger.info(f"  Agents: {len(agents)}")
    logger.info(f"  Graph nodes: {graph.get_node_count()}")

    # 3. Run simulation
    logger.info("\nStarting simulation...")
    simulator = Simulator(graph, config)
    simulator.setup(orders, agents)
    results = simulator.run()

    # 4. Output results
    print("\n" + simulator.metrics.get_human_readable_summary())

    # Workload fairness
    workload = results['workload']
    print("\n⚖️  WORKLOAD FAIRNESS")
    print(f"   Mean assignments: {workload['mean']}")
    print(f"   Std deviation:    {workload['std_dev']}")
    print(f"   Range:            {workload['min']} - {workload['max']} "
          f"(spread: {workload['range']})")
    print()

    # 5. Export metrics
    metrics_path = output_dir / 'metrics.json'
    results_json = json.dumps(results, indent=2, default=str)
    with open(metrics_path, 'w') as f:
        f.write(results_json)
    logger.info(f"Full results exported to {metrics_path}")

    # Also export summary metrics
    summary_path = output_dir / 'summary_metrics.json'
    summary = {
        "simulation_summary": results['simulation'],
        "metrics": results['metrics'],
        "workload_fairness": {
            "mean": workload['mean'],
            "std_dev": workload['std_dev'],
            "variance": workload['variance'],
            "min": workload['min'],
            "max": workload['max'],
            "range": workload['range']
        },
        "metadata": results['metadata']
    }
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    logger.info(f"Summary metrics exported to {summary_path}")

    print(f"\n✅ Results saved to {output_dir}/")
    print("=" * 60 + "\n")

    return results


if __name__ == '__main__':
    main()
