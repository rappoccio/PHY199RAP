#!/usr/bin/env bash
# Discovery run for the Blair Mountain figures whose File: titles did not resolve.
# Run from the lecture folder:
#     bash ../../tools/discover_blair_media.sh | tee discovery.txt
# Then send discovery.txt (or just the `yes` lines) back to Claude.
set -u
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/fetch_lecture_media.py"
run () { echo; echo "############ $1"; python3 "$S" --search "$1" 2>&1; }

# --- the ones that matter most (no picture on those slides at all) ---
run "Battle of Blair Mountain"
run "West Virginia mine wars miners 1921"
run "Sid Hatfield"
run "Bill Blizzard"
run "Don Chafin"
run "coal scrip token"
run "company store coal town"

# --- section 1-2 ---
run "Lehigh Canal anthracite"
run "coal breaker boys Pennsylvania"
run "Lackawanna Steel Buffalo"
run "Susquehannock"

# --- section 3 ---
run "Ludlow tent colony ruins 1914"
run "Pan-American Exposition Electric Tower 1901"
run "Rough Riders San Juan Hill 1898"

# --- section 4-5 ---
run "Pullman Illinois company town"
run "Lead Belly Huddie Ledbetter"
run "Ku Klux Klan parade Washington 1928"

echo
echo "############ DONE"
echo "Send back the lines marked 'yes'. Or re-run any single one with --json"
echo "to get a paste-ready manifest entry, e.g.:"
echo "    python3 $S --search \"Sid Hatfield\" --json"
