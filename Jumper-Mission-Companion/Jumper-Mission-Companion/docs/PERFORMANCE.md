# Responsiveness update — 24 October 2026

The original native server rendered and compressed a 960×640 frame while holding the physics/command lock. On a slow graphics path this blocked both commands and state polling. The new renderer owns a separate thread and private scene/data snapshot: only scene preparation uses the lock; GPU readback and JPEG compression happen outside it. Frames are now 640×426, with a target interval of 100 ms. Actual frame rate depends on the device. A rendering error is displayed without shutting down the controls.

The dashboard updates state every 100 ms, avoids rewriting unchanged text/log entries, and sends Stop before waiting for camera shutdown. Stop also invalidates late speech callbacks and pending camera permission/device responses. Monotonic snapshot revisions reject older responses even across simulation resets.

## Measurements

`tests/latency_check.py` sends 100 heartbeat/Stop requests while another client requests native frames. These are local HTTP acknowledgement times, not speech-recognition latency, physical motion onset, or Windows measurements. See the adjacent JSON reports for actual samples and environment-dependent timings.

The baseline measured 493.95 ms median, 3301.50 ms p95 and 6501.75 ms maximum. The first optimised run measured 3.59 ms median, 17.41 ms p95 and 32.02 ms maximum. A separate regression injects a 700 ms delay into every GPU readback and requires p95 acknowledgement below 500 ms. It passed with 1.71 ms median, 8.40 ms p95 and 13.88 ms maximum. These are short diagnostic runs; they are not guaranteed laptop performance. Other test workloads and CPU/GPU scheduling can affect the exact comparison.

## Reproduce

From the configured project environment:

```text
python -m unittest discover -s tests
python tests/native_check.py
python tests/latency_check.py
```

The browser integration runners require a separately installed Playwright/Chromium test environment; normal app startup does not require them. On Windows PowerShell, the artificial slow-render regression can be run with:

```powershell
$env:MISSION_TEST_SLOW_RENDER='1'
python tests/latency_check.py docs/slow-render-results.json
Remove-Item Env:MISSION_TEST_SLOW_RENDER
```

The stock motion controller retains its own pose transitions. Hand gestures retain their deliberate dwell filter. Browser speech recognition still depends on its service and waits for a final transcript. These contribute to visible response time independently of HTTP acknowledgement.

## Install the update

Close the old dashboard/server first. Extract the updated ZIP fully and run `Start-Windows.cmd` from its project folder. Keep your existing `jumper-upstream` asset folder; setup validates the pinned source before reuse. Do not run the launcher inside the ZIP viewer. The package version is 0.1.2 in `docs/BUILD_STATUS.json`.

The connected browser did not have this user's local Jumper dashboard open during verification. Windows execution, actual webcam/microphone performance and the exact installed copy therefore remain unverified.
