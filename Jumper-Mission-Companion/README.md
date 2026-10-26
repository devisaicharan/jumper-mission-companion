# Jumper Mission Companion

An interactive dashboard for the Jumper crab robot in MuJoCo simulation. Give the robot a maze mission, control it with voice or hand gestures, run a focus session, or play a memory game.

## Features

| Feature | What it does |
| --- | --- |
| Maze navigation | Plans a route, follows the simulated robot position and replans around edited obstacles. |
| Voice commands | Supports typed commands and optional browser speech recognition. Uncertain speech matches ask for confirmation. |
| Hand gestures | Uses browser-based hand tracking: V to wave, palm to stop, fist for quiet, and sideways pointing for a short turn. |
| Expressions | Coordinates greetings, bows, a paw gesture, salutes and a short dance using existing Jumper motions. |
| Focus companion | Provides task names, focus/break presets, pause/resume, session history and an optional completion chime. |
| Crab Says | Plays a movement sequence for the user to remember and repeat. |

## Run on Windows

1. Install 64-bit Python **3.12 or 3.13**.
2. Open this project folder and double-click **Start-Windows.cmd**.
3. Keep the terminal open. The dashboard opens at **http://127.0.0.1:8765**.

First-time setup requires internet and space for dependencies and official robot assets. See [Windows setup](START-HERE-WINDOWS.txt).

Use **Browser 3D** for the interactive view or **2D map** for lower browser graphics load. **Stop all** or **Escape** cancels current activities. Camera and microphone are enabled only when requested.

## Deploy

[Deployment guide](DEPLOY-RENDER.md) · [Dockerfile](Dockerfile) · [Render configuration](render.yaml)

Render can serve both the dashboard and Python backend. Netlify is an optional frontend that proxies API requests to Render.

In this repository, the application is inside `Jumper-Mission-Companion/`. For a Render Web Service, select **Docker** and set **Root Directory** to `Jumper-Mission-Companion`, with Dockerfile `./Dockerfile` and health check `/healthz`. For Netlify, use that same folder as the base directory. The deployment guide's flat-root instructions apply when this folder's contents are uploaded as the repository root.

Hosted mode gives each browser a separate simulation. The default configuration allows one active robot at a time; additional visitors receive a capacity message. Session history is temporary. Free-tier performance and live deployment still require verification.

## Development

From this project folder, with dependencies installed:

```sh
python -m unittest discover -s tests
```

Recorded validation: **83 unit checks, 34 dashboard browser checks and 13 hosted browser checks passed** in the development environment. These are recorded results, not a live CI badge or a guarantee of device performance.

[Validation details](docs/VALIDATION.md) · [Build status](docs/BUILD_STATUS.json) · [Performance notes](docs/PERFORMANCE.md)

## Scope and credits

This project controls a simulation; physical robot deployment and real-world recognition accuracy are not verified. Browser speech recognition depends on browser support and may use an external speech service.

Jumper's robot model, controller and stock motion policies are provided by [KingKong Robotics](https://github.com/KingKongRobotics/jumper). The dashboard and activity coordination are this project's contribution.

Original code: [MIT licence](LICENSE). Third-party components retain their own licences; see [credits and notices](THIRD_PARTY.md).
