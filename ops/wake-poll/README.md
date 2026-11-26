# Wake poll cron

Box cron runs `wake_poll_cron.sh` at 07:00–11:00 America/Detroit every 15 minutes.

- Every run logs `START slot=<date> <HH:MM> trigger=<cron|catchup|reboot|manual>` and `END ... exit=N` to `/workspace/gymbro-ops/wake-poll.log`. A slot with no START never ran.
- When the box was frozen (it hibernates while idle), the next run logs `box was frozen ~N min`.
- `wake_poll_catchup.sh` runs every minute in the window and at `@reboot`. If the latest slot never started and the wake-up has not fired, it runs that slot with `trigger=catchup`.
- `ensure_cron.sh` (every 10 minutes, and safe to call from any routine) restarts the cron daemon and reinstalls the crontab when needed, and logs fixes to `cron-health.log`. Cron cannot restart itself after a box rebuild, so routines that run on the box should call it too.

Promote: `git pull` in `/workspace/gymbro-prod`, then `ops/wake-poll/install.sh`.
