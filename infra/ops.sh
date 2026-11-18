#!/usr/bin/env bash
# Day-to-day checks on the live app (read-only).
#   infra/ops.sh status    # alarms, recent traffic and errors
#   infra/ops.sh logs      # follow the API log live
#   infra/ops.sh errors    # API errors from the last 24 hours
#   infra/ops.sh cost      # this month's AWS cost so far
set -euo pipefail

ENV="${SAMPCUP_ENV:-prod}"
FN="sampcup-${ENV}-api"
LOGS="/aws/lambda/${FN}"

since() { date -u -v-"$1" +%s 2>/dev/null || date -u -d "$1 ago" +%s; }

case "${1:-status}" in
  logs)
    aws logs tail "$LOGS" --follow --format short
    ;;
  errors)
    QUERY='fields @timestamp, method, path, status, ms, @message
      | filter status >= 500 or @message like /Traceback|ERROR/
      | sort @timestamp desc | limit 50'
    ID=$(aws logs start-query --log-group-name "$LOGS" --start-time "$(since 24H)" \
      --end-time "$(date -u +%s)" --query-string "$QUERY" --query queryId --output text)
    while true; do
      OUT=$(aws logs get-query-results --query-id "$ID" --output json)
      STATUS=$(echo "$OUT" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
      [ "$STATUS" = "Complete" ] && break
      sleep 1
    done
    echo "$OUT" | python3 -c "
import sys, json
rows = json.load(sys.stdin)['results']
print(f'{len(rows)} error lines in the last 24 hours')
for row in rows:
    f = {c['field']: c['value'] for c in row}
    print(f.get('@timestamp'), f.get('status', ''), f.get('path', ''), f.get('@message', '')[:160])"
    ;;
  cost)
    START=$(date -u +%Y-%m-01)
    END=$(date -u -v+1d +%Y-%m-%d 2>/dev/null || date -u -d tomorrow +%Y-%m-%d)
    aws ce get-cost-and-usage --time-period "Start=$START,End=$END" --granularity MONTHLY \
      --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE \
      --query 'ResultsByTime[0].Groups[].[Keys[0],Metrics.UnblendedCost.Amount]' --output text \
      | awk '$2 > 0.0001 {printf "%-45s $%.4f\n", $1, $2; total += $2} END {printf "%-45s $%.4f\n", "TOTAL", total}'
    ;;
  status)
    echo "Alarms:"
    aws cloudwatch describe-alarms --alarm-name-prefix "sampcup-${ENV}" \
      --query 'MetricAlarms[].[StateValue,AlarmName]' --output text | sed 's/^/  /'
    echo "Last hour:"
    for METRIC in Invocations Errors Throttles; do
      VALUE=$(aws cloudwatch get-metric-statistics --namespace AWS/Lambda --metric-name "$METRIC" \
        --dimensions Name=FunctionName,Value="$FN" --start-time "$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
        --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --period 3600 --statistics Sum \
        --query 'Datapoints[0].Sum' --output text)
      echo "  $METRIC: ${VALUE/None/0}"
    done
    ;;
  *)
    sed -n '2,6p' "$0"
    exit 1
    ;;
esac
