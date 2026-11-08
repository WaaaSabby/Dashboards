from model import *

CORE = ['player_pass_yds', 'player_reception_yds', 'player_rush_yds', 'player_rush_reception_yds']

def rungs(name, mkt):
    return sorted([k for k in BL if k[0] == name and k[1] == mkt], key=lambda k: k[2])

def leg_score(name, mkt, line):
    sub, _ = lens(name, mkt)
    pj = proj(name, mkt) or 0
    base = max(line, 15)
    gap = max(-0.5, min(0.5, (pj - line) / base))
    return (sub or 0) + 30 * gap

def cand_legs(starter=True, mkts=CORE, minsub=65):
    out = []
    for k in BL:
        n, m, l = k
        if m not in mkts or not eligible(n, starter): continue
        pos = PROJ[n]['position']
        if pos == 'QB' and m != 'player_pass_yds': continue
        if pos != 'QB' and m == 'player_pass_yds': continue
        if pos == 'WR' and m in ('player_rush_yds', 'player_rush_reception_yds'): continue
        if pos == 'TE' and m != 'player_reception_yds' and m != 'player_receptions': continue
        sub, _ = lens(n, m)
        if sub is None or sub < minsub: continue
        c = cov(k)
        floor = 3 if m == 'player_rush_reception_yds' else 5
        if starter and c < floor: continue
        if m == 'player_rush_yds' and (proj(n, m) or 0) < 35: continue
        if m == 'player_reception_yds' and (proj(n, m) or 0) < 25: continue
        out.append(k)
    return out

def mp(k):
    m = model_p(*k)
    f = fair_p(k)
    if f is None:
        bb = best(k); f = imp(bb[0]) * 0.93 if bb else None
    if m is None: return f
    if f is None: return m
    return 0.5 * m + 0.5 * f

def build(kind, n_tickets, nlegs, band, floor, cands, used_games_global=None, exp=None, cap=2,
          ticket_games_unique=True, books=BOOKS, prefer_low=True, name_cap=None, extra_score=None, minp=0.0, prior=None, overlap=1, ceil=9.9, noswap=False):
    """Greedy ticket builder. Returns list of tickets: {book, legs:[(k, odds)], price}"""
    exp = exp if exp is not None else collections.Counter()
    tickets = []
    for t in range(n_tickets):
        bestT = None
        nl = nlegs[t] if isinstance(nlegs, list) else nlegs
        for b in books:
            # per player-market: choose rung in band at book b (lowest line = most likely)
            pm = {}
            for k in cands:
                if b not in BL[k]: continue
                o = BL[k][b][0]
                if not (band[0] <= o <= band[1]): continue
                key = (k[0], k[1])
                p = mp(k) or 0
                if p <= minp: continue
                pj = proj(k[0], k[1])
                if pj and k[2] > pj * ceil: continue
                sc = leg_score(*k) + 25 * p + (extra_score(k) if extra_score else 0)
                cur = pm.get(key)
                if cur is None or (sc > cur[0]): pm[key] = (sc, k, o)
            legs = sorted(pm.values(), key=lambda x: -x[0])
            chosen, games, players = [], set(), set()
            for sc, k, o in legs:
                g = INFO[k[0]][2]
                if used_games_global is not None and g in used_games_global: continue
                if ticket_games_unique and g in games: continue
                if k[0] in players: continue
                if exp[k[0]] >= cap: continue
                if any(len(set(x[0] for x, _ in pt['legs']) & (players | {k[0]})) > overlap for pt in (prior or []) + tickets): continue
                chosen.append((sc, k, o)); games.add(g); players.add(k[0])
                if len(chosen) == nl: break
            if len(chosen) < nl: continue
            price = 1
            for _, k, o in chosen: price *= dec(o)
            # push price up if under floor: swap each leg to a higher rung at same book
            tries = 0
            while amer(price) < floor and tries < 12 and not noswap:
                tries += 1
                # find leg whose next rung up costs least score
                bestswap = None
                for i, (sc, k, o) in enumerate(chosen):
                    rs = [r for r in rungs(k[0], k[1]) if r[2] > k[2] and b in BL[r] and BL[r][b][0] <= band[1] and (mp(r) or 0) > minp and r[2] <= (proj(r[0], r[1]) or 1e9) * ceil]
                    if not rs: continue
                    r = rs[0]; o2 = BL[r][b][0]
                    loss = sc - (leg_score(*r) + 25 * (mp(r) or 0))
                    if bestswap is None or loss < bestswap[0]: bestswap = (loss, i, r, o2)
                if not bestswap: break
                _, i, r, o2 = bestswap
                chosen[i] = (leg_score(*r) + 25 * (mp(r) or 0), r, o2)
                price = 1
                for _, k, o in chosen: price *= dec(o)
            if amer(price) < floor: continue
            tot = sum(c[0] for c in chosen)
            linkbonus = 5 if b in LINKABLE else 0
            if bestT is None or tot + linkbonus > bestT[0]:
                bestT = (tot + linkbonus, b, chosen, amer(price))
        if not bestT: break
        _, b, chosen, price = bestT
        tk = {'kind': kind, 'book': b, 'legs': [(k, o) for _, k, o in chosen], 'price': price}
        tickets.append(tk)
        for _, k, o in chosen:
            exp[k[0]] += 1
            if used_games_global is not None: used_games_global.add(INFO[k[0]][2])
    return tickets

def other_books(tk):
    out = []
    for b in BOOKS:
        if b == tk['book']: continue
        if all(b in BL[k] for k, _ in tk['legs']):
            p = 1
            for k, _ in tk['legs']: p *= dec(BL[k][b][0])
            out.append((amer(p), b))
    return sorted(out, reverse=True)

def fair_ticket(tk):
    p = 1
    for k, _ in tk['legs']:
        f = fair_p(k)
        if not f: return None
        p *= f
    return amer(1 / p)
