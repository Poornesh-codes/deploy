"""
Metrics tracking for the delivery dispatch system.
Implements Welford's algorithm for online statistics,
SLA compliance, and workload fairness metrics.
"""

import json
import math
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

from .models import Order, Priority

logger = logging.getLogger(__name__)


class WelfordStats:
    """
    Online mean and variance calculation using Welford's algorithm.
    Numerically stable for running computation.
    """

    def __init__(self):
        self.n = 0
        self.mean = 0.0
        self._m2 = 0.0  # Sum of squared differences

    def update(self, value: float):
        """Add a new value to the running statistics."""
        self.n += 1
        delta = value - self.mean
        self.mean += delta / self.n
        delta2 = value - self.mean
        self._m2 += delta * delta2

    @property
    def variance(self) -> float:
        """Population variance."""
        if self.n < 2:
            return 0.0
        return self._m2 / self.n

    @property
    def sample_variance(self) -> float:
        """Sample variance (Bessel's correction)."""
        if self.n < 2:
            return 0.0
        return self._m2 / (self.n - 1)

    @property
    def std_dev(self) -> float:
        """Population standard deviation."""
        return math.sqrt(self.variance)

    def to_dict(self) -> Dict:
        return {
            "count": self.n,
            "mean": round(self.mean, 2),
            "variance": round(self.variance, 2),
            "std_dev": round(self.std_dev, 2)
        }


class MetricsTracker:
    """
    Comprehensive metrics tracking for the dispatch system.
    
    Tracks:
    - Delivery time (overall + by priority)
    - SLA compliance (violations, rates, margins)
    - Workload fairness
    - Priority-level statistics
    """

    def __init__(self):
        # Delivery time stats (Welford's algorithm)
        self.delivery_time_overall = WelfordStats()
        self.delivery_time_by_priority: Dict[str, WelfordStats] = {
            "HIGH": WelfordStats(),
            "NORMAL": WelfordStats(),
            "LOW": WelfordStats()
        }

        # SLA tracking
        self.total_delivered = 0
        self.sla_violations = 0
        self.sla_violations_by_priority: Dict[str, int] = defaultdict(int)
        self.delivered_by_priority: Dict[str, int] = defaultdict(int)
        self.sla_margins: List[float] = []
        self.sla_margin_stats = WelfordStats()

        # Delivery records
        self.deliveries: List[Dict] = []

    def record_delivery(self, order: Order):
        """Record a completed delivery and update all metrics."""
        if order.delivery_time is None:
            logger.warning(f"Order {order.order_id} has no delivery time")
            return

        priority_name = order.priority.name
        delivery_time = order.delivery_time

        # Update delivery time stats
        self.delivery_time_overall.update(delivery_time)
        if priority_name in self.delivery_time_by_priority:
            self.delivery_time_by_priority[priority_name].update(delivery_time)

        # Update SLA stats
        self.total_delivered += 1
        self.delivered_by_priority[priority_name] += 1

        if order.sla_violated:
            self.sla_violations += 1
            self.sla_violations_by_priority[priority_name] += 1

        # SLA margin (positive = met, negative = violated)
        margin = order.sla_minutes - delivery_time
        self.sla_margins.append(margin)
        self.sla_margin_stats.update(margin)

        # Record delivery
        self.deliveries.append({
            "order_id": order.order_id,
            "priority": priority_name,
            "delivery_time": round(delivery_time, 2),
            "sla_minutes": order.sla_minutes,
            "sla_margin": round(margin, 2),
            "sla_violated": order.sla_violated,
            "agent": order.assigned_agent
        })

    def get_delivery_time_metrics(self) -> Dict:
        """Get delivery time metrics overall and by priority."""
        result = {
            "overall": self.delivery_time_overall.to_dict(),
            "by_priority": {}
        }
        for priority, stats in self.delivery_time_by_priority.items():
            if stats.n > 0:
                result["by_priority"][priority] = stats.to_dict()
        return result

    def get_sla_metrics(self) -> Dict:
        """Get SLA compliance metrics."""
        violation_rate = (
            (self.sla_violations / self.total_delivered * 100)
            if self.total_delivered > 0 else 0.0
        )
        compliance_rate = 100.0 - violation_rate

        result = {
            "total_delivered": self.total_delivered,
            "violations": self.sla_violations,
            "violation_rate_percent": round(violation_rate, 2),
            "compliance_rate_percent": round(compliance_rate, 2),
            "margin": self.sla_margin_stats.to_dict(),
            "by_priority": {}
        }

        for priority in ["HIGH", "NORMAL", "LOW"]:
            delivered = self.delivered_by_priority.get(priority, 0)
            violations = self.sla_violations_by_priority.get(priority, 0)
            if delivered > 0:
                result["by_priority"][priority] = {
                    "delivered": delivered,
                    "violations": violations,
                    "violation_rate_percent": round(violations / delivered * 100, 2),
                    "compliance_rate_percent": round(
                        (delivered - violations) / delivered * 100, 2
                    )
                }

        return result

    def get_all_metrics(self) -> Dict:
        """Get all metrics combined."""
        return {
            "delivery_time": self.get_delivery_time_metrics(),
            "sla_compliance": self.get_sla_metrics(),
            "priority_stats": {
                priority: {
                    "count": self.delivered_by_priority.get(priority, 0),
                    "avg_delivery_time": (
                        round(self.delivery_time_by_priority[priority].mean, 2)
                        if self.delivery_time_by_priority[priority].n > 0 else None
                    )
                }
                for priority in ["HIGH", "NORMAL", "LOW"]
            },
            "deliveries": self.deliveries
        }

    def get_human_readable_summary(self) -> str:
        """Generate a human-readable summary of all metrics."""
        lines = []
        lines.append("=" * 60)
        lines.append("DELIVERY DISPATCH SYSTEM - METRICS SUMMARY")
        lines.append("=" * 60)
        lines.append("")

        # Delivery Time
        dt = self.delivery_time_overall
        lines.append("📦 DELIVERY TIME")
        lines.append(f"   Average: {dt.mean:.1f} minutes")
        lines.append(f"   Std Dev: {dt.std_dev:.1f} minutes")
        lines.append(f"   Orders:  {dt.n}")
        lines.append("")

        for priority in ["HIGH", "NORMAL", "LOW"]:
            stats = self.delivery_time_by_priority[priority]
            if stats.n > 0:
                emoji = {"HIGH": "🔴", "NORMAL": "🟡", "LOW": "🟢"}[priority]
                lines.append(f"   {emoji} {priority}: avg={stats.mean:.1f}min "
                           f"(σ={stats.std_dev:.1f}) [{stats.n} orders]")

        lines.append("")

        # SLA Compliance
        sla = self.get_sla_metrics()
        lines.append("📋 SLA COMPLIANCE")
        lines.append(f"   Compliance Rate: {sla['compliance_rate_percent']:.1f}%")
        lines.append(f"   Violations:      {sla['violations']}/{sla['total_delivered']}")
        lines.append(f"   Avg Margin:      {self.sla_margin_stats.mean:.1f} minutes")
        lines.append("")

        for priority in ["HIGH", "NORMAL", "LOW"]:
            if priority in sla["by_priority"]:
                p = sla["by_priority"][priority]
                lines.append(
                    f"   {priority}: {p['compliance_rate_percent']:.1f}% "
                    f"({p['violations']}/{p['delivered']} violations)"
                )

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def export_json(self, filepath: Optional[str] = None) -> str:
        """
        Export all metrics as JSON.
        Optionally writes to file.
        """
        output = {
            "metrics": self.get_all_metrics(),
            "deliveries": self.deliveries,
            "metadata": {
                "timestamp": datetime.now().isoformat(),
                "total_orders": self.total_delivered
            }
        }

        json_str = json.dumps(output, indent=2, default=str)

        if filepath:
            with open(filepath, 'w') as f:
                f.write(json_str)
            logger.info(f"Metrics exported to {filepath}")

        return json_str
