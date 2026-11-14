"""Builds BlockyPuzzle-v1.12-scratch.sb3: a Scratch 3 recreation of the Godot game Blocky Puzzle.

One hidden sprite ("Game") draws everything with pen stamps and holds all the logic; the Stage only
plays the music. All text is drawn from the game's own typeface, converted to outlines here.

Run:  python3 gen_sb3.py <audio_dir> <music.wav> <music2.wav> <font.ttf> <out.sb3>
"""
import json, hashlib, zipfile, wave, sys, os
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

AUDIO, MUSIC, MUSIC2, FONTPATH, OUT = sys.argv[1:6]

# ================================================================ block builder
_n = [0]
def nid():
    _n[0] += 1
    return "b%d" % _n[0]

class R:                     # reporter block
    def __init__(s, opcode, inputs=None, fields=None, mutation=None):
        s.opcode, s.inputs, s.fields, s.mutation = opcode, inputs or {}, fields or {}, mutation
class S(R): pass             # stack block
class V:                     # variable reporter
    def __init__(s, name): s.name = name

BLOCKS, SIG = {}, {}
VARS, LISTS, GLOBALS = {}, {}, {"musicOn": 1}

def lit(kind, v):
    if isinstance(v, float) and v == int(v): v = int(v)
    return [1, [10 if kind == "s" else 4, str(v)]]

def enc(kind, val, parent):
    if kind == "sub":
        first = stack(val, parent)
        return [2, first] if first else None
    if kind == "b":
        return [2, emit(val, parent)]
    if kind == "menu":
        op, fname, v = val
        sid = nid()
        const = v if not isinstance(v, (R, V)) else ""
        BLOCKS[sid] = {"opcode": op, "next": None, "parent": parent, "inputs": {}, "fields": {fname: [const, None]}, "shadow": True, "topLevel": False}
        if isinstance(v, R): return [3, emit(v, parent), sid]
        if isinstance(v, V): return [3, [12, v.name, "var_" + v.name], sid]
        return [1, sid]
    if isinstance(val, V): return [3, [12, val.name, "var_" + val.name], [10, ""]]
    if isinstance(val, R): return [3, emit(val, parent), [10 if kind == "s" else 4, ""]]
    return lit(kind, val)

def emit(b, parent, top=False):
    bid = nid()
    d = {"opcode": b.opcode, "next": None, "parent": parent, "inputs": {}, "fields": dict(b.fields), "shadow": False, "topLevel": top}
    if top: d["x"], d["y"] = 0, 0
    if b.mutation: d["mutation"] = b.mutation
    BLOCKS[bid] = d
    for name, (kind, val) in b.inputs.items():
        e = enc(kind, val, bid)
        if e is not None: d["inputs"][name] = e
    return bid

def stack(stmts, parent, top=False):
    first = prev = None
    for st in stmts:
        bid = emit(st, parent if prev is None else prev, top and prev is None)
        if prev: BLOCKS[prev]["next"] = bid
        else: first = bid
        prev = bid
    return first

def v(name, default=0):
    if name not in GLOBALS: VARS.setdefault(name, default)
    return V(name)
def op2(code, a, b, k="n", n1="NUM1", n2="NUM2"): return R(code, {n1: (k, a), n2: (k, b)})
def add(a, b, *more):
    r = op2("operator_add", a, b)
    for m in more: r = op2("operator_add", r, m)
    return r
def sub(a, b): return op2("operator_subtract", a, b)
def mul(a, b, *more):
    r = op2("operator_multiply", a, b)
    for m in more: r = op2("operator_multiply", r, m)
    return r
def div(a, b): return op2("operator_divide", a, b)
def mod(a, b): return op2("operator_mod", a, b)
def rnd(a): return R("operator_round", {"NUM": ("n", a)})
def mathop(o, a): return R("operator_mathop", {"NUM": ("n", a)}, {"OPERATOR": [o, None]})
def floor(a): return mathop("floor", a)
def ceil(a): return mathop("ceiling", a)
def absv(a): return mathop("abs", a)
def sin(a): return mathop("sin", a)          # degrees
def cos(a): return mathop("cos", a)
def sqrt(a): return mathop("sqrt", a)
def rand(a, b): return R("operator_random", {"FROM": ("n", a), "TO": ("n", b)})
def join(a, b, *more):
    r = R("operator_join", {"STRING1": ("s", a), "STRING2": ("s", b)})
    for m in more: r = R("operator_join", {"STRING1": ("s", r), "STRING2": ("s", m)})
    return r
def letter(i, s): return R("operator_letter_of", {"LETTER": ("n", i), "STRING": ("s", s)})
def length(s): return R("operator_length", {"STRING": ("s", s)})
def lt(a, b): return op2("operator_lt", a, b, "s", "OPERAND1", "OPERAND2")
def gt(a, b): return op2("operator_gt", a, b, "s", "OPERAND1", "OPERAND2")
def eq(a, b): return op2("operator_equals", a, b, "s", "OPERAND1", "OPERAND2")
def and_(a, b, *more):
    r = R("operator_and", {"OPERAND1": ("b", a), "OPERAND2": ("b", b)})
    for m in more: r = R("operator_and", {"OPERAND1": ("b", r), "OPERAND2": ("b", m)})
    return r
def or_(a, b, *more):
    r = R("operator_or", {"OPERAND1": ("b", a), "OPERAND2": ("b", b)})
    for m in more: r = R("operator_or", {"OPERAND1": ("b", r), "OPERAND2": ("b", m)})
    return r
def not_(a): return R("operator_not", {"OPERAND": ("b", a)})
def mn(a, b): return div(sub(add(a, b), absv(sub(a, b))), 2)
def mx(a, b): return div(add(add(a, b), absv(sub(a, b))), 2)
def LF(name):
    assert name in LISTS, name
    return {"LIST": [name, "list_" + name]}
def item(lst, i): return R("data_itemoflist", {"INDEX": ("n", i)}, LF(lst))
def itemnum(lst, x): return R("data_itemnumoflist", {"ITEM": ("s", x)}, LF(lst))
def lenlist(lst): return R("data_lengthoflist", {}, LF(lst))
def arg(name): return R("argument_reporter_string_number", {}, {"VALUE": [name, None]})
def mousex(): return R("sensing_mousex")
def mousey(): return R("sensing_mousey")
def mousedown(): return R("sensing_mousedown")
def timer(): return R("sensing_timer")
def VF(name):
    v(name)
    return {"VARIABLE": [name, "var_" + name]}
def setv(n, x): return S("data_setvariableto", {"VALUE": ("s", x)}, VF(n))
def chg(n, x): return S("data_changevariableby", {"VALUE": ("n", x)}, VF(n))
def replace(lst, i, x): return S("data_replaceitemoflist", {"INDEX": ("n", i), "ITEM": ("s", x)}, LF(lst))
def addto(lst, x): return S("data_addtolist", {"ITEM": ("s", x)}, LF(lst))
def delall(lst): return S("data_deletealloflist", {}, LF(lst))
def if_(c, body): return S("control_if", {"CONDITION": ("b", c), "SUBSTACK": ("sub", body)})
def ifelse(c, a, b): return S("control_if_else", {"CONDITION": ("b", c), "SUBSTACK": ("sub", a), "SUBSTACK2": ("sub", b)})
def repeat(n, body): return S("control_repeat", {"TIMES": ("n", n), "SUBSTACK": ("sub", body)})
def forever(body): return S("control_forever", {"SUBSTACK": ("sub", body)})
def until(c, body): return S("control_repeat_until", {"CONDITION": ("b", c), "SUBSTACK": ("sub", body)})
def goto(x, y): return S("motion_gotoxy", {"X": ("n", x), "Y": ("n", y)})
def point(d): return S("motion_pointindirection", {"DIRECTION": ("n", d)})
def costume(c): return S("looks_switchcostumeto", {"COSTUME": ("menu", ("looks_costume", "COSTUME", c))})
def size(x): return S("looks_setsizeto", {"SIZE": ("n", x)})
def ghost(x): return S("looks_seteffectto", {"VALUE": ("n", x)}, {"EFFECT": ["GHOST", None]})
def clearfx(): return S("looks_cleargraphiceffects")
def hide(): return S("looks_hide")
def erase(): return S("pen_clear")
def stamp_(): return S("pen_stamp")
def play(name): return S("sound_play", {"SOUND_MENU": ("menu", ("sound_sounds_menu", "SOUND_MENU", name))})
def playwait(name): return S("sound_playuntildone", {"SOUND_MENU": ("menu", ("sound_sounds_menu", "SOUND_MENU", name))})
def pitch(x): return S("sound_seteffectto", {"VALUE": ("n", x)}, {"EFFECT": ["PITCH", None]})
def volume(x): return S("sound_setvolumeto", {"VOLUME": ("n", x)})
def resettimer(): return S("sensing_resettimer")
def flag(body): stack([S("event_whenflagclicked")] + body, None, True)
def proccode(name): return name + " %s" * len(SIG[name])
def argids(name): return ["arg_%s_%s" % (name.replace(" ", "_"), a) for a in SIG[name]]
def call(name, *args):
    assert len(args) == len(SIG[name]), name
    return S("procedures_call", {i: ("s", a) for i, a in zip(argids(name), args)},
             mutation={"tagName": "mutation", "children": [], "proccode": proccode(name), "argumentids": json.dumps(argids(name)), "warp": "true"})
DEFINED = set()
def define(name, body):
    DEFINED.add(name)
    did, pid = nid(), nid()
    ids = argids(name)
    BLOCKS[did] = {"opcode": "procedures_definition", "next": None, "parent": None, "inputs": {"custom_block": [1, pid]}, "fields": {}, "shadow": False, "topLevel": True, "x": 0, "y": 0}
    proto = {"opcode": "procedures_prototype", "next": None, "parent": did, "inputs": {}, "fields": {}, "shadow": True, "topLevel": False,
             "mutation": {"tagName": "mutation", "children": [], "proccode": proccode(name), "argumentids": json.dumps(ids),
                          "argumentnames": json.dumps(SIG[name]), "argumentdefaults": json.dumps([""] * len(ids)), "warp": "true"}}
    BLOCKS[pid] = proto
    for i, a in zip(ids, SIG[name]):
        rid = nid()
        BLOCKS[rid] = {"opcode": "argument_reporter_string_number", "next": None, "parent": pid, "inputs": {}, "fields": {"VALUE": [a, None]}, "shadow": True, "topLevel": False}
        proto["inputs"][i] = [1, rid]
    BLOCKS[did]["next"] = stack(body, did)

# ================================================================ game data
N, CS = 8, 34
BX, BY, BW = -136, 136, 272             # board: top-left corner and width, in stage steps
LX, TX = -188, 188                      # centre of the left panel (score) and of the tray
TC = 17                                 # tray cell size
BASES = [(["x"], 1, 1), (["xx"], 2, 3), (["xxx"], 3, 4), (["xxxx"], 4, 3), (["xxxxx"], 5, 2),
         (["xx", "xx"], 6, 5), (["xxx", "xxx", "xxx"], 7, 3), (["xxx", "xxx"], 2, 3),
         (["x.", "xx"], 3, 4), (["x.", "x.", "xx"], 4, 3), ([".x", ".x", "xx"], 5, 3),
         (["x..", "x..", "xxx"], 6, 3), (["xxx", ".x."], 1, 3), ([".xx", "xx."], 7, 2), (["xx.", ".xx"], 5, 2),
         (["x.", ".x"], 4, 1)]
def rot90(m): return ["".join(m[r][c] for r in range(len(m) - 1, -1, -1)) for c in range(len(m[0]))]
pw, ph, pcol, pstart, pcount, pdx, pdy, bag = [], [], [], [], [], [], [], []
for shape, color, weight in BASES:
    seen, m = [], shape
    for _ in range(4):
        if m not in seen: seen.append(m)
        m = rot90(m)
    for vv in seen:
        cells = [(c, r) for r, row in enumerate(vv) for c, ch in enumerate(row) if ch == "x"]
        pw.append(len(vv[0])); ph.append(len(vv)); pcol.append(color)
        pstart.append(len(pdx) + 1); pcount.append(len(cells))
        for c, r in cells: pdx.append(c); pdy.append(r)
        bag += [len(pw)] * max(1, round(12 * weight / len(seen)))

# ================================================================ costumes
INK, CREAM, CELLC, GOLD, GREEN, GREEN2, MUTED, RED = "#1c1a17", "#f3ead5", "#e2d5b6", "#f2b632", "#1f4b43", "#235249", "#7a6f5a", "#e8503a"
COLORS = ["#000000", "#e8503a", "#f58a1f", "#f2b632", "#6cba3f", "#3d8fd9", "#8f5bd0", "#ef7fa5", "#8f897b"]
FONT = TTFont(FONTPATH); GSET = FONT.getGlyphSet(); CMAP = FONT.getBestCmap(); HMTX = FONT["hmtx"]
def adv(ch): return HMTX[CMAP[ord(ch)]][0] / 1000.0
def twidth(t, px): return sum(adv(c) for c in t) * px
def tpath(t, x, base, px):
    d = ""
    for ch in t:
        pen = SVGPathPen(GSET)
        GSET[CMAP[ord(ch)]].draw(TransformPen(pen, (px / 1000.0, 0, 0, -px / 1000.0, x, base)))
        d += pen.getCommands()
        x += adv(ch) * px
    return d
def txt(t, cx, cy, px, fill, outline=None, anchor="m", opacity=1.0):
    w = twidth(t, px)
    x = cx - w / 2 if anchor == "m" else (cx if anchor == "l" else cx - w)
    d = tpath(t, x, cy + px * 0.35, px)
    o = ' fill-opacity="%g"' % opacity if opacity < 1 else ""
    s = ""
    if outline:
        s += '<path d="%s" fill="%s" stroke="%s" stroke-width="%g" stroke-linejoin="round"/>' % (d, outline, outline, px * 0.17)
    return s + '<path d="%s" fill="%s"%s/>' % (d, fill, o)
def dark(h, k=0.72): return "#%02x%02x%02x" % tuple(int(int(h[i:i + 2], 16) * k) for i in (1, 3, 5))
def svg(w, h, body):
    return ('<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%g" height="%g" viewBox="0 0 %g %g">'
            '<rect width="%g" height="%g" fill="none"/>%s</svg>') % (w, h, w, h, w, h, body)
COSTUMES, LABW = [], {}
def C(name, w, h, body, cx=None, cy=None):
    assert name not in [c[0] for c in COSTUMES], name
    COSTUMES.append((name, svg(w, h, body), w / 2 if cx is None else cx, h / 2 if cy is None else cy))
def label(name, t, px, fill, outline=None, opacity=1.0):
    w = twidth(t, px)
    LABW[name] = w
    pad = px * 0.3
    C(name, w + pad * 2, px * 1.5, txt(t, w / 2 + pad, px * 0.75, px, fill, outline, opacity=opacity))
def tile_body(col, s=CS, x=0, y=0):
    k = s / 34.0
    return ('<rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s"/><rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s"/>'
            '<rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="%s"/><rect x="%g" y="%g" width="%g" height="%g" rx="%g" fill="#ffffff" fill-opacity="0.45"/>'
            % (x + 1 * k, y + 1 * k, 32 * k, 32 * k, 6 * k, INK, x + 3 * k, y + 3 * k, 28 * k, 28 * k, 4 * k, dark(col),
               x + 3 * k, y + 3 * k, 28 * k, 24 * k, 4 * k, col, x + 7 * k, y + 6 * k, 7 * k, 3 * k, 1.5 * k))
def body(w, h, fill, r):       # a button face with an ink border
    return '<rect x="1.5" y="1.5" width="%g" height="%g" rx="%g" fill="%s" stroke="%s" stroke-width="3"/>' % (w - 3, h - 3, r, fill, INK)
def shadow(name, w, h, r):
    C(name, w, h, '<rect x="0" y="0" width="%g" height="%g" rx="%g" fill="%s"/>' % (w, h, r, INK))

for i in range(1, 9): C("t%d" % i, CS, CS, tile_body(COLORS[i]))
C("t9", CS, CS, '<rect x="1" y="1" width="32" height="32" rx="6" fill="#ffffff" stroke="%s" stroke-width="2"/>' % INK)
C("tg", CS, CS, tile_body("#b9b3a3"))
C("cell", CS, CS, '<rect x="2" y="2" width="30" height="30" rx="5" fill="%s"/>' % CELLC)
frame = '<rect x="0" y="6" width="292" height="292" rx="12" fill="%s"/><rect x="2" y="2" width="288" height="288" rx="12" fill="%s" stroke="%s" stroke-width="4"/>' % (INK, CREAM, INK)
cells = "".join('<rect x="%d" y="%d" width="30" height="30" rx="5" fill="%s"/>' % (12 + c * CS, 12 + r * CS, CELLC) for r in range(N) for c in range(N))
C("frame", 292, 298, frame, 146, 146)
C("board", 292, 298, frame + cells, 146, 146)
C("stripes", 760, 360, "".join('<polygon points="%g,0 %g,0 %g,360 %g,360" fill="%s"/>' % (x, x + 22.5, x + 22.5 - 144, x - 144, GREEN2) for x in [k * 50.625 for k in range(0, 19)]), 380, 180)
BROWN = "#6b4226"
C("splash-bg", 480, 360, '<rect width="480" height="360" fill="%s"/>' % BROWN + "".join('<polygon points="%g,0 %g,0 %g,360 %g,360" fill="#754b2d"/>' % (x, x + 14, x + 14 - 144, x - 144) for x in range(0, 640, 34)))
label("splash-t", "Seh's Workshop", 44, CREAM, INK)
C("title1", 300, 70, txt("BLOCKY", 150, 35, 45, CREAM, INK))
C("title2", 300, 70, txt("PUZZLE", 150, 35, 45, GOLD, INK))
C("deco1", 44, 44, "".join(tile_body(COLORS[6], 13, x, y) for x, y in [(2, 2), (15, 2), (28, 2), (2, 15), (2, 28)]))
C("deco2", 32, 44, "".join(tile_body(COLORS[2], 13, x, y) for x in (2, 15) for y in (2, 15, 28)))
# buttons: a shadow costume plus a face; the face sinks onto the shadow while it is held down
shadow("sh-play", 161, 46, 11); C("b-play", 161, 46, body(161, 46, COLORS[4], 11) + txt("PLAY", 80.5, 17, 25, INK))
shadow("sh-menu", 133, 31, 15.5)
for n_, t_ in [("b-modes", "GAME MODES"), ("b-help", "HOW TO PLAY"), ("b-settings", "SETTINGS")]:
    C(n_, 133, 31, body(133, 31, CREAM, 14) + txt(t_, 66.5, 15.5, 13, INK))
shadow("sh-sq", 27, 27, 6)
C("b-back", 27, 27, body(27, 27, CREAM, 6) + '<polygon points="6.5,13.5 14.5,6.5 14.5,10.7 20.5,10.7 20.5,16.3 14.5,16.3 14.5,20.5" fill="%s"/>' % INK)
shadow("sh-hud", 30, 30, 7)
C("b-home", 30, 30, body(30, 30, CREAM, 7) + '<polygon points="15,7 23.5,15 20.5,15 20.5,22 9.5,22 9.5,15 6.5,15" fill="%s"/>' % INK)
C("b-new", 30, 30, body(30, 30, CREAM, 7) + '<path d="M 17.2 9.4 A 6 6 0 1 0 20.8 16.6" fill="none" stroke="%s" stroke-width="2.4" stroke-linecap="round"/><polygon points="13.4,6.2 20,8.8 14.6,12.6" fill="%s"/>' % (INK, INK))
C("b-ask", 30, 30, body(30, 30, GOLD, 7) + txt("?", 15, 15, 17, INK))
MODES = [("CLASSIC", "No clock. Play till the board jams.", 1), ("RUSH", "Two minutes. Each line adds 2 sec.", 5),
         ("30 MOVES", "Thirty pieces. Make them count.", 4), ("RUBBLE", "Stones drop in every 4 moves.", 3)]
shadow("sh-card", 325, 45, 8)
for i, (nm, desc, col) in enumerate(MODES, 1):
    C("card%d" % i, 325, 45, body(325, 45, CREAM, 8) + tile_body(COLORS[col], 29, 8, 8) + txt(nm, 45, 15, 15.4, INK, anchor="l")
      + txt(desc, 45, 32, 11.5, MUTED, anchor="l") + txt("BEST", 316, 13, 9.5, MUTED, anchor="r"))
    label("m%d" % i, nm, 13, "#b9c4b3")
    label("sub%d" % i, nm + "  -  best", 10.5, INK, opacity=0.75)
    label("os%d" % i, nm + " SCORE", 10.4, MUTED)
HELP = [(3, "Drag a piece from the tray", "onto the board."), (5, "Fill a whole row or column", "and it clears."),
        (1, "Clear on back-to-back moves", "to build a combo."), (6, "Pieces never rotate. Out of", "room means game over.")]
for i, (col, a, b) in enumerate(HELP, 1):
    C("help%d" % i, 325, 51, '<rect x="0" y="6" width="325" height="45" rx="8" fill="%s"/>' % INK + '<g transform="translate(0,3)">' + body(325, 45, CREAM, 8)
      + tile_body(COLORS[col], 29, 8, 8) + txt(str(i), 22.5, 21.5, 15.4, INK) + txt(a, 45, 15, 11.2, INK, anchor="l") + txt(b, 45, 30, 11.2, INK, anchor="l") + "</g>", 162.5, 25.5)
for n_, a, b in [("row-sound", "SOUND", "Clicks, thuds and chimes"), ("row-music", "MUSIC", "Background tune"), ("row-reset", "BEST SCORES", "Wipe every mode's record")]:
    C(n_, 325, 51, '<rect x="0" y="6" width="325" height="45" rx="8" fill="%s"/>' % INK + '<g transform="translate(0,3)">' + body(325, 45, CREAM, 8)
      + txt(a, 10, 15, 14, INK, anchor="l") + txt(b, 10, 32, 11.5, MUTED, anchor="l") + "</g>", 162.5, 25.5)
shadow("sh-tg", 69, 27, 13.5)
for n_, t_, f_ in [("tg-on", "ON", GOLD), ("tg-off", "OFF", CELLC), ("tg-reset", "RESET", CREAM), ("tg-sure", "SURE?", RED)]:
    C(n_, 69, 27, body(69, 27, f_, 12) + txt(t_, 34.5, 13.5, 11.5, INK))
label("madeby", "Made by sehrn.xyz", 16, GOLD, INK)
label("credits", "Built with Scratch  -  Typeface: Lilita One (OFL)", 9.5, CREAM, opacity=0.6)
label("h-modes", "GAME MODES", 22, CREAM, INK); label("h-help", "HOW TO PLAY", 22, CREAM, INK); label("h-settings", "SETTINGS", 22, CREAM, INK)
label("ver", "v1.13-scratch", 8.5, CREAM, opacity=0.5)
label("l-best", "BEST", 14, GOLD); label("l-best-s", "BEST", 11, "#b9c4b3"); label("l-moves", "MOVES LEFT", 11, GOLD); label("l-stones", "STONES IN", 11, GOLD)
C("bar-bg", 86, 8, '<rect width="86" height="8" rx="4" fill="%s"/>' % INK)
C("bar-seg", 2, 4, '<rect width="2" height="4" fill="%s"/>' % GOLD)
C("bar-red", 2, 4, '<rect width="2" height="4" fill="%s"/>' % RED)
C("badge", 46, 48, '<circle cx="23" cy="26" r="21" fill="%s"/><circle cx="23" cy="23" r="19.5" fill="%s" stroke="%s" stroke-width="3"/>' % (INK, COLORS[2], INK), 23, 24)
PRAISE = {"p2": "NICE!", "p3": "SWEET!", "p4": "WHOA!", "p5": "UNREAL!", "p6": "LEGEND!", "p-sweep": "CLEAN SWEEP!", "p-combo": "COMBO x", "p-gotit": "YOU GOT IT!"}
for n_, t_ in PRAISE.items(): label(n_, t_, 25, CREAM, INK)
C("overpanel", 284, 284, '<rect x="0" y="0" width="284" height="284" rx="9" fill="%s" fill-opacity="0.93"/>' % CREAM)
label("o-noroom", "NO ROOM LEFT", 25, RED); label("o-timeup", "TIME'S UP", 25, RED); label("o-nomoves", "OUT OF MOVES", 25, RED)
label("o-newbest", "NEW BEST!", 13, "#d9800d"); label("l-best-k", "BEST", 13, MUTED)
shadow("sh-again", 152, 37, 18.5); C("b-again", 152, 37, body(152, 37, COLORS[4], 17) + txt("PLAY AGAIN", 76, 18.5, 16.5, INK))
shadow("sh-omenu", 96, 27, 13.5); C("b-omenu", 96, 27, body(96, 27, CREAM, 12) + txt("MENU", 48, 13.5, 12.5, INK))
C("hand", 16, 30, '<rect x="1" y="3" width="14" height="27" rx="7" fill="%s"/><rect x="2" y="1.5" width="12" height="25" rx="6" fill="%s" stroke="%s" stroke-width="2"/>' % (INK, CREAM, INK), 8, 4)
label("c-drag", "DRAG A PIECE ONTO THE BOARD", 12.5, CREAM, INK); label("c-line", "FILL A LINE TO CLEAR IT", 12.5, CREAM, INK)
C("hl", 276, 38, '<rect x="2" y="2" width="272" height="34" rx="7" fill="%s" fill-opacity="0.2" stroke="%s" stroke-width="3"/>' % (GOLD, GOLD))
C("beam", 288, 34, '<rect width="288" height="34" rx="17" fill="#fff8d0"/>')
C("vign", 480, 360, '<path d="M0 0H480V360H0Z M7 7V353H473V7Z" fill="%s" fill-rule="evenodd"/>' % RED)
C("dust", 8, 8, '<circle cx="4" cy="4" r="4" fill="#c0b393"/>')
# glyphs for numbers that change while playing: 0-9 : + x -   (index 1..14), in five paint jobs
GCH = list("0123456789:+x-")
GSETS = {"o": (CREAM, INK), "y": (GOLD, INK), "g": (GOLD, None), "k": (INK, None), "u": (MUTED, None)}
for s_, (fill, outl) in GSETS.items():
    for i, ch in enumerate(GCH, 1):
        C("%s%d" % (s_, i), adv(ch) * 40 + 12, 60, txt(ch, 6, 30, 40, fill, outl, anchor="l"), 6, 30)

assets = {}
def add_asset(data, ext):
    md5 = hashlib.md5(data).hexdigest()
    assets[md5 + "." + ext] = data
    return md5
def costume_entry(name, src, cx, cy):
    md5 = add_asset(src.encode(), "svg")
    return {"name": name, "bitmapResolution": 1, "dataFormat": "svg", "assetId": md5, "md5ext": md5 + ".svg", "rotationCenterX": cx, "rotationCenterY": cy}
def sound_entry(name, path):
    data = open(path, "rb").read()
    w = wave.open(path)
    md5 = add_asset(data, "wav")
    return {"name": name, "assetId": md5, "dataFormat": "wav", "format": "", "rate": w.getframerate(), "sampleCount": w.getnframes(), "md5ext": md5 + ".wav"}

# ================================================================ lists and buttons
NPART, NPOP = 48, 6
# buttons: id -> (x, y, half width, half height, screen)
CARDY = [103, 50, -4, -57]
BTN = {1: (0, 4, 82, 24, "main"), 2: (0, -57, 68, 17, "main"), 3: (0, -96, 68, 17, "main"), 4: (0, -134, 68, 17, "main"),
       5: (-150, 158, 16, 16, "sub"),
       6: (0, CARDY[0], 163, 23, "modes"), 7: (0, CARDY[1], 163, 23, "modes"), 8: (0, CARDY[2], 163, 23, "modes"), 9: (0, CARDY[3], 163, 23, "modes"),
       10: (118, CARDY[0], 36, 15, "settings"), 11: (118, CARDY[1], 36, 15, "settings"), 12: (118, CARDY[2], 36, 15, "settings"),
       13: (-206, -119, 17, 17, "play"), 14: (-170, -119, 17, 17, "play"),
       15: (0, -51, 78, 20, "over"), 16: (0, -103, 50, 15, "over")}
LISTS.update({
    "grid": [0] * 64, "sim": [0] * 64, "will": [0] * 64, "placeT": [1] * 64, "fxT": [9] * 64, "fxC": [0] * 64,
    "tray": [0, 0, 0], "trayT": [1, 1, 1], "bests": [0, 0, 0, 0], "rowsFull": [], "colsFull": [],
    "pw": pw, "ph": ph, "pcol": pcol, "pstart": pstart, "pcount": pcount, "pdx": pdx, "pdy": pdy, "bag": bag,
    "dch": GCH, "dw": [round(adv(c), 4) for c in GCH],
    "btnX": [BTN[i][0] for i in range(1, 17)], "btnY": [BTN[i][1] for i in range(1, 17)], "btnW": [BTN[i][2] for i in range(1, 17)],
    "btnH": [BTN[i][3] for i in range(1, 17)], "btnS": [BTN[i][4] for i in range(1, 17)],
    "pX": [0] * NPART, "pY": [0] * NPART, "pVX": [0] * NPART, "pVY": [0] * NPART, "pT": [9] * NPART, "pLife": [0] * NPART, "pS": [0] * NPART, "pC": ["t1"] * NPART, "pG": [0] * NPART,
    "popX": [0] * NPOP, "popY": [0] * NPOP, "popS": [""] * NPOP, "popT": [9] * NPOP, "popBig": [0] * NPOP,
    "beamRow": [], "beamI": [], "beamT": [],
    "subW": [round(LABW["sub%d" % i], 2) for i in range(1, 5)],
    "praiseW": [0, round(LABW["p2"], 2), round(LABW["p3"], 2), round(LABW["p4"], 2), round(LABW["p5"], 2), round(LABW["p6"], 2)],
})
SIG.update({
    "stamp": ["cos", "x", "y", "size"], "stamp rot": ["cos", "x", "y", "size", "dir"], "ease": ["k"],
    "str width": ["s", "px"], "draw str": ["s", "x", "y", "px", "set"], "draw num": ["s", "x", "y", "px", "set"],
    "label num": ["cos", "lw", "s", "x", "y", "px", "set", "numfirst"],
    "button": ["id", "cos", "sh", "x", "y", "scale"], "draw piece": ["p", "x", "y", "cell"],
    "sfx": ["name", "pitch"], "fits": ["p", "c", "r"], "fits anywhere": ["p"], "can move": [],
    "sim fits": ["p", "c", "r"], "sim lines": ["p", "c", "r"], "sim place": ["p", "c", "r"], "deal": [],
    "coach calc": [], "new game": [], "check lines": [], "drop stones": [], "end game": ["why"], "place": ["slot", "c", "r"],
    "spawn": ["x", "y", "vx", "vy", "life", "s", "cos", "g"], "confetti": ["n"], "popup": ["x", "y", "s", "big"],
    "will calc": [], "go": ["screen"], "start mode": ["m"], "act": ["id"], "hit": [], "tick": [], "anim": [],
    "draw head": ["cos"], "draw main": [], "draw modes": [], "draw help": [], "draw settings": [],
    "draw splash": [], "draw hud": [], "draw board": [], "draw fx": [], "draw coach": [], "draw over": [], "draw": [],
})
def gidx(c, r): return add(mul(r, 8), c, 1)
def cellx(c): return add(BX + CS / 2, mul(c, CS))
def celly(r): return sub(BY - CS / 2, mul(r, CS))
def stp(c, x, y, s=100): return call("stamp", c, x, y, s)

BLOCKS = {}
# ---------------------------------------------------------------- small helpers
define("stamp", [costume(arg("cos")), size(arg("size")), goto(arg("x"), arg("y")), stamp_()])
define("stamp rot", [point(arg("dir")), costume(arg("cos")), size(arg("size")), goto(arg("x"), arg("y")), stamp_(), point(90)])
define("ease", [                                           # "back" ease-out, result in eb; k is clamped to 0..1
    setv("ek", arg("k")), if_(lt(v("ek"), 0), [setv("ek", 0)]), if_(gt(v("ek"), 1), [setv("ek", 1)]),
    setv("ek", sub(v("ek"), 1)),
    setv("eb", add(1, mul(2.70158, v("ek"), v("ek"), v("ek")), mul(1.70158, v("ek"), v("ek")))),
])
define("str width", [
    setv("sw", 0), setv("swi", 1),
    repeat(length(arg("s")), [
        setv("swn", itemnum("dch", letter(v("swi"), arg("s")))),
        if_(gt(v("swn"), 0), [chg("sw", mul(item("dw", v("swn")), arg("px")))]),
        chg("swi", 1)]),
])
define("draw str", [                                       # x = left edge
    setv("dsx", arg("x")), setv("dsi", 1),
    repeat(length(arg("s")), [
        setv("dsn", itemnum("dch", letter(v("dsi"), arg("s")))),
        if_(gt(v("dsn"), 0), [stp(join(arg("set"), v("dsn")), v("dsx"), arg("y"), mul(arg("px"), 2.5)), chg("dsx", mul(item("dw", v("dsn")), arg("px")))]),
        chg("dsi", 1)]),
])
define("draw num", [call("str width", arg("s"), arg("px")), call("draw str", arg("s"), sub(arg("x"), div(v("sw"), 2)), arg("y"), arg("px"), arg("set"))])
define("label num", [                                      # a word and a number side by side, centred on x
    call("str width", arg("s"), arg("px")),
    setv("lnT", add(arg("lw"), 4, v("sw"))),
    ifelse(eq(arg("numfirst"), 1), [
        call("draw str", arg("s"), sub(arg("x"), div(v("lnT"), 2)), arg("y"), arg("px"), arg("set")),
        stp(arg("cos"), sub(add(arg("x"), div(v("lnT"), 2)), div(arg("lw"), 2)), arg("y")),
    ], [
        stp(arg("cos"), add(sub(arg("x"), div(v("lnT"), 2)), div(arg("lw"), 2)), arg("y")),
        call("draw str", arg("s"), add(sub(arg("x"), div(v("lnT"), 2)), arg("lw"), 4), arg("y"), arg("px"), arg("set")),
    ]),
])
define("button", [                                         # leaves the face's vertical offset in boff
    ifelse(eq(v("pressId"), arg("id")), [setv("boff", -3)], [setv("boff", 0)]),
    stp(arg("sh"), arg("x"), sub(arg("y"), 3), arg("scale")),
    stp(arg("cos"), arg("x"), add(arg("y"), v("boff")), arg("scale")),
])
define("draw piece", [                                     # x, y = centre of the piece
    setv("dpk", item("pstart", arg("p"))),
    setv("dpx", sub(arg("x"), mul(item("pw", arg("p")), div(arg("cell"), 2)))),
    setv("dpy", add(arg("y"), mul(item("ph", arg("p")), div(arg("cell"), 2)))),
    repeat(item("pcount", arg("p")), [
        stp(join("t", item("pcol", arg("p"))),
            add(v("dpx"), mul(add(item("pdx", v("dpk")), 0.5), arg("cell"))),
            sub(v("dpy"), mul(add(item("pdy", v("dpk")), 0.5), arg("cell"))), mul(arg("cell"), 100.0 / CS)),
        chg("dpk", 1)]),
])
# (the pitch argument is unused: Scratch's "set pitch" block makes the script wait a frame, which would stall the game loop)
define("sfx", [if_(eq(v("soundOn", 1), 1), [S("sound_play", {"SOUND_MENU": ("menu", ("sound_sounds_menu", "SOUND_MENU", arg("name")))})])])

# ---------------------------------------------------------------- rules
define("fits", [
    setv("fit", 1),
    ifelse(or_(lt(arg("c"), 0), lt(arg("r"), 0), gt(add(arg("c"), item("pw", arg("p"))), 8), gt(add(arg("r"), item("ph", arg("p"))), 8)),
           [setv("fit", 0)],
           [setv("fk", item("pstart", arg("p"))),
            repeat(item("pcount", arg("p")), [
                if_(not_(eq(item("grid", gidx(add(arg("c"), item("pdx", v("fk"))), add(arg("r"), item("pdy", v("fk"))))), 0)), [setv("fit", 0)]),
                chg("fk", 1)])]),
])
define("fits anywhere", [
    setv("any", 0), setv("far", 0),
    repeat(sub(9, item("ph", arg("p"))), [
        setv("fac", 0),
        repeat(sub(9, item("pw", arg("p"))), [call("fits", arg("p"), v("fac"), v("far")), if_(eq(v("fit"), 1), [setv("any", 1)]), chg("fac", 1)]),
        chg("far", 1)]),
])
define("can move", [
    setv("canMove", 0), setv("cmi", 1),
    repeat(3, [
        if_(gt(item("tray", v("cmi")), 0), [call("fits anywhere", item("tray", v("cmi"))), if_(eq(v("any"), 1), [setv("canMove", 1)])]),
        chg("cmi", 1)]),
])
# -- fair dealing works on "sim", a scratch copy of the board
define("sim fits", [
    setv("fit", 1), setv("fk", item("pstart", arg("p"))),
    repeat(item("pcount", arg("p")), [
        if_(not_(eq(item("sim", gidx(add(arg("c"), item("pdx", v("fk"))), add(arg("r"), item("pdy", v("fk"))))), 0)), [setv("fit", 0)]),
        chg("fk", 1)]),
])
def sim_line_count(rows):                                  # counts full rows (or columns) the piece touches
    n, start = ("ph", arg("r")) if rows else ("pw", arg("c"))
    cellref = gidx(v("slj"), v("sli")) if rows else gidx(v("sli"), v("slj"))
    return [setv("sli", start),
            repeat(item(n, arg("p")), [
                setv("full", 1), setv("slj", 0),
                repeat(8, [if_(eq(item("sim", cellref), 0), [setv("full", 0)]), chg("slj", 1)]),
                chg("sl", v("full")), chg("sli", 1)])]
def sim_cells(value):
    return [setv("fk", item("pstart", arg("p"))),
            repeat(item("pcount", arg("p")), [
                replace("sim", gidx(add(arg("c"), item("pdx", v("fk"))), add(arg("r"), item("pdy", v("fk")))), value), chg("fk", 1)])]
define("sim lines", sim_cells(9) + [setv("sl", 0)] + sim_line_count(True) + sim_line_count(False) + sim_cells(0))
define("sim place", sim_cells(item("pcol", arg("p"))) + [
    delall("rowsFull"), delall("colsFull"), setv("sli", 0),
    repeat(8, [
        setv("full", 1), setv("slj", 0),
        repeat(8, [if_(eq(item("sim", gidx(v("slj"), v("sli"))), 0), [setv("full", 0)]), chg("slj", 1)]),
        if_(eq(v("full"), 1), [addto("rowsFull", v("sli"))]),
        setv("full", 1), setv("slj", 0),
        repeat(8, [if_(eq(item("sim", gidx(v("sli"), v("slj"))), 0), [setv("full", 0)]), chg("slj", 1)]),
        if_(eq(v("full"), 1), [addto("colsFull", v("sli"))]),
        chg("sli", 1)]),
    setv("fk", 1), repeat(lenlist("rowsFull"), [setv("slj", 0), repeat(8, [replace("sim", gidx(v("slj"), item("rowsFull", v("fk"))), 0), chg("slj", 1)]), chg("fk", 1)]),
    setv("fk", 1), repeat(lenlist("colsFull"), [setv("slj", 0), repeat(8, [replace("sim", gidx(item("colsFull", v("fk")), v("slj")), 0), chg("slj", 1)]), chg("fk", 1)]),
])
# Deals a hand that can always be placed: each piece is chosen to fit on the board left by the ones
# before it, and the fuller the board, the likelier a piece that clears a line.
define("deal", [
    setv("i", 1), repeat(64, [replace("sim", v("i"), item("grid", v("i"))), chg("i", 1)]),
    setv("dk", 1),
    repeat(3, [
        setv("n", 0), setv("i", 1), repeat(64, [if_(gt(item("sim", v("i")), 0), [chg("n", 1)]), chg("i", 1)]),
        ifelse(lt(div(rand(1, 1000), 1000), add(0.25, div(v("n"), 64))), [setv("wantClear", 1)], [setv("wantClear", 0)]),
        setv("firstP", 0), setv("clearP", 0), setv("tries", 0),
        until(or_(gt(v("tries"), 11), gt(v("clearP"), 0), and_(eq(v("wantClear"), 0), gt(v("firstP"), 0))), [
            setv("cand", item("bag", rand(1, lenlist("bag")))), setv("nfit", 0), setv("gotClear", 0), setv("dr", 0),
            repeat(sub(9, item("ph", v("cand"))), [
                setv("dc", 0),
                repeat(sub(9, item("pw", v("cand"))), [
                    call("sim fits", v("cand"), v("dc"), v("dr")),
                    if_(eq(v("fit"), 1), [
                        chg("nfit", 1),
                        if_(eq(rand(1, v("nfit")), 1), [setv("rc", v("dc")), setv("rr", v("dr"))]),
                        if_(and_(eq(v("wantClear"), 1), eq(v("gotClear"), 0)), [
                            call("sim lines", v("cand"), v("dc"), v("dr")),
                            if_(gt(v("sl"), 0), [setv("gotClear", 1), setv("cc", v("dc")), setv("cr", v("dr"))])])]),
                    chg("dc", 1)]),
                chg("dr", 1)]),
            if_(gt(v("nfit"), 0), [
                if_(eq(v("firstP"), 0), [setv("firstP", v("cand")), setv("firstC", v("rc")), setv("firstR", v("rr"))]),
                if_(eq(v("gotClear"), 1), [setv("clearP", v("cand"))])]),
            chg("tries", 1)]),
        ifelse(gt(v("clearP"), 0), [replace("tray", v("dk"), v("clearP")), call("sim place", v("clearP"), v("cc"), v("cr"))], [
            ifelse(gt(v("firstP"), 0), [replace("tray", v("dk"), v("firstP")), call("sim place", v("firstP"), v("firstC"), v("firstR"))],
                   [replace("tray", v("dk"), 1)])]),                # nothing found in twelve draws: the single tile always fits somewhere
        chg("dk", 1)]),
    setv("i", rand(1, 3)), setv("n", item("tray", 1)), replace("tray", 1, item("tray", v("i"))), replace("tray", v("i"), v("n")),
    setv("i", rand(2, 3)), setv("n", item("tray", 2)), replace("tray", 2, item("tray", v("i"))), replace("tray", v("i"), v("n")),
    replace("trayT", 1, 0), replace("trayT", 2, -0.08), replace("trayT", 3, -0.16),
    if_(eq(v("state", "main"), "play"), [call("sfx", "whoosh", 0)]),
])
define("coach calc", [                                     # where the tutorial hand should drag: a real piece to a real free spot
    setv("coachSlot", 0), setv("cmi", 1),
    repeat(3, [
        if_(and_(eq(v("coachSlot"), 0), gt(item("tray", v("cmi")), 0)), [
            call("fits anywhere", item("tray", v("cmi"))), if_(eq(v("any"), 1), [setv("coachSlot", v("cmi"))])]),
        chg("cmi", 1)]),
    if_(gt(v("coachSlot"), 0), [
        setv("p", item("tray", v("coachSlot"))), setv("coachD", 999), setv("far", 0),
        repeat(sub(9, item("ph", v("p"))), [
            setv("fac", 0),
            repeat(sub(9, item("pw", v("p"))), [
                call("fits", v("p"), v("fac"), v("far")),
                if_(eq(v("fit"), 1), [
                    setv("n", add(absv(sub(add(v("fac"), div(item("pw", v("p")), 2)), 4)), absv(sub(add(v("far"), div(item("ph", v("p")), 2)), 4.5)))),
                    if_(lt(v("n"), v("coachD")), [setv("coachD", v("n")), setv("coachC", v("fac")), setv("coachR", v("far"))])]),
                chg("fac", 1)]),
            chg("far", 1)])]),
    # and which row or column is closest to full, for the second hint
    setv("lineN", -1), setv("i", 0),
    repeat(8, [
        setv("n", 0), setv("k", 0), setv("j", 0),
        repeat(8, [if_(gt(item("grid", gidx(v("j"), v("i"))), 0), [chg("n", 1)]), if_(gt(item("grid", gidx(v("i"), v("j"))), 0), [chg("k", 1)]), chg("j", 1)]),
        if_(gt(v("n"), v("lineN")), [setv("lineN", v("n")), setv("lineRow", 1), setv("lineI", v("i"))]),
        if_(gt(v("k"), v("lineN")), [setv("lineN", v("k")), setv("lineRow", 0), setv("lineI", v("i"))]),
        chg("i", 1)]),
])
define("spawn", [                                          # one particle into the pool
    chg("pNext", 1), if_(gt(v("pNext"), NPART), [setv("pNext", 1)]),
    replace("pX", v("pNext"), arg("x")), replace("pY", v("pNext"), arg("y")), replace("pVX", v("pNext"), arg("vx")), replace("pVY", v("pNext"), arg("vy")),
    replace("pT", v("pNext"), 0), replace("pLife", v("pNext"), arg("life")), replace("pS", v("pNext"), arg("s")), replace("pC", v("pNext"), arg("cos")), replace("pG", v("pNext"), arg("g")),
])
define("confetti", [
    repeat(arg("n"), [
        setv("ang", rand(-55, 55)),
        setv("spd", rand(150, 400)),
        call("spawn", add(rand(-100, 100), 0), -30, mul(v("spd"), sin(v("ang"))), mul(v("spd"), cos(v("ang"))), div(rand(110, 200), 100), rand(14, 26), join("t", rand(1, 7)), 250)]),
])
define("popup", [
    chg("popNext", 1), if_(gt(v("popNext"), NPOP), [setv("popNext", 1)]),
    replace("popX", v("popNext"), arg("x")), replace("popY", v("popNext"), arg("y")), replace("popS", v("popNext"), arg("s")),
    replace("popT", v("popNext"), 0), replace("popBig", v("popNext"), arg("big")),
])
define("new game", [
    setv("i", 1), repeat(64, [replace("grid", v("i"), 0), replace("fxT", v("i"), 9), replace("placeT", v("i"), 1), chg("i", 1)]),
    setv("i", 1), repeat(NPART, [replace("pT", v("i"), 9), replace("pLife", v("i"), 0), chg("i", 1)]),
    setv("i", 1), repeat(NPOP, [replace("popT", v("i"), 9), chg("i", 1)]),
    delall("beamRow"), delall("beamI"), delall("beamT"),
    setv("score", 0), setv("shown", 0), setv("combo", 0), setv("dry", 0), setv("timeLeft", 120), setv("movesLeft", 30), setv("rubbleIn", 4),
    setv("dragSlot", 0), setv("dragC", -1), setv("retSlot", 0), setv("willOn", 0), setv("willKey", -1), setv("newBest", 0), setv("over", 0), setv("overT", 0), setv("introT", 0),
    setv("toastT", 0), setv("shake", 0), setv("bump", 0), setv("pulse", 0), setv("armed", ""), setv("lastTick", 0),
    setv("state", "play"),
    call("deal"), call("coach calc"), call("sfx", "start", 0),
])
define("check lines", [                                    # clears full rows and columns; count in "lines"; pcx/pcy = where the wave starts
    delall("rowsFull"), delall("colsFull"), setv("i", 0),
    repeat(8, [
        setv("full", 1), setv("j", 0),
        repeat(8, [if_(eq(item("grid", gidx(v("j"), v("i"))), 0), [setv("full", 0)]), chg("j", 1)]),
        if_(eq(v("full"), 1), [addto("rowsFull", v("i"))]),
        setv("full", 1), setv("j", 0),
        repeat(8, [if_(eq(item("grid", gidx(v("i"), v("j"))), 0), [setv("full", 0)]), chg("j", 1)]),
        if_(eq(v("full"), 1), [addto("colsFull", v("i"))]),
        chg("i", 1)]),
    setv("lines", add(lenlist("rowsFull"), lenlist("colsFull"))),
    setv("k", 1),
    repeat(lenlist("rowsFull"), [
        setv("j", 0), addto("beamRow", 1), addto("beamI", item("rowsFull", v("k"))), addto("beamT", 0),
        repeat(8, [
            setv("idx", gidx(v("j"), item("rowsFull", v("k")))),
            if_(gt(item("grid", v("idx")), 0), [
                replace("fxC", v("idx"), item("grid", v("idx"))),
                replace("fxT", v("idx"), mul(-0.035, sqrt(add(mul(sub(v("j"), v("pcx")), sub(v("j"), v("pcx"))), mul(sub(item("rowsFull", v("k")), v("pcy")), sub(item("rowsFull", v("k")), v("pcy"))))))),
                replace("grid", v("idx"), 0)]),
            chg("j", 1)]),
        chg("k", 1)]),
    setv("k", 1),
    repeat(lenlist("colsFull"), [
        setv("j", 0), addto("beamRow", 0), addto("beamI", item("colsFull", v("k"))), addto("beamT", 0),
        repeat(8, [
            setv("idx", gidx(item("colsFull", v("k")), v("j"))),
            if_(gt(item("grid", v("idx")), 0), [
                replace("fxC", v("idx"), item("grid", v("idx"))),
                replace("fxT", v("idx"), mul(-0.035, sqrt(add(mul(sub(item("colsFull", v("k")), v("pcx")), sub(item("colsFull", v("k")), v("pcx"))), mul(sub(v("j"), v("pcy")), sub(v("j"), v("pcy"))))))),
                replace("grid", v("idx"), 0)]),
            chg("j", 1)]),
        chg("k", 1)]),
])
define("drop stones", [
    setv("n", 3), setv("tries", 0),
    until(or_(eq(v("n"), 0), gt(v("tries"), 300)), [
        setv("idx", rand(1, 64)),
        if_(eq(item("grid", v("idx")), 0), [replace("grid", v("idx"), 8), replace("placeT", v("idx"), mul(-0.12, v("n"))), chg("n", -1)]),
        chg("tries", 1)]),
    setv("shake", 2), call("sfx", "stone", 0),
    setv("pcx", 3.5), setv("pcy", 3.5), call("check lines"),
    if_(gt(v("lines"), 0), [chg("score", mul(10, v("lines"), v("lines")))]),
])
define("end game", [
    if_(eq(v("over"), 0), [
        setv("over", 1), setv("overT", 0), setv("overWhy", arg("why")), setv("dragSlot", 0), setv("willOn", 0), setv("retSlot", 0), setv("armed", ""), setv("toastT", 0),
        ifelse(and_(eq(v("newBest"), 1), gt(v("score"), 0)), [call("sfx", "best", 0), call("confetti", 40)], [call("sfx", "over", 0)])]),
])
define("place", [
    setv("p", item("tray", arg("slot"))), setv("k", item("pstart", v("p"))),
    repeat(item("pcount", v("p")), [
        setv("idx", gidx(add(arg("c"), item("pdx", v("k"))), add(arg("r"), item("pdy", v("k"))))),
        replace("grid", v("idx"), item("pcol", v("p"))), replace("placeT", v("idx"), 0),
        chg("k", 1)]),
    replace("tray", arg("slot"), 0),
    setv("pcx", sub(add(arg("c"), div(item("pw", v("p")), 2)), 0.5)), setv("pcy", sub(add(arg("r"), div(item("ph", v("p")), 2)), 0.5)),
    setv("gain", item("pcount", v("p"))), setv("bump", 1),
    repeat(3, [call("spawn", add(cellx(v("pcx")), rand(-14, 14)), sub(celly(sub(add(arg("r"), item("ph", v("p"))), 1)), 15), rand(-70, 70), rand(15, 50), 0.35, 60, "dust", 80)]),
    call("check lines"),
    ifelse(gt(v("lines"), 0), [
        chg("combo", 1), setv("dry", 0),
        chg("gain", mul(10, v("lines"), v("lines"), v("combo"))),
        setv("n", 0), setv("i", 1), repeat(64, [if_(gt(item("grid", v("i")), 0), [chg("n", 1)]), chg("i", 1)]),
        setv("toastP", ""), setv("toastC", 0),
        ifelse(eq(v("n"), 0), [chg("gain", 300), setv("toastP", "p-sweep"), setv("toastW", round(LABW["p-sweep"], 2))], [
            if_(gt(v("lines"), 1), [setv("i", v("lines")), if_(gt(v("i"), 6), [setv("i", 6)]), setv("toastP", join("p", v("i"))), setv("toastW", item("praiseW", v("i")))])]),
        if_(gt(v("combo"), 1), [setv("toastC", v("combo"))]),
        if_(lt(v("tut"), 2), [setv("tut", 2), if_(and_(eq(v("toastP"), ""), eq(v("toastC"), 0)), [setv("toastP", "p-gotit"), setv("toastW", round(LABW["p-gotit"], 2))])]),
        ifelse(or_(not_(eq(v("toastP"), "")), gt(v("toastC"), 0)), [setv("toastT", 1.2)], [setv("toastT", 0)]),
        setv("shake", add(1.4, mul(1.4, v("lines")))),
        if_(eq(v("mode", 1), 2), [chg("timeLeft", mul(2, v("lines")))]),
        setv("i", mul(sub(v("combo"), 1), 14)), if_(gt(v("i"), 100), [setv("i", 100)]),
        ifelse(or_(gt(v("lines"), 1), eq(v("n"), 0)), [call("sfx", "big", v("i"))], [call("sfx", "clear", v("i"))]),
        if_(or_(eq(v("n"), 0), gt(v("lines"), 2)), [call("confetti", 30)]),
        call("popup", cellx(v("pcx")), celly(v("pcy")), join("+", v("gain")), 1),
    ], [
        chg("dry", 1), if_(gt(v("dry"), 2), [setv("combo", 0)]),
        if_(eq(v("tut"), 0), [setv("tut", 1)]),
        call("sfx", "place", rand(-10, 10)),
        call("popup", cellx(v("pcx")), celly(v("pcy")), join("+", v("gain")), 0),
    ]),
    chg("score", v("gain")), setv("pulse", 1),
    if_(gt(v("score"), item("bests", v("mode"))), [replace("bests", v("mode"), v("score")), setv("newBest", 1)]),
    if_(eq(v("mode"), 4), [chg("rubbleIn", -1), if_(lt(v("rubbleIn"), 1), [setv("rubbleIn", 4), call("drop stones")])]),
    if_(eq(add(item("tray", 1), item("tray", 2), item("tray", 3)), 0), [call("deal")]),
    if_(eq(v("mode"), 3), [chg("movesLeft", -1), if_(lt(v("movesLeft"), 1), [call("end game", "o-nomoves")])]),
    call("can move"),
    if_(eq(v("canMove"), 0), [call("end game", "o-noroom")]),
    if_(lt(v("tut"), 2), [call("coach calc")]),
])
define("will calc", [                                      # marks the cells of every line the carried piece would complete
    setv("wi", 1), repeat(64, [replace("will", v("wi"), 0), chg("wi", 1)]),
    setv("willOn", 0), setv("wp", item("tray", v("dragSlot"))),
    setv("wk", item("pstart", v("wp"))),
    repeat(item("pcount", v("wp")), [replace("grid", gidx(add(v("dragC"), item("pdx", v("wk"))), add(v("dragR"), item("pdy", v("wk")))), 9), chg("wk", 1)]),
    setv("wi", v("dragR")),
    repeat(item("ph", v("wp")), [
        setv("full", 1), setv("wj", 0),
        repeat(8, [if_(eq(item("grid", gidx(v("wj"), v("wi"))), 0), [setv("full", 0)]), chg("wj", 1)]),
        if_(eq(v("full"), 1), [setv("willOn", 1), setv("wj", 0), repeat(8, [replace("will", gidx(v("wj"), v("wi")), 1), chg("wj", 1)])]),
        chg("wi", 1)]),
    setv("wi", v("dragC")),
    repeat(item("pw", v("wp")), [
        setv("full", 1), setv("wj", 0),
        repeat(8, [if_(eq(item("grid", gidx(v("wi"), v("wj"))), 0), [setv("full", 0)]), chg("wj", 1)]),
        if_(eq(v("full"), 1), [setv("willOn", 1), setv("wj", 0), repeat(8, [replace("will", gidx(v("wi"), v("wj")), 1), chg("wj", 1)])]),
        chg("wi", 1)]),
    setv("wk", item("pstart", v("wp"))),
    repeat(item("pcount", v("wp")), [replace("grid", gidx(add(v("dragC"), item("pdx", v("wk"))), add(v("dragR"), item("pdy", v("wk")))), 0), chg("wk", 1)]),
])
# ---------------------------------------------------------------- screens and input
define("go", [setv("willOn", 0), setv("state", arg("screen")), setv("menuT", 0), setv("armed", ""), setv("pressId", 0), setv("dragSlot", 0)])
define("start mode", [setv("mode", arg("m")), setv("lastMode", arg("m")), call("new game")])
define("act", [
    call("sfx", "click", 0),
    if_(eq(arg("id"), 1), [call("start mode", v("lastMode", 1))]),
    if_(eq(arg("id"), 2), [call("go", "modes")]), if_(eq(arg("id"), 3), [call("go", "help")]), if_(eq(arg("id"), 4), [call("go", "settings")]),
    if_(eq(arg("id"), 5), [call("go", "main")]),
    if_(and_(gt(arg("id"), 5), lt(arg("id"), 10)), [call("start mode", sub(arg("id"), 5))]),
    if_(eq(arg("id"), 10), [setv("soundOn", sub(1, v("soundOn"))), call("sfx", "clear", 0)]),
    if_(eq(arg("id"), 11), [setv("musicOn", sub(1, v("musicOn")))]),
    if_(eq(arg("id"), 12), [
        ifelse(eq(v("armed"), "reset"), [replace("bests", 1, 0), replace("bests", 2, 0), replace("bests", 3, 0), replace("bests", 4, 0), setv("tut", 0), setv("armed", "")],
               [setv("armed", "reset"), setv("armedT", 3)])]),
    if_(eq(arg("id"), 13), [ifelse(or_(eq(v("mode"), 1), eq(v("score"), 0), eq(v("armed"), "home")), [call("go", "main")], [setv("armed", "home"), setv("armedT", 2)])]),
    if_(eq(arg("id"), 14), [ifelse(or_(eq(v("score"), 0), eq(v("armed"), "new")), [call("new game")], [setv("armed", "new"), setv("armedT", 2)])]),
    if_(eq(arg("id"), 15), [call("new game")]),
    if_(eq(arg("id"), 16), [call("go", "main")]),
])
define("hit", [                                            # which button is under the pointer on this screen
    setv("hitId", 0), setv("hi", 1),
    repeat(16, [
        if_(and_(or_(eq(item("btnS", v("hi")), v("scr")), and_(eq(item("btnS", v("hi")), "sub"), or_(eq(v("scr"), "modes"), eq(v("scr"), "help"), eq(v("scr"), "settings")))),
                 lt(absv(sub(v("mx"), item("btnX", v("hi")))), item("btnW", v("hi"))), lt(absv(sub(v("my"), item("btnY", v("hi")))), item("btnH", v("hi")))),
            [setv("hitId", v("hi"))]),
        chg("hi", 1)]),
])
define("anim", [                                           # everything that just moves with time
    if_(lt(v("shown"), v("score")), [chg("shown", mx(1, mul(sub(v("score"), v("shown")), 8, v("dt")))), if_(gt(v("shown"), v("score")), [setv("shown", v("score"))])]),
    if_(gt(v("toastT"), 0), [chg("toastT", mul(-1, v("dt")))]),
    if_(gt(v("armedT"), 0), [chg("armedT", mul(-1, v("dt"))), if_(lt(v("armedT"), 0.001), [setv("armed", "")])]),
    if_(gt(v("pulse"), 0), [chg("pulse", mul(-3, v("dt"))), if_(lt(v("pulse"), 0), [setv("pulse", 0)])]),
    if_(gt(v("bump"), 0), [chg("bump", mul(-7, v("dt"))), if_(lt(v("bump"), 0), [setv("bump", 0)])]),
    setv("shake", mul(v("shake"), 0.72)),
    ifelse(gt(v("shake"), 0.2), [setv("shx", div(mul(rand(-100, 100), v("shake")), 100)), setv("shy", div(mul(rand(-100, 100), v("shake")), 100))], [setv("shx", 0), setv("shy", 0)]),
    chg("shy", mul(-1.4, sin(mul(v("bump"), 180)))),
    setv("i", 1),
    repeat(64, [
        if_(lt(item("placeT", v("i")), 1), [replace("placeT", v("i"), add(item("placeT", v("i")), v("dt")))]),
        if_(lt(item("fxT", v("i")), 1), [
            if_(and_(lt(item("fxT", v("i")), 0), not_(lt(add(item("fxT", v("i")), v("dt")), 0))), [      # the cell pops now: burst
                repeat(2, [setv("ang", rand(0, 359)), setv("spd", rand(40, 150)),
                           call("spawn", cellx(mod(sub(v("i"), 1), 8)), celly(floor(div(sub(v("i"), 1), 8))), mul(v("spd"), cos(v("ang"))), add(mul(v("spd"), sin(v("ang"))), 50),
                                div(rand(45, 85), 100), rand(16, 30), join("t", item("fxC", v("i"))), 420)])]),
            replace("fxT", v("i"), add(item("fxT", v("i")), v("dt")))]),
        chg("i", 1)]),
    setv("i", 1), repeat(3, [if_(lt(item("trayT", v("i")), 1), [replace("trayT", v("i"), add(item("trayT", v("i")), v("dt")))]), chg("i", 1)]),
    setv("i", 1),
    repeat(NPART, [
        if_(lt(item("pT", v("i")), item("pLife", v("i"))), [
            replace("pT", v("i"), add(item("pT", v("i")), v("dt"))),
            replace("pVY", v("i"), sub(item("pVY", v("i")), mul(item("pG", v("i")), v("dt")))),
            replace("pX", v("i"), add(item("pX", v("i")), mul(item("pVX", v("i")), v("dt")))),
            replace("pY", v("i"), add(item("pY", v("i")), mul(item("pVY", v("i")), v("dt"))))]),
        chg("i", 1)]),
    setv("i", 1), repeat(NPOP, [if_(lt(item("popT", v("i")), 1), [replace("popT", v("i"), add(item("popT", v("i")), v("dt")))]), chg("i", 1)]),
    setv("i", 1), setv("n", 0),
    repeat(lenlist("beamT"), [replace("beamT", v("i"), add(item("beamT", v("i")), v("dt"))), if_(lt(item("beamT", v("i")), 0.3), [setv("n", 1)]), chg("i", 1)]),
    if_(and_(eq(v("n"), 0), gt(lenlist("beamT"), 0)), [delall("beamRow"), delall("beamI"), delall("beamT")]),
    if_(gt(v("retSlot"), 0), [chg("retT", v("dt")), if_(gt(v("retT"), 0.16), [setv("retSlot", 0)])]),
])
SLOTH = BW / 3.0
define("tick", [
    setv("dt", sub(timer(), v("lastFrame"))), setv("lastFrame", timer()),
    if_(gt(v("dt"), 0.1), [setv("dt", 0.1)]), if_(lt(v("dt"), 0), [setv("dt", 0)]),
    chg("tNow", v("dt")), chg("menuT", v("dt")), chg("introT", v("dt")),
    if_(eq(v("over"), 1), [chg("overT", v("dt"))]),
    setv("mx", mousex()), setv("my", mousey()),
    ifelse(mousedown(), [setv("down", 1)], [setv("down", 0)]),
    if_(eq(v("state"), "splash"), [                             # the maker's card: goes away by itself, or on a tap
        chg("splashT", v("dt")),
        if_(or_(gt(v("splashT"), 1.7), and_(eq(v("down"), 1), eq(v("wasDown"), 0), gt(v("splashT"), 0.4))), [call("go", "main"), setv("wasDown", 1)])]),
    setv("scr", v("state")),
    if_(and_(eq(v("state"), "play"), eq(v("over"), 1)), [ifelse(gt(v("overT"), 1.2), [setv("scr", "over")], [setv("scr", "wait")])]),
    call("hit"),
    if_(and_(eq(v("down"), 1), eq(v("wasDown"), 0)), [                 # pressed
        setv("pressId", v("hitId")),
        if_(and_(eq(v("pressId"), 0), eq(v("scr"), "play"), eq(v("dragSlot"), 0), gt(v("mx"), TX - 50)), [
            setv("slot", add(1, floor(div(sub(BY, v("my")), SLOTH)))),
            if_(lt(v("slot"), 1), [setv("slot", 1)]), if_(gt(v("slot"), 3), [setv("slot", 3)]),
            if_(and_(gt(item("tray", v("slot")), 0), gt(item("trayT", v("slot")), 0)), [
                setv("dragSlot", v("slot")), setv("dragC", -1), setv("retSlot", 0), setv("willOn", 0), setv("willKey", -1),
                setv("dragX", TX), setv("dragY", sub(BY - SLOTH / 2, mul(sub(v("slot"), 1), SLOTH))), setv("dragS", TC),
                call("sfx", "pick", 0)])])]),
    if_(and_(gt(v("dragSlot"), 0), eq(v("scr"), "play")), [            # carrying a piece: it floats a little above the pointer
        setv("p", item("tray", v("dragSlot"))),
        setv("c0", rnd(div(sub(sub(v("mx"), mul(item("pw", v("p")), CS / 2)), BX), CS))),
        setv("r0", rnd(div(sub(BY, add(v("my"), 22, mul(item("ph", v("p")), CS / 2))), CS))),
        call("fits", v("p"), v("c0"), v("r0")),
        ifelse(eq(v("fit"), 1), [
            setv("dragC", v("c0")), setv("dragR", v("r0")),
            if_(not_(eq(add(mul(v("c0"), 10), v("r0")), v("willKey"))), [setv("willKey", add(mul(v("c0"), 10), v("r0"))), call("will calc")]),
        ], [setv("dragC", -1), setv("willOn", 0), setv("willKey", -1)]),
        chg("dragX", mul(sub(v("mx"), v("dragX")), 0.6)), chg("dragY", mul(sub(add(v("my"), 22), v("dragY")), 0.6)), chg("dragS", mul(sub(CS, v("dragS")), 0.5))]),
    if_(and_(eq(v("down"), 0), eq(v("wasDown"), 1)), [                 # released
        ifelse(gt(v("pressId"), 0), [
            setv("n", v("pressId")), setv("pressId", 0),
            if_(eq(v("hitId"), v("n")), [call("act", v("n"))]),
        ], [
            if_(gt(v("dragSlot"), 0), [
                setv("slot", v("dragSlot")), setv("dragSlot", 0), setv("willOn", 0), setv("willKey", -1),
                ifelse(gt(v("dragC"), -1), [call("place", v("slot"), v("dragC"), v("dragR"))],
                       [setv("retSlot", v("slot")), setv("retT", 0), setv("retX", v("dragX")), setv("retY", v("dragY")), setv("retS", v("dragS")), call("sfx", "back", 0)])])])]),
    setv("wasDown", v("down")),
    if_(and_(eq(v("state"), "play"), eq(v("over"), 0)), [
        if_(and_(eq(v("mode"), 2), gt(v("introT"), 0.6), eq(v("tut"), 2)), [
            chg("timeLeft", mul(-1, v("dt"))),
            if_(and_(lt(v("timeLeft"), 10), not_(eq(ceil(v("timeLeft")), v("lastTick")))), [setv("lastTick", ceil(v("timeLeft"))), call("sfx", "tick", 0)]),
            if_(lt(v("timeLeft"), 0.001), [setv("timeLeft", 0), call("end game", "o-timeup")])])]),
    call("anim"),
])
# ---------------------------------------------------------------- drawing
def slide(k, delay, dist=480):      # eb -> slide-in offset in "sl2"
    return [call("ease", div(sub(v("menuT"), delay + k * 0.07 if isinstance(k, (int, float)) else add(delay, mul(k, 0.07))), 0.4)), setv("sl2", mul(sub(1, v("eb")), dist))]
define("draw head", [
    call("button", 5, "b-back", "sh-sq", BTN[5][0], BTN[5][1], 100),
    call("ease", div(v("menuT"), 0.35)),
    call("stamp rot", arg("cos"), 12, 158, mul(100, v("eb")), 89),
])
define("draw main", [
    call("ease", div(v("menuT"), 0.4)), setv("pop", v("eb")),
    setv("wob", mul(1.4, sin(mul(v("tNow"), 92)))),
    call("stamp rot", "title1", 0, 144, mul(100, v("pop")), add(87.7, v("wob"))),
    call("ease", div(sub(v("menuT"), 0.08), 0.4)),
    call("stamp rot", "title2", 0, 101, mul(100, v("eb")), sub(91.7, v("wob"))),
    call("stamp rot", "deco1", -118, add(160, mul(3.5, sin(mul(v("tNow"), 115)))), mul(100, v("pop")), add(70, mul(v("wob"), 3))),
    call("stamp rot", "deco2", 118, add(88, mul(3.5, cos(mul(v("tNow"), 97)))), mul(100, v("pop")), sub(107, mul(v("wob"), 3))),
    setv("di", 0),
    repeat(7, [
        call("ease", div(sub(v("menuT"), add(0.2, mul(v("di"), 0.04))), 0.3)),
        setv("n", mul(5, sin(sub(mul(v("tNow"), 172), mul(v("di"), 34))))), if_(lt(v("n"), 0), [setv("n", 0)]),
        stp(join("t", add(v("di"), 1)), add(-65.1, mul(v("di"), 21.7)), add(60, v("n")), mul(59, v("eb"))),
        chg("di", 1)]),
    call("ease", div(sub(v("menuT"), 0.15), 0.35)),
    call("button", 1, "b-play", "sh-play", 0, 4, mul(mul(100, v("eb")), add(1, mul(0.02, sin(mul(v("tNow"), 229)))))),
    if_(gt(v("menuT"), 0.45), [call("label num", join("sub", v("lastMode")), item("subW", v("lastMode")), item("bests", v("lastMode")), 0, add(-8, v("boff")), 10.5, "k", 0)]),
] + slide(0, 0.25) + [call("button", 2, "b-modes", "sh-menu", v("sl2"), -57, 100)]
  + slide(1, 0.25) + [call("button", 3, "b-help", "sh-menu", mul(-1, v("sl2")), -96, 100)]
  + slide(2, 0.25) + [call("button", 4, "b-settings", "sh-menu", v("sl2"), -134, 100),
    stp("ver", 0, -171),
])
define("draw modes", [
    call("draw head", "h-modes"),
    setv("di", 1),
    repeat(4, slide(v("di"), -0.02) + [
        call("button", add(5, v("di")), join("card", v("di")), "sh-card", v("sl2"), item("btnY", add(5, v("di"))), 100),
        call("str width", item("bests", v("di")), 13),
        call("draw str", item("bests", v("di")), sub(add(v("sl2"), 153), v("sw")), add(item("btnY", add(5, v("di"))), -6, v("boff")), 13, "k"),
        chg("di", 1)]),
])
define("draw help", [
    call("draw head", "h-help"),
    setv("di", 1),
    repeat(4, [
        call("ease", div(sub(v("menuT"), add(0.05, mul(v("di"), 0.07))), 0.35)),
        stp(join("help", v("di")), 0, sub(item("btnY", add(5, v("di"))), 1.5), mul(100, v("eb"))),
        chg("di", 1)]),
])
define("draw settings", [
    call("draw head", "h-settings"),
    call("ease", div(sub(v("menuT"), 0.05), 0.35)), stp("row-sound", 0, CARDY[0] - 1.5, mul(100, v("eb"))),
    call("ease", div(sub(v("menuT"), 0.12), 0.35)), stp("row-music", 0, CARDY[1] - 1.5, mul(100, v("eb"))),
    call("ease", div(sub(v("menuT"), 0.19), 0.35)), stp("row-reset", 0, CARDY[2] - 1.5, mul(100, v("eb"))),
    call("ease", div(sub(v("menuT"), 0.2), 0.3)), setv("pop", mul(100, v("eb"))),
    ifelse(eq(v("soundOn"), 1), [call("button", 10, "tg-on", "sh-tg", 118, CARDY[0], v("pop"))], [call("button", 10, "tg-off", "sh-tg", 118, CARDY[0], v("pop"))]),
    ifelse(eq(v("musicOn"), 1), [call("button", 11, "tg-on", "sh-tg", 118, CARDY[1], v("pop"))], [call("button", 11, "tg-off", "sh-tg", 118, CARDY[1], v("pop"))]),
    ifelse(eq(v("armed"), "reset"), [call("button", 12, "tg-sure", "sh-tg", 118, CARDY[2], v("pop"))], [call("button", 12, "tg-reset", "sh-tg", 118, CARDY[2], v("pop"))]),
    call("ease", div(sub(v("menuT"), 0.35), 0.35)),
    call("stamp rot", "madeby", 0, -52, mul(100, v("eb")), 89.2),
    stp("credits", 0, -74),
])
define("draw hud", [
    stp(join("m", v("mode")), LX, 124),
    setv("n", 40), if_(gt(length(rnd(v("shown"))), 4), [setv("n", div(160, length(rnd(v("shown")))))]),
    call("draw num", rnd(v("shown")), LX, 88, mul(v("n"), add(1, mul(0.22, v("pulse"), v("pulse")))), "o"),
    if_(eq(v("mode"), 1), [call("label num", "l-best", round(LABW["l-best"], 2), item("bests", 1), LX, 50, 14, "g", 0)]),
    if_(eq(v("mode"), 2), [
        setv("n", ceil(v("timeLeft"))),
        ifelse(lt(mod(v("n"), 60), 10), [setv("hs", join(floor(div(v("n"), 60)), ":0", mod(v("n"), 60)))], [setv("hs", join(floor(div(v("n"), 60)), ":", mod(v("n"), 60)))]),
        ifelse(and_(lt(v("timeLeft"), 10), gt(sin(mul(v("tNow"), 687)), 0), eq(v("over"), 0)), [call("draw num", v("hs"), LX, 50, 18, "o")], [call("draw num", v("hs"), LX, 50, 18, "g")]),
        stp("bar-bg", LX, 35),
        setv("n", rnd(mul(41, mn(1, div(v("timeLeft"), 120))))), setv("di", 0),
        repeat(v("n"), [ifelse(lt(v("timeLeft"), 10), [stp("bar-red", add(LX - 40, mul(v("di"), 2)), 35)], [stp("bar-seg", add(LX - 40, mul(v("di"), 2)), 35)]), chg("di", 1)]),
        call("label num", "l-best-s", round(LABW["l-best-s"], 2), item("bests", 2), LX, 16, 11, "u", 0)]),
    if_(eq(v("mode"), 3), [call("label num", "l-moves", round(LABW["l-moves"], 2), v("movesLeft"), LX, 50, 11, "g", 1),
                            call("label num", "l-best-s", round(LABW["l-best-s"], 2), item("bests", 3), LX, 30, 11, "u", 0)]),
    if_(eq(v("mode"), 4), [call("label num", "l-stones", round(LABW["l-stones"], 2), v("rubbleIn"), LX, 50, 11, "g", 0),
                            call("label num", "l-best-s", round(LABW["l-best-s"], 2), item("bests", 4), LX, 30, 11, "u", 0)]),
    ifelse(eq(v("armed"), "home"), [call("button", 13, "b-ask", "sh-hud", BTN[13][0], BTN[13][1], 100)], [call("button", 13, "b-home", "sh-hud", BTN[13][0], BTN[13][1], 100)]),
    ifelse(eq(v("armed"), "new"), [call("button", 14, "b-ask", "sh-hud", BTN[14][0], BTN[14][1], 100)], [call("button", 14, "b-new", "sh-hud", BTN[14][0], BTN[14][1], 100)]),
])
define("draw board", [
    setv("ox", v("shx")), setv("oy", v("shy")),
    ifelse(lt(v("introT"), 0.85), [
        stp("frame", v("ox"), v("oy")),
        setv("di", 1),
        repeat(64, [
            call("ease", div(sub(v("introT"), mul(add(mod(sub(v("di"), 1), 8), floor(div(sub(v("di"), 1), 8))), 0.03)), 0.3)),
            if_(gt(v("eb"), 0.02), [stp("cell", add(cellx(mod(sub(v("di"), 1), 8)), v("ox")), add(celly(floor(div(sub(v("di"), 1), 8))), v("oy")), mul(100, v("eb")))]),
            chg("di", 1)]),
    ], [stp("board", v("ox"), v("oy"))]),
    setv("glow", add(0.5, mul(0.5, sin(mul(v("tNow"), 687))))),
    setv("di", 1),
    repeat(64, [
        setv("bx", add(cellx(mod(sub(v("di"), 1), 8)), v("ox"))), setv("by", add(celly(floor(div(sub(v("di"), 1), 8))), v("oy"))),
        setv("n", item("grid", v("di"))),
        if_(and_(eq(v("willOn"), 1), eq(item("will", v("di")), 1), gt(v("dragSlot"), 0)), [     # this line is about to clear: gold pulsing to white
            setv("n", 0),
            stp("t3", v("bx"), v("by"), add(100, mul(4, v("glow")))),
            ghost(mul(60, sub(1, v("glow")))), stp("t9", v("bx"), v("by"), add(100, mul(4, v("glow")))), clearfx()]),
        if_(gt(v("n"), 0), [
            setv("k", item("placeT", v("di"))),
            ifelse(lt(v("k"), 0), [
                if_(gt(v("k"), -0.1), [ghost(mul(-600, v("k"))), stp(join("t", v("n")), v("bx"), sub(v("by"), mul(v("k"), 680))), clearfx()]),
            ], [
                setv("sc", 100),
                if_(lt(v("k"), 0.25), [call("ease", div(v("k"), 0.25)), setv("sc", add(72, mul(28, v("eb"))))]),
                stp(join("t", v("n")), v("bx"), v("by"), v("sc")),
                if_(eq(v("over"), 1), [
                    setv("k", div(sub(v("overT"), mul(floor(div(sub(v("di"), 1), 8)), 0.07)), 0.25)),
                    if_(gt(v("k"), 0), [if_(gt(v("k"), 1), [setv("k", 1)]), ghost(mul(100, sub(1, v("k")))), stp("tg", v("bx"), v("by"), v("sc")), clearfx()])]),
            ])]),
        setv("k", item("fxT", v("di"))),
        if_(lt(v("k"), 0.32), [
            ifelse(lt(v("k"), 0), [stp(join("t", item("fxC", v("di"))), v("bx"), v("by"))], [
                setv("k", div(v("k"), 0.32)),
                ghost(mul(100, v("k"), v("k"), v("k"))),
                stp("t9", v("bx"), v("by"), mul(100, add(1, mul(0.35, sin(mul(v("k"), 180)))), sub(1, mul(v("k"), v("k"))))),
                clearfx()])]),
        chg("di", 1)]),
    if_(and_(gt(v("dragSlot"), 0), gt(v("dragC"), -1)), [
        setv("p", item("tray", v("dragSlot"))),
        ghost(add(50, mul(10, sin(mul(v("tNow"), 687))))),
        setv("dpk", item("pstart", v("p"))),
        repeat(item("pcount", v("p")), [
            if_(not_(and_(eq(v("willOn"), 1), eq(item("will", gidx(add(v("dragC"), item("pdx", v("dpk"))), add(v("dragR"), item("pdy", v("dpk"))))), 1))), [
                stp(join("t", item("pcol", v("p"))), add(cellx(add(v("dragC"), item("pdx", v("dpk")))), v("ox")), add(celly(add(v("dragR"), item("pdy", v("dpk")))), v("oy")), 94)]),
            chg("dpk", 1)]),
        clearfx()]),
])
define("draw fx", [
    setv("di", 1),
    repeat(lenlist("beamT"), [
        setv("k", div(item("beamT", v("di")), 0.3)),
        if_(lt(v("k"), 1), [
            ghost(sub(100, mul(85, sub(1, v("k")), sub(1, v("k"))))),
            ifelse(eq(item("beamRow", v("di")), 1), [stp("beam", v("ox"), add(celly(item("beamI", v("di"))), v("oy")), add(100, mul(4, v("k"))))],
                   [call("stamp rot", "beam", add(cellx(item("beamI", v("di"))), v("ox")), v("oy"), add(100, mul(4, v("k"))), 0)]),
            clearfx()]),
        chg("di", 1)]),
    setv("di", 1),
    repeat(NPART, [
        if_(lt(item("pT", v("di")), item("pLife", v("di"))), [
            setv("k", sub(1, div(item("pT", v("di")), item("pLife", v("di"))))),
            if_(lt(v("k"), 0.4), [ghost(mul(100, sub(1, div(v("k"), 0.4))))]),
            call("stamp rot", item("pC", v("di")), item("pX", v("di")), item("pY", v("di")), mul(item("pS", v("di")), add(0.5, mul(0.5, v("k")))), add(90, mul(item("pT", v("di")), 340))),
            clearfx()]),
        chg("di", 1)]),
    # tray
    setv("ti", 1),
    repeat(3, [
        if_(and_(gt(item("tray", v("ti")), 0), not_(eq(v("ti"), v("dragSlot"))), not_(eq(v("ti"), v("retSlot"))), gt(item("trayT", v("ti")), 0)), [
            setv("p", item("tray", v("ti"))),
            call("ease", div(item("trayT", v("ti")), 0.35)),
            call("fits anywhere", v("p")),
            setv("n", 0), if_(and_(eq(v("any"), 1), eq(v("over"), 0)), [setv("n", mul(1.7, sin(add(mul(v("tNow"), 126), mul(v("ti"), 97)))))]),
            if_(eq(v("any"), 0), [ghost(70)]),
            call("draw piece", v("p"), TX, add(sub(BY - SLOTH / 2, mul(sub(v("ti"), 1), SLOTH)), v("n")), mul(TC, v("eb"))),
            clearfx()]),
        chg("ti", 1)]),
    if_(gt(v("retSlot"), 0), [
        setv("k", div(v("retT"), 0.16)), setv("k", sub(1, mul(sub(1, v("k")), sub(1, v("k"))))),
        call("draw piece", item("tray", v("retSlot")), add(v("retX"), mul(sub(TX, v("retX")), v("k"))),
             add(v("retY"), mul(sub(sub(BY - SLOTH / 2, mul(sub(v("retSlot"), 1), SLOTH)), v("retY")), v("k"))), add(v("retS"), mul(sub(TC, v("retS")), v("k"))))]),
    if_(gt(v("dragSlot"), 0), [
        ghost(75), setv("p", item("tray", v("dragSlot"))),
        setv("dpk", item("pstart", v("p"))),
        repeat(item("pcount", v("p")), [
            stp("t9", add(sub(v("dragX"), mul(item("pw", v("p")), div(v("dragS"), 2))), mul(add(item("pdx", v("dpk")), 0.5), v("dragS"))),
                sub(sub(add(v("dragY"), mul(item("ph", v("p")), div(v("dragS"), 2))), mul(add(item("pdy", v("dpk")), 0.5), v("dragS"))), 4), mul(v("dragS"), 80.0 / CS)),
            chg("dpk", 1)]),
        clearfx(),
        call("draw piece", v("p"), v("dragX"), v("dragY"), v("dragS"))]),
    # +points rising from the move
    setv("di", 1),
    repeat(NPOP, [
        setv("k", div(item("popT", v("di")), 0.9)),
        if_(lt(v("k"), 1), [
            call("ease", div(item("popT", v("di")), 0.25)),
            if_(gt(v("k"), 0.6), [ghost(mul(250, sub(v("k"), 0.6)))]),
            ifelse(eq(item("popBig", v("di")), 1),
                   [call("draw num", item("popS", v("di")), item("popX", v("di")), add(item("popY", v("di")), mul(41, sub(1, mul(sub(1, v("k")), sub(1, v("k")))))), mul(20, v("eb")), "y")],
                   [call("draw num", item("popS", v("di")), item("popX", v("di")), add(item("popY", v("di")), mul(41, sub(1, mul(sub(1, v("k")), sub(1, v("k")))))), mul(14, v("eb")), "o")]),
            clearfx()]),
        chg("di", 1)]),
    if_(and_(gt(v("combo"), 1), eq(v("over"), 0)), [
        setv("k", add(100, mul(30, v("pulse")), mul(5, sin(mul(v("tNow"), 515))))),
        call("stamp rot", "badge", 129, 139, v("k"), add(97, mul(3, sin(mul(v("tNow"), 344))))),
        call("draw num", join("x", v("combo")), 129, 139, mul(0.19, v("k")), "k")]),
    if_(gt(v("toastT"), 0), [
        setv("k", sub(1.2, v("toastT"))),
        call("ease", div(v("k"), 0.3)),
        if_(lt(v("toastT"), 0.33), [ghost(mul(300, sub(0.33, v("toastT"))))]),
        setv("by", add(27, mul(v("k"), 9))),
        ifelse(eq(v("toastC"), 0), [call("stamp rot", v("toastP"), 0, v("by"), mul(100, v("eb")), 86.6)], [
            call("str width", v("toastC"), 25),
            ifelse(eq(v("toastP"), ""), [
                setv("n", add(round(LABW["p-combo"], 2), v("sw"))),
                stp("p-combo", sub(round(LABW["p-combo"] / 2, 2), div(v("n"), 2)), v("by"), 100),
                call("draw str", v("toastC"), sub(round(LABW["p-combo"], 2), div(v("n"), 2)), v("by"), 25, "o"),
            ], [
                setv("n", add(v("toastW"), 8, round(LABW["p-combo"], 2), v("sw"))),
                stp(v("toastP"), sub(div(v("toastW"), 2), div(v("n"), 2)), v("by"), 100),
                stp("p-combo", add(sub(add(v("toastW"), 8), div(v("n"), 2)), round(LABW["p-combo"] / 2, 2)), v("by"), 100),
                call("draw str", v("toastC"), add(sub(add(v("toastW"), 8), div(v("n"), 2)), round(LABW["p-combo"], 2)), v("by"), 25, "o"),
            ])]),
        clearfx()]),
    if_(and_(eq(v("mode"), 2), lt(v("timeLeft"), 10), eq(v("over"), 0)), [ghost(sub(92, mul(8, sin(mul(v("tNow"), 687))))), stp("vign", 0, 0), clearfx()]),
])
define("draw coach", [                                     # first-game hints, shown instead of written instructions
    setv("pop", add(0.5, mul(0.5, sin(mul(v("tNow"), 286))))),
    ifelse(eq(v("tut"), 0), [
        if_(and_(gt(v("coachSlot"), 0), gt(item("tray", v("coachSlot")), 0)), [
            setv("p", item("tray", v("coachSlot"))),
            ghost(sub(78, mul(16, v("pop")))),
            setv("dpk", item("pstart", v("p"))),
            repeat(item("pcount", v("p")), [stp(join("t", item("pcol", v("p"))), cellx(add(v("coachC"), item("pdx", v("dpk")))), celly(add(v("coachR"), item("pdy", v("dpk")))), 94), chg("dpk", 1)]),
            clearfx(),
            setv("k", div(mod(v("tNow"), 2), 2)),
            setv("n", div(sub(v("k"), 0.15), 0.5)), if_(lt(v("n"), 0), [setv("n", 0)]), if_(gt(v("n"), 1), [setv("n", 1)]),
            setv("n", mul(v("n"), v("n"), sub(3, mul(2, v("n"))))),
            setv("bx", add(TX, mul(sub(sub(cellx(add(v("coachC"), div(item("pw", v("p")), 2))), CS / 2), TX), v("n")))),
            setv("by", sub(BY - SLOTH / 2, mul(sub(v("coachSlot"), 1), SLOTH))),
            setv("by", add(v("by"), mul(sub(add(celly(add(v("coachR"), div(item("ph", v("p")), 2))), CS / 2), v("by")), v("n")))),
            setv("sc", add(TC, mul(CS - TC, v("n")))),
            setv("ek", 0), if_(lt(v("k"), 0.1), [setv("ek", mul(100, sub(1, div(v("k"), 0.1))))]), if_(gt(v("k"), 0.85), [setv("ek", mul(100, div(sub(v("k"), 0.85), 0.15)))]),
            ghost(add(15, mul(0.85, v("ek")))),
            call("draw piece", v("p"), v("bx"), v("by"), v("sc")),
            ghost(v("ek")),
            call("stamp rot", "hand", add(v("bx"), mul(v("sc"), 0.2)), sub(v("by"), add(mul(item("ph", v("p")), div(v("sc"), 2)), 2)), 100, 70),
            clearfx(),
            ghost(sub(25, mul(25, v("pop")))), stp("c-drag", 0, BY - BW + 19), clearfx()]),
    ], [
        ghost(sub(40, mul(40, v("pop")))),
        ifelse(eq(v("lineRow"), 1), [stp("hl", 0, celly(v("lineI")))], [call("stamp rot", "hl", cellx(v("lineI")), 0, 100, 0)]),
        ghost(sub(25, mul(25, v("pop")))),
        ifelse(and_(eq(v("lineRow"), 1), gt(v("lineI"), 5)), [stp("c-line", 0, BY - 19)], [stp("c-line", 0, BY - BW + 19)]),
        clearfx()]),
])
define("draw over", [
    setv("k", div(sub(v("overT"), 0.8), 0.35)),
    if_(gt(v("k"), 0), [
        if_(gt(v("k"), 1), [setv("k", 1)]),
        call("ease", v("k")), setv("by", mul(sub(v("eb"), 1), 17)), setv("n", sub(100, mul(100, v("k")))),
        ghost(v("n")), stp("overpanel", 0, 0),
        call("stamp rot", v("overWhy"), 0, add(92, v("by")), 100, 88.3),
        stp(join("os", v("mode")), 0, add(60, v("by"))),
        call("draw num", v("score"), 0, add(27, v("by")), 42, "k"),
        ifelse(and_(eq(v("newBest"), 1), gt(v("score"), 0)), [stp("o-newbest", 0, add(-8, v("by")))],
               [call("label num", "l-best-k", round(LABW["l-best-k"], 2), item("bests", v("mode")), 0, add(-8, v("by")), 13, "u", 0)]),
        clearfx(),
        if_(gt(v("overT"), 1), [
            call("ease", div(sub(v("overT"), 1), 0.3)),
            call("button", 15, "b-again", "sh-again", 0, -51, mul(mul(100, v("eb")), add(1, mul(0.03, sin(mul(v("tNow"), 286)))))),
            call("ease", div(sub(v("overT"), 1.1), 0.3)),
            call("button", 16, "b-omenu", "sh-omenu", 0, -103, mul(100, v("eb")))])]),
])
define("draw splash", [
    stp("splash-bg", 0, 0),
    call("ease", div(v("splashT"), 0.45)),
    call("stamp rot", "splash-t", 0, 14, mul(100, v("eb")), 88.3),
    setv("di", 0),
    repeat(3, [
        call("ease", div(sub(v("splashT"), add(0.25, mul(v("di"), 0.08))), 0.3)),
        setv("n", mul(5, sin(sub(mul(v("tNow"), 286), mul(v("di"), 52))))), if_(lt(v("n"), 0), [setv("n", 0)]),
        stp(join("t", add(1, mul(v("di"), 2))), add(-27, mul(v("di"), 27)), add(-34, v("n")), mul(68, v("eb"))),
        chg("di", 1)]),
])
define("draw", [
    erase(),
    if_(eq(v("state"), "splash"), [call("draw splash")]),
    if_(not_(eq(v("state"), "splash")), [stp("stripes", sub(0, mod(mul(v("tNow"), 3.9), 50.625)), 0)]),
    if_(eq(v("state"), "main"), [call("draw main")]),
    if_(eq(v("state"), "modes"), [call("draw modes")]),
    if_(eq(v("state"), "help"), [call("draw help")]),
    if_(eq(v("state"), "settings"), [call("draw settings")]),
    if_(eq(v("state"), "play"), [
        call("draw hud"), call("draw board"),
        if_(and_(lt(v("tut"), 2), eq(v("over"), 0), eq(v("dragSlot"), 0), gt(v("introT"), 0.7)), [call("draw coach")]),
        call("draw fx"),
        if_(eq(v("over"), 1), [call("draw over")])]),
])
flag([hide(), clearfx(), point(90), resettimer(), setv("lastFrame", 0), setv("tNow", 0), setv("wasDown", 1), setv("pressId", 0),
      setv("tut", 0), setv("soundOn", 1), setv("musicOn", 1), setv("lastMode", 1), setv("mode", 1), setv("over", 0),
      call("go", "main"), setv("state", "splash"), setv("splashT", 0), forever([call("tick"), call("draw")])])
missing = set(SIG) - DEFINED
assert not missing, missing
GAME_BLOCKS = BLOCKS

BLOCKS = {}
flag([forever([playwait("music"), playwait("music2")])])      # the two themes take turns
flag([forever([volume(mul(35, V("musicOn")))])])
STAGE_BLOCKS = BLOCKS

# ================================================================ project
SFX = ["click", "pick", "place", "back", "tick", "whoosh", "stone", "clear", "big", "over", "best", "start"]
BACKDROP = svg(480, 360, '<rect width="480" height="360" fill="%s"/>' % GREEN)
project = {
    "targets": [
        {"isStage": True, "name": "Stage", "variables": {"var_" + k: [k, val] for k, val in GLOBALS.items()}, "lists": {}, "broadcasts": {},
         "blocks": STAGE_BLOCKS, "comments": {}, "currentCostume": 0, "costumes": [costume_entry("felt", BACKDROP, 240, 180)],
         "sounds": [sound_entry("music", MUSIC), sound_entry("music2", MUSIC2)], "volume": 35, "layerOrder": 0, "tempo": 60, "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None},
        {"isStage": False, "name": "Game", "variables": {"var_" + k: [k, val] for k, val in VARS.items()},
         "lists": {"list_" + k: [k, val] for k, val in LISTS.items()}, "broadcasts": {}, "blocks": GAME_BLOCKS, "comments": {},
         "currentCostume": 0, "costumes": [costume_entry(*c) for c in COSTUMES], "sounds": [sound_entry(n, os.path.join(AUDIO, n + ".wav")) for n in SFX],
         "volume": 100, "layerOrder": 1, "visible": False, "x": 0, "y": 0, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "all around"},
    ],
    "monitors": [], "extensions": ["pen"],
    "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "Blocky Puzzle v1.13-scratch generator"},
}
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("project.json", json.dumps(project))
    for name, data in assets.items(): z.writestr(name, data)
print("wrote", OUT, "| pieces", len(pw), "| blocks", len(GAME_BLOCKS) + len(STAGE_BLOCKS), "| costumes", len(COSTUMES), "| variables", len(VARS), "| size", os.path.getsize(OUT))
