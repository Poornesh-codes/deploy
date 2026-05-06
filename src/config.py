"""
Configuration management for dispatch system.
Supports loading from JSON file with sensible defaults.
"""

import json
import csv
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Default configuration values
DEFAULT_CONFIG = {
    # Scoring weights (must sum to meaningful relative values)
    "weights": {
        "delivery_time": 0.30,     # Minimize travel + prep time
        "sla_urgency": 0.30,       # Prioritize orders close to SLA deadline
        "workload_fairness": 0.20, # Distribute work evenly across agents
        "priority_boost": 0.10,    # Boost high-priority orders
        "agent_rating": 0.10       # Prefer higher-rated agents
    },
    # Constraints
    "max_active_orders_per_agent": 2,
    "decision_latency_target_seconds": 5,
    "default_sla_minutes": 50,
    # Priority weights
    "priority_weights": {
        "high": 1.5,
        "normal": 1.0,
        "low": 0.8
    },
    # Performance
    "throughput_target_per_minute": 100,
    # Simulation
    "travel_speed_factor": 1.0  # Multiplier for travel time
}


class Config:
    """System configuration with file-based override support."""

    def __init__(self):
        self._config: Dict[str, Any] = dict(DEFAULT_CONFIG)

    def load_from_json(self, filepath: str):
        """Load configuration overrides from JSON file."""
        try:
            with open(filepath, 'r') as f:
                overrides = json.load(f)
            self._deep_update(self._config, overrides)
            logger.info(f"Loaded config overrides from {filepath}")
        except FileNotFoundError:
            logger.info(f"No config file found at {filepath}, using defaults")
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON in config file: {e}, using defaults")

    def load_constraints_csv(self, filepath: str):
        """Load constraints from the provided constraints.csv."""
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    constraint = row.get('constraint', '').strip()
                    value = row.get('value', '').strip()
                    if not constraint or not value:
                        continue
                    try:
                        if constraint == 'max_active_orders_per_agent':
                            self._config['max_active_orders_per_agent'] = int(value)
                        elif constraint == 'decision_latency_target_seconds':
                            self._config['decision_latency_target_seconds'] = float(value)
                        elif constraint == 'default_sla_minutes':
                            self._config['default_sla_minutes'] = float(value)
                        elif constraint.startswith('priority_weight_'):
                            priority = constraint.replace('priority_weight_', '')
                            self._config['priority_weights'][priority] = float(value)
                    except ValueError as e:
                        logger.warning(f"Invalid constraint value '{value}' for '{constraint}': {e}")
            logger.info(f"Loaded constraints from {filepath}")
        except FileNotFoundError:
            logger.info(f"No constraints file at {filepath}, using defaults")

    def _deep_update(self, base: dict, updates: dict):
        """Recursively update nested dicts."""
        for key, value in updates.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_update(base[key], value)
            else:
                base[key] = value

    def get(self, key: str, default=None):
        """Get a config value by key (supports dot notation)."""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            if value is None:
                return default
        return value

    @property
    def weights(self) -> Dict[str, float]:
        return self._config['weights']

    @property
    def max_active_orders(self) -> int:
        return self._config['max_active_orders_per_agent']

    @property
    def priority_weights(self) -> Dict[str, float]:
        return self._config['priority_weights']

    def to_dict(self) -> Dict[str, Any]:
        return dict(self._config)
