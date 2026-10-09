import sys,json,html
from pathlib import Path
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
ROOT=Path(__file__).resolve().parents[1]
film=json.loads((ROOT/'output/pdf/film_index.json').read_text())
def film_link(game,label):
 url=next(r['film_url'] for r in film if r['game_id']==game)
 return f'<link href="{url}" color="#694133">{label}</link>'
styles=getSampleStyleSheet()
styles.add(ParagraphStyle(name='TitleX',fontName='Helvetica-Bold',fontSize=25,leading=28,textColor=colors.HexColor('#382218'),spaceAfter=16))
styles.add(ParagraphStyle(name='HeadX',fontName='Helvetica-Bold',fontSize=13,leading=16,textColor=colors.HexColor('#382218'),spaceBefore=12,spaceAfter=7))
styles.add(ParagraphStyle(name='BodyX',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=9))
styles.add(ParagraphStyle(name='SmallX',fontName='Helvetica',fontSize=7.6,leading=9.6,spaceAfter=5,textColor=colors.HexColor('#525252')))
styles.add(ParagraphStyle(name='CellX',fontName='Helvetica',fontSize=9,leading=12))
pages=[]
def page(title):
 p=[('title',title)];pages.append(p);return p
def body(p,t):p.append(('body',t))
def head(p,t):p.append(('head',t))
def small(p,t):p.append(('small',t))
def table(p,headers,rows,widths):p.append(('table',(headers,rows,widths)))
p=page('End-of-game clock management')
small(p,'BROWN FOOTBALL  |  STAFF REPORT  |  6 OCTOBER 2026')
body(p,'<b>Recommendation:</b> Make the clock plan explicit before each late possession: the opponent’s timeouts, the next down, whether the clock will restart, and whether the two-minute timeout has occurred. When trailing and time is scarce, assign an immediate defensive timeout trigger. When leading, distinguish a verified kneel-out from a possession that still requires a first down.')
head(p,'What we studied')
body(p,'The question is how Brown should preserve time while trailing and exhaust it while leading. This report reviews the existing PFF analysis, the prior timeout report, the staff kneel chart, and the development records. The clock arithmetic is useful now. The work does not yet establish the best run, pass, punt, or field-goal decision in every situation.')
table(p,['Finding','Evidence','Staff implication'],[
['Defensive timeouts preserve a substantial clock interval.','33.5 seconds between plays on 6,833 national clock-running, four-minute runs.','When a timeout is needed, call at the whistle.'],
['Brown has specific decisions worth reviewing.','The revised screen has 17 flags after setting aside nine two-minute-affected sequences. Brown called timeout in eight.','Review these sequences on film and agree on the trigger.'],
['Clock-killing depends on execution.','National four-minute snaps had a median 5 seconds left on the play clock; only 35% were at 3 or less.','Use a rehearsed late-snap procedure.'],
['A kneel-out is an arithmetic question.','The staff chart assumes 4-second plays and 38 seconds of play-clock use; existing tools use other assumptions.','Check the actual clock state before using a threshold.']
],[155,185,164])
head(p,'Where the evidence comes from')
body(p,'The national timeout dataset contains 5,578 games, 773,020 modeled scrimmage snaps, and 35,040 reconstructed timeouts, with season labels 2023-2026 through week 4. Brown contributes 32 games: 10 in each of 2023-2025 and 2 in 2026. These are the downloaded sample’s counts; completeness of every national game was not independently established. [1-3]')
small(p,'The national clock summaries and defensive audit were rerun from the available play-by-play on 6 October. “Flagged” means the existing heuristic recommends a timeout; it does not mean a coach’s error has been established. Sources and review details appear on page 5.')
p=page('1. Trailing: preserve the useful seconds')
body(p,'A defensive timeout removes the wait between plays. It cannot recover the seconds spent on the play itself. On national four-minute runs with a running clock, the measured average is 7.1 seconds of live play plus 33.5 seconds between plays: 40.6 seconds from snap to snap. Brown’s two-minute passing sample has 16.0 seconds between plays (61 intervals). These are estimates conditional on the clock continuing to run, not the saving from every timeout. [1,2]')
head(p,'A practical trigger, with defined limits')
body(p,'For a running clock, no imminent automatic stoppage, and an expected punt if the defense gets stops, compare our timeouts with the dead-ball intervals remaining before the punt. If time is scarce and we can cover every interval, start immediately. The next-down count includes the wait before the punt snap.')
table(p,['Their next down','Waits before an assumed punt','Immediate trigger'],[['1st','4','Cannot cover all with 3 timeouts'],['2nd','3','3 timeouts'],['3rd','2','2 or 3 timeouts'],['4th','1','At least 1 timeout']],[120,205,179])
body(p,'With fewer timeouts than waits, postponing one can preserve the same total clock if the offense fails to convert and the waits are interchangeable. That is the case for waiting. It is not a universal instruction: a first down, fourth-down attempt, natural stoppage, or the two-minute timeout changes the sequence. Reassess after every play.')
head(p,'A sequence to review')
body(p,film_link(25327,'2023 Princeton: Q4 3:31, 2:46 and 2:01')+' shows two consecutive flagged intervals with Brown down seven and three timeouts. The audit estimates 38 seconds between plays in each interval. Review the whistles and the possession’s finish. Brown won 28-27 in overtime: the sequence illustrates available clock, not a loss caused by timeout use. [2,8]')
head(p,'What the Brown audit actually shows')
body(p,'The original last-five-minutes audit identified 26 immediate-call situations with Brown trailing by 1-16. The revised screen sets aside nine because the average no-timeout path reaches the automatic timeout before the expected punt. Brown called timeout in eight of the remaining 17. Nine noncalls averaged 37.9 seconds; eight began with all three timeouts. The adjusted FCS call rate was 50.4% across 979 flags, and the Ivy rate was 65.5% across 84. [1,2]')
small(p,'These are repeated situations, sometimes within one possession. Brown’s 50% rate has an approximate 95% Wilson interval of 32%-68%, even before accounting for within-game dependence. This sample cannot establish that Brown is worse than the league. The prior “44 seconds a game” figure divides by games containing eligible audit situations, not all 32 Brown games.')
p=page('2. Leading: verify the kneel-out')
body(p,'When a lead can be protected by exhausting the clock without surrendering possession, victory formation removes the need to gain yards. When it cannot, the offense still needs a conversion or a plan for returning the ball. A conservative call is not automatically the call that gives the best chance to win.')
head(p,'The staff chart and the model answer different clock states')
body(p,'The supplied chart assumes each play lasts 4 seconds and the offense uses 38 seconds of the play clock. Its first-down, one-timeout entry is 1:28. That matches three kneels and two full waits: 3 × 4 + 2 × 38 = 88 seconds. This calculation needs a usable running-clock wait before the first snap. [4]')
body(p,'If the clock is stopped and restarts at the first snap, three kneels against one immediate opponent timeout instead provide only one usable wait between those kneels: 3 × 4 + 1 × 38 = 50 seconds. Any further play must be checked separately. A fourth-down kneel is safe only if the clock expires before possession can pass to the opponent; negative field position and safety risk also matter.')
head(p,'Three required checks')
table(p,['Check','Why it changes the answer'],[['Running or stopped clock?','Count a pre-snap wait only if the game clock actually runs. Use the play clock remaining, not an assumed full interval.'],['Two-minute timeout pending or taken?','The automatic stoppage can erase a planned wait. A play crossing 2:00 must be timed through the stoppage.'],['How many safe plays remain?','Track the down, opponent timeouts, space for kneel losses, and whether a fourth-down play ends the game.']],[160,344])
body(p,'The chart’s highlighted no-timeout windows (2:01-2:07 and 2:41-2:53 after first down) recognize the free stoppage near 2:00. They should be rehearsed as specific sequences, not applied to every play length and clock state. The current clock-kill function uses 2 seconds live plus 39 seconds dead per kneel and does not explicitly model the two-minute timeout or initial clock state. The prior interactive report instead uses measured national kneel averages of 4.2 plus 31.5 seconds. Those are three different conventions. [1,4,5]')
head(p,'Execution can change the margin')
body(p,'National clock-running four-minute snaps had a median 5 seconds left on the play clock. Snapping at 1 rather than 5 would consume 4 additional seconds on that wait; three comparable running-clock waits would consume 12. This is available clock only when the clock runs and no timeout intervenes. Brown’s tagged sample is too small for a reliable team estimate: 7 running intervals for runs, 2 for passes, and 3 for kneels. [1,2]')
small(p,'The 95 Brown “kill-regime” runs in the older runoff file use a different situation definition and historical sample. They must not be combined with the seven PFF-tagged, clock-running intervals as if they measured the same population.')
p=page('3. What the evidence can support')
head(p,'“We should save the timeouts for our offense.”')
body(p,'There is a valid reason to save one: an offensive timeout can prevent the final possession from ending with the clock running. But the measured dead-ball interval is about 34 seconds against a clock-killing opponent versus 16 in Brown’s hurry-up passing sample. Prefer the defensive use when the offense can still finish its drive without it. If spending every timeout leaves no workable offensive finish, retain one. A two-score deficit does not remove the need to complete the first score.')
head(p,'“We should always run when protecting a lead.”')
body(p,'Runs can keep the clock moving, but a failed series returns the ball. When kneeling cannot end the game, conversion probability, turnover risk, field position, and the opponent’s scoring chance all matter. The proposed play-outcome, punt, and endgame simulation modules are absent from the current checkout. Their optimal-call recommendations are not established results. [5,6]')
head(p,'“The model proves a timeout is worth only 0.33 points.”')
body(p,'The saved-timeout estimate averages 0.33 percentage points of win probability in the sampled one-score states at the start of the final four minutes. The prior five-yard estimates range from 1.82 to 4.70 points in selected tied, third-quarter situations. This supports using a timeout to avoid delay of game in many ordinary situations. It does not compare both choices in the same late-game state or price protection against a bad call, substitution problem, or clock expiration. [1,3]')
body(p,'The win model translates extra seconds into a change in estimated win probability. That is a coherent clock-value approximation, not a demonstrated causal effect of timeout use. Its held-out calibration uses many snaps from the same games, and team strength is calculated from full-season scoring margins, including results unavailable at the time of a live decision. Strong average calibration does not validate every late-game choice. [3]')
head(p,'“Unused timeouts cost Brown close games.”')
body(p,'Three of six sampled Brown losses by eight or fewer ended with timeouts unused. That identifies games to inspect; it does not establish a lost opportunity. A timeout can remain because no running-clock possession offered a useful chance to spend it. In '+film_link(27785,'2024 Princeton, Q4 3:16 to 2:33')+', the flagged wait leads to a fourth-down defensive-holding no-play, then first down at 2:22. The actual sequence supersedes an assumed-punt calculation. [1-3,8]')
head(p,'“The earlier report’s 2:30 cutoff is the right rule.”')
body(p,'The 151-second estimate is the 75th percentile of 430 successful hurry-up scoring drives. Unsuccessful attempts were excluded; time is measured from first to last snap, not through the final scoring play. It describes those successes and supplies a planning heuristic. It is not the required time to score, a 75% success probability, or a validated universal timeout threshold. [2]')
small(p,'Staff takeaway: adopt the clock-state checklist and prompt-call procedure; use the audit to select film; treat exact trigger times and run/pass advice as provisional until the full possession model is completed and validated.')
p=page('Evidence and source record')
head(p,'Brown film-review queue')
small(p,'All 13 audit intervals. Click a game for selected film; clocks below are Q4 snap clocks. “Est. wait” is snap-to-next-event time minus an assumed 7-second play, not a measured dead-ball interval. Cut film can omit the wait. Sign-in and playlist access are required. Full play IDs and game fallbacks: film_index.md. [2,8]')
rows=[]
for r in film:
 rows.append([film_link(r['game_id'],f"{r['season']} {r['opponent_name']}"),r['snap_clock']+' / '+r['next_snap_clock'],f"Down {-r['lead']}",str(r['next_down']),str(r['timeouts']),f"{r['lost']} sec"])
table(p,['Film / game','Snap / next','Margin','Next down','TO left','Est. wait'],rows,[136,99,65,72,60,72])
small(p,film_link(32154,'2026 Harvard, 2:52 to 2:14')+': Harvard is at Brown’s 31/30; the next fourth down is at 2:00 on Brown’s 27. Check the automatic stoppage and fourth-down/scoring options; a punt is not assured. [8]')
head(p,'Sources and method')
small(p,'<b>[1] Existing report and saved results.</b> Brown Timeout Decisions.pdf, supplied reference (11 pages); tos/out/report_data.json and timeout_report.html. The 11-page reference was reviewed and its claims checked against the available code.')
small(p,'<b>[2] Reproduced clock evidence.</b> data/ncaa/pbp.csv.gz; tos/clock_game.py, using end_of_game/runoff_model.py. The rerun produced nine adjusted Brown noncalls after the two-minute holdout. Live time uses snap clocks and play-clock use, clipped to 0-20 seconds; unflagged stops and resets can affect it.')
small(p,'<b>[3] Timeout reconstruction and valuation.</b> tos/timeouts.py, wp_model.py, report_data.py; data/ncaa/games.csv, timeouts.csv and timeouts_unused.csv. Timeout purposes are inferred. The audit excludes known natural stops and filters short unflagged stops; urgency assumes a stop, typical punt position and successful-drive timing.')
small(p,'<b>[4] Staff reference.</b> 2POINT_EOG - KNEEL DOWN SITUATION CHART.xlsx - USE THIS ONE w-2min waning NEW.pdf (one page). The two-point conversion portion is outside this report’s scope. <b>[5]</b> end_of_game/clock_kill.py, params_brown.json, params_ivy.json, opp_offense.py, DESIGN.md and PLAN-02-refit.md.')
small(p,'<b>[6] Development history.</b> /Users/graceyang/Documents/evertrue1.txt and evertrue2.txt. The later record reports an approved switch from expected points to raw yards-to-goal; current opp_offense.py still uses expected points. Its historical 720-drive Ivy validation cannot be rerun because ivy_19t26.csv is absent. The available Brown-only CSV fails all six gates, as intended for a thin sample; this does not invalidate the historical Ivy fit.')
small(p,'<b>[7] Rules context.</b> NCAA’s 2023 first-down timing change and 2024 two-minute timeout mean this sample spans different timing regimes. Official sources: <link href="https://www.ncaa.org/news/media-center-football-timing-rules-approved-for-divisions-i-ii/" color="#694133">2023 timing changes</link>; <link href="https://www.ncaa.org/news/media-center-technology-rules-approved-in-football/" color="#694133">2024 timing changes</link>. Current rule resources: <link href="https://www.ncaa.org/championships/playing-rules/football-playing-rules/" color="#694133">NCAA Football Playing Rules</link>. Exact boundary cases require the current rule and the actual restart signal.')
small(p,'<b>[8] Ultimate film review.</b> Reviewed the main sections, report catalogs, clock filters, IQ timing tools and video/playlist workflow on 6 October. Eight selected film sequences cover all 13 audit intervals, matched by PFF play ID and checked on their playlist pages. See film_index.md, film_index.json and ultimate_site_review.md. Links identify the plays; the audit estimates are not presented as film-measured timeout savings.')
# Save editable content in a simple text form alongside the PDF.
import re
def to_md(t):
 t=re.sub(r'<link href="([^"]+)"[^>]*>(.*?)</link>',r'[\2](\1)',t)
 return html.unescape(re.sub('<[^>]+>','',t))
md=[]
for pageitems in pages:
 for kind,val in pageitems:
  if kind=='table':
   headers,rows,_=val;md.extend(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(to_md(c) for c in r)+' |' for r in rows]+[''])
  else:
   md.append(('# ' if kind=='title' else '## ' if kind=='head' else '')+to_md(val));md.append('')
(ROOT/'output/pdf/end_of_game_clock_report.md').write_text('\n'.join(md))
story=[]
for i,pageitems in enumerate(pages):
 if i:story.append(PageBreak())
 for kind,val in pageitems:
  if kind=='table':
   headers,rows,widths=val
   data=[[Paragraph('<b>'+html.escape(c)+'</b>',styles['CellX']) for c in headers]]+[[Paragraph(c if c.startswith('<link ') else html.escape(c),styles['CellX']) for c in row] for row in rows]
   t=Table(data,colWidths=widths,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#eee8e2')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#694133')),('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#d6d1cb'))]));story.extend([t,Spacer(1,9)])
  else:story.append(Paragraph(val,styles[{'title':'TitleX','head':'HeadX','body':'BodyX','small':'SmallX'}[kind]]))
def footer(c,d):
 c.setStrokeColor(colors.HexColor('#d6d1cb'));c.line(54,43,558,43);c.setFont('Helvetica',8);c.setFillColor(colors.HexColor('#666666'));c.drawString(54,29,'BROWN FOOTBALL  |  END-OF-GAME CLOCK MANAGEMENT');c.drawRightString(558,29,str(d.page))
SimpleDocTemplate(str(ROOT/'output/pdf/end_of_game_clock_report.pdf'),pagesize=(612,792),rightMargin=54,leftMargin=54,topMargin=43,bottomMargin=55,title='Brown Football: End-of-game Clock Management',author='Brown Football Analytics').build(story,onFirstPage=footer,onLaterPages=footer)
import pymupdf as fitz
d=fitz.open(ROOT/'output/pdf/end_of_game_clock_report.pdf'); print('pages',len(d))
for i,p in enumerate(d):
 print(i+1,len(p.get_text()),p.get_text().splitlines()[0]);p.get_pixmap(matrix=fitz.Matrix(1.3,1.3)).save(str(ROOT/f'tmp/pdfs/final-{i+1}.png'))
