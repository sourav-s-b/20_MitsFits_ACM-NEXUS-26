## 09:00

### Features Added
- Initialized project structure
- Added `AGENTS.md` with hackathon workflow rules
- Created `CHANGELOG.md` with predefined format

### Files Modified
- AGENTS.md
- CHANGELOG.md
- README.md

### Issues Faced
- None

## 12:47

### Features Added
- Added local template image assets (template_acm.png, template_clique.png)
- Refactored AGENTS.md, README.md, and CHANGELOG.md to use 24-hour time format (HH:MM) instead of "Hour X"

### Files Modified
- AGENTS.md
- CHANGELOG.md
- README.md
- template_acm.png
- template_clique.png

### Issues Faced
- Initial remote image download attempt failed, resolved by using provided local files

## 21:32

### Features Added
- Created a demo frontend
- Added working backend UI
- Integrated calls to TomTom API

### Files Modified
- frontend/
- backend/

### Issues Faced
- None explicitly stated

## 22:32

### Features Added
- Auto-start shipment on backend boot (lifespan hook in server.py)
- Auto-pipeline poll every 30s (frontend keeps risk fresh automatically)
- Connection error screen if backend is unreachable
- Wired Person 2's real `/risk?lat=&lon=` and `/sop?status=` endpoints
- Created `risk-engine/.env` with shared API keys (OWM_KEY, TOMTOM_KEY)
- Progress file added to `/progress/1.md`

### Files Modified
- backend/server.py
- backend/routes/orchestration_routes.py
- frontend/src/App.jsx
- risk-engine/.env (created)
- progress/1.md (created)

### Issues Faced
- Person 2's endpoint was GET /risk not POST /predict — fixed by reading their actual code

## 22:34

### Features Added
- Integrated trained Random Forest ML model (`risk_model.pkl`) into the risk prediction engine.
- Implemented robust SOP matching logic supporting numeric triggers (e.g., `weather_score > 0.7`).
- Added comprehensive unit testing suite for the risk engine (`tests/test_risk_engine.py`).
- Implemented automated startup checks for API keys and data path validation.

### Files Modified
- `risk-engine/main.py`
- `risk-engine/model/predictor.py`
- `risk-engine/model/__init__.py`
- `risk-engine/tests/test_risk_engine.py`

### Issues Faced
- Resolved `ModuleNotFoundError` during testing by establishing proper package structure.
- Addressed `scikit-learn` feature name warnings in the prediction model.

## 23:10

### Features Added
- Completely replaced in-memory single-vehicle prototype with a multi-tenant `live_store.py` (Redis mock).
- Built SQLite `database.py` with `shipments` and `audit_logs` persistence for all AI intelligence decisions.
- Subbed heavy API polling loops entirely out for native WebSockets `ws://{host}/ws/{shipment_id}`.
- Refactored `orchestration_routes.py` pipeline runs to `BackgroundTasks` avoiding application stalls.
- Updated `App.jsx` React frontend to seamlessly ingest continuous WebSocket broadcast streams.

### Files Modified
- backend/state.py (Deleted)
- backend/database.py (Created)
- backend/live_store.py (Created)
- backend/websocket.py (Created)
- backend/simulator.py
- backend/server.py
- backend/routes/main_routes.py
- backend/routes/decision_routes.py
- backend/routes/orchestration_routes.py
- frontend/src/App.jsx
- progress/2.md (Created)

### Issues Faced
- Leaflet re-rendering errors caused by React polling interval overriding native state. Resolved gracefully by switching purely to WebSocket push events preventing double-mutations.
