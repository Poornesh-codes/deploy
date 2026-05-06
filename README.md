# Smart Delivery Dispatch System

## Team Information
- **Team Name**: CodeCrafters
- **Year**: 2026
- **All-Female Team**: No

## Architecture Overview

#### Describe your approach here. Keep it short and clear.

We implemented a robust event-driven simulator with a dynamic multi-objective scoring engine. 

- **Dispatch strategy**: When an order arrives or an agent becomes available, the dispatcher generates valid candidates (agents with capacity and a valid path). We evaluate these candidates based on a weighted scoring mechanism and select the agent with the highest score.
- **Scoring agents**: The scoring function considers 5 objectives:
  1. Delivery Time (Travel + Prep time)
  2. SLA Urgency (How close the order is to its deadline)
  3. Workload Fairness (Agents with fewer assignments get boosted)
  4. Priority Boost (High priority orders are assigned higher scores)
  5. Agent Rating (Higher rated agents are slightly favored)
- **Managing SLA, priority, capacity**: We maintain an order queue grouped by priority. Agents are strictly limited to `max_active_orders` (2) via the agent registry. SLA deadlines directly impact the urgency score, ensuring tight-deadline orders preempt others.
- **Pipeline**:
  1. **Data Loading**: Load constraints, map graph, and validate agents & orders. Precompute shortest paths via Floyd-Warshall for O(1) latency.
  2. **Simulation**: Time-stepped processing of order arrivals and delivery events (PENDING → ASSIGNED → IN_TRANSIT → DELIVERED).
  3. **Metrics**: Real-time evaluation of SLA compliance, delivery times, and agent workloads using Welford's algorithm.

**Note:** Please do not change the format or spelling of anything in this README. The fields are extracted using a script, so any changes to the structure or formatting may break the extraction process.
