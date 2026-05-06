"""
Delivery simulation engine.
Processes orders through the complete lifecycle:
PENDING → ASSIGNED → IN_TRANSIT → DELIVERED
"""

import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict

from .models import Order, Agent, OrderState, Priority
from .graph import EnvironmentGraph
from .priority_queue import OrderQueue
from .agent_registry import AgentRegistry
from .dispatcher import Dispatcher
from .metrics import MetricsTracker
from .config import Config

logger = logging.getLogger(__name__)


class DeliveryEvent:
    """Represents a scheduled delivery event."""

    def __init__(self, order_id: str, agent_id: str,
                 event_type: str, event_time: datetime,
                 destination: tuple = None):
        self.order_id = order_id
        self.agent_id = agent_id
        self.event_type = event_type  # 'in_transit' or 'delivered'
        self.event_time = event_time
        self.destination = destination

    def __lt__(self, other):
        return self.event_time < other.event_time


class Simulator:
    """
    Discrete event simulation for the delivery dispatch system.
    
    Processes orders chronologically, schedules assignments and deliveries,
    and tracks all metrics.
    """

    def __init__(self, graph: EnvironmentGraph, config: Config):
        self.graph = graph
        self.config = config
        self.queue = OrderQueue()
        self.registry = AgentRegistry()
        self.dispatcher = Dispatcher(graph, self.queue, self.registry, config)
        self.metrics = MetricsTracker()
        self.events: List[DeliveryEvent] = []
        self.simulation_log: List[Dict] = []
        self._start_time: Optional[float] = None
        self._orders_processed: int = 0

    def setup(self, orders: List[Order], agents: List[Agent]):
        """Initialize simulation with orders and agents."""
        self.registry.register_all(agents)

        # Sort orders by timestamp
        sorted_orders = sorted(orders, key=lambda o: o.timestamp)
        for order in sorted_orders:
            self.queue.add(order)

        logger.info(
            f"Simulation setup: {len(orders)} orders, "
            f"{len(agents)} agents"
        )

    def run(self) -> Dict:
        """
        Run the complete simulation.
        Returns comprehensive results dictionary.
        """
        self._start_time = time.time()
        logger.info("=" * 60)
        logger.info("SIMULATION STARTED")
        logger.info("=" * 60)

        # Get all orders sorted by timestamp
        all_orders = sorted(
            [self.queue.get_order(oid) for oid in self.queue._orders],
            key=lambda o: o.timestamp
        )

        if not all_orders:
            logger.warning("No orders to process")
            return self._build_results()

        # Collect all events: order arrivals + delivery events
        # Process in chronological order
        order_idx = 0
        sim_time = all_orders[0].timestamp

        while order_idx < len(all_orders) or self.events:
            # Determine next event time
            next_order_time = (
                all_orders[order_idx].timestamp
                if order_idx < len(all_orders)
                else datetime.max
            )
            next_event_time = (
                min(e.event_time for e in self.events)
                if self.events
                else datetime.max
            )

            if next_order_time == datetime.max and next_event_time == datetime.max:
                break

            # Process whichever comes first
            if next_order_time <= next_event_time:
                # Process new order arrival
                sim_time = next_order_time

                # Process all orders at this timestamp
                while (order_idx < len(all_orders) and
                       all_orders[order_idx].timestamp == sim_time):
                    order = all_orders[order_idx]
                    self._log_event(sim_time, "ORDER_ARRIVED", order.order_id,
                                   f"Priority: {order.priority.name}, "
                                   f"Location: {order.location}")
                    order_idx += 1

                # Try to assign pending orders
                assigned = self.dispatcher.dispatch_pending_orders(sim_time)
                if assigned > 0:
                    self._schedule_deliveries(sim_time)

            else:
                # Process delivery events
                sim_time = next_event_time
                self._process_events_at(sim_time)

                # After deliveries complete, try to assign pending orders
                assigned = self.dispatcher.try_assign_pending(sim_time)
                if assigned > 0:
                    self._schedule_deliveries(sim_time)

        # Handle any remaining pending orders
        if self.queue.pending_count > 0:
            logger.warning(
                f"{self.queue.pending_count} orders remain PENDING at end of simulation"
            )

        elapsed = time.time() - self._start_time
        logger.info("=" * 60)
        logger.info(f"SIMULATION COMPLETE in {elapsed:.2f}s")
        logger.info(f"Orders processed: {self._orders_processed}/{len(all_orders)}")
        logger.info("=" * 60)

        return self._build_results()

    def _schedule_deliveries(self, current_time: datetime):
        """Schedule delivery events for newly assigned orders."""
        assigned_orders = self.queue.get_orders_by_state(OrderState.ASSIGNED)

        for order in assigned_orders:
            # Check if we already have events scheduled for this order
            existing = [e for e in self.events if e.order_id == order.order_id]
            if existing:
                continue

            agent = self.registry.get(order.assigned_agent)
            if agent is None:
                continue

            # Calculate travel time
            travel_time = self.graph.get_travel_time(
                agent.current_location, order.location
            )
            if travel_time is None:
                travel_time = 30.0  # fallback for disconnected locations
                logger.warning(
                    f"No path for {order.order_id}, using default travel time"
                )

            # Effective start: cannot begin before the order was actually placed
            effective_start = max(current_time, order.timestamp)

            # Schedule IN_TRANSIT event (after prep time)
            prep_done = effective_start + timedelta(minutes=order.prep_time)
            self.events.append(DeliveryEvent(
                order.order_id, agent.agent_id,
                'in_transit', prep_done, order.location
            ))

            # Schedule DELIVERED event (after prep + travel)
            delivery_time_dt = prep_done + timedelta(minutes=travel_time)
            self.events.append(DeliveryEvent(
                order.order_id, agent.agent_id,
                'delivered', delivery_time_dt, order.location
            ))

            self._log_event(
                effective_start, "DELIVERY_SCHEDULED", order.order_id,
                f"Agent: {agent.agent_id}, "
                f"Prep: {order.prep_time}min, Travel: {travel_time:.1f}min, "
                f"ETA: {delivery_time_dt.strftime('%H:%M:%S')}"
            )

    def _process_events_at(self, event_time: datetime):
        """Process all delivery events at the given time."""
        due_events = [e for e in self.events if e.event_time <= event_time]
        remaining = [e for e in self.events if e.event_time > event_time]
        self.events = remaining

        # Sort: process in_transit before delivered, ordered by event time
        due_events.sort(key=lambda e: (e.event_time, e.event_type == 'delivered'))

        for event in due_events:
            order = self.queue.get_order(event.order_id)
            if order is None:
                continue

            # Use the event's own time for accurate delivery calculations
            if event.event_type == 'in_transit':
                self._handle_in_transit(order, event, event.event_time)
            elif event.event_type == 'delivered':
                self._handle_delivered(order, event, event.event_time)

    def _handle_in_transit(self, order: Order, event: DeliveryEvent,
                           current_time: datetime):
        """Transition order to IN_TRANSIT state."""
        if order.state != OrderState.ASSIGNED:
            return

        self.queue.update_state(order.order_id, OrderState.IN_TRANSIT)
        order.in_transit_at = current_time

        self._log_event(
            current_time, "IN_TRANSIT", order.order_id,
            f"Agent {event.agent_id} heading to {order.location}"
        )

    def _handle_delivered(self, order: Order, event: DeliveryEvent,
                          current_time: datetime):
        """
        Complete a delivery:
        - Transition to DELIVERED
        - Update agent location and availability
        - Calculate delivery time and SLA violation
        - Update metrics
        """
        if order.state not in (OrderState.ASSIGNED, OrderState.IN_TRANSIT):
            return

        # Update order state
        self.queue.update_state(order.order_id, OrderState.DELIVERED)
        order.delivered_at = current_time

        # Calculate delivery time (from order timestamp to delivery)
        delivery_minutes = (current_time - order.timestamp).total_seconds() / 60.0
        order.delivery_time = delivery_minutes

        # Check SLA
        sla_deadline = order.timestamp + timedelta(minutes=order.sla_minutes)
        if current_time > sla_deadline:
            order.sla_violated = True
            violation_minutes = (current_time - sla_deadline).total_seconds() / 60.0
            logger.warning(
                f"SLA VIOLATED for {order.order_id}: "
                f"delivered {violation_minutes:.1f}min late"
            )

        # Update agent
        self.registry.complete_order_for_agent(
            event.agent_id, order.order_id, event.destination
        )

        # Update metrics
        self.metrics.record_delivery(order)
        self._orders_processed += 1

        self._log_event(
            current_time, "DELIVERED", order.order_id,
            f"Agent: {event.agent_id}, "
            f"Time: {delivery_minutes:.1f}min, "
            f"SLA: {'VIOLATED' if order.sla_violated else 'OK'}"
        )

    def _log_event(self, sim_time: datetime, event_type: str,
                   order_id: str, details: str):
        """Log a simulation event."""
        self.simulation_log.append({
            "time": sim_time.strftime('%Y-%m-%d %H:%M:%S'),
            "event": event_type,
            "order_id": order_id,
            "details": details
        })

    def _build_results(self) -> Dict:
        """Build comprehensive results dictionary."""
        elapsed = time.time() - self._start_time if self._start_time else 0

        results = {
            "simulation": {
                "total_orders": self.queue.total_count,
                "orders_delivered": self.queue.delivered_count,
                "orders_pending": self.queue.pending_count,
                "orders_assigned": self.queue.assigned_count,
                "orders_in_transit": self.queue.in_transit_count,
                "total_agents": self.registry.total_agents,
                "simulation_time_seconds": round(elapsed, 3),
                "order_states": self.queue.get_state_summary()
            },
            "metrics": self.metrics.get_all_metrics(),
            "workload": self.registry.get_workload_stats(),
            "assignment_log": self.dispatcher.assignment_log,
            "event_log": self.simulation_log,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "dataset": "ps2_delivery_dispatch",
                "config": self.config.to_dict()
            }
        }

        return results

    def get_throughput(self) -> float:
        """Get current throughput in orders per minute."""
        if self._start_time is None:
            return 0.0
        elapsed_minutes = (time.time() - self._start_time) / 60.0
        if elapsed_minutes <= 0:
            return 0.0
        return self._orders_processed / elapsed_minutes
