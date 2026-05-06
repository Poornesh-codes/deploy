"""
Priority order queue with state tracking.
Orders are prioritized by: priority level (high > normal > low),
then by timestamp (FIFO within same priority).
"""

import heapq
import logging
from collections import defaultdict
from typing import List, Optional, Dict

from .models import Order, OrderState, Priority

logger = logging.getLogger(__name__)


class OrderQueue:
    """
    Priority queue for orders with state tracking.
    
    Uses a min-heap where the sort key is:
    (-priority_value, timestamp, order_id) to achieve:
    - Higher priority orders come first
    - Same priority → earlier timestamp first (FIFO)
    - Tiebreaker on order_id for deterministic ordering
    """

    def __init__(self):
        self._heap: list = []
        self._orders: Dict[str, Order] = {}  # order_id -> Order
        self._by_state: Dict[OrderState, set] = defaultdict(set)
        self._removed: set = set()  # Lazy deletion markers

    def add(self, order: Order):
        """Add an order to the queue."""
        if order.order_id in self._orders:
            logger.warning(f"Duplicate order {order.order_id}, updating")
            self._removed.add(order.order_id)

        self._orders[order.order_id] = order
        self._by_state[order.state].add(order.order_id)

        # Push to heap: (-priority_value, timestamp, order_id)
        entry = (-order.priority.value, order.timestamp, order.order_id)
        heapq.heappush(self._heap, entry)

    def pop_highest_priority(self) -> Optional[Order]:
        """
        Pop the highest priority PENDING order.
        Returns None if no pending orders.
        """
        while self._heap:
            neg_prio, ts, order_id = self._heap[0]

            # Skip removed entries
            if order_id in self._removed:
                heapq.heappop(self._heap)
                self._removed.discard(order_id)
                continue

            # Check if order is still PENDING
            order = self._orders.get(order_id)
            if order is None or order.state != OrderState.PENDING:
                heapq.heappop(self._heap)
                continue

            heapq.heappop(self._heap)
            return order

        return None

    def peek_highest_priority(self) -> Optional[Order]:
        """Peek at the highest priority PENDING order without removing."""
        temp_removed = []
        result = None

        while self._heap:
            neg_prio, ts, order_id = self._heap[0]

            if order_id in self._removed:
                temp_removed.append(heapq.heappop(self._heap))
                self._removed.discard(order_id)
                continue

            order = self._orders.get(order_id)
            if order is None or order.state != OrderState.PENDING:
                temp_removed.append(heapq.heappop(self._heap))
                continue

            result = order
            break

        # Restore popped entries
        for entry in temp_removed:
            heapq.heappush(self._heap, entry)

        return result

    def update_state(self, order_id: str, new_state: OrderState):
        """Transition an order to a new state."""
        order = self._orders.get(order_id)
        if order is None:
            logger.warning(f"Order {order_id} not found in queue")
            return

        old_state = order.state
        self._by_state[old_state].discard(order_id)
        order.state = new_state
        self._by_state[new_state].add(order_id)
        logger.debug(f"Order {order_id}: {old_state.value} → {new_state.value}")

    def get_order(self, order_id: str) -> Optional[Order]:
        """Get order by ID."""
        return self._orders.get(order_id)

    def get_orders_by_state(self, state: OrderState) -> List[Order]:
        """Get all orders in a given state."""
        return [
            self._orders[oid] for oid in self._by_state.get(state, set())
            if oid in self._orders
        ]

    def get_pending_orders(self) -> List[Order]:
        """Get all pending orders sorted by priority then timestamp."""
        pending = self.get_orders_by_state(OrderState.PENDING)
        return sorted(pending, key=lambda o: (-o.priority.value, o.timestamp))

    @property
    def pending_count(self) -> int:
        return len(self._by_state.get(OrderState.PENDING, set()))

    @property
    def assigned_count(self) -> int:
        return len(self._by_state.get(OrderState.ASSIGNED, set()))

    @property
    def in_transit_count(self) -> int:
        return len(self._by_state.get(OrderState.IN_TRANSIT, set()))

    @property
    def delivered_count(self) -> int:
        return len(self._by_state.get(OrderState.DELIVERED, set()))

    @property
    def total_count(self) -> int:
        return len(self._orders)

    def get_state_summary(self) -> Dict[str, int]:
        """Get count of orders in each state."""
        return {
            state.value: len(ids)
            for state, ids in self._by_state.items()
        }
