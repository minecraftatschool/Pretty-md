"""Builds BlockyPuzzle-v1.9-scratch.sb3: a Scratch 3 recreation of Blocky Puzzle.

Everything on screen is stamped with the pen by one hidden sprite, so the whole game lives in
that sprite's scripts. Run:  python3 gen_sb3.py <audio_dir> <music.wav> <out.sb3>
"""
import json, hashlib, zipfile, wave, sys, os

AUDIO, MUSIC, OUT = sys.argv[1], sys.argv[2], sys.argv[3]

# ---------------------------------------------------------------- block builder
_n = [0]
def nid(p="b"):
    _n[0] += 1
    return "%s%d" % (p, _n[0])

class R:                     # reporter block
    def __init__(s, opcode, inputs=None, fields=None, mutation=None):
        s.opcode, s.inputs, s.fields, s.mutation = opcode, inputs or {}, fields or {}, mutation
class S(R):                  # stack block
    pass
class V:                     # variable reporter
    def __init__(s, name): s.name = name

BLOCKS = {}                  # blocks of the target being built
SIG = {}                     # procedure name -> arg names

def lit(kind, v):
    if isinstance(v, float) and v == int(v): v = int(v)
    return [1, [10 if kind == "s" else 4, str(v)]]

def enc(kind, val, parent):
    if kind == "sub":
        first = stack(val, parent)
        return [2, first] if first else None
    if kind == "b":
        return [2, emit(val, parent)]
    if kind == "menu":       # (menu opcode, field name, constant) or (..., reporter)
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

# reporters
def op2(code, a, b, k="n", n1="NUM1", n2="NUM2"): return R(code, {n1: (k, a), n2: (k, b)})
def add(a, b): return op2("operator_add", a, b)
def sub(a, b): return op2("operator_subtract", a, b)
def mul(a, b): return op2("operator_multiply", a, b)
def div(a, b): return op2("operator_divide", a, b)
def mod(a, b): return op2("operator_mod", a, b)
def rnd(a): return R("operator_round", {"NUM": ("n", a)})
def mathop(o, a): return R("operator_mathop", {"NUM": ("n", a)}, {"OPERATOR": [o, None]})
def floor(a): return mathop("floor", a)
def ceil(a): return mathop("ceiling", a)
def absv(a): return mathop("abs", a)
def rand(a, b): return R("operator_random", {"FROM": ("n", a), "TO": ("n", b)})
def join(a, b): return R("operator_join", {"STRING1": ("s", a), "STRING2": ("s", b)})
def letter(i, s): return R("operator_letter_of", {"LETTER": ("n", i), "STRING": ("s", s)})
def length(s): return R("operator_length", {"STRING": ("s", s)})
def lt(a, b): return op2("operator_lt", a, b, "s", "OPERAND1", "OPERAND2")
def gt(a, b): return op2("operator_gt", a, b, "s", "OPERAND1", "OPERAND2")
def eq(a, b): return op2("operator_equals", a, b, "s", "OPERAND1", "OPERAND2")
def and_(a, b): return R("operator_and", {"OPERAND1": ("b", a), "OPERAND2": ("b", b)})
def or_(a, b): return R("operator_or", {"OPERAND1": ("b", a), "OPERAND2": ("b", b)})
def not_(a): return R("operator_not", {"OPERAND": ("b", a)})
def LF(name): return {"LIST": [name, "list_" + name]}
def item(lst, i): return R("data_itemoflist", {"INDEX": ("n", i)}, LF(lst))
def lenlist(lst): return R("data_lengthoflist", {}, LF(lst))
def arg(name): return R("argument_reporter_string_number", {}, {"VALUE": [name, None]})
MOUSEX, MOUSEY = R("sensing_mousex"), R("sensing_mousey")
def mousedown(): return R("sensing_mousedown")
def timer(): return R("sensing_timer")
# stack blocks
def VF(name): return {"VARIABLE": [name, "var_" + name]}
def setv(v, x): return S("data_setvariableto", {"VALUE": ("s", x)}, VF(v))
def chg(v, x): return S("data_changevariableby", {"VALUE": ("n", x)}, VF(v))
def replace(lst, i, x): return S("data_replaceitemoflist", {"INDEX": ("n", i), "ITEM": ("s", x)}, LF(lst))
def addto(lst, x): return S("data_addtolist", {"ITEM": ("s", x)}, LF(lst))
def delall(lst): return S("data_deletealloflist", {}, LF(lst))
def if_(c, body): return S("control_if", {"CONDITION": ("b", c), "SUBSTACK": ("sub", body)})
def ifelse(c, a, b): return S("control_if_else", {"CONDITION": ("b", c), "SUBSTACK": ("sub", a), "SUBSTACK2": ("sub", b)})
def repeat(n, body): return S("control_repeat", {"TIMES": ("n", n), "SUBSTACK": ("sub", body)})
def forever(body): return S("control_forever", {"SUBSTACK": ("sub", body)})
def until(c, body): return S("control_repeat_until", {"CONDITION": ("b", c), "SUBSTACK": ("sub", body)})
def goto(x, y): return S("motion_gotoxy", {"X": ("n", x), "Y": ("n", y)})
def costume(c): return S("looks_switchcostumeto", {"COSTUME": ("menu", ("looks_costume", "COSTUME", c))})
def size(v): return S("looks_setsizeto", {"SIZE": ("n", v)})
def ghost(v): return S("looks_seteffectto", {"VALUE": ("n", v)}, {"EFFECT": ["GHOST", None]})
def clearfx(): return S("looks_cleargraphiceffects")
def hide(): return S("looks_hide")
def erase(): return S("pen_clear")
def stamp_(): return S("pen_stamp")
def play(name): return S("sound_play", {"SOUND_MENU": ("menu", ("sound_sounds_menu", "SOUND_MENU", name))})
def playwait(name): return S("sound_playuntildone", {"SOUND_MENU": ("menu", ("sound_sounds_menu", "SOUND_MENU", name))})
def volume(v): return S("sound_setvolumeto", {"VOLUME": ("n", v)})
def resettimer(): return S("sensing_resettimer")
def flag(body): stack([S("event_whenflagclicked")] + body, None, True)

def proccode(name): return name + " %s" * len(SIG[name])
def argids(name): return ["arg_%s_%s" % (name.replace(" ", "_"), a) for a in SIG[name]]
def call(name, *args):
    assert len(args) == len(SIG[name]), name
    return S("procedures_call", {i: ("s", a) for i, a in zip(argids(name), args)},
             mutation={"tagName": "mutation", "children": [], "proccode": proccode(name), "argumentids": json.dumps(argids(name)), "warp": "true"})
def define(name, body):
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
    first = stack(body, did)
    BLOCKS[did]["next"] = first

# ---------------------------------------------------------------- game data
N, CS = 8, 34
BX, BY = -156, 136                      # top-left corner of the board on the stage
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
    for v in seen:
        cells = [(c, r) for r, row in enumerate(v) for c, ch in enumerate(row) if ch == "x"]
        pw.append(len(v[0])); ph.append(len(v)); pcol.append(color)
        pstart.append(len(pdx) + 1); pcount.append(len(cells))
        for c, r in cells: pdx.append(c); pdy.append(r)
        bag += [len(pw)] * max(1, round(12 * weight / len(seen)))     # weighted draw: pick a random bag item

# ---------------------------------------------------------------- costumes
INK, CREAM, CELLC, GOLD, GREEN, GREEN2 = "#1c1a17", "#f3ead5", "#e2d5b6", "#f2b632", "#1f4b43", "#235249"
COLORS = ["#000000", "#e8503a", "#f58a1f", "#f2b632", "#6cba3f", "#3d8fd9", "#8f5bd0", "#ef7fa5", "#8f897b", "#ffffff"]
def dark(h, k=0.72): return "#%02x%02x%02x" % tuple(int(int(h[i:i + 2], 16) * k) for i in (1, 3, 5))
def svg(w, h, body): return ('<svg version="1.1" xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">'
                             '<rect width="%d" height="%d" fill="none"/>%s</svg>') % (w, h, w, h, w, h, body)
def text(t, x, y, sz, fill, anchor="middle", stroke=None):
    st = ' stroke="%s" stroke-width="%g" stroke-linejoin="round" paint-order="stroke"' % (stroke, sz * 0.22) if stroke else ""
    return '<text x="%g" y="%g" font-family="Marker" font-size="%g" fill="%s" text-anchor="%s" xml:space="preserve"%s>%s</text>' % (x, y + sz * 0.35, sz, fill, anchor, st, t)
def tile(col):
    return svg(CS, CS, '<rect x="1" y="1" width="32" height="32" rx="6" fill="%s"/><rect x="3" y="3" width="28" height="28" rx="4" fill="%s"/>'
               '<rect x="3" y="3" width="28" height="24" rx="4" fill="%s"/><rect x="7" y="6" width="7" height="3" rx="1.5" fill="#ffffff" fill-opacity="0.5"/>' % (INK, dark(col), col))
def button(w, h, label, fill=CREAM, sz=None):
    sz = sz or h * 0.5
    return svg(w, h + 5, '<rect x="1" y="6" width="%d" height="%d" rx="%g" fill="%s"/><rect x="2.5" y="2.5" width="%d" height="%d" rx="%g" fill="%s" stroke="%s" stroke-width="3"/>%s'
               % (w - 2, h - 2, h * 0.3, INK, w - 5, h - 5, h * 0.3, fill, INK, text(label, w / 2, h / 2, sz, INK)))
def label(t, w, h, sz, fill=CREAM, stroke=None): return svg(w, h, text(t, w / 2, h / 2, sz, fill, stroke=stroke))

board_cells = "".join('<rect x="%d" y="%d" width="30" height="30" rx="5" fill="%s"/>' % (10 + c * CS, 10 + r * CS, CELLC) for r in range(N) for c in range(N))
stripes = "".join('<polygon points="%d,0 %d,0 %d,360 %d,360" fill="%s"/>' % (x, x + 40, x + 40 - 144, x - 144, GREEN2) for x in range(-40, 700, 90))
COSTUMES = [("t%d" % i, tile(COLORS[i]), CS / 2, CS / 2) for i in range(1, 9)]
COSTUMES += [
    ("t9", svg(CS, CS, '<rect x="1" y="1" width="32" height="32" rx="6" fill="#ffffff" stroke="%s" stroke-width="2"/>' % INK), 17, 17),
    ("board", svg(288, 294, '<rect x="1" y="7" width="286" height="286" rx="14" fill="%s"/><rect x="2" y="2" width="284" height="284" rx="14" fill="%s" stroke="%s" stroke-width="4"/>%s' % (INK, CREAM, INK, board_cells)), 144, 144),
    ("panel", svg(250, 220, '<rect x="2" y="2" width="246" height="216" rx="16" fill="%s" fill-opacity="0.9" stroke="%s" stroke-width="4"/>' % (INK, CREAM)), 125, 110),
    ("title", svg(440, 120, text("BLOCKY", 220, 30, 58, CREAM, stroke=INK) + text("PUZZLE", 220, 86, 58, GOLD, stroke=INK)), 220, 60),
    ("btn-m1", button(204, 62, "CLASSIC"), 102, 33), ("btn-m2", button(204, 62, "RUSH"), 102, 33),
    ("btn-m3", button(204, 62, "30 MOVES"), 102, 33), ("btn-m4", button(204, 62, "RUBBLE"), 102, 33),
    ("btn-again", button(180, 44, "PLAY AGAIN", "#6cba3f"), 90, 24), ("btn-menu", button(120, 34, "MENU"), 60, 19),
    ("btn-home", button(72, 30, "MENU", CREAM, 14), 36, 17),
    ("m1", label("CLASSIC", 84, 22, 15), 42, 11), ("m2", label("RUSH", 84, 22, 15), 42, 11),
    ("m3", label("30 MOVES", 84, 22, 15), 42, 11), ("m4", label("RUBBLE", 84, 22, 15), 42, 11),
    ("txt-score", label("SCORE", 84, 20, 13, GOLD), 42, 10), ("txt-best", label("BEST", 84, 20, 13, GOLD), 42, 10),
    ("txt-time", label("TIME", 84, 20, 13, GOLD), 42, 10), ("txt-moves", label("MOVES", 84, 20, 13, GOLD), 42, 10),
    ("txt-stones", label("STONES IN", 84, 20, 12, GOLD), 42, 10), ("txt-combo", label("COMBO", 84, 20, 13, "#ef7fa5"), 42, 10),
    ("txt-gameover", label("GAME OVER", 240, 40, 32, "#e8503a"), 120, 20), ("txt-timeup", label("TIME'S UP", 240, 40, 32, "#e8503a"), 120, 20),
    ("txt-nomoves", label("OUT OF MOVES", 240, 40, 28, "#e8503a"), 120, 20),
    ("txt-newbest", label("NEW BEST!", 200, 26, 18, GOLD), 100, 13),
    ("txt-drag", label("DRAG A PIECE ONTO THE BOARD", 280, 22, 13, INK), 140, 11),
    ("ver", label("v1.9-scratch", 160, 18, 11, CREAM), 80, 9),
]
COSTUMES += [("d%d" % i, label(str(i), 20, 28, 24), 10, 14) for i in range(10)]
BACKDROP = svg(480, 360, '<rect width="480" height="360" fill="%s"/>%s' % (GREEN, stripes))

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

# ---------------------------------------------------------------- scripts of the Game sprite
SIG.update({
    "fits": ["p", "c", "r"], "fits anywhere": ["p"], "can move": [], "deal": [], "new game": [], "check lines": [],
    "drop stones": [], "end game": ["why"], "place": ["slot", "c", "r"], "stamp": ["cos", "x", "y", "size"],
    "draw piece": ["p", "x", "y", "cell", "size"], "draw number": ["n", "x", "y", "size"], "draw play": [], "draw menu": [],
    "draw over": [], "tick": [], "draw": [],
})
VARS = {"state": "menu", "mode": 1, "score": 0, "combo": 0, "dry": 0, "timeLeft": 120, "movesLeft": 30, "rubbleIn": 4, "lastT": 0,
        "dragSlot": 0, "dragC": -1, "dragR": -1, "mx": 0, "my": 0, "down": 0, "wasDown": 0, "click": 0, "overT": 0, "newBest": 0,
        "overWhy": "txt-gameover", "moved": 0, "fit": 0, "any": 0, "canMove": 0, "lines": 0, "gain": 0, "tries": 0, "n": 0,
        "i": 0, "j": 0, "k": 0, "full": 0, "idx": 0, "p": 0, "c0": 0, "r0": 0, "slot": 0, "fk": 0, "far": 0, "fac": 0, "cmi": 0,
        "dpk": 0, "dnx": 0, "dni": 0, "di": 0, "ti": 0, "bi": 0, "bx": 0, "by": 0}
LISTS = {"grid": [0] * 64, "fx": [0] * 64, "tray": [0, 0, 0], "bests": [0, 0, 0, 0], "rowsFull": [], "colsFull": [],
         "pw": pw, "ph": ph, "pcol": pcol, "pstart": pstart, "pcount": pcount, "pdx": pdx, "pdy": pdy, "bag": bag}
def v(n):
    assert n in VARS, n
    return V(n)
def gidx(c, r): return add(add(mul(r, 8), c), 1)             # 1-based index into grid

BLOCKS = {}
define("fits", [
    setv("fit", 1),
    ifelse(or_(or_(lt(arg("c"), 0), lt(arg("r"), 0)), or_(gt(add(arg("c"), item("pw", arg("p"))), 8), gt(add(arg("r"), item("ph", arg("p"))), 8))),
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
        repeat(sub(9, item("pw", arg("p"))), [
            call("fits", arg("p"), v("fac"), v("far")),
            if_(eq(v("fit"), 1), [setv("any", 1)]),
            chg("fac", 1)]),
        chg("far", 1)]),
])
define("can move", [
    setv("canMove", 0), setv("cmi", 1),
    repeat(3, [
        if_(gt(item("tray", v("cmi")), 0), [call("fits anywhere", item("tray", v("cmi"))), if_(eq(v("any"), 1), [setv("canMove", 1)])]),
        chg("cmi", 1)]),
])
define("deal", [                                               # three weighted-random pieces, redrawn until at least one fits
    setv("tries", 0), setv("canMove", 0),
    until(or_(eq(v("canMove"), 1), gt(v("tries"), 40)), [
        replace("tray", 1, item("bag", rand(1, lenlist("bag")))),
        replace("tray", 2, item("bag", rand(1, lenlist("bag")))),
        replace("tray", 3, item("bag", rand(1, lenlist("bag")))),
        call("can move"), chg("tries", 1)]),
])
define("new game", [
    setv("i", 1), repeat(64, [replace("grid", v("i"), 0), replace("fx", v("i"), 0), chg("i", 1)]),
    setv("score", 0), setv("combo", 0), setv("dry", 0), setv("timeLeft", 120), setv("movesLeft", 30), setv("rubbleIn", 4),
    setv("dragSlot", 0), setv("dragC", -1), setv("newBest", 0), setv("overT", 0), setv("moved", 0),
    call("deal"), resettimer(), setv("lastT", 0), setv("state", "play"), play("start"),
])
define("check lines", [                                        # clears every full row and column, leaves the count in "lines"
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
        setv("j", 0),
        repeat(8, [setv("idx", gidx(v("j"), item("rowsFull", v("k")))), replace("grid", v("idx"), 0), replace("fx", v("idx"), 8), chg("j", 1)]),
        chg("k", 1)]),
    setv("k", 1),
    repeat(lenlist("colsFull"), [
        setv("j", 0),
        repeat(8, [setv("idx", gidx(item("colsFull", v("k")), v("j"))), replace("grid", v("idx"), 0), replace("fx", v("idx"), 8), chg("j", 1)]),
        chg("k", 1)]),
])
define("drop stones", [
    setv("n", 3), setv("tries", 0),
    until(or_(eq(v("n"), 0), gt(v("tries"), 300)), [
        setv("idx", rand(1, 64)),
        if_(eq(item("grid", v("idx")), 0), [replace("grid", v("idx"), 8), chg("n", -1)]),
        chg("tries", 1)]),
    play("stone"),
    call("check lines"),
    if_(gt(v("lines"), 0), [chg("score", mul(10, mul(v("lines"), v("lines"))))]),
])
define("end game", [
    if_(eq(v("state"), "play"), [
        setv("state", "over"), setv("overT", 0), setv("overWhy", arg("why")), setv("dragSlot", 0), setv("newBest", 0),
        ifelse(gt(v("score"), item("bests", v("mode"))), [replace("bests", v("mode"), v("score")), setv("newBest", 1), play("best")], [play("over")])]),
])
define("place", [
    setv("p", item("tray", arg("slot"))), setv("k", item("pstart", v("p"))),
    repeat(item("pcount", v("p")), [
        replace("grid", gidx(add(arg("c"), item("pdx", v("k"))), add(arg("r"), item("pdy", v("k")))), item("pcol", v("p"))),
        chg("k", 1)]),
    replace("tray", arg("slot"), 0),
    setv("gain", item("pcount", v("p"))), setv("moved", 1),
    call("check lines"),
    ifelse(gt(v("lines"), 0), [
        chg("combo", 1), setv("dry", 0),
        chg("gain", mul(mul(10, mul(v("lines"), v("lines"))), v("combo"))),
        if_(eq(v("mode"), 2), [chg("timeLeft", mul(2, v("lines")))]),
        ifelse(gt(v("lines"), 1), [play("big")], [play("clear")]),
    ], [
        chg("dry", 1), if_(gt(v("dry"), 2), [setv("combo", 0)]), play("place"),
    ]),
    chg("score", v("gain")),
    if_(eq(v("mode"), 4), [chg("rubbleIn", -1), if_(lt(v("rubbleIn"), 1), [setv("rubbleIn", 4), call("drop stones")])]),
    if_(eq(add(add(item("tray", 1), item("tray", 2)), item("tray", 3)), 0), [call("deal")]),
    if_(eq(v("mode"), 3), [chg("movesLeft", -1), if_(lt(v("movesLeft"), 1), [call("end game", "txt-nomoves")])]),
    call("can move"),
    if_(eq(v("canMove"), 0), [call("end game", "txt-gameover")]),
])
# ---- drawing: everything is a pen stamp of one of this sprite's costumes
define("stamp", [costume(arg("cos")), size(arg("size")), goto(arg("x"), arg("y")), stamp_()])
define("draw piece", [                                         # x, y = top-left corner of the piece, cell = cell size in steps
    setv("dpk", item("pstart", arg("p"))),
    repeat(item("pcount", arg("p")), [
        call("stamp", join("t", item("pcol", arg("p"))),
             add(arg("x"), add(mul(item("pdx", v("dpk")), arg("cell")), div(arg("cell"), 2))),
             sub(arg("y"), add(mul(item("pdy", v("dpk")), arg("cell")), div(arg("cell"), 2))), arg("size")),
        chg("dpk", 1)]),
])
define("draw number", [                                        # centred on x
    setv("dnx", sub(arg("x"), mul(sub(length(arg("n")), 1), mul(arg("size"), 0.085)))), setv("dni", 1),
    repeat(length(arg("n")), [
        call("stamp", join("d", letter(v("dni"), arg("n"))), v("dnx"), arg("y"), arg("size")),
        chg("dnx", mul(arg("size"), 0.17)), chg("dni", 1)]),
])
HX = -198                                                      # centre of the left-hand panel
define("draw play", [
    call("stamp", "board", BX + 136, 0, 100),
    setv("di", 1),
    repeat(64, [
        setv("bx", add(BX + 17, mul(mod(sub(v("di"), 1), 8), CS))),
        setv("by", sub(BY - 17, mul(floor(div(sub(v("di"), 1), 8)), CS))),
        ifelse(gt(item("fx", v("di")), 0),
               [call("stamp", "t9", v("bx"), v("by"), mul(item("fx", v("di")), 12.5)), replace("fx", v("di"), sub(item("fx", v("di")), 1))],
               [if_(gt(item("grid", v("di")), 0), [call("stamp", join("t", item("grid", v("di"))), v("bx"), v("by"), 100)])]),
        chg("di", 1)]),
    if_(and_(eq(v("moved"), 0), eq(v("dragSlot"), 0)), [call("stamp", "txt-drag", BX + 136, 0, 100)]),
    if_(and_(gt(v("dragSlot"), 0), gt(v("dragC"), -1)), [
        ghost(55),
        call("draw piece", item("tray", v("dragSlot")), add(BX, mul(v("dragC"), CS)), sub(BY, mul(v("dragR"), CS)), CS, 100),
        clearfx()]),
    setv("ti", 1),
    repeat(3, [
        if_(and_(gt(item("tray", v("ti")), 0), not_(eq(v("ti"), v("dragSlot")))), [
            call("draw piece", item("tray", v("ti")),
                 sub(180, mul(item("pw", item("tray", v("ti"))), 9)),
                 add(sub(91, mul(sub(v("ti"), 1), 91)), mul(item("ph", item("tray", v("ti"))), 9)), 18, 53)]),
        chg("ti", 1)]),
    if_(gt(v("dragSlot"), 0), [
        call("draw piece", item("tray", v("dragSlot")),
             sub(v("mx"), mul(item("pw", item("tray", v("dragSlot"))), 17)),
             add(add(v("my"), 24), mul(item("ph", item("tray", v("dragSlot"))), 17)), CS, 100)]),
    call("stamp", join("m", v("mode")), HX, 150, 100),
    call("stamp", "txt-score", HX, 118, 100), call("draw number", v("score"), HX, 94, 110),
    if_(eq(v("mode"), 2), [call("stamp", "txt-time", HX, 52, 100), call("draw number", ceil(v("timeLeft")), HX, 30, 100)]),
    if_(eq(v("mode"), 3), [call("stamp", "txt-moves", HX, 52, 100), call("draw number", v("movesLeft"), HX, 30, 100)]),
    if_(eq(v("mode"), 4), [call("stamp", "txt-stones", HX, 52, 100), call("draw number", v("rubbleIn"), HX, 30, 100)]),
    if_(gt(v("combo"), 1), [call("stamp", "txt-combo", HX, -10, 100), call("draw number", v("combo"), HX, -32, 100)]),
    call("stamp", "txt-best", HX, -74, 100), call("draw number", item("bests", v("mode")), HX, -96, 90),
    call("stamp", "btn-home", HX, -150, 100),
])
define("draw menu", [
    call("stamp", "title", 0, 112, 100),
    setv("bi", 1),
    repeat(4, [
        setv("bx", add(-112, mul(mod(sub(v("bi"), 1), 2), 224))),
        setv("by", sub(22, mul(floor(div(sub(v("bi"), 1), 2)), 96))),
        call("stamp", join("btn-m", v("bi")), v("bx"), v("by"), 100),
        call("stamp", "txt-best", sub(v("bx"), 24), sub(v("by"), 48), 100),
        call("draw number", item("bests", v("bi")), add(v("bx"), 24), sub(v("by"), 48), 70),
        chg("bi", 1)]),
    call("stamp", "ver", 0, -168, 100),
])
OX = BX + 136
define("draw over", [
    if_(gt(v("overT"), 12), [
        call("stamp", "panel", OX, 0, 100),
        call("stamp", v("overWhy"), OX, 78, 100),
        call("draw number", v("score"), OX, 36, 170),
        if_(eq(v("newBest"), 1), [call("stamp", "txt-newbest", OX, 0, 100)]),
        call("stamp", "btn-again", OX, -40, 100),
        call("stamp", "btn-menu", OX, -86, 100)]),
])
define("draw", [
    erase(),
    ifelse(eq(v("state"), "menu"), [call("draw menu")], [call("draw play"), if_(eq(v("state"), "over"), [call("draw over")])]),
])
def near(x, y, hw, hh): return and_(lt(absv(sub(v("mx"), x)), hw), lt(absv(sub(v("my"), y)), hh))
define("tick", [
    setv("mx", MOUSEX), setv("my", MOUSEY),
    ifelse(mousedown(), [setv("down", 1)], [setv("down", 0)]),
    ifelse(and_(eq(v("down"), 1), eq(v("wasDown"), 0)), [setv("click", 1)], [setv("click", 0)]),
    if_(eq(v("state"), "over"), [
        chg("overT", 1),
        if_(and_(eq(v("click"), 1), gt(v("overT"), 20)), [
            ifelse(near(OX, -40, 92, 24), [call("new game")], [if_(near(OX, -86, 62, 19), [setv("state", "menu"), setv("click", 0), play("click")])])]),
    ]),
    if_(eq(v("state"), "play"), [
        if_(eq(v("mode"), 2), [
            chg("timeLeft", sub(v("lastT"), timer())),
            if_(lt(v("timeLeft"), 0.01), [setv("timeLeft", 0), call("end game", "txt-timeup")])]),
        setv("lastT", timer()),
    ]),
    if_(eq(v("state"), "play"), [
        ifelse(eq(v("dragSlot"), 0), [
            if_(eq(v("click"), 1), [
                if_(gt(v("mx"), 122), [
                    setv("slot", add(1, floor(div(sub(136, v("my")), 91)))),
                    if_(lt(v("slot"), 1), [setv("slot", 1)]), if_(gt(v("slot"), 3), [setv("slot", 3)]),
                    if_(gt(item("tray", v("slot")), 0), [setv("dragSlot", v("slot")), setv("dragC", -1), play("pick")])]),
                if_(near(HX, -150, 38, 18), [setv("state", "menu"), setv("click", 0), play("click")])]),
        ], [
            setv("p", item("tray", v("dragSlot"))),
            setv("c0", rnd(div(sub(sub(v("mx"), mul(item("pw", v("p")), 17)), BX), CS))),
            setv("r0", rnd(div(sub(BY, add(add(v("my"), 24), mul(item("ph", v("p")), 17))), CS))),
            call("fits", v("p"), v("c0"), v("r0")),
            ifelse(eq(v("fit"), 1), [setv("dragC", v("c0")), setv("dragR", v("r0"))], [setv("dragC", -1)]),
            if_(eq(v("down"), 0), [
                setv("slot", v("dragSlot")), setv("dragSlot", 0),
                ifelse(gt(v("dragC"), -1), [call("place", v("slot"), v("dragC"), v("dragR"))], [play("back")])]),
        ]),
    ]),
    if_(and_(eq(v("state"), "menu"), eq(v("click"), 1)), [
        setv("bi", 1),
        repeat(4, [
            if_(and_(eq(v("state"), "menu"), near(add(-112, mul(mod(sub(v("bi"), 1), 2), 224)), sub(22, mul(floor(div(sub(v("bi"), 1), 2)), 96)), 102, 33)),
                [setv("mode", v("bi")), call("new game")]),
            chg("bi", 1)]),
    ]),
    setv("wasDown", v("down")),
])
flag([hide(), clearfx(), setv("state", "menu"), setv("wasDown", 1), setv("dragSlot", 0), forever([call("tick"), call("draw")])])
GAME_BLOCKS = BLOCKS

BLOCKS = {}
flag([volume(35), forever([playwait("music")])])
STAGE_BLOCKS = BLOCKS

# ---------------------------------------------------------------- project
SFX = ["click", "pick", "place", "back", "stone", "clear", "big", "over", "best", "start"]
project = {
    "targets": [
        {"isStage": True, "name": "Stage", "variables": {}, "lists": {}, "broadcasts": {}, "blocks": STAGE_BLOCKS, "comments": {},
         "currentCostume": 0, "costumes": [costume_entry("felt", BACKDROP, 240, 180)], "sounds": [sound_entry("music", MUSIC)],
         "volume": 100, "layerOrder": 0, "tempo": 60, "videoTransparency": 50, "videoState": "on", "textToSpeechLanguage": None},
        {"isStage": False, "name": "Game", "variables": {"var_" + k: [k, val] for k, val in VARS.items()},
         "lists": {"list_" + k: [k, val] for k, val in LISTS.items()}, "broadcasts": {}, "blocks": GAME_BLOCKS, "comments": {},
         "currentCostume": 0, "costumes": [costume_entry(*c) for c in COSTUMES], "sounds": [sound_entry(n, os.path.join(AUDIO, n + ".wav")) for n in SFX],
         "volume": 100, "layerOrder": 1, "visible": False, "x": 0, "y": 0, "size": 100, "direction": 90, "draggable": False, "rotationStyle": "all around"},
    ],
    "monitors": [], "extensions": ["pen"],
    "meta": {"semver": "3.0.0", "vm": "0.2.0", "agent": "Blocky Puzzle v1.9-scratch generator"},
}
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("project.json", json.dumps(project))
    for name, data in assets.items(): z.writestr(name, data)
print("wrote", OUT, "| pieces", len(pw), "| blocks", len(GAME_BLOCKS) + len(STAGE_BLOCKS), "| assets", len(assets))
