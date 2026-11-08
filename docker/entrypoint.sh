#!/bin/sh
# Run Pressarr as PUID:PGID, like the other *arr images.
#
# - PUID/PGID unset: runs as root, as before (existing installs keep
#   working with their root-owned files).
# - Compose `user:` / `docker run --user`: already not root, nothing to do.
# - UMASK (optional, e.g. 002) applies to the files Pressarr writes.
set -e

if [ -n "$UMASK" ]; then
    umask "$UMASK"
fi

if [ "$(id -u)" != "0" ] || [ -z "$PUID$PGID" ]; then
    exec "$@"
fi

PUID=${PUID:-0}
PGID=${PGID:-0}

if [ "$PUID" = "0" ] && [ "$PGID" = "0" ]; then
    exec "$@"
fi

# The ids may already belong to an image account (-o allows duplicates).
if ! getent group "$PGID" >/dev/null; then
    groupadd -o -g "$PGID" pressarr
fi
if ! getent passwd "$PUID" >/dev/null; then
    useradd -o -u "$PUID" -g "$PGID" -d /config -M -s /usr/sbin/nologin pressarr
fi

echo "Pressarr runs as uid=$PUID gid=$PGID"

# /config holds the database and config Pressarr writes at every start;
# files left by a run as root are taken over too. /magazines and
# /downloads are only checked: they can be large or on a network share,
# their owner is the operator's to set.
mkdir -p /config
if [ -n "$(find /config \( ! -user "$PUID" -o ! -group "$PGID" \) -print -quit)" ]; then
    chown -R "$PUID:$PGID" /config
fi
for dir in /magazines /downloads; do
    [ -d "$dir" ] || continue
    # An empty one (fresh install, or not mounted) is cheap to hand over.
    if [ -z "$(ls -A "$dir")" ]; then
        chown "$PUID:$PGID" "$dir" 2>/dev/null || true
    fi
    if ! setpriv --reuid="$PUID" --regid="$PGID" --clear-groups test -w "$dir"; then
        echo "Warning: $dir is not writable by uid=$PUID gid=$PGID (chown it on the host)"
    fi
done

exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups "$@"
