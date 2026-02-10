# DEMANDER Backend

Python FastAPI backend for the DEMANDER demand intelligence platform.

## Setup

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --port 8000
```

## API Docs

Once running, visit:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

## Project Structure

```
app/
├── main.py              # FastAPI app entry point + lifespan (DB init)
├── config.py            # Environment config
├── db.py                # SQLAlchemy engine, session, Base
├── models/
│   ├── property.py      # Property ORM model
│   └── report.py        # Report ORM model
├── routers/
│   ├── properties.py    # Property CRUD + URL extraction
│   ├── simulation.py    # Run simulation → auto-persist report
│   └── reports.py       # Report retrieval + per-property listing
├── schemas/
│   ├── property.py      # Pydantic: PropertyCreate, PropertyUpdate, PropertyResponse
│   └── report.py        # Pydantic: DemandReport, SimulationRequest
└── simulation/
    ├── archetypes.py    # 5 buyer archetype definitions + market weighting
    └── engine.py        # Monte Carlo simulation engine (funnel, blockers, recs)
```

## Database

SQLite by default (`demander.db` auto-created on first run).
Set `DATABASE_URL` in `.env` to switch to PostgreSQL:
```
DATABASE_URL=postgresql://user:password@localhost:5432/demander
```

## API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |

### Properties
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/properties/` | Create a property |
| GET | `/api/properties/` | List all properties |
| GET | `/api/properties/{id}` | Get a single property |
| PATCH | `/api/properties/{id}` | Update a property (partial) |
| DELETE | `/api/properties/{id}` | Delete a property |
| POST | `/api/properties/extract` | Extract from listing URL (API-first, scrape fallback + enrichment) |

### Simulation
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/simulation/run` | Run demand simulation (auto-saves report) |

### Reports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/reports/` | List all reports |
| GET | `/api/reports/{id}` | Get a single report |
| GET | `/api/reports/property/{property_id}` | All reports for a property |
| DELETE | `/api/reports/{id}` | Delete a report |

## Listing URL Extraction (optional providers)

`POST /api/properties/extract` uses this fallback ladder:

1. **Listings API (recommended)** if configured via environment variables
2. **Best-effort scrape** (JSON-LD + simple regex heuristics)
3. **Enrichment** using free geocoding (OpenStreetMap Nominatim) when an address is available

### Environment Variables

If you have a 3rd-party listings API, configure:

```
LISTING_API_URL_TEMPLATE=https://your-provider.example/extract?url={url}
LISTING_API_KEY=your_key_here
LISTING_API_KEY_HEADER=X-API-Key
```

Free enrichment toggle (defaults to enabled):

```
NOMINATIM_ENABLED=true
```

## Simulation Engine

The core engine (`app/simulation/engine.py`) performs:

1. **Archetype Selection** — adjusts 5 buyer archetype weights based on listing price
2. **Buyer Generation** — creates N synthetic agents with noisy preference parameters
3. **Decision Funnel** — each agent progresses through Click → Save → Tour → Offer
4. **Monte Carlo** — runs M simulation passes for statistical confidence
5. **Aggregation** — computes demand score, sale probability, funnel rates, timeline
6. **Blocker Detection** — identifies friction factors (HOA, risk zones, schools, etc.)
7. **Recommendations** — generates ranked, actionable improvements with estimated lift

### Buyer Archetypes (v1)

| Archetype | Weight | Budget Range | Key Priorities |
|-----------|--------|--------------|----------------|
| Starter Couple | 25% | $200K–$500K | Commute, affordability, condition |
| Growing Family | 30% | $350K–$800K | Schools, space, safety |
| Relocation Pro | 20% | $300K–$650K | Commute, turnkey condition |
| Downsizer | 10% | $250K–$550K | Low maintenance, condition |
| Investor | 15% | $150K–$1.2M | ROI, low HOA, risk tolerant |
