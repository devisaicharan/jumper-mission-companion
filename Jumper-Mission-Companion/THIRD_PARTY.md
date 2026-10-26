# Third-party components and provenance

## Jumper — downloaded separately by setup.py

Source: https://github.com/KingKongRobotics/jumper

Pinned source commit: `b2e58669848a3ba4f209597cd6bebdfe9d0533a4`.

Copyright 2026 KingKong Robotics. Maintainer-owned materials are Apache-2.0; third-party components keep their respective terms. The source checkout's LICENSE and NOTICE remain authoritative. Our ZIP does not embed the source checkout, mesh files, trained ONNX models, motion trajectories, RKNN files or compiled controller runtimes. The local native host reads those files from the separately installed checkout and verifies the loaded bundle files' SHA-256 digests.

The upstream example bundle's compiled-controller provenance may predate its containing source checkout. Its `bundle.json` records the actual runtime commits. We do not rewrite those records or claim that the packaged binary was rebuilt by this project.

The browser 3D display reads visual mesh buffers from the locally installed model and displays them at measured MuJoCo geom poses. It does not ship a separate robot mesh copy in this ZIP or replace the native physics/controller. The original browser renderer is MIT-licensed; robot geometry keeps its upstream license.

Jumper motions used: existing hello, bow, paw, salute and crab dance. Our interaction labels and sequencing do not make the underlying motions original choreography. The native host was independently written against the documented host contract and current upstream implementation; no full mjlab physics-parity certification is claimed.

## Bundled MediaPipe vision runtime

`static/vendor/vision`: selected unmodified files from `@mediapipe/tasks-vision` **0.10.32**, fetched using npm. Source: https://www.npmjs.com/package/@mediapipe/tasks-vision

Copyright The MediaPipe Authors / Google. Apache License 2.0. Full license: `docs/LICENSE-Apache-2.0.txt`. The original inline license notices remain in the unmodified runtime and WebAssembly loader files.

`static/vendor/hand_landmarker.task`: official float16 Hand Landmarker model bundle version 1, downloaded from:

https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task

Official model documentation: https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/index

The linked Hand Tracking model card identifies Apache License 2.0. The model is intended for experimental landmark tracking, with performance limitations under occlusion, gloves, poor lighting and blur. Our gesture rules do not establish accuracy across users or conditions. No identity recognition is implemented.

`docs/vendor-integrity.json` records the exact shipped vision asset sizes and SHA-256 digests.

## Installed dependencies

MuJoCo, ONNX Runtime, NumPy, Pillow and PyYAML are installed through pip in an isolated virtual environment; Gunicorn is an optional hosted WSGI server installed through `requirements-cloud.txt`; its MIT licence remains with its package. Playwright is an optional development test dependency through npm. They are not redistributed as installed environments in this ZIP. Refer to their distributions for their own license and notice files.

## Original code

Original code, UI and documentation are under the included MIT license. No claim is made to third-party trademarks, robot design, learned policies or model weights.
