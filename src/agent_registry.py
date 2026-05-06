"""
Agent Registry for managing delivery agent state.
Supports fast lookups by ID and availability status.
"""

import logging
from typing import List, Optional, Dict

from .models import Agent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Manages agent state including location, availability, 
    active orders, and cumulative assignments.
    """

    def __init__(self):
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent):
        """Register an agent in the registry."""
        if agent.agent_id in self._agents:
            logger.warning(f"Agent {agent.agent_id} already registered, updating")
        self._agents[agent.agent_id] = agent

    def register_all(self, agents: List[Agent]):
        """Register multiple agents."""
        for agent in agents:
            self.register(agent)
        logger.info(f"Registered {len(agents)} agents")

    def get(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def get_available_agents(self) -> List[Agent]:
        """Get all agents that can accept orders (active_orders < 2)."""
        return [a for a in self._agents.values() if a.can_accept_order]

    def get_all_agents(self) -> List[Agent]:
        """Get all registered agents."""
        return list(self._agents.values())

    def assign_order_to_agent(self, agent_id: str, order_id: str) -> bool:
        """
        Assign an order to an agent.
        Returns True if successful, False if agent can't accept.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            logger.error(f"Agent {agent_id} not found")
            return False

        if not agent.can_accept_order:
            logger.warning(f"Agent {agent_id} at max capacity, cannot assign {order_id}")
            return False

        agent.assign_order(order_id)
        logger.debug(
            f"Assigned {order_id} to {agent_id} "
            f"(active: {len(agent.active_orders)}, "
            f"cumulative: {agent.cumulative_assignments})"
        )
        return True

    def complete_order_for_agent(self, agent_id: str, order_id: str,
                                  new_location: tuple):
        """
        Complete an order: remove from active, update location.
        """
        agent = self._agents.get(agent_id)
        if agent is None:
            logger.error(f"Agent {agent_id} not found")
            return

        agent.complete_order(order_id)
        agent.current_location = new_location
        logger.debug(
            f"Agent {agent_id} completed {order_id}, "
            f"now at {new_location} "
            f"(active: {len(agent.active_orders)})"
        )

    def get_workload_stats(self) -> Dict:
        """Get workload distribution statistics."""
        agents = list(self._agents.values())
        if not agents:
            return {"count": 0}

        assignments = [a.cumulative_assignments for a in agents]
        n = len(assignments)
        mean = sum(assignments) / n
        variance = sum((x - mean) ** 2 for x in assignments) / n
        std_dev = variance ** 0.5

        return {
            "count": n,
            "total_assignments": sum(assignments),
            "mean": round(mean, 2),
            "variance": round(variance, 2),
            "std_dev": round(std_dev, 2),
            "min": min(assignments),
            "max": max(assignments),
            "range": max(assignments) - min(assignments),
            "per_agent": {a.agent_id: a.cumulative_assignments for a in agents}
        }

    @property
    def total_agents(self) -> int:
        return len(self._agents)

    @property
    def available_count(self) -> int:
        return len(self.get_available_agents())
