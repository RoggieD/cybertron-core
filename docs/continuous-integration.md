# Continuous integration

The `CyberTron CI` GitHub Actions workflow runs on every branch push, pull requests
targeting main, and manual dispatch. Independent Ubuntu jobs run:

- Python 3.12: install `backend/requirements.txt`, then the complete backend test suite.
- Node 24: install frontend dependencies, run all `tests/*.test.mjs`, then `npm run build`
  (TypeScript checking followed by the Vite production build).

No backend tests are excluded. Jobs have 15-minute timeouts, read-only repository
permissions, and cancellation of superseded runs on the same ref. CI does not deploy,
refresh reference knowledge, or require GM-AI01 services, local certificates, or secrets.
Passing CI is automated regression coverage, not a live infrastructure inspection.

## Frontend dependencies and certificates

The existing `frontend/package-lock.json` does not include the declared `@types/node`
dependency. CI intentionally uses `npm install --no-package-lock` and checks that the
lockfile remains unchanged. This resolves the version ranges in `package.json`; frontend
dependency installation is not fully reproducible until the lockfile is reconciled.
Changing the preserved lockfile is a separate maintenance task. After that task, switch
the install step to `npm ci` and consider an npm cache keyed to the lockfile.

The Vite config loads HTTPS certificates only for the development server (`serve`).
Production builds need no certificates. The existing development HTTPS configuration
and API/WebSocket proxies are preserved.

## Reading results

Open the repository's Actions tab and select `CyberTron CI`. Both `Backend tests`
and `Frontend tests and build` must pass. A green workflow does not enforce branch
protection; required-check rules are a separate repository setting.

The known test-client dependency deprecations and Vite bundle-size warning remain
visible. They are warnings, not suppressed failures.
