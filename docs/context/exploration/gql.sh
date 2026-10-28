#!/usr/bin/env bash
# usage: gql.sh <query-file> [variables-json]  -- read-only exploration of the panel
S=$(dirname "$0")
q=$(cat "$1"); v=${2:-null}
python3 -I -c 'import json,sys; print(json.dumps({"query":sys.argv[1],"variables":json.loads(sys.argv[2])}))' "$q" "$v" \
 | curl -sk --max-time 15 -u "$(cat "$S/.auth")" -H 'Content-Type: application/json' --data-binary @- ${PANEL:-https://stage.tourney.esportal.xyz}/api/ui/graphql/query
