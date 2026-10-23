# ADR-0006: Server-Sent Events for planning progress

Status: Accepted · Date: 2026-10-23 · Refs: SPEC §5.4, §7.7, §12; architecture §8.3, §10.4, §11.7

## Context
The Drive screen shows real stages («Делим путь на N дней», «Ищем отели, куда пустят с собакой», …) and road signs of future stops flying toward the viewer as they are found. The first stage must appear ≤ 1 s, plans take up to ~10 s, and the user can cancel at any time.

## Decision
`POST /v1/trips/plan` with `Accept: text/event-stream` returns an SSE stream with events `stage {key,text,progress}`, `stop {day, stop}`, `done {tripId, trip}`, `error {code,message,details}`; heartbeat comments every 5 s; nginx `proxy_buffering off`. The planner emits domain events through a `ProgressSink` port; the API bridges them from the worker thread to the async response via a thread-safe queue. Client disconnect cancels the plan through `CancelToken`. Without the SSE header the same endpoint returns the final JSON (used by tests and as a fallback). Android consumes the stream with `okhttp-sse` in a `callbackFlow`.

## Consequences
- One request, unidirectional, works through standard HTTP infrastructure and nginx; trivial to test with `curl -N`.
- POST + SSE is not supported by the browser `EventSource` API — irrelevant (native client), but tests use raw HTTP.
- Errors after the 200 header are delivered as `error` events, so clients must handle both HTTP and in-stream errors (documented in §10.4).

## Alternatives
- **WebSockets** — bidirectional not needed; heavier proxying and auth.
- **Polling a job resource** (`POST` → `202` + `GET /jobs/{id}`) — needs job storage, adds latency to the first stage.
- **Fake client-side progress** — rejected by SPEC ("real progress steps").
