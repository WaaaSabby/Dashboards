"""Helpers for building the NBA dashboard from Sabby's MKB API pull.

Usage inside a build script:
    import sys; sys.path.insert(0, '<repo>/tools')
    from nba_api_lib import Slate
    S = Slate('/mnt/user-data/uploads/VF/API/2026-10-29/')   # folder with the day's nba_*.json files

Files expected in that folder (written by mkb_pull.py on her PC):
    nba_projections.json, nba_dvp.json, nba_games.json, nba_board.json (+EV board),
    nba_board_full.json (whole board, best price at her books),
    nba_board_full_<BOOK>.json for FD DK MG CZ ES BB BR HR (each book's own prices; HO is usually empty for NBA)

Conventions (match the Oct 28/29 pages):
    - DvP grade per stat from DvP HQ rank vs the player's position: pct = (30-rank)/29*100;
      Elite >= 91, Good 70-90, Neutral 40-69, Tough < 40. PRA = average of PTS/REB/AST pcts. G->PG, F->SF.
    - Exploit-board tags: red = lanes #1-6, yellow = #7-12 (class "xt red"/"xt yellow").
    - Every ticket priced at ONE book: S.price(legs) picks the book that pays most among books pricing every leg.
    - No EV numbers anywhere on the page. Overs only.
    - Use the latest nba/archive/<date>.html as the layout/CSS/JS template (tab script must not scroll).
"""
import json, html as _html

BOOKS = ['FD', 'DK', 'MG', 'CZ', 'ES', 'BB', 'BR', 'HR', 'HO']
MK = {'player_points': 'PTS', 'player_rebounds': 'REB', 'player_assists': 'AST', 'player_threes': '3PM',
      'player_points_rebounds_assists': 'PRA', 'player_points_rebounds': 'PR', 'player_points_assists': 'PA',
      'player_rebounds_assists': 'RA', 'player_double_double': 'DD', 'player_triple_double': 'TD',
      'player_first_basket': 'FB', 'player_first_team_basket': 'FTB', 'player_steals': 'STL', 'player_blocks': 'BLK'}
YESNO = ('DD', 'TD', 'FB', 'FTB')
STK = {'PTS': 'points', 'REB': 'rebounds', 'AST': 'assists', '3PM': 'threes'}
MCK = {'PTS': 'points', 'REB': 'rebounds', 'AST': 'assists', '3PM': 'threes', 'PRA': 'pra', 'RA': 'ra', 'PR': 'pr', 'PA': 'pa'}
PROJ = {'PTS': 'proj_points', 'REB': 'proj_rebounds', 'AST': 'proj_assists', '3PM': 'proj_threes', 'PRA': 'proj_pra'}
esc = _html.escape


def dec(a): return 1 + (a / 100 if a > 0 else 100 / -a)
def am(d): return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))
def fmt(o): return f'{o:+,d}'
def pct_from_rank(r): return round((30 - r) / 29 * 100)
def xt(rank):
    cls = 'red' if rank <= 6 else 'yellow' if rank <= 12 else 'green'
    return f'<span class="xt {cls}">board #{rank}</span>'


class Slate:
    def __init__(self, folder):
        f = folder.rstrip('/') + '/'
        ld = lambda n: json.load(open(f + n))['data']
        self.P = {r['player_name']: r for r in ld('nba_projections.json')}
        self.DV = {(r['team'], r['position']): r for r in ld('nba_dvp.json')}
        self.G = ld('nba_games.json')
        self.EV = ld('nba_board.json')
        self.FULL = ld('nba_board_full.json')
        self.GAME = {}
        for g in self.G:
            k = f"{g['away_team']} @ {g['home_team']}"
            self.GAME[g['away_team']] = self.GAME[g['home_team']] = k
        # per-book prices: (player, stat, rung) -> {book: odds}   (rung 1 for yes/no markets)
        self.BL = {}
        for bk in BOOKS:
            try: rows = ld(f'nba_board_full_{bk}.json')
            except FileNotFoundError: continue
            for r in rows:
                s = MK.get(r['market_type'])
                if not s or r['side'] not in ('Over', 'Yes'): continue
                rung = 1 if s in YESNO else int(r['line_value'] + 0.5)
                self.BL.setdefault((r['player_name'], s, rung), {})[bk] = r['best_book_odds']
        # whole board for baselines
        self._lines, self._under = {}, {}
        for r in self.FULL:
            s = MK.get(r['market_type'])
            if not s: continue
            tgt = self._lines if r['side'] == 'Over' else self._under if r['side'] == 'Under' else None
            if tgt is not None: tgt.setdefault((r['player_name'], s), {})[r['line_value']] = r

    # ----- player facts -----
    def team(self, p): return self.P[p]['team']
    def pos(self, p): return {'G': 'PG', 'F': 'SF'}.get(self.P[p]['position'], self.P[p]['position'])

    def grade(self, p, s):
        r = self.P[p]; d = self.DV.get((r['opponent'], self.pos(p)))
        if not d: return None
        if s in STK: v = pct_from_rank(d[STK[s] + '_rank'])
        else: v = round(sum(pct_from_rank(d[k + '_rank']) for k in ('points', 'rebounds', 'assists')) / 3)
        return ('Elite' if v >= 91 else 'Good' if v >= 70 else 'Neutral' if v >= 40 else 'Tough'), v

    def gtag(self, p, s):
        g = self.grade(p, s)
        if not g: return '<span class="tag ty">DvP n/a</span>'
        cls = {'Elite': 'tg', 'Good': 'tg', 'Neutral': 'ty', 'Tough': 'tr'}[g[0]]
        return f'<span class="tag {cls}">{g[0]} {g[1]}</span>'

    def model(self, p, s, rung):
        v = self.P[p]['mc_ladders'].get(MCK.get(s, ''), {}).get(str(rung))
        return None if v is None else round(v * 100)

    def baseline(self, p, s):
        L = self._lines.get((p, s)); U = self._under.get((p, s), {})
        if not L: return None
        pool = [l for l in L if l in U] or list(L)
        return max(pool, key=lambda l: L[l]['market_coverage'])

    def prices(self, p, s, rung):
        """[(book, odds)] best first."""
        return sorted(self.BL.get((p, s, rung), {}).items(), key=lambda x: -x[1])

    # ----- tickets -----
    def price(self, legs, book=None):
        """legs: dicts with p/s/rung. Returns list of (combined_american, book, [odds]) best first."""
        out = []
        for bk in BOOKS:
            if book and bk != book: continue
            os = [self.BL.get((l['p'], l['s'], l['rung']), {}).get(bk) for l in legs]
            if None in os: continue
            d = 1
            for o in os: d *= dec(o)
            out.append((am(d), bk, os))
        return sorted(out, reverse=True)

    def render_leg(self, l, o, bk):
        p, s, r = l['p'], l['s'], l['rung']
        bits = [self.GAME[self.team(p)], self.gtag(p, s)]
        m = self.model(p, s, r)
        if m is not None: bits.append(f'model {m}%')
        if l.get('why'): bits.append(l['why'])
        b = self.baseline(p, s)
        if b is not None and s in ('PTS', 'REB', 'AST'): bits.append(f'{b} baseline')
        if l.get('board'): bits.append(xt(l['board']))
        pj = self.P[p].get(PROJ.get(s, ''))
        if pj is not None: bits.append(f'proj {pj:.1f}')
        if l.get('bench'): bits.append('<b>Bench</b>')
        bits.append(f'<i>{l.get("tag", "Both agree")}</i>')
        return (f'<div class="leg"><div class="ln"><span class="n">{esc(p)} <span class="tm">({self.team(p)})</span> — {r}+ {s}</span>'
                f'<span class="lo">{fmt(o)} {bk}</span></div><div class="m">{" · ".join(bits)}</div></div>')

    def render_ticket(self, title, legs, note, fav=False, book=None):
        opts = self.price(legs, book)
        if not opts: raise ValueError(f'no single book prices every leg of {title}')
        comb, bk, odds = opts[0]
        star = '<span class="star">⭐</span> ' if fav else ''
        body = ''.join(self.render_leg(l, o, bk) for l, o in zip(legs, odds))
        return (f'<div class="parlay{" fav" if fav else ""}"><div class="ph"><span class="t">{star}{title} · {len(legs)} legs · {bk}</span>'
                f'<span class="o">{fmt(comb)}</span></div>{body}<div class="note">{note}</div></div>'), comb, bk


def leg(p, s, rung, why='', board=None, tag='Both agree', bench=False):
    return dict(p=p, s=s, rung=rung, why=why, board=board, tag=tag, bench=bench)


def table(heads, rows):
    """rows: list of cell tuples, or (cells, 'favrow') to border a starred row."""
    th = ''.join(f'<th>{h}</th>' for h in heads); body = ''
    for r in rows:
        cls = ''
        if isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], tuple):
            r, cls = r[0], (f' class="{r[1]}"' if r[1] else '')
        body += f'<tr{cls}>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>'
    return f'<div class="tblw"><table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table></div>'
