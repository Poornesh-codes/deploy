"""
Environment graph with shortest path computation.
Uses Floyd-Warshall for all-pairs shortest paths on the 10x10 grid.
"""

import csv
import math
import logging
from collections import defaultdict
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)


class EnvironmentGraph:
    """
    Weighted graph representing the delivery environment.
    Nodes are (x, y) grid locations.
    Edges have travel times with delay multipliers.
    """

    def __init__(self):
        self.adjacency: Dict[Tuple[int, int], list] = defaultdict(list)
        self.nodes: set = set()
        self.dist: Dict[Tuple[Tuple[int, int], Tuple[int, int]], float] = {}
        self._precomputed = False

    def add_edge(self, from_loc: Tuple[int, int], to_loc: Tuple[int, int],
                 distance: float, delay_multiplier: float = 1.0):
        """Add a bidirectional edge to the graph."""
        effective_distance = distance * delay_multiplier
        self.adjacency[from_loc].append((to_loc, effective_distance))
        self.adjacency[to_loc].append((from_loc, effective_distance))
        self.nodes.add(from_loc)
        self.nodes.add(to_loc)
        self._precomputed = False

    def load_from_csv(self, filepath: str) -> int:
        """
        Load environment edges from CSV file.
        Returns number of edges loaded.
        """
        edge_count = 0
        try:
            with open(filepath, 'r') as f:
                reader = csv.DictReader(f)
                for row_num, row in enumerate(reader, start=2):
                    try:
                        from_loc = (int(row['from_x']), int(row['from_y']))
                        to_loc = (int(row['to_x']), int(row['to_y']))
                        distance = float(row['distance_minutes'])
                        delay = float(row.get('delay_multiplier', 1.0))

                        if distance <= 0:
                            logger.warning(f"Row {row_num}: Invalid distance {distance}, skipping")
                            continue

                        self.add_edge(from_loc, to_loc, distance, delay)
                        edge_count += 1
                    except (KeyError, ValueError) as e:
                        logger.warning(f"Row {row_num}: Malformed edge data: {e}, skipping")
                        continue
        except FileNotFoundError:
            logger.error(f"Environment file not found: {filepath}")
            raise
        except Exception as e:
            logger.error(f"Error loading environment: {e}")
            raise

        logger.info(f"Loaded {edge_count} edges, {len(self.nodes)} nodes")
        return edge_count

    def precompute_shortest_paths(self):
        """
        Precompute all-pairs shortest paths using Floyd-Warshall.
        Optimal for small graphs (10x10 = 100 nodes).
        """
        nodes = sorted(self.nodes)
        n = len(nodes)
        node_idx = {node: i for i, node in enumerate(nodes)}

        # Initialize distance matrix
        INF = float('inf')
        dist_matrix = [[INF] * n for _ in range(n)]

        for i in range(n):
            dist_matrix[i][i] = 0.0

        # Fill direct edges
        for node, neighbors in self.adjacency.items():
            i = node_idx[node]
            for neighbor, weight in neighbors:
                if neighbor in node_idx:
                    j = node_idx[neighbor]
                    dist_matrix[i][j] = min(dist_matrix[i][j], weight)

        # Floyd-Warshall
        for k in range(n):
            for i in range(n):
                if dist_matrix[i][k] == INF:
                    continue
                for j in range(n):
                    if dist_matrix[k][j] == INF:
                        continue
                    new_dist = dist_matrix[i][k] + dist_matrix[k][j]
                    if new_dist < dist_matrix[i][j]:
                        dist_matrix[i][j] = new_dist

        # Store results in dict for O(1) lookup
        self.dist = {}
        for i, node_i in enumerate(nodes):
            for j, node_j in enumerate(nodes):
                if dist_matrix[i][j] < INF:
                    self.dist[(node_i, node_j)] = dist_matrix[i][j]

        self._precomputed = True
        logger.info(f"Precomputed shortest paths for {n} nodes")

    def get_travel_time(self, from_loc: Tuple[int, int],
                        to_loc: Tuple[int, int]) -> Optional[float]:
        """
        Get shortest travel time between two locations.
        Returns None if no path exists (disconnected).
        """
        if not self._precomputed:
            self.precompute_shortest_paths()

        if from_loc == to_loc:
            return 0.0

        return self.dist.get((from_loc, to_loc))

    def has_path(self, from_loc: Tuple[int, int],
                 to_loc: Tuple[int, int]) -> bool:
        """Check if a path exists between two locations."""
        travel_time = self.get_travel_time(from_loc, to_loc)
        return travel_time is not None

    def get_node_count(self) -> int:
        """Return number of nodes in graph."""
        return len(self.nodes)

    def get_edge_count(self) -> int:
        """Return number of edges (counting each direction)."""
        return sum(len(neighbors) for neighbors in self.adjacency.values())
