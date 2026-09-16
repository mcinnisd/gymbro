# Athlete readiness score

`get_readiness` is the sparse-aware composite coaches previously improvised from
`get_wellness_metrics`, `get_recent_activities`, calendar context, journals, and
biomarkers. It is a **read** tool (registry + MCP + `GET /telemetry/tools/readiness`).

Athlete identity is server-bound. The tool never invents missing telemetry.

## Payload

| Field | Meaning |
|-------|---------|
| `score` | `0–100`, or `null` when no scored signals exist |
| `band` | `green` (≥70) / `yellow` (45–69) / `red` (<45) / `null` |
| `confidence` | `0–1` from coverage × freshness |
| `components[]` | Present signals only: `raw`, component `score`, `contribution`, **renormalized** `weight`, `missing: false` |
| `missing[]` | Absent signals with `reason` and `optional` |
| `as_of` | UTC date the score is computed for |
| `notes` | Short formula / freshness / penalty remarks |

## Sources (Garmin-first)

| Signal | Table / stream | Scored when |
|--------|----------------|-------------|
| Sleep | `biometrics_daily.sleep_score` (else `sleep_hours`) | Value in last 7 days |
| HRV | `hrv` / `hrv_ms` + optional `hrv_status` | Garmin status **or** personal baseline (≥3 other days). Raw ms alone is **not** scored. |
| RHR | `resting_hr` | Personal baseline (≥3 other days). Isolated RHR is omitted. |
| Body Battery | `body_battery` | 0–100 as-is |
| Stress | `stress_level` | `100 − stress` |
| Training load | `garmin_activities` (Strava secondary). Does **not** query `public.activities`. | 7d volume vs **prior** 7d. Prefer Garmin `activityTrainingLoad` when both weeks have it; else duration hours; else km. No prior week → omit (do not treat chronic as 0). |
| Residual fatigue | Same Garmin-first activity stream | Any session in last 7d. Hard sessions (keywords, ≥90 min, ≥16 km, HR ≥155, or high training load) decay over ~72h. |
| Journal | `daily_journals.answers` (optional) | Last 2 days: `energy_level`, `felt_sore`, `soreness`. Missing table → `missing[]`, not a tool error. |
| Biomarkers | Latest `lab_panels` ≤90d (optional) | Soft **penalty** after the weighted average. `PGRST205` / schema-cache miss → `missing[]`; the score still computes from Garmin. |

Optional sources (`lab_panels`, `biomarkers`, `daily_journals`, generic `activities`) **fail soft**. A missing PostgREST relation never returns `status=error` for the whole tool.

## Formula

Nominal weights (sum = 1.00):

```
sleep 0.22  hrv 0.18  rhr 0.12  body_battery 0.10  stress 0.08
training_load 0.15  residual_fatigue 0.08  journal 0.07
```

1. Drop every component with no real value.
2. Let `W` = sum of remaining nominal weights.
3. `contribution_i = score_i × (w_i / W)`
4. `score = clamp(sum(contribution_i) − biomarker_penalty, 0, 100)`

Biomarker penalty is `min(15, 4×recovery_flags + 2×other_flags)` (hs-CRP, ferritin, CK, vitamin D, testosterone, cortisol, hemoglobin count as recovery flags). A clean panel contributes `0`.

Sleep hours (only if `sleep_score` is absent): 7–9h → 100; each hour below 7 costs 25 points; hours above 9 taper slowly. This maps an **observed** duration, it does not impute a Garmin sleep score.

HRV vs baseline: `70 + 150 × (hrv − baseline) / baseline`, blended 70/30 with Garmin status when both exist.

RHR vs baseline: `70 + 200 × (baseline − rhr) / baseline` (lower is better).

Training-load ratio (acute / chronic): ≤0.8 recovered (90–100); 0.8–1.2 balanced (75–90); 1.2–1.5 accumulating (50–75); >1.5 overloaded (15–50).

## Confidence

```
coverage  = W / 1.00
freshness = weight-average of per-signal freshness (overnight wellness = 1.0; daily metrics stale after 7d)
confidence = min(0.98, coverage × (0.40 + 0.60 × freshness))
```

Sleep-only or activities-only therefore score honestly with **low** confidence. Empty windows return `score: null`, `confidence: 0`.

## Localhost checks

```bash
MOCK_DB=true PYTHONPATH=. python -m pytest tests/unit/test_readiness_tools.py -v

# live athlete (JWT-bound; never invent user_id)
curl -s "http://127.0.0.1:5001/telemetry/tools/readiness" \
  -H "Authorization: Bearer $TOKEN"
```

MCP: `tools/call` `get_readiness` (optional `as_of`). See [`docs/mcp.md`](mcp.md).
