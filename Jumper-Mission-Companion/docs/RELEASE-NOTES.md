# Mission Companion 1.0.0 — consolidated local release

Released 25 October 2026. All six planned features are integrated: gestures, voice/typed commands, maze navigation, expressive sequencing, ClawClock, and Crab Says.

## Performance architecture

The official mesh geometry is sent once to browser WebGL. Measured MuJoCo geom poses drive its animation; physics and stock ONNX policies remain native. Python's offscreen image renderer is idle in the default view, directly removing the expensive graphics path observed on the prior Windows build. The live 2D map is available when browser graphics are unavailable. Python image streaming remains an explicit diagnostic option.

Physics work is bounded to at most 20 ms of simulation per host slice. Slow machines yield between slices rather than holding the command lock for a 250 ms catch-up batch. Image rendering has its own model/data scene so scene preparation is outside the physics lock. Motor constants and ONNX input names are cached.

Hand recognition normally runs in a local worker. Recognition loading and inference were exercised on a generated blank frame in both main-thread and worker paths. A compatibility fallback is retained. Stop invalidates late voice/camera responses and disables gesture routing.

Focus timers and heartbeat safety use wall time. Motion completion and navigation timeout calculations use simulation time, avoiding false failures when the host runs below real time. The upstream controller, source collision settings and 1 ms physics integration step remain unchanged.

## Acceptance results

- 52 unit/regression tests passed.
- 12 native physics scenarios passed, including all expressive modes, focus, memory game, three maze headings and a physical obstacle replan.
- 12 dashboard/recognition browser checks passed.
- 10 native browser checks passed, including WebGL poses, view switching, graphics-loss fallback, cancellation and native mission completion.
- Native mode entry measured 5 ms of simulation time from idle, with policy readiness at 530 ms after the measured-pose handoff.
- A 100-request diagnostic run measured 1.94 ms median and 7.27 ms p95 HTTP acknowledgement with the browser-rendering server configuration.
- A separate 700 ms artificial image-render delay test measured 6.66 ms p95 acknowledgement, with no robot fault.

These are test-environment results, not promised Windows laptop timings or acoustic/webcam accuracy. See the raw JSON reports in this directory.

## Install once

Close the old server and dashboard tabs. Extract the update over the existing project, replace project files, preserve the environment/configuration/upstream assets, and run Start-Windows.cmd. Confirm v1.0.0 and Browser 3D. A matching existing server is reused; an older server produces a clear instruction to close its terminal.

Check-Performance.cmd runs a no-image physics benchmark and saves performance-report.json. The normal app does not require Node.js, Playwright or Git.

No public deployment, competition submission, video upload, physical hardware deployment, unknown-map SLAM or BE UNLIMITED .app export is included. Live Windows acceptance of this release, live microphone and live webcam accuracy remain device-dependent checks.

## 1.0.1 — view movement update

Camera tracking now uses the same interpolated pose timeline as the crab, instead of jumping directly to each network snapshot. Duplicate snapshots no longer restart interpolation. The view uses display-aligned pacing with a 60 FPS target (actual FPS depends on the device), caps rendering at one pixel per CSS pixel, merges static walls into one cached mesh, and caches vertex array bindings. The Follow crab checkbox holds the scene stationary when disabled.

52 unit tests and 12 native browser acceptance checks passed, including drag orbit, camera reset, the follow toggle, zero WebGL errors, actual obstacle replanning and graphics-loss recovery. The other simulation/recognition results above are retained from the unchanged v1.0 backend. This camera update has not yet been measured on the user's laptop.

## 1.1.0 — voice, hand feedback and focus update

Speech now shows the transcript, supported action and robot execution status. Multiple recognition alternatives are considered; missing or low confidence requires explicit confirmation before motion. Exact greeting phrases including “Hey, hi” trigger Wave. Negated and descriptive phrases remain rejected. English locale selection and microphone errors are visible.

The camera shows landmark tracking and hold progress, tolerates short tracking gaps and recognises straight foreshortened fingers more reliably. V triggers Wave, fist selects Quiet (cancel), and palm stops activity while leaving the camera ready. Stop all still disables the camera.

Focus now has task names, presets, an immediately starting 12-second demo, clear phase explanations, progress, break pause/resume, skip/end controls, server-session history and an optional chime. Leaving the dashboard preserves only the timer while stopping robot motion; completion in the background does not trigger unattended rewards. Keep the server running.

Validation: 66 unit checks, 12 dashboard checks, 12 native browser checks and 10 native input/focus checks passed, including leaving the dashboard until focus and break finish without unattended motion. Generated speech callbacks and landmark fixtures exercise native command routing; these do not measure live acoustic or webcam accuracy. See BUILD_STATUS.json and inputs-ui-results.json for the completed browser acceptance results. Windows device acceptance remains pending.

## 1.2.0 — workspace design update

The interface now uses a forest-green sidebar and original crab mark, clearer type and spacing, warm activity cards and stronger action hierarchy. Active navigation updates the breadcrumb and exposes its current state to assistive tools. Mission steps and a map legend explain navigation; voice and gesture controls have numbered sections and feedback colours. Focus presets show their selection, and timer colours distinguish focus, break and pause.

Stop all remains in a sticky header. The robot view adapts to laptop height, mobile navigation scrolls directly to activity controls, and a keyboard skip link is provided. Thirty layout checks cover every panel at 320, 390, 820, 1024 and 1440 pixels wide without horizontal page overflow. Design changes add no network requests, external fonts or animation loops. Physics and motion policies are unchanged.

66 unit checks, 34 browser interaction checks and 30 responsive panel/viewport checks passed. Keyboard skip navigation, mobile panel scrolling and sticky Stop visibility also passed. Exact results are recorded in BUILD_STATUS.json. Native physics results are retained from the unchanged 1.1.0 backend. Live Windows camera and microphone accuracy remain device-dependent acceptance checks.

## 1.3.0 — Render package and optional Netlify frontend

The separate hosted WSGI entrypoint runs behind Gunicorn, binds Render's PORT on 0.0.0.0, validates exact public origins, and uses random HttpOnly/SameSite cookies with distinct per-session command tokens. Each active visitor has an independent engine, physics model and task history. Session capacity, idle expiry, maximum lifetime and command rates are bounded. Release hosted robot destroys only that visitor’s resources and prevents pending polls from reconnecting the ended UI. The default free configuration allows one active robot; other visitors receive a capacity message rather than sharing control.

Docker and render.yaml are included. Official pinned assets are fetched at image-build time, followed by a headless native startup check. The optional Netlify build copies frontend assets and generates an API proxy rule from RENDER_BACKEND_URL; it requires Render to allow the exact Netlify origin. Hosted mode supports Browser 3D/map and disables Python image streaming. The normal Windows launcher stays on the local entrypoint.

83 unit checks and 13 local production-entrypoint/native-browser checks passed. The hosted checks cover separate cookies/tokens, actual native motion isolation, task isolation, cross-session token rejection, foreign-origin rejection, capacity messaging, release, capacity reuse and pending-poll behaviour. The native asset/controller/ONNX headless preflight passed. Existing local browser suites are rerun and their results recorded in BUILD_STATUS.json.

Docker is unavailable in this authoring environment: the full image has not been built here. No live Render or Netlify deployment has been made, no free-tier throughput guarantee is given, and actual Netlify proxy cookie forwarding remains to be checked on deployment. No video, competition entry or public repository has been published.
