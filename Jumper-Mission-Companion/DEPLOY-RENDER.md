# Deploy Jumper Mission Companion 1.3.0

This package is prepared for Render. It has not been deployed to your account, and its real-time speed on Render Free has not been measured. No competition video or entry is uploaded by any deployment command.

## Recommended: Render serves the whole app

1. Extract the ZIP. Create a GitHub repository for this project and upload the **contents** of the `Jumper-Mission-Companion` folder. `Dockerfile`, `render.yaml`, `cloud_server.py` and `static` must be at the repository root. Keep all licences and third-party notices. Do not upload your `.venv`, `local-config.json`, logs, keys or the separate `jumper-upstream` directory; `.gitignore` lists the exclusions. The official assets are fetched at image-build time.
2. Sign into https://dashboard.render.com/ and choose **New → Blueprint**. Connect that repository and select its branch. Render reads `render.yaml`. Verify the compute plan says **Free** before creating the service. Alternatively choose **New → Web Service**, Docker runtime, Dockerfile `./Dockerfile`, Free plan and health-check path `/healthz`.
3. Keep `MISSION_BACKEND=native` and `MAX_SESSIONS=1`. The app reads Render's `PORT` and `RENDER_EXTERNAL_URL` automatically. Do not set `HOSTED_LOCAL_TEST` on Render. For a custom domain, set `PUBLIC_ORIGIN` to its exact HTTPS origin. Add any other trusted frontend origins to `ALLOWED_ORIGINS`, separated by commas; do not use `*`.
4. Wait for the Docker build. It downloads the pinned official source, installs dependencies and runs a headless native-model/controller/ONNX preflight. A failed preflight fails the build instead of substituting a fake robot. Native execution currently requires Linux x86_64.
5. Open the generated `https://…onrender.com` URL. Confirm **v1.3.0**, **Hosted robot session**, **MuJoCo · official model**, and the simulation-speed readout. The first visitor initializes their native robot, so this request may take longer than `/healthz`.
6. Try Expressions → Friendly, Stop all, Voice → type `wave`, then Focus → 12s demo. Enable camera/microphone yourself to test device permissions. Leave **Browser 3D** selected; **2D map** is also available. Hosted Python image streaming is intentionally disabled.
7. Click **Release hosted robot** when finished. With the default one-slot configuration, a second visitor sees a clear capacity message and never receives control of the active robot. Refreshing the active browser retains its own session. A different browser is a different visitor.

## What the free configuration does

Render's documented Free allowance is 0.1 CPU and 512 MB RAM. The simulation may be too slow or exceed memory. Test it before sharing a public link. Native model initialization is lazy; `/healthz` means the web server is up, not that a visitor has completed native initialization. Native initialization errors appear in logs and in the visitor startup message.

One server worker owns a bounded pool of simulations. Each browser gets a random HttpOnly, SameSite cookie and a distinct command token. No account is required. There is no cross-origin wildcard access. Commands are rate limited per session. This is a bounded demonstration service, not a multi-user production platform.

The default limits are one active visitor, five minutes after the last request for idle non-focus sessions, and two hours maximum lifetime. A running or paused focus session survives the idle cleanup but is still subject to the maximum lifetime. Closing a tab stops robot actions through the existing heartbeat safety; its resources are reclaimed after the idle interval. A visible dashboard keeps its own slot active. Use Release to free it immediately.

Session data, task history and game scores are in memory only. Render restart, redeploy or idle shutdown clears them. A background focus timer cannot survive the hosting service shutting down. The local Windows version remains available for longer/private sessions.

Render Free sleeps after 15 minutes without incoming traffic and can take around a minute to wake. Bandwidth/build quotas also apply. Do not add artificial keep-alive traffic. If the native service is too slow, choose a suitable paid instance only after reviewing its price, or use the local Windows version. Setting `MISSION_BACKEND=preview` is an explicitly labelled schematic demo, **not** the complete native simulation and not evidence of physical robot behaviour.

## Optional: Netlify frontend with Render backend

Render alone already hosts the interface. Use this option only if you specifically want a Netlify frontend address; it does not remove the need for Render compute.

1. Deploy and test the Render app first.
2. Create a Netlify site from the same repository. The included `netlify.toml` sets the build command to `python3 tools/build_netlify.py` and publish directory to `netlify-dist`.
3. In Netlify's build environment, set `RENDER_BACKEND_URL` to the exact Render HTTPS origin, such as `https://your-service.onrender.com`. There is no trailing API path. The build validates the URL and generates an `/api/*` proxy rule, while keeping assets and the local hand model on Netlify. Missing configuration fails the build clearly.
4. In Render, add the exact Netlify HTTPS origin to `ALLOWED_ORIGINS` (for example `https://your-site.netlify.app`). Preserve your Render origin via its automatic `RENDER_EXTERNAL_URL` or explicit `PUBLIC_ORIGIN`. Redeploy/restart as required.
5. Open the Netlify address and repeat the tests above. The proxy must preserve the session cookie and Origin. Visitors using the Render and Netlify addresses get different browser-cookie sessions and compete for the same bounded pool. Preview deployment origins are not automatically allowed.

The generated Netlify assets and proxy configuration are tested locally. Actual Netlify proxy behaviour, cookie forwarding and free-plan timeouts still need an acceptance check on your live deployment. Render Free cold starts may exceed a proxy timeout; if that happens, open the Render URL directly and allow it to wake, then retry Netlify. Never fix an origin error by disabling the origin check.

## Troubleshooting

| Symptom | Check |
|---|---|
| Build fails while downloading | Check the GitHub source URL/network and retry the build. The pinned source is about 500 MB extracted. |
| Preflight says unsupported platform | Use Linux x86_64; the shipped upstream runtime does not cover every architecture. |
| First page load says simulation could not start | Read Render logs for native initialization, memory or dependency errors. The app never silently changes to preview. |
| The hosted robot is in use | Release the other session or wait for its idle expiry. Increase `MAX_SESSIONS` only after measuring memory and CPU. |
| 403 on command | Check exact HTTPS origins and Netlify proxy settings. Cookies and the per-session token are both required. |
| 401 or session expired | Reload to acquire a fresh session. Old task history is gone. |
| Camera/mic fails | Open the HTTPS page directly and check browser permissions; speech-service availability varies by browser/device. |
| Slow robot | Check the speed readout; switch to 2D to reduce browser work. The free server's CPU remains a limit. |

## Local hosted testing

The normal Windows launcher is unchanged. To test the hosted entrypoint on Linux with the optional cloud requirements installed:

```sh
pip install -r requirements-cloud.txt
PUBLIC_ORIGIN=http://127.0.0.1:10000 HOSTED_LOCAL_TEST=1 UPSTREAM_DIR=/absolute/path/to/jumper-upstream python cloud_start.py
```

`HOSTED_LOCAL_TEST=1` allows HTTP test cookies; it must be absent on public hosting. Open http://127.0.0.1:10000. Gunicorn binds to 0.0.0.0; use this only on a trusted development machine/network.

With Docker installed, you can additionally build and run the actual image:

```sh
docker build -t jumper-companion .
docker run --rm -p 127.0.0.1:10000:10000 -e PUBLIC_ORIGIN=http://127.0.0.1:10000 -e HOSTED_LOCAL_TEST=1 jumper-companion
```

## Verification scope

See `docs/hosted-ui-results.json` and `docs/BUILD_STATUS.json`. Automated checks exercise the real Gunicorn entrypoint and native MuJoCo backend with independent browser contexts. They do not establish live Render/Netlify performance. Docker is not installed in the authoring environment, so the complete Docker image build has not been executed here; Render must perform that final check.

Official platform references checked 25 October 2026:
- https://render.com/docs/web-services
- https://render.com/docs/blueprint-spec
- https://render.com/docs/free
- https://render.com/docs/compute-plans
- https://docs.netlify.com/manage/routing/redirects/rewrites-proxies/
