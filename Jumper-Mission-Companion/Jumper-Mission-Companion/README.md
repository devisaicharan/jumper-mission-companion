# Jumper Mission Companion

Six integrated features for the open-source Jumper robot, running in a local dashboard with a real MuJoCo simulation host. **No competition submission, video upload or public deployment is performed.**

This is a simulation development build. It is not a physical robot controller, a newly trained motion policy, or an importable BE UNLIMITED `.app`. It uses the official Jumper mesh model, compiled controller and existing ONNX motion policies. Our original work is the interaction supervisor, voice and gesture command routing, navigation planner/follower, focus activity, memory game, dashboard and independent simulation host.

## The six features

| Feature | Implementation | Important boundary |
|---|---|---|
| Hand gestures — high effort | Local MediaPipe hand landmarks, normalized gesture rules, dwell filtering, held-sign latch, tracking-loss handling | Live webcam performance needs validation on your laptop; synthetic landmark tests do not establish recognition accuracy |
| Voice interface — high effort | Browser microphone input plus exact closed-vocabulary parser, confidence threshold and command routing | Browser speech service may process audio remotely; live microphone recognition remains device dependent. Typed commands exercise the same parser |
| Maze navigation — high effort | Footprint-aware A*, occupancy grid, body-frame measured-pose follower, stall/clearance stops | Uses the known simulator map and pose, not camera SLAM or unknown-obstacle perception. Map edits activate/deactivate preallocated native collision walls and trigger replanning; this is operator-supplied map information, not sensor detection |
| Expressive interaction — high effort | Bounded, acknowledged motion sequencing, semantic states, supported cancellation, completion detection and timeouts | Gestures/dance policies are upstream work. A celebration is a five-second excerpt of the existing crab dance, not original trained choreography |
| ClawClock — medium effort | Configurable focus/break timer, pause/resume, one completion reward and explicit session restart | Keep dashboard open; heartbeat loss cancels activities. This is not an unattended desktop notification service |
| Crab Says — medium effort | Seedable variable-length memory sequences, acknowledged demonstrations, locked answer phase, scoring and progressive rounds | Buttons or voice can answer; only V-sign wave is mapped from camera to game answers |

## Run on your Windows laptop

Prerequisites: **64-bit Python 3.12 or 3.13**, and Chrome or Edge. The official robot assets occupy roughly 500 MB; allow additional disk space for installation. Initial setup requires internet. Git is no longer required for a fresh install.

1. Download the ZIP and use **Extract All** into a folder such as `D:\JumperLab`.
2. Open the extracted folder that contains **Start-Windows.cmd**.
3. Double-click **Start-Windows.cmd**. It runs first-time setup automatically and opens the browser when the local dashboard responds.
4. Keep the command window open while using the app. First setup can take several minutes.

If startup fails, the launcher stays open and writes **windows-startup.log** in the extracted folder. Send the last 15–20 lines of that log for diagnosis. See `START-HERE-WINDOWS.txt`. Do not run files from inside the ZIP preview.

This is a Python application, not a standalone `.exe`. The launcher looks for an existing Python installation; it does not silently install Python or change Windows security settings. Setup downloads the pinned official source into staging, verifies the archive, installs an isolated Python environment and runs the unit tests. It refuses to overwrite an unrecognized existing source folder.

Manual alternative:

```powershell
py -3.12 setup.py
.venv\Scripts\python.exe launch.py --open-browser
```

On Linux/macOS: run `python3 setup.py`, then `.venv/bin/python launch.py`. Headless Linux requires EGL support; Windows/macOS rendering depends on the local OpenGL driver. **The development run was Linux; Windows/macOS execution is not claimed as verified.**

For a lightweight logic preview without MuJoCo dependencies:

```bash
python server.py --backend preview
```

The preview is deliberately labelled kinematic and schematic. The default `--backend native` fails visibly if dependencies or official assets are missing; it never silently falls back to the preview.

## Commands

Voice/typed examples: `Jumper say hello`, `bow`, `offer paw`, `salute`, `celebrate`, `curious`, `turn left`, `turn right`, `start mission`, `start focus`, `pause focus`, `resume focus`, `start game`, `next round`, `quiet`, `stop`.

Commands must match complete supported phrases. A sentence such as “explain how to solve maze” does nothing. Confidence below 0.65 is rejected except for the explicit stop vocabulary, which uses 0.35. This does not make speech a certified stop mechanism.

Camera gestures: open palm = stop, V-sign = wave, fist = cancel optional motions, one index finger pointing sideways = a short turn. Hold deliberately, then lower your hand before repeating the same sign. The displayed camera is mirrored and left/right classification follows that displayed view. Hand images stay in the browser; only coordinates reach the loopback server.

**Stop all / Escape** clears current activities and requests the official controller's supported motion exit. Closing or hiding the page requests the same stop; a two-second heartbeat watchdog handles a lost page. None of these is a physical emergency stop. No physical actuation code is included.

## Tests and evidence

```bash
python -m unittest discover -s tests -v
python -m tests.native_check
```

For native checks, install requirements and supply `--upstream PATH` if needed. The native checks verify file hashes, compiled-controller reference replay, ONNX reference inference, exact requested motion modes, stop/cancel, focus activity, memory game and maze navigation. Results are written to `docs/native-results.json` only after the complete acceptance run passes.

Optional UI checks:

```bash
npm install
npx playwright install chromium
python tests/run_ui.py
```

The UI test launches an isolated test browser; it never controls your ordinary browser. It checks desktop/mobile UI, typed voice routing, Escape, focus pause/resume, game answers, mission commands and loading/running the actual bundled hand-landmark model on a blank image. It does not prove webcam or microphone accuracy.

See `docs/VALIDATION.md` for measured results and remaining acceptance work. UI test scripts generate dashboard screenshots for local inspection; these browser captures are not bundled in the ZIP. `docs/native-bright.png` is an actual MuJoCo physics rendering, not physical robot evidence.

## Architecture

`server.py` serves a loopback-only dashboard and owns the simulation loop. `mission/engine.py` owns activity arbitration. `perception.py`, `navigation.py` and `activities.py` implement the six features. `mission/native.py` loads the official FSM extension, verifies its bundle file hashes, pairs all 22 joints by name, runs official ONNX policies and applies their targets/gains to MuJoCo using the source motor torque-speed and thermal model.

The native host is independent of the upstream mjlab host. Passing the bundled controller reference checks validates arithmetic on recorded inputs; it does **not** establish complete physics parity, hardware transfer or full upstream deployment certification. No gains, joint limits, learned policies or robot mechanical geometry are modified.

## Privacy and attribution

All ordinary control, planning, logs and hand detection stay local. The app makes no analytics calls. Speech recognition is the browser's optional service and may send audio to that provider; enable it only if you accept that service's behavior. No API key is required. Do not expose the loopback development server publicly.

Original Mission Companion code: MIT. Jumper and MediaPipe components retain their own licenses. See `THIRD_PARTY.md`. The upstream code checkout is fetched separately, not redistributed inside this ZIP. No winner or competition-readiness guarantee is implied.
# Responsiveness update (0.1.2)

Rendering no longer blocks robot commands. Stop is sent immediately, pending camera/speech callbacks are cancelled, and the dashboard avoids unnecessary redraws. See `docs/PERFORMANCE.md` for measured acknowledgement times, test commands and update instructions. Measurements are from the test environment; Windows and live camera/microphone acceptance remain pending.

