import json, math, collections
O = json.load(open('/home/claude/nfl/data.json'))
BOOKS = ['FD', 'DK', 'MG', 'CZ', 'ES', 'BB', 'BR', 'HR']
BN = {'FD': 'FD', 'DK': 'DK', 'MG': 'MGM', 'CZ': 'CZR', 'ES': 'ES', 'BB': 'BB', 'BR': 'BR', 'HR': 'HR'}
LINKABLE = {'FD', 'DK', 'MG', 'CZ', 'BR', 'HR'}  # ES/BB: no working slips in ON
TODAY = '2026-11-08'
# quick out/Q list (feed + news). Q starters kept off tickets.
NO_TICKET = {'Jake Ferguson', 'Hunter Henry', 'Emeka Egbuka', 'Amon-Ra St. Brown', 'Mike Evans',
             'Sam Darnold', 'Kyler Murray', 'George Pickens', 'David Njoku', 'Brenen Thompson',
             'Cam Skattebo', 'Tanner McKee', 'Deshaun Watson'}

GAMES = {g['game_id']: g for g in O['games'] if g['game_date'] == TODAY}
SPREAD = {  # Fanatics snapshot Nov 3 (home team view: negative = home favoured)
    '2026_09_NYJ_KC': ('KC', -9.5, 46.5), '2026_09_CLE_NO': ('NO', -2.5, 43.5),
    '2026_09_DAL_IND': ('DAL', -6, 51.5), '2026_09_LA_WAS': ('LA', -5.5, 47.5),
    '2026_09_DET_MIA': ('DET', -7, 50.5), '2026_09_NYG_PHI': ('NYG', -3.5, 39.5),
    '2026_09_DEN_CAR': ('DEN', -3, 44.0), '2026_09_LV_SF': ('SF', -9.5, 51.5),
    '2026_09_HOU_LAC': ('HOU', -4.5, 40.5), '2026_09_GB_NE': ('NE', -2.5, 46.5),
    '2026_09_ARI_SEA': ('SEA', -11, 42.0), '2026_09_TB_CHI': ('CHI', -6, 46.5)}

def gname(gid):
    g = GAMES[gid]; return f"{g['away_team']} @ {g['home_team']}"

PROJ = {}
for p in O['proj']:
    if p['game_date'] == TODAY:
        PROJ[p['player_name']] = p
DVP = {(d['defense'], d['position']): d for d in O['dvp'] if d['game_date'] == TODAY}

MK = {  # market: (label, proj field, mc field, dvp sub)
    'player_pass_yds': ('Pass Yds', 'proj_pass_yds', 'mc_pass_yds_probs', 'dvp_pass_yds_sub'),
    'player_reception_yds': ('Rec Yds', 'proj_rec_yds', 'mc_rec_yds_probs', 'dvp_rec_yds_sub'),
    'player_rush_yds': ('Rush Yds', 'proj_rush_yds', 'mc_rush_yds_probs', 'dvp_rush_yds_sub'),
    'player_rush_reception_yds': ('Rush+Rec Yds', 'proj_rush_rec_yds', 'mc_rush_rec_yds_probs', 'dvp_yds_sub'),
    'player_receptions': ('Receptions', 'proj_receptions', 'mc_receptions_probs', 'dvp_vol_sub'),
    'player_anytime_td': ('Anytime TD', 'proj_total_tds', None, 'dvp_td_sub'),
    'player_sacks': ('Sacks', None, None, None),
    'player_1st_td': ('First TD', None, None, 'dvp_td_sub'),
}

def dec(a): return 1 + (a / 100 if a > 0 else 100 / -a)
def amer(d):
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))
def imp(a): return 1 / dec(a)
def fmt(a):
    s = f"{abs(a):,}"; return ('+' if a > 0 else '-') + s

# board: key (player, market, line) -> {book: (odds, fair, cov, haslink)}
BL = collections.defaultdict(dict)
INFO = {}
for b in BOOKS:
    for r in O['board'][b]:
        name, gi, gd, gt, mkt, side, line, odds, fair, cov, team, opp, gid, hl = r
        if gd != TODAY or mkt not in MK: continue
        if side not in ('Over', 'Yes'): continue
        if odds is None: continue
        if mkt == 'player_anytime_td' and line not in (0.5, 1.5): continue
        k = (name, mkt, line)
        BL[k][b] = (odds, fair, cov, hl)
        INFO[name] = (team, opp, gid, gt)

def grade(v):
    if v is None: return ('—', None)
    for t, n in ((80, 'Elite'), (65, 'Good'), (45, 'Neutral'), (30, 'Tough')):
        if v >= t: return (n, round(v))
    return ('Bad', round(v))

def lens(name, mkt):
    p = PROJ.get(name); inf = INFO.get(name)
    if not p or not inf: return None, None
    d = DVP.get((p['opponent'], p['position']))
    if not d or not MK[mkt][3]: return None, d
    return d.get(MK[mkt][3]), d

def model_p(name, mkt, line):
    p = PROJ.get(name)
    if not p: return None
    if mkt == 'player_anytime_td':
        return p['mc_anytime_td'] if line == 0.5 else p['mc_2plus_td']
    if mkt == 'player_1st_td': return p['mc_first_td']
    f = MK[mkt][2]
    if not f or not p.get(f): return None
    pts = sorted((float(k), v) for k, v in p[f].items())
    if line <= pts[0][0]:
        return min(0.995, pts[0][1] + (pts[0][0] - line) * 0.002)
    if line >= pts[-1][0]:
        x0, y0 = pts[-1]; x1, y1 = pts[-2]
        slope = (y0 - y1) / (x0 - x1) if x0 != x1 else 0
        return max(0.005, y0 + slope * (line - x0))
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= line <= x1:
            return y0 + (y1 - y0) * (line - x0) / (x1 - x0)

def fair_p(k):
    fs = [v[1] for v in BL[k].values() if v[1] is not None]
    if not fs: return None
    return sum(imp(f) for f in fs) / len(fs)

def cov(k):
    return max(v[2] or 0 for v in BL[k].values())

def best(k, books=None):
    c = [(v[0], b) for b, v in BL[k].items() if (books is None or b in books)]
    return max(c) if c else None

def proj(name, mkt):
    p = PROJ.get(name); f = MK[mkt][1]
    return p.get(f) if p and f else None

def eligible(name, starter=True):
    p = PROJ.get(name)
    if not p or name in NO_TICKET or p['injury_status'] in ('Out', 'IR', 'Doubtful', 'Questionable'): return False
    if INFO.get(name, (0, 0, 0))[2] not in GAMES: return False
    return bool(p['is_starter']) if starter else not p['is_starter']
