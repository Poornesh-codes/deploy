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

## Deployment & Approach

### Web Dashboard
- **Technology**: Flask application converted to **Frozen Flask** for static site generation
- **Hosting**: GitHub Pages (https://poornesh-codes.github.io/deploy/)
- **Architecture**: 
  - **Frontend**: Interactive HTML/CSS/JavaScript dashboard
  - **Backend**: Pre-computed simulation results cached as static JSON files
  - **No Server Required**: All data is frozen into static assets for instant loading

### Deployment Process
1. **Local Development**: Run simulations with `python main.py` or `python app.py`
2. **Static Generation**: Execute `python freeze.py` to convert Flask app to static HTML/JSON
3. **Build Output**: Generated files stored in `/build` directory:
   - `build/index.html` - Dashboard UI
   - `build/api/metrics` - Cached metrics JSON
   - `build/api/run` - Cached simulation results JSON
4. **GitHub Pages**: Commit `/build` directory and enable Pages from `main` branch `/build` folder
5. **Live Site**: Dashboard accessible at GitHub Pages URL with zero infrastructure cost

### Key Advantages
- **Fast Deployment**: Static files load instantly with CDN caching
- **Zero Cost Hosting**: GitHub Pages is completely free
- **No Server Maintenance**: Pre-computed results require no backend
- **Version Control**: All deployment snapshots tracked in git
- **Easy Updates**: Re-run simulation, regenerate static files, push to update live site

**Note:** Please do not change the format or spelling of anything in this README. The fields are extracted using a script, so any changes to the structure or formatting may break the extraction process.
