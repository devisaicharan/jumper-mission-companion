# Jumper Mission Companion

An interactive MuJoCo simulation dashboard for the Jumper crab robot, with voice and hand-gesture controls, maze navigation, expressive movements, focus sessions and the Crab Says memory game.

## Get started

The application lives in **[Jumper-Mission-Companion/](Jumper-Mission-Companion/)**.

- **Windows:** install 64-bit Python 3.12 or 3.13, open that folder and run `Start-Windows.cmd`. Keep the terminal open; the dashboard runs at http://127.0.0.1:8765.
- **Usage and development:** [project README](Jumper-Mission-Companion/README.md).
- **Hosting:** [Render and optional Netlify guide](Jumper-Mission-Companion/DEPLOY-RENDER.md). For a Render Web Service, use Docker and set Root Directory to `Jumper-Mission-Companion`, Dockerfile to `./Dockerfile`, and health check to `/healthz`.

## Status

Version **1.3.0** includes local simulation and a prepared hosted backend with separate visitor sessions. Recorded development validation includes 83 unit checks, 34 dashboard browser checks and 13 hosted browser checks. These are recorded results; live cloud performance is not verified.

This is a simulation project, not verified physical-robot software. The default hosted configuration allows one active visitor and stores session history temporarily.

## Credits

The robot model, controller and existing motion policies come from [KingKong Robotics / Jumper](https://github.com/KingKongRobotics/jumper). This project adds the dashboard and activity coordination.

[Original-code licence](Jumper-Mission-Companion/LICENSE) · [Third-party notices](Jumper-Mission-Companion/THIRD_PARTY.md)
