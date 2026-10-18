# Worker and dispatch investigation

The dispatcher already reuses a persistent HTTPX client for claims. Each execution
has its own HTTPX client, reused for bootstrap, checkpoints, inference and completion,
and closed at completion. Tokens and clients are not shared between executions.
No transport or checkpoint semantics were changed.

The dispatcher submits jobs while slots remain free. `wait(FIRST_COMPLETED)` applies
only while all configured worker slots are occupied. LISTEN is registered before the
durable empty check, uses no transaction during waiting and has a bounded fallback.
Capacity release wakes the waiters. Claim identity is preserved on transport retry.

The recorded queue interval starts at execution creation, before admission commits.
The first instrumented stage-1 warm sample at index 2 has 147.9 ms queue, comprising
91.7 ms before commit and 56.2 ms after commit. The accepted response is still built
inside the admission transaction; in these three diagnostic samples that work took
24–40 ms. Moving it outside the transaction needs a separate concurrency proof and
has not been done. The queue metric has not been redefined to hide admission cost.

SDK profile on the pinned Windows environment, synthetic internal HTTP, no external
sockets or database, measures construction of InternalClient to its first inference
request. Imports are already complete. There are 30 warm observations per variant;
cProfile runs are separate and excluded from percentiles.

| Granted professional functions | Before median / p95 | After median / p95 |
| --- | ---: | ---: |
| None (`execute` is supplied by the SDK) | 144.8 / 213.2 ms | 39.2 / 56.9 ms |
| All 11 | 145.1 / 209.5 ms | 154.1 / 226.2 ms |

The original implementation inferred all 11 Pydantic tool schemas on every run and
then discarded excluded tools. The change filters function names first and decorates
only permitted functions. Each selected function still closes
over its own execution, and server authorization remains unchanged. With all functions
permitted there is no demonstrated speedup; Linux installed-profile measurements must
determine the contribution to the end-to-end result.

The subsequent Linux diagnostic found 75 ms worker CPU before inference, with only
8 ms in graph construction; six custom functions are actually offered alongside six
SDK tools. This justified the additional static schema cache in `_runtime_tool`.
It caches only Pydantic argument classes, never functions, clients, leases or grants.
Each wrapper is newly bound to its own execution. Scope is one worker process, key
is function name, compiled code identity, complete signature and documentation, and
the LRU limit is 11 entries. A changed definition misses the key; module reload or
process replacement clears the cache. Grant filtering occurs before cache lookup;
server revocations still apply at each operation.

The paired installed-grant microbenchmark offers the exact same 12 names on both
sides, including all SDK file tools. With cache disabled/enabled, 30 warm samples
give median 50.2 / 20.8 ms and p95 54.5 / 25.2 ms. The first invocation is 59.5 /
64.2 ms: this cache has no claimed cold benefit. These samples are
`worker-sdk-installed-no-cache.json` and `worker-sdk-installed-cache.json`.
For all 11 custom functions, cached warm median/p95 is 30.7/40.3 ms
(`worker-sdk-cache-all.json`). That report also compares all exact schemas after
cache hits with immutable source commit `a9e58ed73d65d7e59dcf6f23ee814f3668f413d1`.

Raw before samples remain in `../latency-optimization-20261017-b/worker-sdk-profile.json`
and `worker-sdk-before-all.json`. After samples are `worker-sdk-after-minimal.json` and
`worker-sdk-after-all.json` here. `worker-schema-comparison.json` verifies all 11 exact
SDK JSON schemas against pre-change HEAD, including defaults, types and required fields.

Seven focused tests pass: excluded tools skip construction even after a warm grant,
all permitted schemas
preserve server arguments, and `read_output` retains runtime injection and exact tool
identity through the real SDK graph. Two consecutive real InternalClients retain
independent callbacks; eight concurrent first uses share one schema with eight
independent closures; weak references prove cached schemas retain neither callback
nor execution marker; changed signatures invalidate and the 11-entry bound holds.
The existing 12 runtime tests also passed with
the production change, including recovery, cancellation, concurrency and retry identity.
A PostgreSQL test was added for a saturated queue, committed capacity release and
identical claim replay; its execution belongs to the root agent's isolated DB suite.

Reproduce the focused SDK checks from the repository root:

```powershell
rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\ops\agent_probe\.venv\Scripts\python.exe -m unittest discover -s ops/agent_chat -p test_professional_tool_preparation.py -v
rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\ops\agent_probe\.venv\Scripts\python.exe ops/agent_chat/latency_worker_profile.py --count 31 --tools all
rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\ops\agent_probe\.venv\Scripts\python.exe ops/agent_chat/latency_worker_profile.py --count 31 --tools installed --schema-cache disabled
rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\ops\agent_probe\.venv\Scripts\python.exe ops/agent_chat/latency_worker_profile.py --count 31 --tools installed
```

This microbenchmark does not measure server/SQL preparation, actual transport, model
latency, or a completely cold process. No conclusion about the real model is inferred.

## Admission follow-up

Professional admission now reuses the context already prepared by execution creation
for its local preparation. The private `_begin_execution_with_context` returns three
values; public `begin_execution` still returns exactly `(execution, token)`. The
fresh validation after history, assets and job construction remains, as do download,
claim and provider boundaries. General document admission remains unchanged because
it inserts inputs between its two authorization operations.

There is no new cache. The reused context is limited to local preparation in the same
admission call. The database admission lock does not prevent administrative revocation;
the final authorization remains responsible for observing it before commit.

Five focused SQLite tests passed after this change in 0.201 seconds. They verify the
public tuple contract, one initial plus one final context, and grant, connection and
blocking-policy changes injected after initial context. Each changed-authority case
returns 403 with no queued job, no new prompt/input/execution rows and no provider
requests. This deterministic interleaving tests fresh observation and rollback; it is
not a measurement of independent concurrent database sessions.

```powershell
rtk proxy C:\Users\javi\Documents\Codex\regulai-platform\.venv\Scripts\python.exe regulai/manage.py test front.test_agent_admission_context --settings=regulai.test_settings --noinput -v 2
```
