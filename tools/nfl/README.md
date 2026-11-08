NFL dashboard builder (from the Nov 8 2026 build). Expects /home/claude/nfl/data.json (MKB pull: proj, dvp, games, def, per-book boards) and links.json (per-book ON/NJ slip links).
python3 gen.py && python3 render.py. Every leg carries a colour tag (red/yellow/green): exploit-board rank when the board is available, otherwise the DvP lens (red 85+, yellow 75-84, green <75).
