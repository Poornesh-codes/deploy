"""
Core dispatch logic: candidate generation, scoring, and assignment.
Implements multi-objective optimization with configurable weights.
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Tuple, Optional, Dict

from .models import Order, Agent, OrderState, Priority
from .graph import EnvironmentGraph
from .priority_queue import OrderQueue
from .agent_registry import AgentRegistry
from .config import Config

logger = logging.getLogger(__name__)


class Dispatcher:
    """
    Assigns delivery agents to orders using multi-objective scoring.
    
    Scoring considers:
    - Delivery time (travel + prep): lower is better
    - SLA urgency: orders closer to deadline get priority
    - Workload fairness: prefer agents with fewer cumulative assignments
    - Priority boost: high > normal > low
    - Agent rating: prefer higher-rated agents
    """

    def __init__(self, graph: EnvironmentGraph, queue: OrderQueue,
                 registry: AgentRegistry, config: Config):
        self.graph = graph
        self.queue = queue
        self.registry = registry
        self.config = config
        self._assignment_log: List[Dict] = []

    def generate_candidates(self, order: Order) -> List[Tuple[Agent, float]]:
        """
        Generate feasible (agent, travel_time) pairs for an order.
        
        Filters:
        - Agent must have capacity (active_orders < 2)
        - Agent must have a valid path to order location
        
        Returns list of (agent, travel_time) tuples.
        """
        candidates = []
        available_agents = self.registry.get_available_agents()

        if not available_agents:
            logger.debug(f"No available agents for order {order.order_id}")
            return candidates

        for agent in available_agents:
            travel_time = self.graph.get_travel_time(
                agent.current_location, order.location
            )
            if travel_time is not None:
                candidates.append((agent, travel_time))
            else:
                logger.debug(
                    f"No path from agent {agent.agent_id} at {agent.current_location} "
                    f"to order {order.order_id} at {order.location}"
                )

        return candidates

    def score_candidate(self, agent: Agent, order: Order,
                        travel_time: float, current_time: datetime) -> float:
        """
        Score a candidate assignment. Higher score = better assignment.
        
        Components:
        1. Delivery time score: inversely proportional to (travel + prep)
        2. SLA urgency: higher score for orders closer to SLA deadline
        3. Workload fairness: lower assignments = higher score
        4. Priority boost: multiplier based on order priority
        5. Agent rating: normalized to [0, 1]
        """
        weights = self.config.weights
        priority_weights = self.config.priority_weights

        # 1. Delivery time score (lower time = higher score)
        total_delivery_time = travel_time + order.prep_time
        max_possible_time = 100.0  # normalize against reasonable max
        delivery_score = max(0, 1.0 - (total_delivery_time / max_possible_time))

        # 2. SLA urgency score (less time remaining = higher urgency = higher score)
        sla_deadline = order.timestamp + timedelta(minutes=order.sla_minutes)
        time_remaining = (sla_deadline - current_time).total_seconds() / 60.0
        time_until_delivery = total_delivery_time

        if time_remaining <= 0:
            # SLA already passed - maximum urgency
            sla_score = 1.0
            logger.warning(
                f"Order {order.order_id}: SLA already passed, assigning with urgency"
            )
        elif time_until_delivery >= time_remaining:
            # Will likely violate SLA - high urgency
            sla_score = 0.95
        else:
            # Margin ratio: how much of the SLA window is consumed
            sla_score = max(0, 1.0 - (time_remaining - time_until_delivery) / order.sla_minutes)

        # 3. Workload fairness score (fewer assignments = higher score)
        all_agents = self.registry.get_all_agents()
        max_assignments = max((a.cumulative_assignments for a in all_agents), default=1)
        if max_assignments > 0:
            fairness_score = 1.0 - (agent.cumulative_assignments / (max_assignments + 1))
        else:
            fairness_score = 1.0

        # 4. Priority boost
        priority_name = order.priority.name.lower()
        priority_multiplier = priority_weights.get(priority_name, 1.0)
        priority_score = priority_multiplier / 1.5  # normalize to ~[0, 1]

        # 5. Agent rating score (normalized to [0, 1])
        rating_score = agent.rating / 5.0

        # Weighted combination
        total_score = (
            weights['delivery_time'] * delivery_score +
            weights['sla_urgency'] * sla_score +
            weights['workload_fairness'] * fairness_score +
            weights['priority_boost'] * priority_score +
            weights['agent_rating'] * rating_score
        )

        return total_score

    def find_best_assignment(self, order: Order,
                              current_time: datetime) -> Optional[Tuple[Agent, float, float]]:
        """
        Find the best agent for an order.
        
        Returns (agent, score, travel_time) or None if no candidates.
        """
        start = time.time()

        candidates = self.generate_candidates(order)
        if not candidates:
            return None

        best_agent = None
        best_score = -1.0
        best_travel = 0.0

        for agent, travel_time in candidates:
            score = self.score_candidate(agent, order, travel_time, current_time)

            # Tiebreaker: prefer agent with lower ID for determinism
            if score > best_score or (
                score == best_score and best_agent and
                agent.agent_id < best_agent.agent_id
            ):
                best_score = score
                best_agent = agent
                best_travel = travel_time

        elapsed_ms = (time.time() - start) * 1000
        if elapsed_ms > 500:
            logger.warning(
                f"Assignment decision for {order.order_id} took {elapsed_ms:.1f}ms "
                f"(target: 500ms)"
            )

        return (best_agent, best_score, best_travel) if best_agent else None

    def assign_order(self, order: Order, agent: Agent,
                     travel_time: float, score: float,
                     current_time: datetime) -> bool:
        """
        Apply an assignment decision with atomic state updates.
        
        Updates:
        - Order state: PENDING → ASSIGNED
        - Agent: add to active_orders, update availability
        - Queue: update state tracking
        """
        # Validate preconditions
        if order.state != OrderState.PENDING:
            logger.warning(
                f"Cannot assign {order.order_id}: state is {order.state.value}, "
                f"expected PENDING"
            )
            return False

        if not agent.can_accept_order:
            logger.warning(
                f"Cannot assign to {agent.agent_id}: at max capacity"
            )
            return False

        # Apply assignment
        success = self.registry.assign_order_to_agent(agent.agent_id, order.order_id)
        if not success:
            return False

        self.queue.update_state(order.order_id, OrderState.ASSIGNED)
        order.assigned_agent = agent.agent_id
        order.assigned_at = current_time

        # Log assignment
        self._assignment_log.append({
            "order_id": order.order_id,
            "agent_id": agent.agent_id,
            "score": round(score, 4),
            "travel_time": round(travel_time, 2),
            "prep_time": order.prep_time,
            "priority": order.priority.name,
            "assigned_at": current_time.isoformat()
        })

        logger.info(
            f"Assigned {order.order_id} ({order.priority.name}) → "
            f"{agent.agent_id} | score={score:.3f} | "
            f"travel={travel_time:.1f}min | prep={order.prep_time}min"
        )

        return True

    def dispatch_pending_orders(self, current_time: datetime) -> int:
        """
        Attempt to assign all pending orders.
        Returns number of successful assignments.
        """
        assigned_count = 0
        pending = self.queue.get_pending_orders()

        for order in pending:
            if order.state != OrderState.PENDING:
                continue

            result = self.find_best_assignment(order, current_time)
            if result is None:
                logger.debug(
                    f"No agents available for {order.order_id}, "
                    f"keeping in queue (depth: {self.queue.pending_count})"
                )
                continue

            agent, score, travel_time = result
            if self.assign_order(order, agent, travel_time, score, current_time):
                assigned_count += 1

        if self.queue.pending_count > 10 and assigned_count == 0:
            logger.warning(
                f"Queue depth warning: {self.queue.pending_count} orders pending, no assignments made"
            )

        return assigned_count

    def try_assign_pending(self, current_time: datetime) -> int:
        """
        Called after a delivery completes to assign pending orders.
        Returns number of assignments made.
        """
        return self.dispatch_pending_orders(current_time)

    @property
    def assignment_log(self) -> List[Dict]:
        """Get the complete assignment log."""
        return self._assignment_log
