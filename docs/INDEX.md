# Documentation index

All documents in `docs/`, grouped. Start with the root [README](../README.md), then [ARCHITECTURE](ARCHITECTURE.md) and [OPERATIONS](OPERATIONS.md).

## Core
| Document | What it is |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Components, data flow, repository map, data formats, generators, Facebook routine |
| [OPERATIONS.md](OPERATIONS.md) | Schedules, accounts, secrets, runbook, security, open items |
| [ROADMAP.md](ROADMAP.md), [ROADMAP_2026-11-06.md](ROADMAP_2026-11-06.md) | Product/data/monetisation roadmap (2026-10 baseline) and the route-planner roadmap |
| [GROWTH.md](GROWTH.md), [growth_kpis.csv](growth_kpis.csv) | Free traffic strategy, what is automated, outreach drafts, weekly KPI log |

## Facebook (`docs/facebook/` and `FACEBOOK.md`)
| Document | What it is |
|---|---|
| [facebook/GRAPH_API_SETUP.md](facebook/GRAPH_API_SETUP.md) | Meta app, Page token, GitHub secrets; status and how to repeat |
| [facebook/PLAYBOOK.md](facebook/PLAYBOOK.md) | Posting rules and the older browser-based route (disabled; fallback only) |
| [FACEBOOK.md](FACEBOOK.md) | Page set-up, bio, first posts, group templates |
| `facebook/post_log.csv`, `facebook/replied.csv` | Logs written by the routine (one post a day; replied comment ids) |
| `facebook/cover.png`, `profile.png` | Page images |

## Data sources, licences and permissions
| Document | What it is |
|---|---|
| [PERMISSIONS.md](PERMISSIONS.md) | Which source may be reused (granted / pending / open) |
| [REGULATORY_REPORTING.md](REGULATORY_REPORTING.md) | Which governments force stations to report prices, and how fast |
| [LICENCE_OUTREACH.md](LICENCE_OUTREACH.md), [GERMANY_OUTREACH_DRAFTS.md](GERMANY_OUTREACH_DRAFTS.md), [ITALY_ROMANIA_OUTREACH_DRAFTS.md](ITALY_ROMANIA_OUTREACH_DRAFTS.md) | Draft emails asking source owners for permission (owner sends) |
| [OPEN_DATA_RESEARCH_2026-11-05.md](OPEN_DATA_RESEARCH_2026-11-05.md) | Open-data research |
| [GERMANY_SOURCE_DECISION_2026-11-06.md](GERMANY_SOURCE_DECISION_2026-11-06.md), [TANKERKOENIG_SETUP.md](TANKERKOENIG_SETUP.md) | German source options and the Tankerkönig set-up |
| [ITALY_OPTIONS_2026-11-06.md](ITALY_OPTIONS_2026-11-06.md) | Italian feed options (mimit stale from some networks) |
| [ROMANIA_OPTIONS_2026-11-06.md](ROMANIA_OPTIONS_2026-11-06.md), [ROMANIA_SETUP.md](ROMANIA_SETUP.md) | Romanian sources and switches |
| [COMPETITORS.md](COMPETITORS.md) | Competitor teardown |

## Data quality
| Document | What it is |
|---|---|
| [DATA_CHECKS.md](DATA_CHECKS.md) | Automatic checks on every run |
| [DATA_ACCURACY_2026-10-08.md](DATA_ACCURACY_2026-10-08.md), [DATA_ACCURACY_2026-11-05.md](DATA_ACCURACY_2026-11-05.md) | Accuracy audits per country |
| [NOON_RULE_2026-11-06.md](NOON_RULE_2026-11-06.md), [PRICE_CYCLES.md](PRICE_CYCLES.md) | Price-timing rules and weekly price cycles |

## Product: route planner, My car, EV
| Document | What it is |
|---|---|
| [ROUTE_PLANNER_DESIGN.md](ROUTE_PLANNER_DESIGN.md), [ROUTE_RECOMMENDATIONS_2026-11-06.md](ROUTE_RECOMMENDATIONS_2026-11-06.md) | Route planner design and recommendations |
| [ROUTE_IDEAS_A_benchmarks.md](ROUTE_IDEAS_A_benchmarks.md) … [ROUTE_IDEAS_F_feasibility.md](ROUTE_IDEAS_F_feasibility.md) | Idea research (benchmarks, optimisation, PHEV/EV, trip costs, UX, feasibility) |
| [ROUTING_BACKEND_2026-11-06.md](ROUTING_BACKEND_2026-11-06.md), [ROUTING_TESTS_2026-11-06.md](ROUTING_TESTS_2026-11-06.md) | Routing proxy design and tests |
| [NAV_DEEPLINKS_2026-11-06.md](NAV_DEEPLINKS_2026-11-06.md) | Navigation-app deep links |
| [MYCAR_CLARITY_AUDIT_2026-11-06.md](MYCAR_CLARITY_AUDIT_2026-11-06.md), [PHEV_TEMPERATURE_MODEL_2026-11-06.md](PHEV_TEMPERATURE_MODEL_2026-11-06.md) | My car clarity audit, PHEV temperature model |
| [FARES.md](FARES.md), [AC_TARIFFS.md](AC_TARIFFS.md) | Ferry/bridge fares and AC charging tariffs data |
| [CHARGERS_PIPELINE.md](CHARGERS_PIPELINE.md), [CHARGER_DATA_DESIGN_2026-11-07.md](CHARGER_DATA_DESIGN_2026-11-07.md), [NOBIL_TEST_2026-11-06.md](NOBIL_TEST_2026-11-06.md) | EV charging data pipeline |
| [ELPRIS_PIPELINE.md](ELPRIS_PIPELINE.md), [ELPRIS_SOURCES_2026-11-06.md](ELPRIS_SOURCES_2026-11-06.md), [EV_PRICE_SOURCES_2026-11-06.md](EV_PRICE_SOURCES_2026-11-06.md), [EV_ALT_ENERGY_RESEARCH.md](EV_ALT_ENERGY_RESEARCH.md) | Electricity and EV price sources |
