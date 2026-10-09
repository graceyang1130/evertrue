"""Match saved timeout-audit rows to exact PFF snaps and verified playlists."""
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf'
plays = pd.read_csv(ROOT / 'data/ncaa/pbp.csv.gz', low_memory=False)
plays = plays.sort_values(['pff_GAMEID', 'pff_SORTORDER'])
audit = json.loads((ROOT / 'tos/out/report_data.json').read_text())['defense_reality']['brown_missed']
links = json.loads((OUT / 'film_playlists.json').read_text())
names = {'RIUN': 'Rhode Island', 'NJPR': 'Princeton', 'PAUN': 'Penn', 'MAHA': 'Harvard', 'CTYA': 'Yale'}
rows = []
for item in audit:
    # clock_game.defense_reality stores snap clock minus LIVE_BALL=7.
    seconds = item['clock'] + 7
    clock = f'{seconds // 60:02d}:{seconds % 60:02d}'
    match = plays[(plays.pff_GAMESEASON == item['season']) &
                  (plays.pff_QUARTER == 4) & (plays.pff_CLOCK == clock) &
                  (plays.pff_OFFTEAM == item['opponent']) &
                  (plays.pff_DEFTEAM == 'RIBR') & (plays.pff_NOPLAY != 1) &
                  plays.pff_RUNPASS.isin(['R', 'P'])]
    if len(match) != 1:
        raise ValueError(f'Ambiguous audit match: {item}')
    snap = match.iloc[0]
    following = plays[(plays.pff_GAMEID == snap.pff_GAMEID) &
                      (plays.pff_QUARTER == 4) &
                      (plays.pff_SORTORDER > snap.pff_SORTORDER)].iloc[0]
    game = int(snap.pff_GAMEID)
    row = dict(item, opponent_name=names[item['opponent']], game_id=game,
               play_id=int(snap.pff_PLAYID), snap_clock=clock,
               next_play_id=int(following.pff_PLAYID), next_snap_clock=following.pff_CLOCK,
               next_no_play=bool(following.pff_NOPLAY == 1),
               down=int(snap.pff_DOWN), distance=int(snap.pff_DISTANCE),
               field_position=int(snap.pff_FIELDPOSITION),
               film_url=links[str(game)]['url'],
               game_url=f'https://ultimate.pff.com/ncaa/games/{game}/boxscore')
    if game == 27785 and row['next_no_play']:
        row['review_note'] = 'The next audit event is a fourth-down defensive-holding no-play at 2:33. The sequence then resets to first down at 2:22. Check the penalty and abandon an assumed-punt calculation after the new first down.'
    elif game == 32154:
        row['review_note'] = 'Harvard is on Brown\'s 31, then 30. The next fourth-down snap is at 2:00 on Brown\'s 27; do not assume a punt. Check the two-minute timeout and scoring/fourth-down options.'
    elif game == 25327:
        row['review_note'] = 'Two consecutive audit intervals in one possession. Brown later won 28-27 in overtime; these are decision-review examples, not evidence that timeouts caused a loss.'
    else:
        row['review_note'] = 'Check the whistle, actual timeout counts, clock restart, subsequent conversion and eventual possession change before classifying this as an avoidable wait.'
    rows.append(row)
(OUT / 'film_index.json').write_text(json.dumps(rows, indent=2) + '\n')
md = ['# Brown end-of-game film index', '',
      f'All {len(rows)} intervals from the two-minute-adjusted audit, matched to PFF game and play IDs. Links open saved, selected-play sequences in Ultimate. Sign-in and access to the playlist/film are required. Game links are fallbacks. No shared users were added.', '',
      'To watch: open a selected-film link, click the playlist\'s play-count button, then choose **Quick Video**. The table also shows each selected snap\'s clock, down, distance and field position.', '',
      'The snap clocks below are observed PFF data labels. The audit\'s clock is snap minus an assumed seven-second live play. Its wait is snap-to-next-event elapsed time minus seven; neither is a film-measured whistle or dead-ball duration. Cut film may omit time between plays. Verify with continuous footage before changing the audit counts.', '',
      '| Game / selected film | Q4 snap → next event | PFF play ID → next ID | Brown deficit / TO | Estimated wait |',
      '| --- | --- | --- | --- | --- |']
for row in rows:
    label = f"{row['season']} {row['opponent_name']}"
    md.append(f"| [{label}]({row['film_url']}) ([game]({row['game_url']})) | {row['snap_clock']} → {row['next_snap_clock']} | {row['play_id']} → {row['next_play_id']} | {-row['lead']} / {row['timeouts']} | {row['lost']} sec |")
md += ['', '## Review priorities', '']
for row in rows:
    if row['game_id'] in [25327, 27785, 32154] and (row['game_id'] != 27785 or row['next_no_play']):
        if row['game_id'] == 25327 and row['down'] != 1:
            continue
        md.append(f"- **{row['season']} {row['opponent_name']}, {row['snap_clock']}:** {row['review_note']}")
md += ['', '## Verification record', '',
       'Playlist contents were checked against the Ultimate play grid and dedicated playlist page. The report catalog, main site sections, clock filters and video workflow were reviewed before creating the references. See ultimate_site_review.md for scope and limitations. The manifest film_playlists.json records saved selections; film_index.json records the row-level source match.', '']
(OUT / 'film_index.md').write_text('\n'.join(md))
print(f'Matched {len(rows)} audit intervals to {len(links)} verified film sequences.')
