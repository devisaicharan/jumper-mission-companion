# Responsiveness update — 24 October 2026

## Current update: 0.1.4

The user's running Windows dashboard was inspected through Chrome at `http://127.0.0.1:8765`. A Wave command was accepted and completed; no fault banner was present. Its simulation clock lagged the controller's elapsed-time log, so earlier low HTTP acknowledgement numbers did not establish responsive visible movement on that laptop. The new build has not yet been installed or benchmarked there.

The live robot image now uses one MJPEG stream instead of repeated frame downloads followed by 80 ms waits. Frames are 480×320; redundant collision hulls are hidden in the view. If measured simulation speed drops below 0.8× real time, automatic Eco rendering lowers refresh demand and disables shadows. It returns to Balanced after speed exceeds 0.95×. Reflection rendering is disabled. Physics, collision masks and source controller settings are unchanged.

A live speed readout reports simulation seconds per wall second. Command acceptance time and the current motion phase are displayed separately. The idle-expression queue no longer adds a 100 ms handoff delay when no motion needs cancellation. A native timing regression measured mode entry at **5 ms** of simulation time (previously **105 ms**) and policy readiness at **530 ms** after the original measured-pose handoff. These are not guaranteed wall-clock timings on Windows. At 0.5× simulation speed, those motion timings take roughly twice as long in wall time.

Testing ruled out the upstream multi-click window as a delay for these single-key bindings; no controller click-window override is shipped. The official controller, physics timestep and pose-safety thresholds remain unchanged.

The latest reports are `motion-latency-results.json`, `latency-results.json`, `slow-render-results.json`, and `BUILD_STATUS.json`. A fresh local HTTP run with the new rendering path recorded 2.35 ms median and 14.32 ms p95 acknowledgement. The artificial 700 ms render-delay regression remained responsive (13.55 ms p95). Exact timings vary by hardware and workload.

To install, close the old Jumper terminal, extract the update over the existing `Jumper-Mission-Companion` folder and replace project files, then restart `Start-Windows.cmd`. Keep the existing environment, local configuration and upstream assets. Use one dashboard tab while testing, since hiding a dashboard intentionally sends Stop. In the new dashboard, `Simulation 1.00× real time` means normal speed; values significantly below 1 explain slow motion. At 0.5× speed, one simulation second takes two real seconds.

The sections below document previous measurements and implementation versions.

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

## Consolidated 1.0.0 release — 25 October 2026

This supersedes the earlier image-rendering default. Browser WebGL now displays source meshes and measured poses; Python image rendering is off in normal use. The optional image renderer captures a private model/data snapshot before doing graphics work outside the lock. Host physics slices are capped at 20 ms. Motion/navigation use simulation time; focus/watchdog remain on wall time. Recognition is normally handled by a local worker. Read RELEASE-NOTES.md and the current BUILD_STATUS.json for acceptance results and limitations.
