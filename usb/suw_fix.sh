#!/system/bin/sh
# Fix stuck Google SetupWizard & incompatible OTA updates on gbOS86

LOG=/postinstall/gbos/logs/suw_fix.log
mkdir -p "$(dirname "$LOG")"
echo "--- suw_fix starting ---" > "$LOG"

# Wait for system settings service to be available
READY=0
for i in $(seq 1 30); do
  if settings get global device_provisioned >/dev/null 2>&1; then
    READY=1
    echo "Settings service ready after ${i}s" >> "$LOG"
    break
  fi
  sleep 1
done

if [ "$READY" -ne 1 ]; then
  echo "WARNING: Settings service timed out" >> "$LOG"
fi

# 1. Mark global device provisioning
settings put global device_provisioned 1 >> "$LOG" 2>&1

# 2. Iterate over all users (e.g. 0 and 10 on desktop)
USERS=$(pm list users 2>/dev/null | sed -n 's/.*UserInfo{\([0-9]*\):.*/\1/p')
[ -z "$USERS" ] && USERS="0 10"

for u in $USERS; do
  echo "Processing user $u" >> "$LOG"
  settings --user "$u" put secure user_setup_complete 1 >> "$LOG" 2>&1
  pm disable-user --user "$u" com.google.android.setupwizard >> "$LOG" 2>&1
  pm disable-user --user "$u" com.google.android.desktop.setupwizard >> "$LOG" 2>&1
  pm disable-user --user "$u" com.google.android.gms/.update.SystemUpdateActivity >> "$LOG" 2>&1
  am start -a android.intent.action.MAIN -c android.intent.category.HOME --user "$u" >> "$LOG" 2>&1
done

# 3. Disable packages globally
pm disable com.google.android.setupwizard >> "$LOG" 2>&1
pm disable com.google.android.desktop.setupwizard >> "$LOG" 2>&1
pm disable com.google.android.gms/.update.SystemUpdateActivity >> "$LOG" 2>&1
stop update_engine >> "$LOG" 2>&1

echo "--- suw_fix completed ---" >> "$LOG"
