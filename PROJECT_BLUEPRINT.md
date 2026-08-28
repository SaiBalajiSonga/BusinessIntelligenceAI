# BusinessIntelligence.ai: KPI Intelligence-to-Action Engine (Round 2 Architecture & Blueprint)

## 1. Problem Statement & Deep Ideation Analysis

Modern enterprise organizations do not suffer from a lack of dashboards; they suffer from an **action gap** and an **interpretation bottleneck**.

### Core Dilemmas in Enterprise KPI Management:
1. **Dashboards are Descriptive, Not Diagnostic or Prescriptive**:
   - When a KPI like *Gross Margin %* drops 350 basis points week-over-week, standard BI tools (PowerBI, Tableau, Looker) display the red line. 
   - Business leaders must manually assemble cross-functional teams to slice across 15 dimensions (region, channel, product category, discount tier, supplier freight) to guess what happened.
2. **The "LLM Arithmetic Hallucination" & "Text-to-SQL Fragility" Trap**:
   - Naive AI approaches attempt to feed raw SQL schemas or raw data dumps directly to an LLM. This leads to catastrophic failures:
     - LLMs hallucinate calculations and sums.
     - LLMs mix aggregate time granularities (e.g., summing daily POS data with weekly ERP inventory counts or monthly marketing targets).
     - LLMs generate plausible-sounding but mathematically false root causes without statistical rigor.
3. **Data Heterogeneity & Refresh Asynchrony**:
   - Data does not arrive on unified cadences:
     - **POS / Transactional Data**: Daily / Real-time.
     - **Inventory & Supply Chain ERP**: Weekly snapshot batch.
     - **Marketing Ad Spend & Attribution**: Daily with a 48-to-72-hour attribution settlement window.
4. **Persona Context Divergence**:
   - The same 3.5% margin drop demands different context and levers:
     - *VP of Commercial / Sales*: Cares about revenue dollar impact, channel discount abuse, and pricing elasticity.
     - *Supply Chain & Inventory Lead*: Cares about warehouse stock-out duration, freight surcharges, and supplier lead-time penalties.
     - *Performance Marketing Lead*: Cares about ad spend ROAS, customer acquisition cost (CAC), and campaign efficiency.
5. **The Missing Uncertainty & Abstention Mechanism**:
   - Real-world business data is often incomplete, noisy, delayed, or contradictory (e.g., POS shows conversion dropping while Google Ads reports record-high conversion due to a broken tracking pixel).
   - A reliable BI engine must have the intelligence to say: *"Evidence is contradictory / data freshness SLA breached — I abstain from attributing this to marketing and recommend verifying the tracking pixel."*

---

## 2. Best Architecture Evaluation: Why a "Governed Hybrid Core" Wins

### Comparative Evaluation of Architectural Approaches

| Feature / Requirement | Pure LLM Agent (Text-to-SQL) | Heavy Cloud BI (Snowflake/Fabric) | Governed Hybrid Core (DuckDB+LLM) |
| :--- | :--- | :--- | :--- |
| **Mathematical Reliability** | ❌ Low (Hallucinations) |  High | ** 100% Deterministic (Verified)** |
| **Causal & PVM Decomposition** | ❌ Qualitative only | ⚠️ Requires ML extensions | ** Built-in Math Algorithms** |
| **Multi-Grain Reconciliation** | ❌ High error rate | ⚠️ Complex ETL pipelines | ** Dynamic In-Process OLAP Engine** |
| **Contradiction & Abstention** | ❌ Hallucinates certainty | ❌ Manual rule alerts only | ** Automated Evidence Scorer** |
| **Total Cost (Hosting + Tokens)** | ⚠️ Expensive ($$$) | ❌ Heavy Subscription ($$$$) | ** $0.00 (Zero-Cost Open Source)** |
| **Deployment & Latency** | ⚠️ Slow multi-turn | ⚠️ Cloud cluster spin-up | **⚡ Sub-second Local In-Process** |

### The Winning Architecture: Governed Hybrid Intelligence Engine with Supabase Backend
This architecture enforces a strict pipeline:
$$\text{Supabase PostgreSQL (Heterogeneous Sources + RLS)} \xrightarrow{\text{Semantic Contract}} \text{Deterministic Analytics Core} \xrightarrow{\text{EvidencePack}} \text{Governed LLM Narrator} \xrightarrow{\text{Actionable Prescriptions}}$$

1. **Enterprise Backend on Supabase (PostgreSQL Free Tier - $0 Cost)**:
   - Houses the raw tables: `pos_orders` (Daily), `inventory_logistics` (Weekly), and `marketing_campaigns` (Daily with lag).
   - Enforces **Native PostgreSQL Row Level Security (RLS)** and Column-Level filtering for persona entitlements.
   - Stores the **Feedback Audit Log** to capture analyst validation and dynamically update driver prior weights.
2. **Deterministic Analytics Core (Non-LLM)**:
   - All arithmetic, Price-Volume-Mix (PVM) decomposition, Shapley contribution analysis, rolling Z-score anomaly detection, and cross-correlation are executed deterministically.
   - Generates a mathematically verifiable **`EvidencePack`** JSON object containing exact numbers, formulas, sample sizes, and p-values.
3. **Governed LLM Synthesis Layer**:
   - The LLM is **never** asked to calculate numbers or write arbitrary SQL.
   - The LLM receives the `EvidencePack` as ground truth facts and is purely responsible for:
     - Structuring persona-tailored narratives (Executive vs Supply Chain vs Marketing).
     - Mapping drivers to actionable business levers ($Driver \to Lever \to Action \to Expected\ Impact \to Owner$).
     - Communicating uncertainty when confidence flags are low.

---

## 3. Best Tools & Zero-Cost ($0) Stack with Supabase

The competition problem statement mentions: *Databricks, Snowflake, Microsoft Fabric, Tableau, Qlik, Looker, or custom/hybrid.*

### Why the Zero-Cost Supabase + Open Analytics Architecture is Superior:
- **Commercial Cloud Platforms** (Snowflake, Fabric, Databricks) require paid subscriptions, cloud account provisioning, compute credits, and significant setup overhead.
- **Enterprise BI Tools** (Tableau, Looker, Qlik) are closed-source, heavy, and lack native integration with custom causal decomposition and flexible persona-level LLM orchestration.
- **Our Recommended $0 Stack**:
  1. **Managed Backend & Database**: **Supabase (PostgreSQL Free Tier)**
     - Free 500MB hosted PostgreSQL database with REST API and native Row-Level Security.
     - Also includes a zero-config embedded local engine fallback for completely offline demo testing.
  2. **In-Memory Analytical Engine**: **DuckDB / In-Memory OLAP**
     - Executes high-speed dimensional rollups and cross-grain windowing in sub-milliseconds.
  3. **Mathematical & Statistical Core**: **Python (NumPy, Pandas, SciPy, Statsmodels)**
     - Implements exact Price-Volume-Mix (PVM) equations, Waterfall contribution %, Z-scores, and Difference-in-Differences.
  4. **Semantic Contracts & Data Validation**: **Pydantic v2 + PyYAML**
     - Strongly typed schemas for KPI definitions, driver trees, and Row/Column-Level Security (RLS/CLS).
  5. **LLM Orchestration**: **NVIDIA Nemotron (`nvidia/llama-3.1-nemotron-70b-instruct` / Nemotron family)** via NVIDIA NIM API Catalog / OpenRouter + Google Gemini / Groq + Offline Fallback
     - Zero token cost using NVIDIA NIM free developer credits / OpenRouter / Gemini free tier.
     - Built-in deterministic templating fallback ensures the system works 100% offline with zero external API dependencies if required.
  6. **Interactive Decision Workspace UI**: **Streamlit + Plotly**
     - Interactive waterfall charts, live persona toggling, traceable evidence inspection drawers, and real-time latency/token telemetry HUD.

---

## 4. System Blueprint: 8 Core Capabilities & Implementation Logic

### Capability Details:
1. **Materiality & Anomaly Detection**:
   - Dual-threshold filtering: Statistical significance ($Z > 2.0$, $p < 0.05$) AND Business materiality ($|\Delta \text{Revenue}| > \$10,000$ or $|\Delta \text{Margin}| > 150 \text{ bps}$).
2. **Reconciliation Across Heterogeneous Cadences**:
   - Automatically rolls daily POS transactions up to match weekly logistics ERP snapshots using calendar-aware window alignment.
   - Applies 48-hour attribution settlement window lag flags to marketing campaign data.
3. **Multi-Factor Explanatory Decomposition**:
   - **Price-Volume-Mix (PVM)** decomposes Gross Margin / Revenue movement into:
     - Pure Price Effect: $\sum (P_1 - P_0) \times V_1$
     - Pure Volume Effect: $\sum P_0 \times V_0 \times (\frac{V_{tot,1}}{V_{tot,0}} - 1)$
     - Pure Mix Effect: $\sum P_0 \times (V_1 - V_0 \times \frac{V_{tot,1}}{V_{tot,0}})$
   - **Dimensional Waterfall**: Ranks Category, Region, and Channel contributions summing to 100%.
4. **Persona-Specific Narratives & Traceable Evidence**:
   - *VP Commercial*: High-level strategic summary, pricing realization, gross dollar recovery.
   - *Supply Chain Director*: Warehouse stock-out impact, freight surcharges, buffer stock needs.
   - *Marketing Lead*: Ad spend efficiency, ROAS drop, CAC vs LTV.
   - Every claim links to an **Evidence Drawer** showing exact SQL query, dataset freshness timestamp, analytical method, and contribution percentage.
5. **Uncertainty & Abstention Engine**:
   - Calibrates a Composite Confidence Score ($0-100\%$) based on:
     - Data Freshness SLA
     - Cross-Source Contradiction (e.g. POS conversion drops while Marketing analytics reports spike due to tracking pixel outage)
     - History Sparsity ($N < 14$ days for newly launched products)
   - When Confidence $< 60\%$, the engine **abstains from speculative root-cause attribution** and flags actionable data-quality diagnostic steps.
6. **Action Recommendation Engine**:
   - Action output schema:
     $$\text{Driver} \longrightarrow \text{Controllable Lever} \longrightarrow \text{Prescriptive Action} \longrightarrow \text{Expected Impact} \longrightarrow \text{Owner} \longrightarrow \text{Monitoring Guardrail}$$
7. **Feedback & Continuous Learning Loop**:
   - Users/analysts can confirm, edit, or reject identified root causes.
   - Feedback is logged into DuckDB and updates historical likelihood weights and dynamic prompt few-shot context.
8. **Role-Based Security & Runtime Telemetry**:
   - RLS/CLS filters sensitive fields (e.g. masking supplier cost margins for marketing roles).
   - Telemetry HUD measures execution latency (ms), token consumption, and verifies $\$0.00$ cost per insight.
