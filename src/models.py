"""
Data models for the Smart Delivery Dispatch System.
Defines Order, Agent, and state enumerations.
"""

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


class OrderState(Enum):
    """Order lifecycle states."""
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"


class Priority(Enum):
    """Order priority levels with numeric values for comparison."""
    HIGH = 3
    NORMAL = 2
    LOW = 1

    @classmethod
    def from_string(cls, s: str) -> "Priority":
        """Parse priority from string, case-insensitive."""
        mapping = {"high": cls.HIGH, "normal": cls.NORMAL, "low": cls.LOW}
        val = mapping.get(s.strip().lower())
        if val is None:
            raise ValueError(f"Invalid priority: '{s}'. Must be one of: high, normal, low")
        return val


@dataclass
class Order:
    """Represents a delivery order."""
    order_id: str
    timestamp: datetime
    location: tuple  # (x, y)
    prep_time: float  # minutes
    priority: Priority
    sla_minutes: float
    state: OrderState = OrderState.PENDING
    assigned_agent: Optional[str] = None
    assigned_at: Optional[datetime] = None
    in_transit_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    delivery_time: Optional[float] = None  # total minutes from order timestamp to delivery
    sla_violated: bool = False

    @property
    def sla_deadline(self) -> datetime:
        """Absolute SLA deadline based on order timestamp."""
        from datetime import timedelta
        return self.timestamp + timedelta(minutes=self.sla_minutes)


@dataclass
class Agent:
    """Represents a delivery agent."""
    agent_id: str
    current_location: tuple  # (x, y)
    original_location: tuple  # (x, y) - starting location
    rating: float
    availability: bool = True
    active_orders: List[str] = field(default_factory=list)
    cumulative_assignments: int = 0
    # Track when current deliveries will complete
    busy_until: Optional[datetime] = None

    @property
    def can_accept_order(self) -> bool:
        """Check if agent can accept another order (max 2)."""
        return len(self.active_orders) < 2

    def assign_order(self, order_id: str):
        """Add order to active list and update state."""
        self.active_orders.append(order_id)
        self.cumulative_assignments += 1
        if len(self.active_orders) >= 2:
            self.availability = False

    def complete_order(self, order_id: str):
        """Remove order from active list and update state."""
        if order_id in self.active_orders:
            self.active_orders.remove(order_id)
        if len(self.active_orders) < 2:
            self.availability = True
