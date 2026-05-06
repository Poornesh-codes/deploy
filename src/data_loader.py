"""
Data loading and validation for CSV datasets.
Handles orders, agents, environment edges, and constraints.
Implements robust error handling with descriptive messages.
"""

import csv
import logging
from datetime import datetime
from typing import List, Tuple, Optional

from .models import Order, Agent, Priority, OrderState
from .graph import EnvironmentGraph
from .config import Config

logger = logging.getLogger(__name__)


def load_orders(filepath: str, default_sla: float = 50.0) -> List[Order]:
    """
    Load and validate orders from CSV.
    
    Expected columns: order_id, timestamp, location_x, location_y,
                      prep_time_minutes, priority, sla_minutes
    
    Skips invalid rows with warnings. Raises on missing file.
    """
    orders = []
    skipped = 0

    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)
            
            # Validate headers
            required = {'order_id', 'timestamp', 'location_x', 'location_y',
                       'prep_time_minutes', 'priority'}
            if reader.fieldnames is None:
                logger.error(f"Empty CSV file: {filepath}")
                return orders
            
            missing_headers = required - set(reader.fieldnames)
            if missing_headers:
                logger.error(f"Missing required columns in orders: {missing_headers}")
                return orders

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Validate order_id
                    order_id = row.get('order_id', '').strip()
                    if not order_id:
                        logger.warning(f"Row {row_num}: Missing order_id, skipping")
                        skipped += 1
                        continue

                    # Parse timestamp
                    ts_str = row.get('timestamp', '').strip()
                    if not ts_str:
                        logger.warning(f"Row {row_num} ({order_id}): Missing timestamp, skipping")
                        skipped += 1
                        continue
                    timestamp = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')

                    # Parse location
                    loc_x = int(row['location_x'])
                    loc_y = int(row['location_y'])
                    if not (0 <= loc_x <= 9 and 0 <= loc_y <= 9):
                        logger.warning(
                            f"Row {row_num} ({order_id}): Location ({loc_x},{loc_y}) "
                            f"out of grid range [0-9], skipping"
                        )
                        skipped += 1
                        continue

                    # Parse prep time
                    prep_time = float(row['prep_time_minutes'])
                    if prep_time < 0:
                        logger.warning(
                            f"Row {row_num} ({order_id}): Negative prep_time {prep_time}, skipping"
                        )
                        skipped += 1
                        continue

                    # Parse priority
                    priority_str = row.get('priority', 'normal').strip()
                    try:
                        priority = Priority.from_string(priority_str)
                    except ValueError:
                        logger.warning(
                            f"Row {row_num} ({order_id}): Invalid priority '{priority_str}', "
                            f"defaulting to NORMAL"
                        )
                        priority = Priority.NORMAL

                    # Parse SLA
                    sla_str = row.get('sla_minutes', '').strip()
                    sla_minutes = float(sla_str) if sla_str else default_sla
                    if sla_minutes <= 0:
                        logger.warning(
                            f"Row {row_num} ({order_id}): Invalid SLA {sla_minutes}, "
                            f"using default {default_sla}"
                        )
                        sla_minutes = default_sla

                    order = Order(
                        order_id=order_id,
                        timestamp=timestamp,
                        location=(loc_x, loc_y),
                        prep_time=prep_time,
                        priority=priority,
                        sla_minutes=sla_minutes
                    )
                    orders.append(order)

                except (KeyError, ValueError) as e:
                    logger.warning(f"Row {row_num}: Malformed order data: {e}, skipping")
                    skipped += 1
                    continue

    except FileNotFoundError:
        logger.error(f"Orders file not found: {filepath}")
        raise FileNotFoundError(f"Orders file not found: {filepath}")

    logger.info(f"Loaded {len(orders)} orders ({skipped} skipped) from {filepath}")
    return orders


def load_agents(filepath: str, graph: Optional[EnvironmentGraph] = None) -> List[Agent]:
    """
    Load and validate agents from CSV.
    
    Expected columns: agent_id, current_x, current_y, rating
    
    Validates location references exist in environment graph if provided.
    """
    agents = []
    skipped = 0

    try:
        with open(filepath, 'r') as f:
            reader = csv.DictReader(f)

            required = {'agent_id', 'current_x', 'current_y', 'rating'}
            if reader.fieldnames is None:
                logger.error(f"Empty CSV file: {filepath}")
                return agents

            missing_headers = required - set(reader.fieldnames)
            if missing_headers:
                logger.error(f"Missing required columns in agents: {missing_headers}")
                return agents

            for row_num, row in enumerate(reader, start=2):
                try:
                    agent_id = row.get('agent_id', '').strip()
                    if not agent_id:
                        logger.warning(f"Row {row_num}: Missing agent_id, skipping")
                        skipped += 1
                        continue

                    loc_x = int(row['current_x'])
                    loc_y = int(row['current_y'])
                    location = (loc_x, loc_y)

                    # Validate location exists in graph
                    if graph and location not in graph.nodes:
                        logger.warning(
                            f"Row {row_num} ({agent_id}): Location {location} "
                            f"not in environment graph, skipping"
                        )
                        skipped += 1
                        continue

                    rating = float(row['rating'])
                    if not (0.0 <= rating <= 5.0):
                        logger.warning(
                            f"Row {row_num} ({agent_id}): Rating {rating} out of range [0-5], "
                            f"clamping"
                        )
                        rating = max(0.0, min(5.0, rating))

                    agent = Agent(
                        agent_id=agent_id,
                        current_location=location,
                        original_location=location,
                        rating=rating
                    )
                    agents.append(agent)

                except (KeyError, ValueError) as e:
                    logger.warning(f"Row {row_num}: Malformed agent data: {e}, skipping")
                    skipped += 1
                    continue

    except FileNotFoundError:
        logger.error(f"Agents file not found: {filepath}")
        raise FileNotFoundError(f"Agents file not found: {filepath}")

    logger.info(f"Loaded {len(agents)} agents ({skipped} skipped) from {filepath}")
    return agents


def load_all_data(data_dir: str, config: Config) -> Tuple[List[Order], List[Agent], EnvironmentGraph]:
    """
    Load all data files from the given directory.
    Returns (orders, agents, graph).
    """
    import os

    # Load environment graph first (needed for agent validation)
    graph = EnvironmentGraph()
    env_path = os.path.join(data_dir, 'environment_edges.csv')
    graph.load_from_csv(env_path)
    graph.precompute_shortest_paths()

    # Load constraints
    constraints_path = os.path.join(data_dir, 'constraints.csv')
    config.load_constraints_csv(constraints_path)

    # Load orders
    orders_path = os.path.join(data_dir, 'orders.csv')
    default_sla = config.get('default_sla_minutes', 50.0)
    orders = load_orders(orders_path, default_sla=default_sla)

    # Load agents
    agents_path = os.path.join(data_dir, 'agents.csv')
    agents = load_agents(agents_path, graph=graph)

    return orders, agents, graph
