# Live API streams

The `stream` command reuses a registered service and its origin/expiry/authentication checks. It connects only for the requested operation; loading a skill starts no connection, viewer, watcher or daemon. HTTP streams currently support SSE, NDJSON and incremental UTF-8 text. WebSockets, bidirectional protocols and arbitrary binary framing need their actual protocol adapter; do not claim this HTTP path covers them.

```powershell
python -B <KH-root>/scripts/kh_api.py stream <service> --method POST --path /actual-stream-path --body-file <public-request.json> --protocol auto --mapping <display-mapping.json> --output-dir <absolute-task-artifacts>
```

Set streaming in the request body as the provider actually requires. `--protocol auto` recognizes `text/event-stream`, `application/x-ndjson`, `application/ndjson` or `text/plain`. Choose a known explicit protocol for another documented media type. The command does not silently turn an ordinary JSON response into a stream.

## Event contract

Stdout is flushed JSONL, one record per observed update, with monotonic `seq` and actual `elapsed_seconds`. It starts with `request_started`, then `connected`, data/presentation events, and finally `connection_closed`. Keep real-time consumers attached while the command runs. Poll the owning process/session's new output without waiting for its exit; display an `artifact.path` preview when received and forward meaningful status/text/summary changes promptly. Do not expose base64 blobs, authentication headers or encrypted thought signatures to the user.

Kinds include `data`, `text_delta`, `summary_delta`, `status`, `phase`, `tool_call`, `tool_result`, `progress`, `image_preview`, `artifact`, `usage`, `completed` and `error`. Without a mapping, JSON records retain their JSON types under `data`; non-JSON SSE data and plain text become text deltas. Empty dispatched SSE data still preserves its event metadata. Comments and undispatched incomplete SSE tails are not invented events. Raw API data is untrusted and structured credential fields/known registered secrets are masked. Mapped text channels also guard credential values split across deltas. Full records remain available within the configured bounds; keep host previews concise without destroying the underlying API data, and map actual binary output as artifacts. Artifacts containing known credential bytes are rejected before persistence.

An explicit terminal mapping produces `completed`/`provider_error`; EOF without such a terminal is `stream_closed`, with `terminal_received:false`. These identify the mapped stream ending, not application success. Preserve and inspect the provider's actual outcome: for example, Gemini can emit `interaction.completed` with `provider_status:"incomplete"` after a token limit. Report that incomplete answer rather than claiming full completion. Store a provider's actual job id in the mapping if later status/reconciliation needs it. No stream automatically retries or resumes a mutation or replays a `Last-Event-ID`.

## Generic mapping

This non-secret JSON uses exact names and selected fields, not executable code or provider-specific routing:

```json
{
  "rules": [
    {"event": "job.progress", "kind": "progress", "fields": {"percent": ["progress_percent"]}},
    {"event": "job.delta", "kind": "text_delta", "fields": {"text": ["delta", "text"]}, "channel": ["job_id"]},
    {"event": "job.done", "kind": "completed", "fields": {"usage": ["usage"]}}
  ]
}
```

- `event` matches the SSE event name; without one the JSON `type` or `event_type` is used. `when` optionally adds scalar conditions, such as `[{"path":["delta","type"],"equals":"text"}]`. The first matching rule wins.
- `fields` selects public display values through lists of object keys/array indices. Missing optional fields are omitted; text kinds still require a `text` string. An error rule reserves `data` for its original provider envelope; use another name for a selected display field. `channel` optionally identifies a text stream and must select a string/integer.
- `artifact: {"path":["b64_json"],"format":"png"}` saves a complete base64 artifact event only to an explicit absolute `--output-dir`. Supported formats are PNG, JPEG, WebP, GIF and opaque `bin`; image signatures are checked. The receiver generates exclusive filenames and returns path/format/byte metadata. It never uses a provider-supplied path. Fragmented binary assembly is not inferred.
- `terminal` is boolean, defaulting to true for `completed`/`error`. Optional top-level `done_marker` recognizes a documented data marker such as `[DONE]`. Unmatched mapped events retain only their event metadata. Mapped errors also retain their sanitized original data so a missing optional display field does not hide a nested provider error. The transport's `x-request-id`, when present, is retained in connection records for diagnosis.

A `progress` record reports the provider's selected numbers. Do not derive a generation percentage from elapsed time, preview index, token count or number of events. If the API has no progress percentage, show its real stages and previews. Distinguish a public reasoning summary from a model's hidden internal reasoning. Report streamed tool requests/results without automatically executing them.

## Provider examples

- [OpenAI image mapping](streams/openai-images.json): use the Image API with actual `stream:true`, `partial_images` and PNG output. It displays preview artifacts as they arrive and the final image. GIF output currently does not support streaming. See [official image streaming events](https://developers.openai.com/api/reference/resources/images/generation-streaming-events).
- [Gemini Interactions mapping](streams/gemini-interactions.json): use `/v1beta/interactions`, actual `stream:true`, and `generation_config.thinking_summaries:"auto"` when the selected model supports it. Text/public thought summaries and steps are mapped; summaries may be absent. See [official streaming](https://aistudio.google.com/docs/streaming). The same receiver works with another API's independently configured mapping.

These examples describe public API events. They do not grant access to host-native ImageGen percentage cards or the host's internal reasoning UI. Use supported host rendering/updates and accurately identify any separate viewer or replay.

Verify the requested display capability before promising it. If the host cannot show that UI, state the limitation; do not substitute a browser, separate window or custom viewer without the user's request or agreement. A running command log is not a visible progress card, and receiving only a final image does not verify intermediate-image display.

## Limits, cancellation and cleanup

Defaults: 180 seconds overall, 30 seconds idle, 64 MiB total, 8 MiB per event/line, 10,000 wire events, and at most 64 text channels. CLI overrides are bounded and validated. The streaming JSON request has a 1 MiB bound; error bodies retain the existing 1 MiB bound. Redirects do not forward credentials. Transport requests identity encoding and rejects another content encoding. Proxy configuration is not inherited by the streaming HTTP connection in this version; environments requiring a proxy need a justified adapter.

Ctrl+C/callback failure/deadline/error/terminal completion closes the response, owned connection and socket. A cancelled local connection does not prove a remote background job was cancelled; use only the provider's documented cancellation operation when actually authorized. Exit codes are `0` for completed or clean transport EOF, `2` for API/stream failure, `130` for local cancellation. Inspect the last `connection_closed` status and terminal flag as well as the code. Release task-owned sessions/listeners when the live consumer finishes, preserve user deliverables and shared host services, and verify actual exit.
