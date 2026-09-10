# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Table 'iwmsdbGovernment...' doesn't exist` | Pulled code, didn't migrate (migrations are gitignored) | `makemigrations app` then `migrate` |
| `django.db.utils.OperationalError: Access denied` | Wrong `DB_USER`/`DB_PASSWORD`, or missing `.env` | Check `.env` exists and matches the MySQL user |
| `Can't connect to MySQL server ... (timed out)` in production | Trying to reach the host DB via the docker bridge instead of `network_mode: host` | Confirm `docker-compose.prod.yml` still has `network_mode: host` and no `ports:` |
| `no configuration file provided` / compose can't find services | Missing `-f docker-compose.prod.yml` on a production command | Always pass `-f docker-compose.prod.yml` in prod; local dev needs no `-f` |
| `ps` shows a `db` container in production | Regression to the old containerized-DB setup | Should not exist in prod — investigate what started it |
| `systemctl restart` succeeds but nothing works | `Type=simple` reports success on spawn, not readiness | `sleep 5 && systemctl is-active iwms-government-backend` |
| "I edited the systemd unit but nothing changed" | Installed unit at `/etc/systemd/system/` and repo copy have drifted | `sudo cp deploy/systemd/iwms-government-backend.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl restart ...` |
| `DisallowedHost at /` | Address missing from `ALLOWED_HOSTS` | Add it in `config/settings.py` |
| Browser: "blocked by CORS policy" | Frontend origin not matched | Add a regex to `CORS_ALLOWED_ORIGIN_REGEXES` in `config/settings.py` |
| `401 Unauthorized` on every call | Access token expired (5h lifetime) | Use `login/refresh-token`, or log in again |
| Refresh also fails after 7 days | Refresh token lifetime expired | Log in again |
| Everyone logged out at once | `SECRET_KEY` changed — it signs both access and refresh JWTs | Restore the key, or accept a one-time re-login |
| `ImproperlyConfigured: SECRET_KEY` | `.env` missing or `SECRET_KEY` empty | Fill it in |
| Deleted a file, Django still imports it | Stale `__pycache__` | `find . -name __pycache__ -exec rm -rf {} +` |
| `makemigrations` says "no changes" but the table is wrong / conflicting migration files appear | Migration state out of step with models (expected since migrations aren't shared via git) | Locally: drop and rebuild the DB; on shared/prod DBs, resolve manually — never blind-delete migration history on a DB with real data |
| Uploaded images 404 after deploy | `DEBUG=False`, so Django no longer serves `media/` itself | Confirm the `./media:/app/media` volume mount is present and has the files |
| OTP / reset mail never arrives | `EMAIL_*` misconfigured, or SMTP blocks the login | Verify `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD`; Gmail needs an app password |
| Push notifications silently never send | `FIREBASE_CREDENTIALS_PATH` unset or pointing at a path that doesn't exist in the container | Confirm the path in `.env` and that the file is mounted into the container |
| Route optimisation fails | `ORS_API_KEY` missing or over quota | Check the key in `.env` |
| No trips generated overnight | The in-process scheduler thread didn't fire (`ENABLE_DAILY_TRIP_JOB_SCHEDULER=false`, container restarted at the scheduled time, or the DB lock race was lost) | Check logs around the scheduled time; backfill with `manage.py generate_daily_trips --date <missed-date>` (idempotent) |
| A staff member sees zero rows they should have access to | No `StaffDataScope` row resolves for them — default-deny, not a bug | Grant them a `StaffDataScope` for the right geography level |
| Tests fail on MySQL-specific behavior | Tests run on SQLite in-memory (`config.test_settings`) | Expected — verify manually against MySQL if it matters |
| `sudo: a password is required` in a CI step | Command string isn't an exact match in `deploy/sudoers/iwms-runner` | Use the exact allowed command, or add the new one to the sudoers file |
| A command works for you but fails in CI | Your shell had a cached `sudo` timestamp; the runner (`iwmsuser`) has a narrow allow-list | Re-test with `sudo -k` then `sudo -n ...` |
| Permission denied writing `static/` or `media/` | Docker created the directory as `root` via a bind mount | `chgrp`/`chmod`/setgid the shared tree back to the deploy group |
| Deploy is green but the code looks old | The persistent deployment clone lagged `main` | Confirm the workflow's "Sync the deployment directory" step ran |

## Logs

```bash
journalctl -u iwms-government-backend.service -f
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs --since 24h backend | grep generate_daily_trips
```

Apache is running on the host but its `iwms-government` reverse-proxy vhost
is **not currently installed** (verified — only the stock default site is
enabled), so `/var/log/apache2/iwms-government-*.log` does not exist yet.
Production is reached directly on `:9001` today. See the frontend's
`helpDoc/04-cicd-flow.md` for the full detail.
