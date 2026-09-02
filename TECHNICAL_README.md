# BusinessIntelligence.ai 🧠📊

An enterprise-grade, agentic analytical engine that detects material changes in business KPIs, mathematically isolates root causes, and generates persona-tailored action plans. 

Unlike traditional BI dashboards that leave root-cause diagnosis to manual cross-tabulation, and unlike pure LLM approaches (like Text-to-SQL) that hallucinate calculations, **BusinessIntelligence.ai** enforces a strict architectural boundary: **Deterministic Mathematics first, Language generation second.**

---

## 🏗️ Architecture & Philosophy

The engine separates computation from narrative through a rigorous pipeline:

1. **Deterministic Core (Python, FastAPI)**: Computes 100% of the metric variances, executes Logarithmic Mean Divisia Index (LMDI) decomposition, calculates Jensen-Shannon divergence for uncharacteristic behavior, and applies Role-Based Access Control (RBAC) row-level filtering *before* analysis.
2. **Abstention Gate & Data Validation**: Evaluates data freshness SLAs, sample depth (statistical significance), and cross-source contradictions. If confidence falls below the strict materiality threshold, the engine honestly **abstains** from speculative root-cause attribution and instead requests data verification.
3. **The Evidence Object**: All mathematical findings are packed into a locked JSON Schema (The Evidence Object).
4. **Governed LLM Layer**: The LLM converts the mathematical evidence into role-specific business narratives (CFO, Category Manager, Analyst). **Crucially, an interception middleware verifies every single number the LLM generates against the Evidence Object.** Any hallucinatory arithmetic causes the draft to be instantly rejected.
5. **Interactive UI (React + Vite)**: A sleek, zero-latency dashboard built for business leaders, completely devoid of developer jargon, featuring YouTube-style haptic feedback loops.

---

## 🚀 Core Capabilities

### 1. LMDI Root Cause Decomposition
Decomposes complex metric deviations (e.g., Net Revenue dropping) into mathematically perfect, additive components: Price, Volume, Mix, and Competitor influence. This allows the engine to definitively state whether a drop was caused by a discount strategy (Price) or a shift toward cheaper products (Mix).

### 2. Isotonic Calibration & Laplace Smoothing (Feedback Loop)
The platform actively learns from Analyst feedback. When a user clicks "Dislike: Wrong Driver", the engine utilizes **Isotonic Regression** to calibrate the raw statistical confidence scores into true empirical probabilities. **Laplace Smoothing** computes continuous precision scores to penalize drivers that frequently trigger false positives, preventing alert fatigue over time.

### 3. Role-Based Entitlements & Masking
Data access is enforced at the mathematical level, not just visually hidden. If an EU Category Manager logs in, they only see DE, FR, NL data. Highly sensitive metrics (like Gross Margin %) are structurally masked for unauthorized personas before any decomposition occurs.

### 4. Zero-Latency Caching & UI Polish
The React frontend leverages a 30-second TTL in-memory client-side cache (`web/src/api.ts`) so repeat navigation between pages doesn't re-fetch identical data. Combined with custom CSS `@keyframes`, a violet/graphite/serif design system, and professional SVG iconography (`lucide-react`), the platform is meant to read as a decision workspace rather than a generic admin panel.

---

## 📂 Project Structure

```
BusinessIntelligence.ai/
├── api/                            # Backend Server (FastAPI)
│   ├── main.py                     # REST API entrypoint & serves the built frontend
│   ├── cache.py                    # In-memory TTL caching engine
│   └── service.py                  # Core analysis orchestration, warm-up profiling
│
├── engine/                         # Deterministic mathematical core
│   ├── contract.py                 # KPI contract loader (retail/SaaS selectable)
│   ├── warehouse.py                # DuckDB connection, grain reconciliation, freshness
│   ├── detect.py                   # Rung 0 — Anomaly & Materiality (Z-scores)
│   ├── decompose.py                # Rungs 1-2 — LMDI + Bennet price/volume/mix
│   ├── attribute.py                # Rung 3 — Dimensional surprise ranking (Jensen-Shannon)
│   ├── causal.py                   # Rung 4 — Difference-in-differences
│   ├── confidence.py               # Rung 5 — Abstention logic, data gaps, learned recalibration
│   └── levers.py                   # driver -> lever -> action -> recovery
│
├── feedback/                       # Machine Learning Feedback Loop
│   ├── store.py                    # Feedback/annotation persistence (DuckDB)
│   └── learn.py                    # Isotonic Calibration & Laplace-smoothed driver priors
│
├── narrative/                      # LLM Integration
│   ├── provider.py                 # Providers (offline mock / any OpenAI-compatible API)
│   ├── synthesize.py                # Persona prompts, evidence rendering, offline template
│   └── validator.py                # Hallucination interceptor (Numeric Validation)
│
├── contracts/
│   ├── kpis.yaml                   # Semantic Contract defining KPIs & thresholds (retail)
│   └── kpis_saas.yaml              # SaaS vertical contract (KPI_CONTRACT_PATH)
│
├── web/                            # Frontend UI (React + Vite)
│   ├── src/
│   │   ├── pages/                  # Overview, Investigate, Actions, Governance, FeedbackHub, Integrations
│   │   ├── components/             # PersonaSwitcher, InlineFeedback, CommandPalette, Toast, Loader
│   │   ├── charts.tsx               # Bridge waterfall, confidence bars, engine pipeline visual
│   │   ├── api.ts                  # Type-safe API client + 30s client cache
│   │   ├── types.ts                # Strict TypeScript interfaces
│   │   └── styles.css              # Design tokens, component library, animations
│   ├── package.json
│   └── vite.config.ts
│
└── README.md
```

---

## 🛠️ Getting Started (Local Development)

The application is completely self-contained. The FastAPI backend serves the REST API on `/v1` and simultaneously serves the built React frontend on `/`.

### Prerequisites
- **Python 3.10+**
- **Node.js 18+** (only needed if you're changing the frontend — a built copy is already committed at `web/dist`)

### 1. Backend
```bash
# Create and activate a virtual environment
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Mac/Linux: source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt

# Run the server (--env-file is optional; only needed if you created a .env for a real LLM key)
python -m uvicorn api.main:app --port 8000 --host 127.0.0.1 --env-file .env
```
The synthetic dataset generates itself automatically on first use if `data/raw/` doesn't exist yet (`engine/warehouse.py` calls `data/generate.py` on demand) — the very first request will take a few seconds longer. To pre-generate it explicitly: `python data/generate.py`.

### 2. (Optional) Rebuild the Frontend
```bash
cd web
npm install
npm run build
cd ..
```
*(If this is skipped, the backend serves the pre-built `web/dist` already committed to the repo.)*

### 3. Access the Dashboard
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

*(API Swagger documentation is available at `http://127.0.0.1:8000/docs`)*

---

## 🧪 Technical Highlights

- **The Hallucination Interceptor**: The LLM is forced to output prose whose figures are checked against the evidence. `narrative/validator.py` extracts every number the LLM produced and confirms it's traceable to the `Evidence` object passed in the prompt. If a figure appears in the text but wasn't computed by the deterministic engine, the draft is rejected and one retry is attempted with the offending figures named explicitly.
- **Isotonic Calibration**: `feedback/learn.py` fits an isotonic regression mapping the raw heuristic confidence score to the empirical rate at which insights at that score were actually judged correct by analysts, and Laplace-smooths per-driver priors so one bad week can't bury a driver's trust score. Both are persisted (not just computed) and re-applied by `engine/confidence.py` on the very next assessment — the loop actually closes.
- **Honest offline fallback**: when no LLM provider is configured, `narrative/synthesize.py` routes through a deterministic template narrator rather than disguising an echo as a model call — the API reports `llm_called: false` and `source: "template fallback"` truthfully in that case.

---

## 📄 License
MIT License