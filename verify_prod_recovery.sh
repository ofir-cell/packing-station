#!/usr/bin/env bash
# Read-only verification of the EXISTING legacy Production backup in the operational R2
# bucket `packing-station` (prefix backups/<day>/). Discovers the latest day, downloads it
# to an isolated dir, runs PRAGMA integrity_check on every DB, and checks the expected
# org/db inventory. NEVER writes to R2, never prints secrets.
#
# Supply ONLY operational Production R2 READ credentials via env before running
# (load from your Keychain so nothing is typed/echoed):
#   export R2_ENDPOINT="https://<ACCOUNT_ID>.r2.cloudflarestorage.com"
#   export AWS_ACCESS_KEY_ID="$(security find-generic-password -a r2op -s R2_ACCESS_KEY_ID -w)"
#   export AWS_SECRET_ACCESS_KEY="$(security find-generic-password -a r2op -s R2_SECRET_ACCESS_KEY -w)"
# Then:  bash verify_prod_recovery.sh
set -euo pipefail
BUCKET="packing-station"
: "${R2_ENDPOINT:?set R2_ENDPOINT}"; : "${AWS_ACCESS_KEY_ID:?set AWS_ACCESS_KEY_ID}"; : "${AWS_SECRET_ACCESS_KEY:?set AWS_SECRET_ACCESS_KEY}"
DEST="$HOME/prod-recovery/$(date +%Y%m%dT%H%M%SZ)"; mkdir -p "$DEST"
aws(){ command aws --endpoint-url "$R2_ENDPOINT" "$@"; }

echo "== discover latest backup day (by newest object LastModified) =="
LATEST_KEY=$(aws s3api list-objects-v2 --bucket "$BUCKET" --prefix "backups/" \
  --query 'sort_by(Contents,&LastModified)[-1].Key' --output text)
[ "$LATEST_KEY" != "None" ] || { echo "FAIL: no objects under backups/"; exit 1; }
DAY=$(echo "$LATEST_KEY" | cut -d/ -f2)
echo "latest object: $LATEST_KEY  ->  day=$DAY"

echo "== download backups/$DAY/ (read-only) to $DEST =="
aws s3 cp "s3://$BUCKET/backups/$DAY/" "$DEST/" --recursive
echo "preserved at: $DEST"

echo "== PRAGMA integrity_check on every .db =="
FAIL=0
while IFS= read -r f; do
  R=$(sqlite3 "$f" "PRAGMA integrity_check;" 2>&1 | head -1)
  T=$(sqlite3 "$f" "SELECT count(*) FROM sqlite_master;" 2>&1)
  printf '  %-50s integrity=%s tables=%s\n' "${f#$DEST/}" "$R" "$T"
  [ "$R" = "ok" ] || FAIL=1
done < <(find "$DEST" -name '*.db' | sort)

echo "== inventory check (expect: platform.db, users.json, + per-org shipments.db & giveaways.db) =="
[ -f "$DEST/platform.db" ] && echo "  platform.db: present" || { echo "  platform.db: MISSING"; FAIL=1; }
[ -f "$DEST/users.json" ] && echo "  users.json: present" || { echo "  users.json: MISSING"; FAIL=1; }
ORGS=$(find "$DEST" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null)
echo "  orgs found: $(echo "$ORGS" | tr '\n' ' ')"
for o in $ORGS; do
  for db in shipments.db giveaways.db; do
    [ -f "$DEST/$o/$db" ] && echo "    $o/$db: present" || { echo "    $o/$db: MISSING"; FAIL=1; }
  done
done
echo "  NOTE: legacy set omits stations.json + per-org csv/json by design (captured by Backup V2 post-deploy)."

[ "$FAIL" = 0 ] && echo "RESULT: PASS  (recovery copy preserved at $DEST)" || echo "RESULT: FAIL"
exit $FAIL
