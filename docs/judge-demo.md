# Judge Demo

This walkthrough demonstrates the executable control plane, not only the
generated static evidence. Use Python 3.12 so the exact lock audit matches CI.

## 1. Build The Evidence

```bash
make clean
make demo

python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade "pip==25.3"
.venv/bin/python -m pip install \
  --constraint requirements-observability.lock \
  "build==1.5.1" "setuptools==83.0.0" "wheel==0.47.0"
.venv/bin/python -m pip install \
  --no-build-isolation \
  --constraint requirements-observability.lock \
  --editable ".[runtime,test,dev]"

make verify-observability-lock PYTHON=.venv/bin/python
make runtime-contract PYTHON=.venv/bin/python
make notification-outbox-contract PYTHON=.venv/bin/python
make dashboard PYTHON=.venv/bin/python
```

## 2. Start The Live System

Terminal one:

```bash
make api-run PYTHON=.venv/bin/python
```

Terminal two:

```bash
PYTHONPATH=src .venv/bin/python -m model_observability_platform.notification_worker \
  --state-root .local --worker-id judge-demo-worker --poll-seconds 0.5
```

Open `http://127.0.0.1:8081/dashboard` and demonstrate this sequence:

1. Raise population shift, latency, and error rate, then select **Run evaluation**.
2. Show `FREEZE RELEASE`, four stable incidents, and a drained outbox.
3. Acknowledge one incident and show its new lifecycle delivery receipt.
4. Select **Send 2-window recovery** and show `CONTINUE` with zero open incidents.
5. Open `/v1/runtime`, `/metrics`, and `/docs` for machine-readable evidence.

Repeated degraded evaluations should update the same incident fingerprints.
The delivery worker should return pending and in-flight notification counts to
zero after each lifecycle action.

## 3. Generate The Narrated Video

The voice dependency is isolated from the exact runtime environment:

```bash
python3.12 -m venv .demo-venv
.demo-venv/bin/pip install -e '.[demo]'
make demo-voice PYTHON=.demo-venv/bin/python
make demo-video
```

The media path uses `edge-tts` with the `en-GB-SoniaNeural` neural voice and
word-boundary timing for synchronized captions. It then normalizes the voice to
broadcast-style loudness and encodes an H.264/AAC MP4 with a selectable English
subtitle track, crossfades, and web fast-start metadata. The result is
`docs/demo/model-observability-judge-demo.mp4`.

## Judge Narrative

- The UI submits real bounded telemetry and reflects durable API state.
- Stable fingerprints prevent alert storms while preserving occurrence evidence.
- Evaluation, incident state, audit event, and notification outbox commit atomically.
- The worker proves leases, ordering, retries, fencing, receiver idempotency, and DLQ.
- Recovery needs two healthy windows, avoiding a false green from one sample.
- Metrics, traces, and logs intentionally constrain cardinality and sensitive data.
- Airflow and Kubernetes assets are clearly separated into executed and design-only claims.
