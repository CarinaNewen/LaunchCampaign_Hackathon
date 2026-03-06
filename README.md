# Hivewire

> Helping companies launch their dream marketing campaign using superhuman swarm intelligence

---

## Architecture

```
                    ┌─────────────────────────────────────────────────────────────────┐
                    │                         FastAPI (main.py)                         │
                    │  /health  │  /  (landing)  │  /*  (static)  │  CORS middleware   │
                    └─────────────────────────────────────────────────────────────────┘
                                                │
                    ┌───────────────────────────▼───────────────────────────┐
                    │              API Layer (api/routes.py)                 │
                    │  prefix: /swarm                                         │
                    │  POST /start   POST /run   POST /run/{id}   GET /run/{id}  │
                    │  POST /demo   POST .../kill/{agent}   GET/POST /llm/*   │
                    └───────────────────────────┬───────────────────────────┘
                                                │
        ┌───────────────────────────────────────┼───────────────────────────────────────┐
        │                                       ▼                                       │
        │  ┌─────────────────────────────────────────────────────────────────────────┐ │
        │  │                     SwarmEngine (services/swarm_engine.py)               │ │
        │  │  SharedStateManager ──► load/save RunState, events, agent statuses       │ │
        │  │  start_run() → run_rounds() → priority-based agent scheduling → final    │ │
        │  └───────┬─────────────────────────────────────────────────┬───────────────┘ │
        │          │                                                 │                 │
        │          ▼                                                 ▼                 │
        │  ┌───────────────────┐                          ┌──────────────────────────┐ │
        │  │   StateStore      │                          │   LLMService             │ │
        │  │   (abstract)      │                          │   (services/llm.py)      │ │
        │  └─────────┬─────────┘                          │   Gemini / Ollama        │ │
        │            │                                    └────────────┬─────────────┘ │
        │            │  InMemoryStore (memory_store.py)                │               │
        │            │  dict + JSON snapshots to disk                  │               │
        │            │  (RedisStore pluggable later)                   │               │
        │            │                                                 │               │
        │            └─────────────────────┬───────────────────────────┘               │
        │                                  │                                           │
        │                                  ▼                                           │
        │  ┌─────────────────────────────────────────────────────────────────────────┐ │
        │  │                    Swarm Agents (agents/*.py)                            │ │
        │  │  BaseSwarmAgent: act(), can_act(), priority()                            │ │
        │  │  ┌──────────────┬─────────────────────┬──────────────┬─────────────────┐ │ │
        │  │  │ TrendScout   │ AudiencePsychologist│ CreatorFit   │ HookSmith       │ │ │
        │  │  ├──────────────┼─────────────────────┼──────────────┼─────────────────┤ │ │
        │  │  │ FormatComposer                     │ CriticMutator │                 │ │ │
        │  │  └──────────────┴─────────────────────┴──────────────┴─────────────────┘ │ │
        │  │  Each agent reads RunState (ideas, scores, lineage), calls LLM, returns   │ │
        │  │  AgentActionResult (new_ideas, updated_scores, lineage_updates, events)   │ │
        │  └─────────────────────────────────────────────────────────────────────────┘ │
        │                                                                               │
        │  ┌─────────────────────────────────────────────────────────────────────────┐ │
        │  │  models/schemas.py   CampaignInput, RunState, SwarmEvent, FinalOutput    │ │
        │  │  core/config.py      Settings (Gemini, Ollama, app name/version)        │ │
        │  └─────────────────────────────────────────────────────────────────────────┘ │
        └───────────────────────────────────────────────────────────────────────────────┘
```

---

## How do we automatically analyze the best strategies with swarm agents?

Automation streamlines processes — apply this knowledge to generate launch campaign ideas.

- An average ROI of **$5.44 for every dollar spent** with fully autonomous campaigns *(Source: comosoft.us)*
- Agents collaborate with different mindsets/goals on the perfect launch campaign
- Agents work collaboratively on a blackboard and correct each other if their outputs do not align with their respective roles

---

## True Emergence

Agent setup: **non-hierarchical**

| Agent | Role |
|-------|------|
| Agent 1 | General trend scout |
| Agent 2 | Trend scout for a specific target audience |
| Agent 3 | Identifies emotional triggers in videos |
| Agent 4 | Brand alignment |
| Agent 5 | Competitor analyst |
| Agent 6 | Finds a "Face of the Campaign", aligning with the core values of the company and what it should represent |

---

## Tech Stack

- **Python**
- **FastAPI**
- **Pydantic**
- Simple in-memory dict store for v1
- Storage abstraction layer so Redis can be added later
- Clear modular architecture
- JSON-first responses
