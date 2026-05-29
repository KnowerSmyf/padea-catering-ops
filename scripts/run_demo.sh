#!/usr/bin/env bash

set -e

START_DATE="2026-05-01"
DAYS=7

# Change this after first generated run if needed.
DEMO_ORDER_ID="${DEMO_ORDER_ID:-order_2026_05_01_sess_loreto_college_monday}"

echo ""
echo "============================================================"
echo "PADEA CATERING OPS DEMO"
echo "============================================================"
echo ""
echo "Keep Streamlit open in another terminal:"
echo "  streamlit run dashboard.py"
echo ""
echo "Optional: keep confirmation watcher open in another terminal:"
echo "  python -m scripts.check_confirmation_deadlines --watch --interval 5"
echo ""

read -p "Press Enter to reset generated demo state..."

echo ""
echo "============================================================"
echo "1. Reset generated order state"
echo "============================================================"

python - <<'PY'
from padea_ops.db import get_client

client = get_client()

# Clean generated order/output layer.
# This removes stale imported demo orders as well as generated orders.
client.table("order_lines").delete().neq("order_line_id", "__never__").execute()
client.table("orders").delete().neq("order_id", "__never__").execute()

client.table("exceptions").delete().in_("source", [
    "generate_weekly_orders",
    "demo_order_lifecycle",
    "check_confirmation_deadlines",
    "demo_backup_caterer",
]).execute()

print("Cleaned orders, order_lines, and generated/demo exceptions.")
PY

read -p "Press Enter to generate weekly order drafts..."

echo ""
echo "============================================================"
echo "2. Generate weekly order drafts"
echo "============================================================"

python -m scripts.generate_weekly_orders --start "$START_DATE" --days "$DAYS" --write --replace

echo ""
echo "Open/refresh the dashboard now. You should see generated draft orders."
echo "Also inspect output/email_drafts and output/distribution_sheets."
echo ""
read -p "Press Enter when ready to walk one order through lifecycle..."

echo ""
echo "============================================================"
echo "3. Show selected demo order"
echo "============================================================"
echo "Using DEMO_ORDER_ID=$DEMO_ORDER_ID"
echo "Override with: DEMO_ORDER_ID=<order_id> bash scripts/run_demo.sh"
echo ""

python -m scripts.demo_order_lifecycle show --order-id "$DEMO_ORDER_ID"

read -p "Press Enter to approve selected order..."

echo ""
echo "============================================================"
echo "4. Approve order"
echo "============================================================"

python -m scripts.demo_order_lifecycle approve --order-id "$DEMO_ORDER_ID"

read -p "Press Enter to send order to caterer with short confirmation deadline..."

echo ""
echo "============================================================"
echo "5. Send order to caterer"
echo "============================================================"

python -m scripts.demo_order_lifecycle send --order-id "$DEMO_ORDER_ID" --confirmation-minutes 1

echo ""
echo "Refresh dashboard. Status should be sent_to_caterer."
echo ""
echo "If watcher is running, wait about 60 seconds and it should mark this overdue automatically."
echo "If not running watcher, press Enter and the demo will run a one-off deadline check."
echo ""

read -p "Press Enter to run one-off confirmation deadline check..."

echo ""
echo "============================================================"
echo "6. Automatic overdue check"
echo "============================================================"

python -m scripts.check_confirmation_deadlines

echo ""
echo "Refresh dashboard. If deadline has passed, status should be confirmation_overdue."
echo "If not overdue yet, wait a moment and rerun:"
echo "  python -m scripts.check_confirmation_deadlines"
echo ""

read -p "Press Enter to mark backup required..."

echo ""
echo "============================================================"
echo "7. Mark backup required"
echo "============================================================"

python -m scripts.demo_order_lifecycle require-backup --order-id "$DEMO_ORDER_ID"

echo ""
echo "Refresh dashboard. The order should now be backup_required and a high-severity exception should exist."
echo ""

read -p "Press Enter to run backup caterer flow..."

echo ""
echo "============================================================"
echo "8. Backup caterer flow"
echo "============================================================"

# Use your backup script. Adjust args depending on your implemented interface.
# Preferred version: backup script takes --order-id.
python -m scripts.demo_backup_caterer --order-id "$DEMO_ORDER_ID" --write

echo ""
echo "If backup profiles are missing, this should generate an outreach list."
echo "Production extension: SMS/email preference form to affected families."
echo ""

read -p "Press Enter to simulate an absence email..."

echo ""
echo "============================================================"
echo "9. Simulate family absence email"
echo "============================================================"

python -m scripts.demo_process_absence_email \
  --student-id stu_henry_hill_moreton_bay_boys_college \
  --session-id sess_moreton_bay_boys_college_tuesday \
  --absence-date 2026-05-02 \
  --raw-text "Hi Padea, Henry is sick and won't be attending tutoring this week."

echo ""
echo "Regenerating weekly orders so the absence affects the order state..."
python -m scripts.generate_weekly_orders --start "$START_DATE" --days "$DAYS" --write --replace

echo ""
echo "Refresh dashboard and inspect the Moreton Bay Boys distribution sheet."
echo "Henry should be removed from the relevant order."
echo ""

read -p "Press Enter to simulate a preference update..."

echo ""
echo "============================================================"
echo "10. Simulate preference update"
echo "============================================================"

python -m scripts.demo_update_preference \
  --student-id stu_henry_hill_moreton_bay_boys_college \
  --caterer-id cat_lakehouse_victoria_point \
  --preferred-menu-item-id menu_lakehouse_victoria_point_05

echo ""
echo "Regenerating weekly orders so the preference update affects the order state..."
python -m scripts.generate_weekly_orders --start "$START_DATE" --days "$DAYS" --write --replace

echo ""
echo "Refresh dashboard and inspect the distribution sheet / order lines."
echo ""

read -p "Press Enter to run edge-case tests..."

echo ""
echo "============================================================"
echo "11. Run edge-case tests"
echo "============================================================"

python -m scripts.test_order_edge_cases

echo ""
echo "============================================================"
echo "DEMO COMPLETE"
echo "============================================================"
echo ""
echo "What this demonstrated:"
echo "- weekly order generation from Supabase state"
echo "- generated email drafts and distribution sheets"
echo "- order lifecycle: approved → sent → overdue → backup_required"
echo "- automatic overdue detection"
echo "- family absence update affects future orders"
echo "- preference update affects future orders"
echo "- edge-case tests for exclusions and absences"
echo ""