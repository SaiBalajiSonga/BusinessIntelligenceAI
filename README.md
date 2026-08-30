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
The React frontend leverages an aggressive 30-second TTL in-memory cache and `onMouseEnter` pre-fetching. Combined with custom CSS `@keyframes` and professional SVG iconography (`lucide-react`), the platform feels instant and incredibly tactile.

---

## 📂 Project Structure

```
BusinessIntelligence.ai/
├── api/                           # Backend Server (FastAPI)
│   ├── main.py                    # REST API entrypoint & static file serving
│   ├── cache.py                   # In-memory TTL caching engine
│   ├── service.py                 # Core analysis orchestration
│   ├── engine/                    # Mathematical Core
│   │   ├── detect.py              # Anomaly & Materiality (Z-Scores)
│   │   ├── confidence.py          # Abstention logic & data gaps
│   │   ├── lmdi.py                # Logarithmic Mean Divisia Index math
│   │   └── attribution.py         # Dimensional surprise ranking (Jensen-Shannon)
│   ├── feedback/                  # Machine Learning Feedback Loop
│   │   ├── store.py               # Feedback persistence
│   │   └── learn.py               # Isotonic Calibration & Laplace Smoothing
│   └── narrative/                 # LLM Integration
│       ├── provider.py            # API layer (Gemini, Groq, etc)
│       └── guard.py               # Hallucination interceptor (Numeric Validation)
│
├── web/                           # Frontend UI (React + Vite)
│   ├── src/
│   │   ├── pages/                 # NarrativeStudio, RootCause, Overview, Integrations
│   │   ├── components/            # InlineFeedback, Animated Quote Loader, Toast
│   │   ├── charts/                # Financial Impact Waterfall (Bridge Charts)
│   │   ├── api.ts                 # Type-safe API client & Prefetching
│   │   ├── types.ts               # Strict TypeScript interfaces
│   │   └── styles.css             # Custom CSS variables, Grid layouts, animations
│   ├── package.json
│   └── vite.config.ts
│
├── kpis.yaml                      # Semantic Contract defining KPIs & thresholds
└── README.md
```

---

## 🛠️ Getting Started (Local Development)

The application is designed to be completely self-contained. The FastAPI backend serves the REST API on `/v1` and simultaneously serves the built React frontend on `/`.

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**

### 1. Build the Frontend
```bash
cd web
npm install
npm run build
cd ..
```
*(Note: If you encounter Windows Application Control policies blocking Rollup during build, the repository includes a pre-built `/dist` directory for immediate backend serving).*

### 2. Start the Backend Server
```bash
# Create and activate a virtual environment
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# Mac/Linux: source venv/bin/activate

# Install Python dependencies
pip install fastapi uvicorn pydantic scikit-learn pandas

# Run the server
python -m uvicorn api.main:app --port 8000 --host 127.0.0.1 --env-file .env
```

### 3. Access the Dashboard
Open your browser and navigate to:
👉 **[http://127.0.0.1:8000](http://127.0.0.1:8000)**

*(API Swagger documentation is available at `http://127.0.0.1:8000/docs`)*

---

## 🧪 Technical Highlights

- **The Hallucination Interceptor**: The LLM is forced to output JSON containing arrays of numbers. `narrative/guard.py` rips out every number the LLM produced and checks if it exists in the `Evidence` object passed to the prompt. If `42.5` appears in the text but wasn't computed by the deterministic engine, the generation is rejected.
- **Isotonic Calibration**: `feedback/learn.py` maps non-linear heuristic scores (e.g. data freshness + volume = 74) to empirical accuracy probabilities (e.g. 88% chance this driver is correct) based on historical thumbs-up/down clicks.
- **YouTube-Style Micro-Interactions**: The `InlineFeedback.tsx` React component uses custom bouncy cubic-bezier `@keyframes` and un-filled crisp SVG toggles to mimic the premium haptic feel of enterprise applications, completely shedding the "developer UI" aesthetic. 

---

## 📄 License
MIT License