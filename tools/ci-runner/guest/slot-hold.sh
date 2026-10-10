#!/bin/bash
# slot-hold LOCK WORKER_PID READY_FILE SLOT -- hold one factory-ci job slot until WORKER_PID exits.
# Exits 75 at once if the slot is taken. Started only by job-started.
exec 9<"$1"
flock -n 9 || exit 75
umask 022
printf '%s %s %s %s %s\n' "$$" "$4" "${GITHUB_REPOSITORY:-?}" "${GITHUB_RUN_ID:-?}" "$(date -u +%FT%TZ)" >"$3.tmp"
mv "$3.tmp" "$3"
exec tail --pid="$2" -f /dev/null
