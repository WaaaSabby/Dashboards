from pick import *
import pickle

def best_book_reprice(tk):
    """Move ticket to the book that pays most for these exact legs."""
    opts = [(tk['price'], tk['book'])] + other_books(tk)
    p, b = max(opts)
    tk['book'] = b; tk['price'] = p
    tk['legs'] = [(k, BL[k][b][0]) for k, _ in tk['legs']]
    return tk

exp = collections.Counter()
mg = set()
MAX = build('MAX', 2, [3, 3], (300, 1200), 6000, cand_legs(), used_games_global=mg, exp=exp, cap=1, minp=0.12, ceil=1.45)
MAX += build('MAX', 2, [3, 2], (300, 1200), 6000, cand_legs(minsub=55), used_games_global=mg, exp=exp, cap=1, minp=0.10, ceil=1.6, prior=MAX)
NSC = cand_legs(starter=False, minsub=65)
NSC = [k for k in NSC if (PROJ[k[0]].get('proj_snap_pct') or 0) >= 0.45 and cov(k) >= 3]
MAXNS = build('MAX NS', 1, 3, (250, 1200), 6000, NSC, exp=exp, cap=1, minp=0.12, ceil=1.5)
PAR = build('P', 5, [3, 3, 3, 4, 4], (110, 400), 2500, cand_legs(), exp=exp, cap=3, minp=0.25, ceil=1.3, prior=MAX)
PARNS = build('P NS', 2, [3, 3], (110, 400), 2500, NSC, exp=exp, cap=2, minp=0.25, ceil=1.35, prior=MAXNS)

# receptions
RC = [k for k in cand_legs(mkts=['player_receptions'], minsub=60) if k[2] <= 6.5 and k[2] >= 2.5]
REC = build('R', 2, [4, 4], (-130, 300), 2500, RC, exp=collections.Counter(), cap=2, minp=0.3, ceil=1.35)
REC += build('R', 1, [3], (150, 700), 7000, RC, exp=collections.Counter(), cap=2, minp=0.15, ceil=1.6, prior=REC)

# TDs
def td_c(line, pos=None, starter=True, minsub=55):
    out = []
    for k in BL:
        if k[1] != 'player_anytime_td' or k[2] != line: continue
        n = k[0]
        if not eligible(n, starter): continue
        p = PROJ[n]
        if p['position'] not in ('RB', 'WR', 'TE'): continue
        if pos and p['position'] != pos: continue
        sub, _ = lens(n, k[1])
        if sub is None or sub < minsub: continue
        out.append(k)
    return out
td_extra = lambda k: 60 * (PROJ[k[0]]['mc_anytime_td'] or 0)
TD = build('TD', 2, [4, 4], (-150, 450), 2500, td_c(0.5, minsub=50), exp=collections.Counter(), cap=2, minp=0.18, extra_score=td_extra, overlap=1, noswap=True)
TD += build('TD', 1, [3], (150, 600), 2500, td_c(0.5, minsub=45), exp=collections.Counter(), cap=1, minp=0.1, prior=TD, overlap=1, noswap=True)
TD2 = build('2+ TD', 2, [2, 2], (250, 1500), 2500, td_c(1.5, minsub=55), exp=collections.Counter(), cap=1, minp=0.1, overlap=0)
TETD = build('TE TD', 2, [3, 4], (100, 600), 2500, td_c(0.5, 'TE', minsub=45), exp=collections.Counter(), cap=2, minp=0.12, noswap=True)
FTD = []
for k in BL:
    if k[1] == 'player_1st_td' and eligible(k[0]) and PROJ[k[0]]['position'] in ('RB', 'WR', 'TE'):
        sub, _ = lens(k[0], 'player_anytime_td')
        p = PROJ[k[0]]['mc_first_td'] or 0
        FTD.append((p * (1 + (sub or 50) / 200), k))
FTD = [k for _, k in sorted(FTD, reverse=True)[:8]]

# sacks: defender's team pressure rate + market fair prob
DEF = {d['defense']: d for d in O['def']}
SC = []
for k in BL:
    if k[1] != 'player_sacks' or k[2] not in (0.5, 1.5): continue
    if not INFO[k[0]][0]: continue
    team = INFO[k[0]][0]
    if INFO[k[0]][2] not in GAMES or k[0] in NO_TICKET: continue
    SC.append(k)
def sack_extra(k):
    d = DEF.get(INFO[k[0]][0], {})
    return 100 * (d.get('pressure_rate') or 0) + 20 * (d.get('sacks_pg') or 0)
SACK = build('SACK', 3, [4, 4, 3], (-135, 500), 2500, SC, exp=collections.Counter(), cap=2, minp=0.2, extra_score=sack_extra, overlap=2)

for lst in (MAX, MAXNS, PAR, PARNS, REC, TD, TD2, TETD, SACK):
    for t in lst: best_book_reprice(t)

# ceiling straights + ladders: starters with Good+ lens in core markets
CEIL = []
seen = set()
for k in sorted(cand_legs(minsub=65), key=lambda k: -(lens(k[0], k[1])[0] or 0)):
    key = (k[0], k[1])
    if key in seen: continue
    seen.add(key)
    pj = proj(*key)
    if not pj: continue
    rs = [r for r in rungs(*key) if pj * 1.12 <= r[2] <= pj * 1.35 and cov(r) >= 3]
    if not rs: continue
    r = rs[0]
    o, b = best(r)
    CEIL.append((r, o, b))
LAD = []
for key in sorted(seen, key=lambda x: -(lens(*x)[0] or 0)):
    rs = [r for r in rungs(*key) if best(r)]
    if len(rs) < 4: continue
    LAD.append((key, rs))
RLAD = []
for k in RC:
    key = (k[0], k[1])
    if key in [x[0] for x in RLAD]: continue
    rs = [r for r in rungs(*key) if best(r)]
    if len(rs) >= 3: RLAD.append((key, rs))
RLAD = sorted(RLAD, key=lambda x: -(lens(*x[0])[0] or 0))[:10]

pickle.dump(dict(MAX=MAX, MAXNS=MAXNS, PAR=PAR, PARNS=PARNS, REC=REC, TD=TD, TD2=TD2, TETD=TETD, FTD=FTD,
                 SACK=SACK, CEIL=CEIL, LAD=LAD, RLAD=RLAD), open('picks.pkl', 'wb'))

def show(name, ts):
    print('====', name)
    for t in ts:
        print(t['kind'], t['book'], fmt(t['price']), '| other', [(fmt(a), b) for a, b in other_books(t)[:2]])
        for k, o in t['legs']:
            sub, _ = lens(k[0], k[1])
            print('   ', k[0], INFO[k[0]][0], PROJ.get(k[0], {}).get('position'), MK[k[1]][0], k[2], fmt(o), 'sub', sub and round(sub), 'proj', round(proj(k[0], k[1]) or 0, 1), 'mp', round(mp(k) or 0, 2), 'cov', cov(k))
if __name__ == '__main__':
    for n, l in (('MAX', MAX), ('MAXNS', MAXNS), ('PAR', PAR), ('PARNS', PARNS), ('REC', REC), ('TD', TD), ('TD2', TD2), ('TETD', TETD), ('SACK', SACK)):
        show(n, l)
    print('FTD', [(k[0], best(k)) for k in FTD])
    print('CEIL', len(CEIL), [(r[0], MK[r[1]][0], r[2], o, b) for r, o, b in CEIL])
    print('LAD', len(LAD), 'RLAD', len(RLAD))
