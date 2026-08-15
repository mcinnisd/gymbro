# 2. In-Chat Native Interactive Chart & Action Widget Protocol (`gymbro.widget/v1`)

Date: 2026-08-15

## Context

Conversational coaching in GYMBro requires rich, interactive feedback beyond plain markdown text. When an athlete asks about biometric dips, training schedules, or nutrition goals, the AI Agent Engine must return visual, interactive widgets directly in the chat stream:
1. **Interactive Charts**: Multi-metric telemetry trends (e.g. HRV vs Sleep Score correlation) requiring smooth 60fps gesture-driven scrubbing and point inspection on mobile devices.
2. **Action Cards & Sliders**: Training plan proposals with 1-click calendar commitment, dynamic macronutrient tuning sliders with live calorie/ratio recalculation, and morning readiness schedule reschedulers.

Previously, tool returns were unstructured and ad-hoc (`{ type: "CHART", data: ... }`), making client-side gesture handling, optimistic state transitions, and interactive actions fragile.

## Decision

1. **Standardize on `gymbro.widget/v1` Protocol Envelope**:
   All agent tool calls that generate client UI emit a versioned envelope:
   ```json
   {
     "protocol": "gymbro.widget/v1",
     "widget_id": "wid_12345678",
     "widget_type": "interactive_chart" | "calendar_proposal" | "macro_slider" | "readiness_action",
     "title": "...",
     "subtitle": "...",
     "state": "proposed" | "active" | "confirmed" | "executed" | "dismissed",
     "payload": { ... },
     "actions": [
       { "id": "commit", "label": "...", "style": "primary", "action_type": "api_call", "endpoint": "/calendar/commit" }
     ],
     "emitted_at": "..."
   }
   ```

2. **Decouple 60fps Touch-Scrubbing from Message Scroll State**:
   - Interactive charts render normalized point series with discrete date coordinate mapping.
   - Pointer / touch movements update local inspector state in micro-ticks without triggering global message list re-renders.

3. **Optimistic Action State Machine**:
   - Action triggers (e.g. `Commit to Calendar`, `Save Macro Targets`, `Accept Reschedule`) transition the widget state from `proposed` to `confirmed` optimistically with green confirmation badges and haptic feedback.
   - Background dispatches post directly to `/chats/<id>/actions` or domain endpoints (`/calendar/commit`, `/nutrition/targets`).

## Consequences

- Consistent contract between Python Agent Engine tools and React Native Expo client components.
- Extensible to future widget archetypes (e.g., Bloodwork biomarker radar charts, interval session timer editors).
- Enables 60fps native performance with zero layout shift in the chat stream.
