import pickle, json, html, re, datetime
from gen import *
P = pickle.load(open('picks.pkl', 'rb'))
L = json.load(open('links.json'))
CSS = open('css.txt').read()
LOC = open('loc.txt').read()
LOCJS = open('locjs.txt').read()
E = html.escape
BNAME = {'FD': 'FanDuel', 'DK': 'DraftKings', 'MG': 'BetMGM', 'CZ': 'Caesars', 'BR': 'BetRivers', 'HR': 'Hard Rock'}
SLIPBOOKS = ['FD', 'DK', 'MG', 'CZ', 'BR', 'HR']

LK = {}
for kk, rows in L.items():
    st, b = kk.split('_')
    for n, m, line, odds, url in rows:
        LK[(st, b, n, m, line)] = url

def on_url(b, u):
    if b == 'FD': u = u.replace('https://sportsbook.fanduel.com', 'https://on.sportsbook.fanduel.ca', 1)
    if b == 'HR':
        m = re.search(r'deep_link_value=([^&]+)', u)
        if m: u = 'https://app.hardrockbet.ca/?deep_link_value=' + m.group(1)
    return u
def us_tmpl(b, u):
    u = u.replace('sports.nj.betmgm.com', 'sports.{st}.betmgm.com').replace('/us/nj/', '/us/{st}/').replace('://nj.betrivers.com', '://{st}.betrivers.com')
    return u
def link(st, b, k):
    u = LK.get(('ON' if st == 'on' else 'NJ', b, k[0], k[1], k[2]))
    if not u: return None
    return on_url(b, u) if st == 'on' else us_tmpl(b, u)

def combine(b, urls, st):
    if b == 'FD':
        ids = [re.search(r'marketId=([^&]+)&selectionId=(\d+)', u).groups() for u in urls]
        base = 'https://on.sportsbook.fanduel.ca' if st == 'on' else 'https://sportsbook.fanduel.com'
        return base + '/addToBetslip?' + '&'.join(f'marketId[{i}]={a}&selectionId[{i}]={c}' for i, (a, c) in enumerate(ids))
    if b == 'DK':
        return 'https://sportsbook.draftkings.com/?outcomes=' + '+'.join(re.search(r'outcomes=([^&]+)', u).group(1) for u in urls)
    if b == 'MG':
        base = urls[0].split('?')[0]
        return base + '?options=' + ','.join(re.search(r'options=([^&]+)', u).group(1) for u in urls) + '&type=Combo'
    if b == 'CZ':
        return urls[0].split('?')[0] + '?selectionIds=' + ','.join(re.search(r'selectionIds=([^&]+)', u).group(1) for u in urls)
    if b == 'BR':
        ev = re.search(r'#event/(\d+)', urls[0]).group(1)
        host = urls[0].split('/?')[0]
        return f'{host}/?page=sportsbook#event/{ev}?coupon=combination|' + ','.join(re.search(r'single\|(\d+)\|', u).group(1) for u in urls) + '|'
    if b == 'HR':
        return urls[0]  # HR multi-leg links don't load; first leg opens the book

def a(href, text, region, own=False, tmpl=False):
    return (f'<a class="slip{" own" if own else ""}" data-r="{region}"' + (' data-tmpl="1"' if tmpl else '') +
            f' href="{E(href)}" target="_blank" rel="noopener">{text}</a>')

def ticket_buttons(tk):
    out = []
    order = [tk['book']] + [b for _, b in other_books(tk)]
    for st in ('on', 'us'):
        for b in order:
            if b not in SLIPBOOKS: continue
            urls = [link(st, b, k) for k, _ in tk['legs']]
            if all(urls):
                u = combine(b, urls, st)
                note = ' (first leg only)' if b == 'HR' and len(urls) > 1 else ''
                own = b == tk['book']
                lbl = f'Bet this ticket at {BNAME[b]}{note} ↗' + ('' if own else f' <span class="dim">(priced at {BN[tk["book"]]})</span>')
                out.append(a(u, lbl, st, own=own, tmpl=(st == 'us' and '{st}' in u)))
                break
        else:
            out.append(f'<span class="noslip" data-r="{st}">No slip link for every leg at one book</span>')
    return '<div class="slips">' + ''.join(out) + '</div>'

def single_buttons(k, small=False):
    out = []
    bb = best(k, SLIPBOOKS)
    for st in ('on', 'us'):
        for b in SLIPBOOKS:
            if b not in BL[k]: continue
            u = link(st, b, k)
            if not u: continue
            out.append(a(u, f'{BN[b]} {fmt(BL[k][b][0])}', st, own=(bb and b == bb[1]), tmpl=(st == 'us' and '{st}' in u)))
    if not out: return '<span class="noslip">no slip links</span>'
    return ''.join(out)

def gl(v):
    g, n = grade(v); return f'{g} {n}' if n is not None else '—'

def mlabel(k):
    m = MK[k[1]][0]
    if k[1] == 'player_anytime_td': return 'Anytime TD' if k[2] == 0.5 else '2+ TDs'
    if k[1] == 'player_1st_td': return 'First TD'
    return f'{m} O {k[2]:g}'

def why(k):
    n, m, line = k
    p = PROJ.get(n)
    if not p:
        if m == 'player_sacks':
            d = DEF.get(INFO[n][0], {})
            opp = INFO[n][1]
            return f'{INFO[n][0]} pressure rate {d.get("pressure_rate", 0)*100:.0f}% · {d.get("sacks_pg", 0):.1f} sacks/g as a unit · vs {opp}'
        return ''
    sub, d = lens(n, m)
    bits = []
    if d:
        bits.append(f'{MK[m][0].split()[0]} lens {gl(sub)} / Overall {gl(d.get("dvp_matchup_score"))} / TD {gl(d.get("dvp_td_sub"))}')
        bits.append(f'{p["opponent"]} #{d.get("dvp_position_rank")} vs {p["position"]}')
    pj = proj(n, m)
    if m in ('player_anytime_td',):
        bits.append(f'model {p["mc_anytime_td"]*100:.0f}% anytime, {p["mc_2plus_td"]*100:.0f}% 2+')
    elif pj is not None:
        bits.append(f'proj {pj:.1f} vs {line:g}')
    if p.get('proj_targets'): bits.append(f'{p["proj_targets"]:.1f} proj targets')
    if p.get('proj_rush_attempts') and p['position'] == 'RB': bits.append(f'{p["proj_rush_attempts"]:.1f} proj carries')
    tag = 'Proj-led'
    if sub is not None and sub >= 65:
        tag = 'DvP + proj agree' if (pj or 0) >= line * 0.95 or m == 'player_anytime_td' else 'DvP-led'
    if not p['is_starter']: tag = 'Non-starter'
    return ' · '.join(bits) + f' · <i>{tag}</i>'

def sub_pos(n):
    p = PROJ.get(n)
    return f'{p["position"]} · {p["team"]}' if p else f'DEF · {INFO[n][0]}'

def tscore(tk):
    return sum(leg_score(*k) + 40 * (mp(k) or 0) for k, _ in tk['legs']) / len(tk['legs'])

def xt(v, label):
    c = 'red' if v >= 85 else 'yellow' if v >= 75 else 'green'
    return f'<span class="xt {c}">{E(label)} {round(v)}</span>'

def legtag(k):
    n, m, line = k
    if m == 'player_sacks':
        d = DEF.get(INFO[n][0], {}); v = (d.get('pressure_rate') or 0) * 400
        return xt(min(v, 99), 'Pressure')
    sub, d = lens(n, m)
    if sub is None: return ''
    lab = {'player_pass_yds': 'Pass', 'player_reception_yds': 'Rec', 'player_rush_yds': 'Rush', 'player_rush_reception_yds': 'Yds',
           'player_receptions': 'Vol', 'player_anytime_td': 'TD', 'player_1st_td': 'TD'}[m]
    return xt(sub, f'{lab} {PROJ[n]["position"]}')

def card(tk, tid, title, fav=False, note=''):
    fl = max(tk['legs'], key=lambda x: leg_score(*x[0]) + 40 * (mp(x[0]) or 0))[0] if fav else None
    ob = other_books(tk)[:3]
    fair = fair_ticket(tk)
    meta = f'{len(tk["legs"])} legs' + (f' · fair {fmt(fair)}' if fair else '') + (' · other books: ' + ' · '.join(f'{BN[b]} {fmt(p)}' for p, b in ob) if ob else ' · only this book prices every leg')
    rows = ''
    for k, o in tk['legs']:
        bb = best(k)
        f = fair_p(k)
        rows += (f'<tr><td class="st">{"★" if k == fl else ""}</td><td><b>{E(k[0])}</b><span class="sub">{sub_pos(k[0])}</span></td>'
                 f'<td class="nw">{gname(INFO[k[0]][2])}</td><td class="nw">{mlabel(k)} {legtag(k)}</td><td class="odds">{fmt(o)}</td>'
                 f'<td class="nw dim">{fmt(bb[0])} {BN[bb[1]]}</td><td class="dim">{fmt(amer(1/f)) if f else "—"}</td><td class="note">{why(k)}</td></tr>')
    return (f'<div class="card{" fav" if fav else ""}"><div class="ch"><div><span class="tid">{"★ " if fav else ""}{tid}</span> <span class="ttl">{E(title)}</span></div>'
            f'<div class="px"><span class="bk">{BN[tk["book"]]}</span><span class="big">{fmt(tk["price"])}</span></div></div>'
            f'{ticket_buttons(tk)}<div class="meta">{meta}</div><div class="tw"><table class="legs"><thead><tr><th></th><th>Player</th><th>Game</th><th>Market</th><th>Odds</th><th>Best</th><th>Fair</th><th>Matchup / why</th></tr></thead><tbody>{rows}</tbody></table></div>'
            + (f'<p class="why">{note}</p>' if note else '') + '</div>')

def title_for(tk):
    ms = collections.Counter(MK[k[1]][0] for k, _ in tk['legs'])
    pos = collections.Counter(PROJ[k[0]]['position'] if k[0] in PROJ else 'DEF' for k, _ in tk['legs'])
    top = ms.most_common(1)[0][0]
    if len(ms) == 1: return f'{top} across {len(tk["legs"])} games'
    return ' + '.join(f'{m}' for m, _ in ms.most_common())

def cards(lst, prefix, notes=None):
    if not lst: return '<p class="plain">Nothing cleared every gate today.</p>'
    favi = max(range(len(lst)), key=lambda i: tscore(lst[i]))
    return ''.join(card(t, f'{prefix} {i+1}' if len(lst) > 1 or prefix in ('MAX NS',) else prefix, title_for(t), fav=(i == favi), note=(notes or {}).get(i, '')) for i, t in enumerate(lst))

# ---------- overview ----------
def team_outs(team):
    xs = [p for p in O['proj'] if p['team'] == team and p['injury_status'] in ('Out', 'Doubtful', 'Questionable') and p['game_date'] == TODAY]
    xs.sort(key=lambda p: (p['injury_status'] != 'Out', p['depth_chart_rank'] or 9))
    return ', '.join(f'{p["position"]} {p["player_name"].split(" ",1)[-1]} {p["injury_status"][0] if p["injury_status"]!="Doubtful" else "D"}' for p in xs[:4])

def qb(team):
    q = [p for p in PROJ.values() if p['team'] == team and p['position'] == 'QB' and p['is_starter']]
    return q[0]['player_name'] if q else '?'

def toplens(team, opp):
    out = []
    for pos in ('QB', 'RB', 'WR', 'TE'):
        d = DVP.get((opp, pos))
        if not d: continue
        for f, lab in (('dvp_pass_yds_sub', 'Pass'), ('dvp_rush_yds_sub', 'Rush'), ('dvp_rec_yds_sub', 'Rec')):
            if pos == 'QB' and f != 'dvp_pass_yds_sub': continue
            if pos != 'QB' and f == 'dvp_pass_yds_sub': continue
            if pos in ('WR', 'TE') and f == 'dvp_rush_yds_sub': continue
            v = d.get(f)
            if v is not None: out.append((v, f'{team} {lab} ({pos})'))
    return sorted(out, reverse=True)[:2]



slate_rows = ''
gl_sorted = sorted(GAMES.values(), key=lambda g: (g['game_time'], g['game_id']))
for g in gl_sorted:
    gid = g['game_id']; fav, sp, tot = SPREAD[gid]
    away, home = g['away_team'], g['home_team']
    hm = -sp if fav == home else sp
    imp_h = tot / 2 + hm / 2; imp_a = tot - imp_h
    t = datetime.datetime.strptime(g['game_time'], '%H:%M')
    ts = t.strftime('%-I:%M') + ('p' if t.hour >= 12 else 'a')
    lenses = toplens(away, home) + toplens(home, away)
    lenses = sorted(lenses, reverse=True)[:3]
    outs = ' · '.join(x for x in (f'{away}: {team_outs(away)}' if team_outs(away) else '', f'{home}: {team_outs(home)}' if team_outs(home) else '') if x)
    slate_rows += (f'<tr><td>{ts}</td><td><b>{away} @ {home}</b></td><td class="nw">{fav} {sp:g}</td><td>{tot:g}</td><td class="nw">{imp_a:.2f} / {imp_h:.2f}</td>'
                   f'<td>{qb(away)} / {qb(home)}</td><td class="note">{outs or "—"}</td><td>{"".join(xt(v, l) for v, l in lenses)}</td></tr>')

# exposure
expo = collections.Counter()
alltk = P['MAX'] + P['MAXNS'] + P['PAR'] + P['PARNS'] + P['REC'] + P['TD'] + P['TD2'] + P['TETD'] + P['SACK']
for t in alltk:
    for k, _ in t['legs']: expo[k[0]] += 1
expo_html = ''.join(f'<span class="chip{" hot" if c >= 4 else ""}"><b>{E(n)}</b> {c}</span>' for n, c in expo.most_common(14))

# fades: starters whose projection sits well under the main line
fades = []
for n, p in PROJ.items():
    if not eligible(n): continue
    for m in ('player_pass_yds', 'player_reception_yds', 'player_rush_yds'):
        rs = rungs(n, m)
        if not rs: continue
        main = min(rs, key=lambda r: abs((fair_p(r) or 0) - 0.5))
        pj = proj(n, m)
        if pj and main[2] >= 30 and pj < main[2] * 0.82:
            fades.append((pj / main[2], n, MK[m][0], main[2], pj))
fades.sort()
fade_txt = ' · '.join(f'{n} {lab} (projects {pj:.0f} vs {ln:g})' for _, n, lab, ln, pj in fades[:5])

maxp = sorted(P['MAX'], key=lambda t: -tscore(t))
edge_names = []
for t in sorted(alltk, key=lambda t: -tscore(t)):
    for k, _ in t['legs']:
        if k[0] not in edge_names and k[0] in PROJ: edge_names.append(k[0])
edges = []
for n in edge_names[:6]:
    ks = [k for t in alltk for k, _ in t['legs'] if k[0] == n]
    k = ks[0]; sub, _ = lens(n, k[1])
    edges.append(f'{n} ({MK[k[1]][0].split()[0]} lens {gl(sub)}, vs {PROJ[n]["opponent"]})')

mainreads = (f'<div class="mainreads"><div class="mrh">Main Reads</div>'
             f'<p><b>Edges:</b> {" · ".join(edges)}.</p>'
             f'<p><b>Fades:</b> {fade_txt}.</p>'
             f'<p><b>Rule calls this slate:</b> Built <b>without the exploit board</b> (no screenshots reachable this morning), so every leg is DvP-led or projection-led and the board-led tickets are skipped. '
             f'Questionable starters kept off every ticket: Jake Ferguson, Hunter Henry, Emeka Egbuka (all missed practice) and Amon-Ra St. Brown; Mike Evans, Deebo Samuel, A.J. Brown, Garrett Wilson and DeVonta Smith are out. '
             f'Drew Lock starts for SEA (Darnold out). Road favourites DAL, LA, DET, NYG, DEN and HOU are off the spreads (Sep 27 lesson). '
             f'<b>Inactives drop about 11:30 ET for the 1:00 games</b>: re-check any Q before you bet.</p></div>')
legend = ('<div class="intro"><b>Leg tags:</b> <i>DvP + proj agree</i> = DvP HQ lens Good/Elite and the projection clears the line · <i>DvP-led</i> = lens Good/Elite, projection a bit short · <i>Proj-led</i> = projection carries it · <i>Non-starter</i> = NS tickets only. '
          'Every leg carries a lens tag in your board colours: <span class="xt red">red</span> 85+ · <span class="xt yellow">yellow</span> 75-84 · <span class="xt green">green</span> under 75. Every combined price is one book’s real price for all legs (separate games, so no SGP estimate).</div>')
tiles = (f'<div class="tiles"><div class="tile"><span>Slate</span><b>{len(GAMES)} games</b><em>Sun Nov 8 · 1:00p → SNF TB @ CHI</em></div>'
         f'<div class="tile"><span>Tickets</span><b>{len(P["MAX"])} MAX · {len(P["PAR"])} parlays</b><em>+{len(P["MAXNS"])+len(P["PARNS"])} non-starter · {len(P["REC"])} rec · {len(P["TD"])+len(P["TD2"])+len(P["TETD"])} TD · {len(P["SACK"])} sacks · 2 spread</em></div>'
         f'<div class="tile"><span>Biggest spreads</span><b>SEA -11 · KC -9.5 · SF -9.5</b><em>LV @ SF 51.5 and DAL @ IND 51.5 the top totals</em></div>'
         f'<div class="tile"><span>Data</span><b>MKB API · 9:20a pull</b><em>8 books, Ontario + NJ slip links</em></div></div>')
overview = (mainreads + legend + tiles +
            '<h3>Slate &amp; starters <span class="sub">Spreads/totals: Nov 3 Fanatics snapshot (your feed has no market spreads) · tags = the two best DvP lenses in each game</span></h3>'
            '<div class="tw"><table class="legs"><thead><tr><th>ET</th><th>Game</th><th>Spread</th><th>Total</th><th>Implied (A/H)</th><th>QBs</th><th>Key outs / Qs (feed)</th><th>Best lenses</th></tr></thead><tbody>'
            + slate_rows + '</tbody></table></div><h3>Exposure <span class="sub">tickets per player, all tabs</span></h3><div class="expo">' + expo_html + '</div>')

# ---------- tabs ----------
max_tab = ('<div class="intro">Gates: starters only (except MAX NS) · each game once across MAX · every leg +300 to +1200 at the ticket’s book · ticket +6000 or higher · single book. '
           f'{len(set(INFO[k[0]][2] for t in P["MAX"] for k, _ in t["legs"]))} of {len(GAMES)} games used.</div>' + cards(P['MAX'], 'MAX') +
           '<h3>Non-starter MAX <span class="sub">depth-chart WR2/3s with 45%+ projected snaps and a Good/Elite lens</span></h3>' + cards(P['MAXNS'], 'MAX NS'))
par_tab = ('<div class="intro">About five parlays, mostly 3 legs with a couple of 4-leg tickets, each +2500 or higher at one book. Legs priced +110 to +400. No player on more than three tickets.</div>' + cards(P['PAR'], 'P') +
           '<h3>Non-starter parlays</h3>' + cards(P['PARNS'], 'P NS'))
ftd_rows = ''
for i, k in enumerate(P['FTD']):
    bb = best(k)
    ftd_rows += (f'<tr class="{"favrow" if i < 2 else ""}"><td class="st">{"★" if i < 2 else ""}</td><td><b>{E(k[0])}</b><span class="sub">{sub_pos(k[0])}</span></td><td class="nw">{gname(INFO[k[0]][2])}</td>'
                 f'<td class="odds">{fmt(bb[0])}</td><td class="dim">{BN[bb[1]]}</td><td class="dim">{PROJ[k[0]]["mc_first_td"]*100:.1f}%</td><td class="lslip">{single_buttons(k)}</td></tr>')
td_tab = ('<div class="intro">Anytime-TD parlays, 2+ TD tickets and TE TD tickets. Your feed has no defense/special-teams TD market today, so that group is skipped. One ATD ticket is the lower-chalk shot.</div>'
          '<h3>Anytime TD</h3>' + cards(P['TD'], 'TD') + '<h3>2+ TDs</h3>' + cards(P['TD2'], '2+ TD') + '<h3>TE TDs</h3>' + cards(P['TETD'], 'TE TD') +
          '<h3>First TD picks <span class="sub">model first-TD % weighted by the TD lens · ★ = the two I like most to actually hit</span></h3><div class="tw"><table class="legs"><thead><tr><th></th><th>Player</th><th>Game</th><th>Best</th><th>Book</th><th>Model</th><th>Slips</th></tr></thead><tbody>' + ftd_rows + '</tbody></table></div>')
sack_tab = ('<div class="intro">Sacks are exempt from the 5-book coverage floor. Legs ranked on the market’s fair price plus the defender’s unit pressure rate from team defense.</div>' + cards(P['SACK'], 'SACK'))
crow = ''
cl = sorted(P['CEIL'], key=lambda x: -(leg_score(*x[0]) + 40 * (mp(x[0]) or 0)))
favc = set(r for r, _, _ in cl[:4])
for r, o, b in sorted(P['CEIL'], key=lambda x: -(lens(x[0][0], x[0][1])[0] or 0)):
    f = fair_p(r)
    fv = r in favc
    crow += (f'<tr class="{"favrow" if fv else ""}"><td class="st">{"★" if fv else ""}</td><td><b>{E(r[0])}</b><span class="sub">{sub_pos(r[0])}</span></td><td class="nw">{gname(INFO[r[0]][2])}</td><td class="nw">{mlabel(r)} {legtag(r)}</td>'
             f'<td class="odds">{fmt(o)}</td><td class="nw dim">{BN[b]}</td><td class="dim">{fmt(amer(1/f)) if f else "—"}</td><td class="dim">{cov(r)}</td><td class="note">{why(r)}</td><td class="lslip">{single_buttons(r)}</td></tr>')
ceil_tab = ('<div class="intro">Ceiling rungs (about 12 to 35% above projection) on starters with a Good/Elite DvP lens, priced at the best of your books.</div>'
            '<div class="tw"><table class="legs"><thead><tr><th></th><th>Player</th><th>Game</th><th>Market</th><th>Best</th><th>Book</th><th>Fair</th><th>Cov</th><th>Matchup</th><th>Slips</th></tr></thead><tbody>' + crow + '</tbody></table></div>')

def ladder(key, rs):
    n, m = key
    pj = proj(n, m) or 0
    # star: rung nearest projection that pays -125 or better
    cand = [r for r in rs if best(r)[0] >= -125]
    star = min(cand, key=lambda r: abs(r[2] - pj)) if cand else None
    rows = ''
    for r in rs:
        bb = best(r); f = fair_p(r)
        s = r == star
        rows += (f'<tr class="{"favrow" if s else ""}"><td class="st">{"★" if s else ""}</td><td>O {r[2]:g}</td><td class="odds">{fmt(bb[0])}</td><td class="dim">{BN[bb[1]]}</td>'
                 f'<td class="dim">{fmt(amer(1/f)) if f else "—"}</td><td class="dim">{cov(r)}</td><td class="lslip">{single_buttons(r)}</td></tr>')
    return (f'<div class="lad"><div class="lh"><b>{E(n)}</b> <span class="dim">{MK[m][0]} · {sub_pos(n)} · {gname(INFO[n][2])}</span> {legtag((n, m, rs[0][2]))}</div>'
            f'<div class="lnote">{why((n, m, star[2] if star else rs[0][2]))}</div><table class="legs"><thead><tr><th></th><th>Rung</th><th>Best</th><th>Book</th><th>Fair</th><th>Cov</th><th>Slips</th></tr></thead><tbody>{rows}</tbody></table></div>')

def trim(rs, pj):
    # keep a readable window: up to 10 rungs around the projection
    rs = [r for r in rs if r[2] >= pj * 0.6 and r[2] <= pj * 1.9] or rs
    if len(rs) > 11:
        i = min(range(len(rs)), key=lambda j: abs(rs[j][2] - pj))
        rs = rs[max(0, i - 4): i + 7]
    return rs

lad_html = ''
for lab, mkts in (('Receiving yards', ('player_reception_yds',)), ('Rushing yards', ('player_rush_yds',)), ('Rush + rec yards', ('player_rush_reception_yds',)), ('Passing yards', ('player_pass_yds',))):
    items = [(k, rs) for k, rs in P['LAD'] if k[1] in mkts]
    if not items: continue
    lad_html += f'<h3>{lab}</h3><div class="lgrid">' + ''.join(ladder(k, trim(rs, proj(*k) or 0)) for k, rs in items) + '</div>'
lad_tab = '<div class="intro">One starred rung per ladder: the rung nearest the projection that still pays -125 or better. Prices are the best across your books; Cov = books posting that rung.</div>' + lad_html

SPR = [
    ('★ SPR 1', 'Alt-safened home favourites', '≈+760', [('KC', '-6.5 (alt from -9.5)', '≈-175', 'Home vs NYJ · Garrett Wilson OUT · feed has KC by 8.6'), ('SF', '-6.5 (alt from -9.5)', '≈-175', 'Home vs LV · feed has SF by 8.8 · 51.5 total'), ('SEA', '-7.5 (alt from -11)', '≈-170', 'Home vs ARI with Drew Lock: buys through 10 and 7 since SEA is on its backup QB'), ('CHI', '-3 (alt from -6)', '≈-185', 'Home vs TB on SNF · Egbuka Q · feed has CHI by 4.8'), ('NE', '+1.5 (alt from -2.5)', '≈-160', 'Home vs GB · Henry Q, A.J. Brown OUT · buys through the key numbers')], True,
     'Every leg is a home team, bought through the key numbers (3 and 7), as you prefer on spreads.'),
    ('SPR 2', 'Main lines', '≈+2,430', [('KC', '-9.5', '≈-110', 'Main line'), ('SF', '-9.5', '≈-110', 'Main line'), ('CHI', '-6', '≈-110', 'Main line'), ('NO', '-2.5', '≈-115', 'Home vs CLE · Watson Q · feed has NO by 2.7'), ('SEA', '-11', '≈-110', 'Main line: the shakiest leg with Lock starting')], False,
     'Same home-favourite core at the posted numbers, with NO swapped in for NE.')]
spr_html = ''
for tid, ttl, px, legs, fav, note in SPR:
    rows = ''.join(f'<tr><td class="st">{"★" if (fav and i == 0) else ""}</td><td><b>{t}</b></td><td class="nw">{s}</td><td class="odds">{j}</td><td class="note">{w}</td></tr>' for i, (t, s, j, w) in enumerate(legs))
    spr_html += (f'<div class="card{" fav" if fav else ""}"><div class="ch"><div><span class="tid">{tid}</span> <span class="ttl">{ttl}</span></div><div class="px"><span class="bk">any book</span><span class="big">{px}</span></div></div>'
                 f'<div class="tw"><table class="legs"><thead><tr><th></th><th>Team</th><th>Spread</th><th>Juice</th><th>Why</th></tr></thead><tbody>{rows}</tbody></table></div><p class="why">{note}</p></div>')
spr_tab = ('<div class="intro">Exactly two 5-leg spread tickets, one leg per row, home teams only. Numbers are the Nov 3 Fanatics lines and all juice is estimated (≈) because your feed doesn’t carry spreads, so confirm at your book; no slip buttons here for the same reason. '
           'DAL -6, LA -5.5, DET -7, NYG -3.5, DEN -3 and HOU -4.5 are road favourites, so they’re off (Sep 27 lesson).</div>' + spr_html)
rlad = ''.join(ladder(k, trim(rs, proj(*k) or 0)) for k, rs in P['RLAD'])
rec_tab = ('<div class="intro">Receptions get their own group: R1 and R2 at 2.5 to 6.5 lines, plus R3 as the 3-leg shot at +7000 or higher.</div>' + cards(P['REC'], 'R') +
           '<h3>Receptions ladders</h3><div class="lgrid">' + rlad + '</div>')

# reference: DvP lenses per game
refrows = ''
for g in gl_sorted:
    for team, opp in ((g['away_team'], g['home_team']), (g['home_team'], g['away_team'])):
        for pos in ('QB', 'RB', 'WR', 'TE'):
            d = DVP.get((opp, pos))
            if not d: continue
            st = [p for p in PROJ.values() if p['team'] == team and p['position'] == pos and p['is_starter']]
            nm = st[0]['player_name'] if st else '—'
            oncard = sorted(set(t['kind'] for t in alltk for k, _ in t['legs'] if k[0] == nm))
            refrows += (f'<tr><td class="nw">{team} {pos}</td><td>vs {opp}</td><td>{E(nm)}</td><td class="dim">#{d.get("dvp_position_rank")}</td><td>{gl(d.get("dvp_matchup_score"))}</td>'
                        f'<td class="dim">Pass {gl(d.get("dvp_pass_yds_sub")) if pos=="QB" else "—"} · Rush {gl(d.get("dvp_rush_yds_sub"))} · Rec {gl(d.get("dvp_rec_yds_sub"))} · TD {gl(d.get("dvp_td_sub"))}</td><td class="note">{", ".join(oncard) or "<span class=dim>not on card</span>"}</td></tr>')
ref_tab = ('<h3>DvP HQ lenses by team and position <span class="sub">from today’s MKB DvP · stands in for the exploit board today</span></h3><div class="tw"><table class="legs"><thead><tr><th>Unit</th><th>Opp</th><th>Starter</th><th>Rank</th><th>Overall</th><th>Sub-scores</th><th>On card</th></tr></thead><tbody>' + refrows + '</tbody></table></div>')

TABS = [('overview', 'Overview', overview), ('max', 'NFL MAX', max_tab), ('parlays', 'Parlays', par_tab), ('td', 'TDs', td_tab), ('sacks', 'Sacks', sack_tab),
        ('ceiling', 'Ceiling Straights', ceil_tab), ('ladders', 'Ladders', lad_tab), ('spreads', 'Spreads', spr_tab), ('rec', 'Receptions', rec_tab), ('ref', 'Reference', ref_tab)]
nav = ''.join(f'<button class="{"on" if i == 0 else ""}" data-t="{t}" type="button">{lab}</button>' for i, (t, lab, _) in enumerate(TABS))
panes = ''.join(f'<section class="pane{" on" if i == 0 else ""}" id="{t}">{body}</section>' for i, (t, _, body) in enumerate(TABS))
TABJS = """<script>
document.querySelectorAll('.tabs button').forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();
 var w=document.querySelector('.wrap'); w.style.minHeight=Math.max(w.offsetHeight, parseInt(w.style.minHeight||0))+'px';
 document.querySelectorAll('.tabs button').forEach(function(x){x.classList.toggle('on',x===b)});
 document.querySelectorAll('.pane').forEach(function(p){p.classList.toggle('on',p.id===b.dataset.t)});});});
</script>"""
loc = LOC.replace('Parlays load the whole ticket; straights, ladders and double-doubles open single bets.', 'Parlays load the whole ticket; straights, ladders and first-TD picks open single bets.')
locjs = LOCJS.replace("straights, ladders and double-doubles open single bets", "straights, ladders and first-TD picks open single bets")
page = (f'<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"/><meta content="width=device-width,initial-scale=1" name="viewport"/><title>NFL Week 9 Dashboard</title>'
        f'<link href="https://fonts.googleapis.com" rel="preconnect"/><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&amp;display=swap" rel="stylesheet"/><style>{CSS}.lgrid{{grid-template-columns:repeat(auto-fill,minmax(400px,1fr))}}.slip{{white-space:nowrap}}.lad td:nth-child(2){{white-space:nowrap}}.lslip{{min-width:150px}}@media (max-width:640px){{.lgrid{{grid-template-columns:1fr}}}}</style></head><body><div class="wrap">'
        f'<header><h1>NFL <span>Week 9</span> · Sunday Nov 8</h1><div class="subh">{len(GAMES)} games · 1:00p → SNF TB @ CHI · <b>built Sun 10:20a ET</b> from this morning’s MKB API pull (per-book boards for 8 books, projections, DvP HQ, team defense) · no exploit board today · MNF BUF @ MIN not included · ★ = favourite</div></header>'
        f'{loc}<nav class="tabs">{nav}</nav>{panes}</div>{TABJS}{locjs}</body></html>')
open('nfl_2026-11-08.html', 'w').write(page)
print(len(page))
