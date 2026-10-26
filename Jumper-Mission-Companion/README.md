# Jumper Mission Companion 1.3.0

A local robot simulation with six integrated activities: hand gestures, voice commands, maze navigation, expressive movements, ClawClock focus sessions, and the Crab Says memory game. The robot uses the official Jumper model, compiled controller and existing motion policies.

## Hosting on Render / optional Netlify

See **DEPLOY-RENDER.md** for the complete steps. The included Dockerfile and Render Blueprint prepare the native backend; Netlify can optionally serve the interface through an API proxy. Hosted visitors get separate cookie sessions and robot state. The free configuration permits one active visitor, with a clear busy message for others. Hosted image rendering is disabled; Browser 3D and the live map retain native physics.

This is a prepared deployment package, not a live deployment. Free-tier speed, the Docker image build, and actual Netlify proxy/cookie behaviour still require acceptance on those services. The Windows launcher remains separate.

## Start on Windows

1. Close every older Jumper terminal.
2. Extract the entire ZIP into `D:\jumperlab`. When updating, replace the project files inside your existing `Jumper-Mission-Companion` folder. Keep its `.venv`, `local-config.json` and the neighbouring `jumper-upstream` folder.
3. Double-click `Start-Windows.cmd`. The dashboard opens at `http://127.0.0.1:8765`.
4. Confirm **v1.3.0** below the robot view. Leave **Browser 3D** selected.

A first installation needs 64-bit Python 3.12 or 3.13, internet, and space for the Python environment and roughly 500 MB of official robot assets. Setup downloads the pinned source archive and installs dependencies automatically. This is a Python application, not a standalone EXE. Git is not required for a fresh install.

## Use the six features

| Feature | What to do |
|---|---|
| Maze mission | Open Mission control and click Start mission. Click a free map cell to add an obstacle and replan. Reset returns the robot and map to the start. |
| Voice | Open Voice & gestures. Type `hi`, `wave`, `bow`, `start mission`, `turn left`, `start focus`, or `stop`, then Send. For microphone input, select your English variant and enable voice. Read Heard and the action receipt; low-confidence commands need the displayed Confirm button. |
| Hand gestures | Enable hand camera. Hold V for Wave, a fist for Quiet, or point sideways for a short turn. Watch the hand overlay and hold-progress bar. Open palm stops activity while keeping the camera ready. Quiet cancels motion rather than playing an animation. Release a sign before repeating it. |
| Expressions | Choose Friendly, Curious, Joyful, Grateful or Confident. Stop all/Escape cancels the motion. |
| ClawClock | Enter a task, choose a preset or durations, then Start focus. Jumper greets you, stays quiet during work, then celebrates for the break. The 12s demo starts immediately. Pause/Resume also works during breaks; Skip break and End session are explicit controls. Completed tasks appear in this server session’s history. The completion chime is optional. |
| Crab Says | Start a game, watch the sequence, then answer with the four buttons after Your turn. Next round adds one movement. |

Use **Stop all** or **Escape** at any time. Use one dashboard tab. Leaving the page cancels robot motion and turns off camera/microphone. A focus timer continues quietly while the server remains running, without unattended celebration. Stop all or End session cancels it. Camera and microphone start off.

## Interface update

The 1.3.0 design adds a forest-green workspace, clearer action cards, a live activity breadcrumb, selected focus presets and phase colours, mission steps and map legend. Stop all remains visible while scrolling. Mobile navigation takes you directly to the selected controls. A keyboard skip link, visible focus outlines and reduced-motion support are included. No remote fonts or extra animation loops are loaded.

## Performance and views

The default **Browser 3D** view displays source mesh geometry at the actual measured MuJoCo poses. Python image rendering is idle, avoiding the expensive graphics path observed on the previous Windows installation. Drag to orbit, scroll to zoom, or Reset camera. Uncheck Follow crab to keep the scene stationary while the crab moves.

**2D map** uses the same real physics with the lowest graphics load. **Python image** retains the MuJoCo image renderer as an optional diagnostic fallback; it can be slow on some laptops. Changing views does not change physics or policies.

The speed readout compares simulation time with real time: 1.00x is normal speed; 0.50x means one simulation second takes two real seconds. If the new build is still slow in 2D mode, run `Check-Performance.cmd` after closing the app. It writes `performance-report.json`; startup errors are recorded in `windows-startup.log`.

Commands run between short physics slices. Recognition normally runs in a local worker so it does not block the interface. Timers and disconnect protection use real elapsed time; motion completion and navigation use simulation time so a slow machine does not create false timeouts.

## Verification

See `docs/BUILD_STATUS.json` for this release's exact results, `docs/VALIDATION.md` for scope, and `docs/PERFORMANCE.md` for measured timings. The browser tests cover native meshes, all view modes, command routing, Stop, focus, the game, map edits, local recognition loading, and mobile layout. These are test-environment measurements. This version still needs acceptance on the user's Windows hardware, real webcam and microphone.

The project controls simulation only. It does not include physical robot deployment, SLAM, new trained choreography or a BE UNLIMITED `.app` export. Nothing has been uploaded, submitted or published.

## Development

Use the configured environment:

```text
python launch.py --open-browser
python -m unittest discover -s tests
python tests/native_check.py
python tests/motion_latency.py
python tests/latency_check.py
```

Optional browser tests use Playwright 1.51.1 and Chromium (`package.json`). Run `python tests/run_ui.py` and `python tests/run_native_ui.py` from the project folder after installing that test environment. `python tests/run_inputs_ui.py` checks generated speech-service events and landmarks routed into native physics. These fixtures do not measure real microphone or webcam accuracy. Normal use does not need Node.js or Playwright.

Third-party licenses and provenance are in `THIRD_PARTY.md`; original supervisor, UI and rendering code use the included MIT license.
