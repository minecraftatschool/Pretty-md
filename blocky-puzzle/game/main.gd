extends Node2D

const N := 8
const BASES := [
	[["x"], 1, 1.0], [["xx"], 2, 3.0], [["xxx"], 3, 4.0], [["xxxx"], 4, 3.0], [["xxxxx"], 5, 2.0],
	[["xx", "xx"], 6, 5.0], [["xxx", "xxx", "xxx"], 7, 3.0], [["xxx", "xxx"], 2, 3.0],
	[["x.", "xx"], 3, 4.0], [["x.", "x.", "xx"], 4, 3.0], [[".x", ".x", "xx"], 5, 3.0],
	[["x..", "x..", "xxx"], 6, 3.0], [["xxx", ".x."], 1, 3.0], [[".xx", "xx."], 7, 2.0], [["xx.", ".xx"], 5, 2.0],
	[["x.", ".x"], 4, 1.0],
]
const PRAISE := ["", "", "NICE!", "SWEET!", "WHOA!", "UNREAL!", "LEGEND!"]
const SAVE := "user://save2.json"
const MODES := [
	{"name": "CLASSIC", "desc": "No clock. Play till the board jams.", "c": 1},
	{"name": "RUSH", "desc": "Two minutes. Each line adds 2 sec.", "c": 5},
	{"name": "30 MOVES", "desc": "Thirty pieces. Make them count.", "c": 4},
	{"name": "RUBBLE", "desc": "Stones drop in every 4 moves.", "c": 3},
]
const STONE := 8

var BG := Color("1f4b43")
var BG2 := Color("235249")
var INK := Color("1c1a17")
var CREAM := Color("f3ead5")
var CELL := Color("e2d5b6")
var MUTED := Color("7a6f5a")
var GOLD := Color("f2b632")
var COLORS := [Color.black, Color("e8503a"), Color("f58a1f"), Color("f2b632"), Color("6cba3f"), Color("3d8fd9"), Color("8f5bd0"), Color("ef7fa5"), Color("8f897b")]

var pieces := []
var total_w := 0.0
var state := "main"   # main | modes | help | settings | play
var mode := 0
var last_mode := 0
var web := false
var wide := false      # landscape browser window: board in the middle, score left, tray right
var has_js := false
var drag_touch := true
var last_touch := -10.0
var mute_poll := 0.0
var cg_playing := false
var col_x := 0.0
var col_w := 720.0
var bests := [0, 0, 0, 0]
var classic_save = null
var grid := []
var tray := [-1, -1, -1]
var score := 0
var shown := 0.0
var combo := 0
var dry := 0
var over := false
var over_title := "GAME OVER"
var new_best := false
var sound_on := true
var music_on := true
var vib_on := true
var tut := 0   # first-run coaching: 0 = show how to drag, 1 = show what a line is, 2 = done
var time_left := 120.0
var moves_left := 30
var rubble_in := 4

var cell := 64.0
var origin := Vector2()
var head_y := 0.0
var tray_y := 0.0
var vs := Vector2(720, 1280)
var compact := false
var dia := 720.0
var mini := 0.5
var rects := {}
var press_id := ""
var armed := ""
var armed_t := 0.0

var drag_slot := -1
var drag_idx := -1
var drag_pos := Vector2()
var drag_c := -1
var drag_r := -1
var drag_center := Vector2()
var drag_scale := 1.0
var ret := {}
var fx := []
var parts := []
var popups := []
var toast := ""
var toast_t := 0.0
var t_now := 0.0
var place_t := []
var tray_t := [0.0, 0.0, 0.0]
var intro_t := 0.0
var over_t := 0.0
var menu_t := 0.0
var score_pulse := 0.0
var shake_mag := 0.0
var shake := Vector2()
var sb := StyleBoxFlat.new()
var font_data: DynamicFontData
var fonts := {}
var sfx := {}
var players := []
var next_player := 0
var music: AudioStreamPlayer
var bump := 0.0
var beams := []
var last_tick := 0


func _ready() -> void:
	randomize()
	web = OS.get_name() == "HTML5" or OS.get_environment("BP_WEB") != ""
	has_js = OS.has_feature("JavaScript")
	font_data = load("res://font.ttf")
	for b in BASES:
		var seen := {}
		var m: Array = b[0]
		for _i in range(4):
			seen[PoolStringArray(m).join("/")] = m
			m = _rot90(m)
		for k in seen:
			var v: Array = seen[k]
			var cs := []
			for r in range(v.size()):
				for c in range(v[r].length()):
					if v[r][c] == "x":
						cs.append(Vector2(c, r))
			var w: float = b[2] / seen.size()
			total_w += w
			pieces.append({"cells": cs, "w": v[0].length(), "h": v.size(), "color": b[1], "weight": w})
	for n in ["click", "pick", "place", "back", "tick", "whoosh", "stone", "clear", "big", "over", "best", "start"]:
		sfx[n] = load("res://audio/%s.wav" % n)
	for _i in range(8):
		var p := AudioStreamPlayer.new()
		add_child(p)
		players.append(p)
	music = AudioStreamPlayer.new()
	var song = load("res://audio/music.ogg")
	song.loop = true
	music.stream = song
	music.volume_db = -13.0
	add_child(music)
	for _i in range(N * N):
		place_t.append(1.0)
		grid.append(0)
	_load()
	_music_sync()
	get_viewport().connect("size_changed", self, "_layout")
	_layout()
	if OS.get_environment("BP_TEST") != "":
		_selftest()


func _rot90(m: Array) -> Array:
	var o := []
	for c in range(m[0].length()):
		var s := ""
		for r in range(m.size() - 1, -1, -1):
			s += m[r][c]
		o.append(s)
	return o


func _sfx(name: String, pitch := 1.0, db := 0.0) -> void:
	if not sound_on:
		return
	var p: AudioStreamPlayer = players[next_player]
	next_player = (next_player + 1) % players.size()
	p.stream = sfx[name]
	p.pitch_scale = pitch
	p.volume_db = db
	p.play()


# Tells the hosting page what is happening (used by the CrazyGames build; a no-op elsewhere).
func _portal(event: String) -> void:
	if has_js:
		JavaScript.eval("window.cgEvent && window.cgEvent('%s')" % event, true)


func _portal_play(on: bool) -> void:
	if on == cg_playing:
		return
	cg_playing = on
	_portal("gameplayStart" if on else "gameplayStop")


func _buzz(ms: int) -> void:
	if vib_on and not web:
		Input.vibrate_handheld(ms)


func _music_sync() -> void:
	if music_on and not music.playing:
		music.play()
	elif not music_on and music.playing:
		music.stop()


func _font(size: int, outline := 0) -> DynamicFont:
	var key := size * 100 + outline
	if not fonts.has(key):
		var f := DynamicFont.new()
		f.font_data = font_data
		f.size = size
		f.use_filter = true
		f.outline_size = outline
		f.outline_color = INK
		fonts[key] = f
	return fonts[key]


# ---------- layout ----------
func _layout() -> void:
	vs = get_viewport_rect().size
	compact = vs.y < vs.x * 1.3
	col_w = vs.x
	col_x = 0.0
	wide = false
	if compact and web:
		# a browser window, not a watch: menus in a centred column, gameplay spread across the width
		compact = false
		wide = vs.x > vs.y * 1.2
		col_w = min(vs.x, 1000.0 if wide else vs.y * 0.6)
		col_x = (vs.x - col_w) / 2.0
	var cx := vs.x / 2.0
	rects = {}
	if compact:
		dia = min(vs.x, vs.y)
		var top := vs.y / 2.0 - dia / 2.0
		mini = 0.42
		cell = floor(dia * 0.075)
		var b := cell * 8.0
		head_y = top
		origin = Vector2(cx - b / 2.0, top + dia * 0.15)
		tray_y = origin.y + b + dia * 0.015
		var bs := dia * 0.11
		var by := origin.y + b / 2.0 - bs / 2.0
		rects["home"] = Rect2(cx - dia * 0.4 - bs / 2.0, by, bs, bs)
		rects["new"] = Rect2(cx + dia * 0.4 - bs / 2.0, by, bs, bs)
		var gw := dia * 0.3
		var gh := dia * 0.15
		for i in range(4):
			rects["mode%d" % i] = Rect2(cx - gw - dia * 0.015 + (i % 2) * (gw + dia * 0.03), top + dia * 0.27 + int(i / 2) * (gh + dia * 0.03), gw, gh)
		rects["back"] = Rect2(cx - dia * 0.13, top + dia * 0.68, dia * 0.26, dia * 0.085)
		rects["play"] = Rect2(cx - dia * 0.23, top + dia * 0.32, dia * 0.46, dia * 0.15)
		var sw := dia * 0.2
		rects["modes"] = Rect2(cx - sw * 1.5 - dia * 0.02, top + dia * 0.53, sw, dia * 0.11)
		rects["help"] = Rect2(cx - sw * 0.5, top + dia * 0.53, sw, dia * 0.11)
		rects["settings"] = Rect2(cx + sw * 0.5 + dia * 0.02, top + dia * 0.53, sw, dia * 0.11)
		var sn := 0
		for sid in ["set_sound", "set_music", "set_vib", "set_reset"]:
			rects[sid] = Rect2(cx - dia * 0.24, top + dia * (0.25 + sn * 0.105), dia * 0.48, dia * 0.085)
			sn += 1
	else:
		mini = 0.56
		var head := 190.0
		cell = floor(min((col_w - 36.0) / 8.0, (vs.y - head - 90.0) / 11.2))
		var bw := cell * 8.0
		var total := head + bw + 34.0 + cell * 3.0
		head_y = max(16.0, (vs.y - total) / 2.0)
		origin = Vector2((vs.x - bw) / 2.0, head_y + head)
		tray_y = origin.y + bw + 34.0
		rects["home"] = Rect2(origin.x, head_y + 24.0, 76.0, 76.0)
		rects["new"] = Rect2(origin.x + bw - 76.0, head_y + 24.0, 76.0, 76.0)
		if wide:
			cell = floor(min((vs.y - 110.0) / 8.0, (vs.x - 760.0) / 8.0))
			bw = cell * 8.0
			origin = Vector2((vs.x - bw) / 2.0, (vs.y - bw) / 2.0)
			var side := min(origin.x - 30.0, 560.0)
			var lx := origin.x - 30.0 - side / 2.0
			mini = min(0.5, (side - 20.0) / (5.0 * cell))
			rects["home"] = Rect2(lx - 116.0, origin.y + bw - 112.0, 104.0, 104.0)
			rects["new"] = Rect2(lx + 12.0, origin.y + bw - 112.0, 104.0, 104.0)
		var cw := col_w - 72.0
		var y0 := max(vs.y * 0.22, 230.0)
		for i in range(4):
			rects["mode%d" % i] = Rect2(col_x + 36.0, y0 + i * 152.0, cw, 128.0)
		rects["back"] = Rect2(col_x + 36.0, max(40.0, vs.y * 0.06), 76.0, 76.0)
		var my := max(vs.y * 0.44, 540.0)
		rects["play"] = Rect2(cx - 230.0, my, 460.0, 132.0)
		rects["modes"] = Rect2(cx - 190.0, my + 196.0, 380.0, 88.0)
		rects["help"] = Rect2(cx - 190.0, my + 306.0, 380.0, 88.0)
		rects["settings"] = Rect2(cx - 190.0, my + 416.0, 380.0, 88.0)
		var sn2 := 0
		for sid in ["set_sound", "set_music", "set_vib", "set_reset"]:
			rects[sid] = Rect2(col_x + col_w - 36.0 - 220.0, y0 + 26.0 + sn2 * 152.0, 196.0, 76.0)
			sn2 += 1
	var bw2 := cell * 8.0
	var ks := cell / 85.0 if wide else 1.0
	rects["again"] = Rect2(cx - 190.0 * ks, origin.y + bw2 * 0.62, 380.0 * ks, 92.0 * ks)
	rects["menu"] = Rect2(cx - 120.0 * ks, origin.y + bw2 * 0.83, 240.0 * ks, 68.0 * ks)
	update()


# ---------- rules ----------
func _rand_piece() -> int:
	var x := randf() * total_w
	for i in range(pieces.size()):
		x -= pieces[i].weight
		if x <= 0.0:
			return i
	return 0


func _fits_g(g: Array, p: Dictionary, c0: int, r0: int) -> bool:
	if c0 < 0 or r0 < 0 or c0 + p.w > N or r0 + p.h > N:
		return false
	for c in p.cells:
		if g[(r0 + int(c.y)) * N + c0 + int(c.x)] != 0:
			return false
	return true


func _fits_anywhere(p: Dictionary) -> bool:
	for r in range(N - p.h + 1):
		for c in range(N - p.w + 1):
			if _fits_g(grid, p, c, r):
				return true
	return false


func _can_move() -> bool:
	for i in tray:
		if i >= 0 and _fits_anywhere(pieces[i]):
			return true
	return false


func _lines_if(g: Array, mine: Dictionary, c0: int, r0: int, w: int, h: int) -> Array:
	var rows := []
	var cols := []
	for r in range(r0, r0 + h):
		var full := true
		for j in range(N):
			if g[r * N + j] == 0 and not mine.has(r * N + j):
				full = false
				break
		if full:
			rows.append(r)
	for c in range(c0, c0 + w):
		var full2 := true
		for j in range(N):
			if g[j * N + c] == 0 and not mine.has(j * N + c):
				full2 = false
				break
		if full2:
			cols.append(c)
	return [rows, cols]


func _mine(p: Dictionary, c0: int, r0: int) -> Dictionary:
	var m := {}
	for c in p.cells:
		m[(r0 + int(c.y)) * N + c0 + int(c.x)] = p.color
	return m


func _sim_place(g: Array, p: Dictionary, c0: int, r0: int) -> void:
	var m := _mine(p, c0, r0)
	var f := _lines_if(g, m, c0, r0, p.w, p.h)
	for i in m:
		g[i] = p.color
	for r in f[0]:
		for j in range(N):
			g[r * N + j] = 0
	for c in f[1]:
		for j in range(N):
			g[j * N + c] = 0


# Deals a hand that is always solvable: each piece is picked so it fits on the board left by
# the previous ones, and the fuller the board, the likelier a piece that clears a line.
func _refill() -> void:
	var g := grid.duplicate()
	var hand := []
	for _k in range(3):
		var filled := 0
		for v in g:
			if v != 0:
				filled += 1
		var fill := filled / 64.0
		var fit_list := []
		var clear_list := []
		var tried := {}
		for _t in range(12):
			var idx := _rand_piece()
			if tried.has(idx):
				continue
			tried[idx] = true
			var p: Dictionary = pieces[idx]
			var spots := []
			var best_l := 0
			var best_spot := []
			for r in range(N - p.h + 1):
				for c in range(N - p.w + 1):
					if _fits_g(g, p, c, r):
						spots.append([c, r])
						var f := _lines_if(g, _mine(p, c, r), c, r, p.w, p.h)
						var l: int = f[0].size() + f[1].size()
						if l > best_l:
							best_l = l
							best_spot = [c, r]
			if spots.size() > 0:
				fit_list.append([idx, spots])
			if best_l > 0:
				clear_list.append([idx, best_spot])
		if fit_list.empty():
			var best_n := 99
			for idx in range(pieces.size()):
				var p: Dictionary = pieces[idx]
				if p.cells.size() >= best_n:
					continue
				var spots := []
				for r in range(N - p.h + 1):
					for c in range(N - p.w + 1):
						if _fits_g(g, p, c, r):
							spots.append([c, r])
				if spots.size() > 0:
					best_n = p.cells.size()
					fit_list = [[idx, spots]]
		if fit_list.empty():
			hand.append(_rand_piece())
			continue
		var pick := -1
		var spot := []
		if clear_list.size() > 0 and randf() < 0.25 + fill:
			var e: Array = clear_list[randi() % clear_list.size()]
			pick = e[0]
			spot = e[1]
		else:
			var e2: Array = fit_list[0]
			pick = e2[0]
			spot = e2[1][randi() % e2[1].size()]
		_sim_place(g, pieces[pick], spot[0], spot[1])
		hand.append(pick)
	hand.shuffle()
	tray = hand
	tray_t = [0.0, -0.08, -0.16]
	if state == "play":
		_sfx("whoosh")


func _reset_fx() -> void:
	fx = []
	parts = []
	popups = []
	toast_t = 0.0
	ret = {}
	drag_slot = -1
	drag_idx = -1
	drag_c = -1
	drag_r = -1
	armed = ""
	shake_mag = 0.0


func _new_game() -> void:
	for i in range(N * N):
		grid[i] = 0
	score = 0
	shown = 0.0
	combo = 0
	dry = 0
	over = false
	new_best = false
	over_t = 0.0
	intro_t = 0.0
	time_left = 120.0
	moves_left = 30
	rubble_in = 4
	_reset_fx()
	_refill()
	_save()
	_portal_play(state == "play")


func _start_mode(i: int) -> void:
	mode = i
	last_mode = i
	state = "play"
	_sfx("start")
	if i == 0 and typeof(classic_save) == TYPE_DICTIONARY and _restore(classic_save):
		_reset_fx()
		intro_t = 0.0
		tray_t = [0.0, -0.08, -0.16]
		_portal_play(true)
	else:
		_new_game()


func _go_menu() -> void:
	_portal_play(false)
	_reset_fx()
	_save()
	_goto("main")


func _goto(s: String) -> void:
	state = s
	menu_t = 0.0
	armed = ""
	press_id = ""


func _nav_back() -> void:
	if state == "play":
		_go_menu()
	elif state == "main":
		if not web:
			get_tree().quit()
	else:
		_goto("main")


func _notification(what: int) -> void:
	if what == MainLoop.NOTIFICATION_WM_GO_BACK_REQUEST:
		_nav_back()
	elif what == MainLoop.NOTIFICATION_WM_FOCUS_OUT or what == MainLoop.NOTIFICATION_WM_QUIT_REQUEST:
		if state == "play":
			_save()


func _end(title: String) -> void:
	if over:
		return
	over = true
	over_t = 0.0
	over_title = title
	_reset_fx()
	_buzz(120)
	_portal_play(false)
	if new_best and score > 0:
		_portal("happytime")
		_sfx("best")
		_confetti(70)
	else:
		_sfx("over")


func _place(slot: int, c0: int, r0: int) -> void:
	var p: Dictionary = pieces[tray[slot]]
	var m := _mine(p, c0, r0)
	var f := _lines_if(grid, m, c0, r0, p.w, p.h)
	for i in m:
		grid[i] = p.color
		place_t[i] = 0.0
	tray[slot] = -1
	var pc := Vector2(c0 + p.w / 2.0 - 0.5, r0 + p.h / 2.0 - 0.5)
	var gain: int = p.cells.size()
	var lines: int = f[0].size() + f[1].size()
	if lines > 0:
		var gone := {}
		for r in f[0]:
			for j in range(N):
				gone[r * N + j] = true
		for c in f[1]:
			for j in range(N):
				gone[j * N + c] = true
		for i in gone:
			var d := Vector2(i % N, int(i / N)).distance_to(pc)
			fx.append({"i": i, "t": -0.035 * d, "color": COLORS[grid[i]], "burst": false})
			grid[i] = 0
		combo += 1
		dry = 0
		gain += 10 * lines * lines * combo
		var msg := ""
		var empty := true
		for v in grid:
			if v != 0:
				empty = false
				break
		if empty:
			gain += 300
			msg = "CLEAN SWEEP! "
		elif lines > 1:
			msg = PRAISE[int(min(lines, 6))] + " "
		if combo > 1:
			msg += "COMBO x%d" % combo
		toast = msg.strip_edges()
		if tut < 2:
			tut = 2
			if toast == "":
				toast = "YOU GOT IT!"
		toast_t = 1.2 if toast != "" else 0.0
		shake_mag = 5.0 + 5.0 * lines
		if mode == 1:
			time_left += 2.0 * lines
		for r in f[0]:
			beams.append({"row": true, "i": r, "t": 0.0})
		for c in f[1]:
			beams.append({"row": false, "i": c, "t": 0.0})
		_sfx("big" if lines > 1 or empty else "clear", 1.0 + 0.08 * min(combo - 1, 7))
		_sfx("place", 0.8, -4.0)
		_buzz(25 + 15 * lines)
		if empty or lines >= 3:
			_confetti(50)
	else:
		dry += 1
		if dry >= 3:
			combo = 0
		if tut == 0:
			tut = 1
		_sfx("place", 0.95 + randf() * 0.15)
		_buzz(12)
	bump = 1.0
	for c in p.cells:
		if parts.size() < 260 and not m.has((r0 + int(c.y) + 1) * N + c0 + int(c.x)):
			var base := origin + Vector2(c0 + c.x + 0.5, r0 + c.y + 1.0) * cell
			for _k in range(2):
				parts.append({"p": base + Vector2((randf() - 0.5) * cell * 0.6, -4.0), "v": Vector2((randf() - 0.5) * 260.0, -60.0 - randf() * 120.0),
					"t": 0.0, "life": 0.25 + randf() * 0.2, "s": cell * (0.08 + randf() * 0.08), "c": CELL.darkened(0.15), "r": randf() * TAU, "dust": true})
	popups.append({"p": origin + (pc + Vector2(0.5, 0.5)) * cell, "s": "+%d" % gain, "t": 0.0, "big": lines > 0})
	score += gain
	score_pulse = 1.0
	if score > bests[mode]:
		bests[mode] = score
		new_best = true
	if mode == 3:
		rubble_in -= 1
		if rubble_in <= 0:
			rubble_in = 4
			_drop_stones(3)
	var all_used := true
	for i in tray:
		if i >= 0:
			all_used = false
	if all_used:
		_refill()
	if mode == 2:
		moves_left -= 1
		if moves_left <= 0:
			_end("OUT OF MOVES")
	if not over and not _can_move():
		_end("NO ROOM LEFT")
	_save()


func _drop_stones(n: int) -> void:
	var empty := []
	for i in range(N * N):
		if grid[i] == 0:
			empty.append(i)
	empty.shuffle()
	for i in empty:
		if n <= 0:
			break
		var f := _lines_if(grid, {i: STONE}, i % N, int(i / N), 1, 1)
		if f[0].size() + f[1].size() > 0:
			continue
		grid[i] = STONE
		place_t[i] = -0.12 * n
		n -= 1
	shake_mag = max(shake_mag, 7.0)
	_sfx("stone")
	get_tree().create_timer(0.14).connect("timeout", self, "_sfx", ["stone", 1.15])
	get_tree().create_timer(0.28).connect("timeout", self, "_sfx", ["stone", 0.9])
	_buzz(40)


func _confetti(n: int) -> void:
	for _k in range(n):
		if parts.size() >= 320:
			return
		var a := -PI / 2.0 + (randf() - 0.5) * 1.9
		parts.append({"p": Vector2(vs.x / 2.0 + (randf() - 0.5) * cell * 6.0, origin.y + cell * 5.0), "v": Vector2(cos(a), sin(a)) * (500.0 + randf() * 900.0),
			"t": 0.0, "life": 1.1 + randf() * 0.9, "s": cell * (0.14 + randf() * 0.14), "c": COLORS[1 + randi() % 7], "r": randf() * TAU, "conf": true})


# ---------- save ----------
func _snapshot() -> Dictionary:
	return {"grid": grid.duplicate(), "tray": tray.duplicate(), "score": score, "combo": combo, "dry": dry}


func _restore(d: Dictionary) -> bool:
	var g = d.get("grid", [])
	var t = d.get("tray", [])
	if typeof(g) != TYPE_ARRAY or g.size() != N * N or typeof(t) != TYPE_ARRAY or t.size() != 3:
		return false
	for i in range(N * N):
		grid[i] = int(clamp(int(g[i]), 0, 8))
	tray = []
	for v in t:
		tray.append(int(clamp(int(v), -1, pieces.size() - 1)))
	score = int(d.get("score", 0))
	shown = score
	combo = int(d.get("combo", 0))
	dry = int(d.get("dry", 0))
	over = false
	new_best = false
	return _can_move()


func _save() -> void:
	if mode == 0 and state == "play":
		classic_save = null if over else _snapshot()
	var f := File.new()
	if f.open(SAVE, File.WRITE) == OK:
		f.store_string(to_json({"bests": bests, "sound": sound_on, "music": music_on, "vib": vib_on, "tut": tut, "classic": classic_save, "last": last_mode}))
		f.close()


func _load() -> void:
	var f := File.new()
	if not f.file_exists(SAVE) or f.open(SAVE, File.READ) != OK:
		return
	var d = parse_json(f.get_as_text())
	f.close()
	if typeof(d) != TYPE_DICTIONARY:
		return
	sound_on = bool(d.get("sound", true))
	music_on = bool(d.get("music", true))
	vib_on = bool(d.get("vib", true))
	last_mode = int(clamp(int(d.get("last", 0)), 0, 3))
	var b = d.get("bests", [])
	if typeof(b) == TYPE_ARRAY:
		for i in range(min(4, b.size())):
			bests[i] = int(b[i])
	var played := false
	for v in bests:
		if v > 0:
			played = true
	tut = int(clamp(int(d.get("tut", 2 if played else 0)), 0, 2))   # players from before the tutorial skip it
	if typeof(d.get("classic")) == TYPE_DICTIONARY:
		classic_save = d["classic"]


# ---------- input ----------
func _slot_rect(i: int) -> Rect2:
	if compact:
		var cw := dia * 0.5 / 3.0
		return Rect2(vs.x / 2.0 - dia * 0.25 + cw * i, tray_y, cw, dia * 0.165)
	if wide:
		var side := min(origin.x - 30.0, 560.0)
		return Rect2(origin.x + cell * 8.0 + 30.0, origin.y + i * cell * 8.0 / 3.0, side, cell * 8.0 / 3.0)
	var w := cell * 8.0 / 3.0
	return Rect2(origin.x + w * i, tray_y, w, cell * 3.0)


func _buttons() -> Array:
	if state == "main":
		return ["play", "modes", "help", "settings"]
	if state == "modes":
		return ["mode0", "mode1", "mode2", "mode3", "back"]
	if state == "help":
		return ["back"]
	if state == "settings":
		return ["set_sound", "set_music", "set_vib", "set_reset", "back"]
	if over:
		return ["again", "menu"] if over_t > 1.2 else []
	return ["home", "new"]


func _hit(pos: Vector2) -> String:
	for id in _buttons():
		if rects[id].grow(8.0).has_point(pos):
			return id
	return ""


func _input(ev: InputEvent) -> void:
	if ev is InputEventScreenTouch:
		last_touch = t_now
		if ev.pressed:
			drag_touch = true
			_press(ev.index, ev.position)
		else:
			_release(ev.index, ev.position)
	elif ev is InputEventScreenDrag and ev.index == drag_idx and drag_slot >= 0:
		_move(ev.position)
	elif ev is InputEventMouseButton and ev.button_index == BUTTON_LEFT and t_now - last_touch > 0.8:
		if ev.pressed:
			if drag_idx == -1:
				drag_touch = false
				_press(99, ev.position)
		else:
			_release(99, ev.position)
	elif ev is InputEventMouseMotion and drag_idx == 99 and drag_slot >= 0:
		_move(ev.position)
	elif ev is InputEventKey and ev.pressed and not ev.echo and ev.scancode == KEY_ESCAPE:
		_nav_back()


func _press(idx: int, pos: Vector2) -> void:
	var id := _hit(pos)
	if id != "":
		press_id = id
		drag_idx = idx
		return
	if state != "play" or over or drag_slot >= 0:
		return
	for i in range(3):
		if tray[i] >= 0 and tray_t[i] > 0.0 and _slot_rect(i).has_point(pos):
			drag_slot = i
			drag_idx = idx
			var sr := _slot_rect(i)
			drag_center = sr.position + sr.size / 2.0
			drag_scale = mini
			ret = {}
			_sfx("pick")
			_move(pos)
			return


func _click(id: String) -> void:
	_sfx("click")
	if id.begins_with("mode") and id != "modes":
		_start_mode(int(id.substr(4, 1)))
	elif id == "play":
		_start_mode(last_mode)
	elif id == "modes" or id == "help" or id == "settings":
		_goto(id)
	elif id == "back":
		_goto("main")
	elif id == "set_sound":
		sound_on = not sound_on
		_save()
		_sfx("clear")
	elif id == "set_music":
		music_on = not music_on
		_music_sync()
		_save()
	elif id == "set_vib":
		vib_on = not vib_on
		_buzz(40)
		_save()
	elif id == "set_reset":
		if armed == "reset":
			bests = [0, 0, 0, 0]
			classic_save = null
			tut = 0
			armed = ""
			_save()
		else:
			armed = "reset"
			armed_t = 3.0
	elif id == "again":
		_new_game()
	elif id == "menu":
		_go_menu()
	elif id == "home":
		if mode == 0 or score == 0 or armed == "home":
			_go_menu()
		else:
			armed = "home"
			armed_t = 2.0
	elif id == "new":
		if score == 0 or armed == "new":
			_new_game()
		else:
			armed = "new"
			armed_t = 2.0


func _float_pos() -> Vector2:
	var p: Dictionary = pieces[tray[drag_slot]]
	if not drag_touch:
		return drag_pos - Vector2(p.w * cell / 2.0, p.h * cell / 2.0)   # mouse: carry the piece under the cursor
	return drag_pos - Vector2(p.w * cell / 2.0, p.h * cell + cell * 1.5)


func _move(pos: Vector2) -> void:
	drag_pos = pos
	var p: Dictionary = pieces[tray[drag_slot]]
	var tl := (_float_pos() - origin) / cell
	var c0 := int(round(tl.x))
	var r0 := int(round(tl.y))
	if _fits_g(grid, p, c0, r0):
		drag_c = c0
		drag_r = r0
	else:
		drag_c = -1
		drag_r = -1


func _release(idx: int, pos: Vector2) -> void:
	if idx != drag_idx:
		return
	drag_idx = -1
	if press_id != "":
		var id := press_id
		press_id = ""
		if _hit(pos) == id:
			_click(id)
		return
	if drag_slot < 0:
		return
	if drag_c < 0:
		_sfx("back")
	var slot := drag_slot
	var c0 := drag_c
	var r0 := drag_r
	drag_slot = -1
	drag_c = -1
	drag_r = -1
	if c0 >= 0:
		_place(slot, c0, r0)
	else:
		ret = {"slot": slot, "from": drag_center, "scale": drag_scale, "t": 0.0}


func _process(dt: float) -> void:
	dt = min(dt, 0.05)
	t_now += dt
	intro_t += dt
	menu_t += dt
	if over:
		over_t += dt
	if state == "play" and mode == 1 and not over and intro_t > 0.6:
		time_left -= dt
		if time_left <= 0.0:
			time_left = 0.0
			_end("TIME'S UP")
			_save()
	if shown < score:
		shown = min(score, shown + max(1.0, (score - shown) * 8.0 * dt))
	toast_t = max(0.0, toast_t - dt)
	armed_t = max(0.0, armed_t - dt)
	if armed_t <= 0.0:
		armed = ""
	score_pulse = max(0.0, score_pulse - dt * 3.0)
	if has_js:
		mute_poll -= dt
		if mute_poll <= 0.0:
			mute_poll = 0.5
			AudioServer.set_bus_mute(0, bool(JavaScript.eval("window.cgMuted ? true : false", true)))
	bump = max(0.0, bump - dt * 7.0)
	var kb := []
	for b in beams:
		b.t += dt
		if b.t < 0.3:
			kb.append(b)
	beams = kb
	if state == "play" and mode == 1 and not over and time_left < 10.0 and int(ceil(time_left)) != last_tick:
		last_tick = int(ceil(time_left))
		_sfx("tick", 1.0 if last_tick > 3 else 1.3)
	shake_mag *= exp(-dt * 10.0)
	shake = Vector2(randf() - 0.5, randf() - 0.5) * 2.0 * shake_mag if shake_mag > 0.3 else Vector2()
	for i in range(N * N):
		place_t[i] += dt
	for i in range(3):
		tray_t[i] += dt
	if drag_slot >= 0:
		var p: Dictionary = pieces[tray[drag_slot]]
		var target := _float_pos() + Vector2(p.w, p.h) * cell / 2.0
		drag_center = drag_center.linear_interpolate(target, 1.0 - exp(-dt * 28.0))
		drag_scale = lerp(drag_scale, 1.0, 1.0 - exp(-dt * 22.0))
	if not ret.empty():
		ret.t += dt
		if ret.t >= 0.16:
			ret = {}
	var keep := []
	for e in fx:
		e.t += dt
		if e.t >= 0.0 and not e.burst:
			e.burst = true
			if parts.size() < 260:
				var c := origin + (Vector2(e.i % N, int(e.i / N)) + Vector2(0.5, 0.5)) * cell
				for _k in range(3):
					var a := randf() * TAU
					parts.append({"p": c, "v": Vector2(cos(a), sin(a)) * (120.0 + randf() * 420.0) + Vector2(0, -180),
						"t": 0.0, "life": 0.45 + randf() * 0.45, "s": cell * (0.14 + randf() * 0.16), "c": e.color, "r": randf() * TAU})
		if e.t < 0.32:
			keep.append(e)
	fx = keep
	var keep2 := []
	for q in parts:
		q.t += dt
		q.v.y += (300.0 if q.has("dust") else (900.0 if q.has("conf") else 1500.0)) * dt
		if q.has("conf"):
			q.v.x *= 1.0 - dt * 1.5
		q.p += q.v * dt
		q.r += dt * 6.0
		if q.t < q.life:
			keep2.append(q)
	parts = keep2
	var keep3 := []
	for q in popups:
		q.t += dt
		if q.t < 0.9:
			keep3.append(q)
	popups = keep3
	update()


func _back(k: float) -> float:
	k = clamp(k, 0.0, 1.0)
	return 1.0 + 2.70158 * pow(k - 1.0, 3.0) + 1.70158 * pow(k - 1.0, 2.0)


# ---------- drawing ----------
func _rr(rect: Rect2, col: Color, radius: float) -> void:
	sb.bg_color = col
	sb.set_border_width_all(0)
	sb.set_corner_radius_all(int(radius))
	sb.corner_detail = 5
	draw_style_box(sb, rect)


func _box(rect: Rect2, col: Color, radius: float, border: float, bcol: Color) -> void:
	sb.bg_color = col
	sb.border_color = bcol
	sb.set_border_width_all(int(max(1.0, border)))
	sb.set_corner_radius_all(int(radius))
	sb.corner_detail = 5
	draw_style_box(sb, rect)


# A flat, ink-outlined tile with a darker lip along the bottom.
func _block(pos: Vector2, size: float, col: Color, alpha := 1.0) -> void:
	var g := size * 0.035
	var s := size - g * 2.0
	var b := max(2.0, floor(s * 0.065))
	var r := Rect2(pos + Vector2(g, g), Vector2(s, s))
	_box(r, Color(col.r * 0.72, col.g * 0.72, col.b * 0.72, alpha), s * 0.17, b, Color(INK.r, INK.g, INK.b, alpha))
	_rr(Rect2(r.position + Vector2(b, b), Vector2(s - b * 2.0, s - b * 2.0 - s * 0.11)), Color(col.r, col.g, col.b, alpha), s * 0.1)
	_rr(Rect2(r.position + Vector2(b + s * 0.09, b + s * 0.08), Vector2(s * 0.2, s * 0.09)), Color(1, 1, 1, 0.45 * alpha), s * 0.04)


func _blockc(pos: Vector2, size: float, col: Color, alpha: float, scale: float) -> void:
	if scale <= 0.02:
		return
	var s := size * scale
	_block(pos + Vector2(size - s, size - s) / 2.0, s, col, alpha)


func _piece(center: Vector2, p: Dictionary, size: float, alpha: float) -> void:
	var tl := center - Vector2(p.w, p.h) * size / 2.0
	for c in p.cells:
		_block(tl + c * size, size, COLORS[p.color], alpha)


func _text(t: String, center: Vector2, size: int, col: Color, outline := 0) -> void:
	var f := _font(size, outline)
	var w := f.get_string_size(t).x
	draw_string(f, Vector2(center.x - w / 2.0, center.y + size * 0.34), t, col)


func _textl(t: String, pos: Vector2, size: int, col: Color) -> void:
	draw_string(_font(size), Vector2(pos.x, pos.y + size * 0.34), t, col)


func _textr(t: String, pos: Vector2, size: int, col: Color) -> void:
	var f := _font(size)
	draw_string(f, Vector2(pos.x - f.get_string_size(t).x, pos.y + size * 0.34), t, col)


func _reset_xf() -> void:
	draw_set_transform(Vector2(), 0.0, Vector2.ONE)


# Chunky button: ink shadow below, body sinks onto it while held.
func _button(id: String, fill: Color, radius: float, scale := 1.0, offset := Vector2()) -> Vector2:
	var r: Rect2 = rects[id]
	var depth := min(8.0, r.size.y * 0.1)
	var lift := 0.0 if press_id == id else depth
	var c := r.position + r.size / 2.0 + offset
	draw_set_transform(c, 0.0, Vector2.ONE * scale)
	var half := r.size / 2.0
	_rr(Rect2(-half + Vector2(0, depth), r.size), INK, radius)
	_box(Rect2(-half + Vector2(0, depth - lift), r.size), fill, radius, max(3.0, min(6.0, r.size.y * 0.045)), INK)
	draw_set_transform(c + Vector2(0, depth - lift) * scale, 0.0, Vector2.ONE * scale)
	return r.size


func _draw() -> void:
	draw_rect(Rect2(Vector2(), vs), BG)
	var off := fmod(t_now * 14.0, 180.0)
	var k := -2
	while k * 180.0 - 200.0 < vs.x + vs.y * 0.4:
		var x0 := k * 180.0 + off
		draw_colored_polygon(PoolVector2Array([Vector2(x0, 0), Vector2(x0 + 80.0, 0), Vector2(x0 + 80.0 - vs.y * 0.4, vs.y), Vector2(x0 - vs.y * 0.4, vs.y)]), BG2)
		k += 1
	if state == "main":
		_draw_main()
	elif state == "modes":
		_draw_modes()
	elif state == "help":
		_draw_help()
	elif state == "settings":
		_draw_settings()
	else:
		_draw_hud()
		_draw_board()
	_reset_xf()


func _draw_title(ty: float) -> void:
	var cx := vs.x / 2.0
	var wob := sin(t_now * 1.6) * 0.025
	var pop := _back(menu_t / 0.4)
	if compact:
		var ts := int(dia * 0.075)
		draw_set_transform(Vector2(cx, ty), wob, Vector2.ONE * pop)
		_text("BLOCKY PUZZLE", Vector2(), ts, CREAM, int(ts * 0.09))
	else:
		draw_set_transform(Vector2(cx, ty - 60.0), -0.04 + wob, Vector2.ONE * pop)
		_text("BLOCKY", Vector2(), 128, CREAM, 10)
		draw_set_transform(Vector2(cx, ty + 66.0), 0.03 - wob, Vector2.ONE * _back((menu_t - 0.08) / 0.4))
		_text("PUZZLE", Vector2(), 128, GOLD, 10)
		draw_set_transform(Vector2(cx - 292.0, ty - 138.0 + sin(t_now * 2.0) * 10.0), -0.35 + wob * 3.0, Vector2.ONE * pop)
		_piece(Vector2(), pieces[26 % pieces.size()], 30.0, 1.0)
		draw_set_transform(Vector2(cx + 296.0, ty + 140.0 + cos(t_now * 1.7) * 10.0), 0.3 - wob * 3.0, Vector2.ONE * pop)
		_piece(Vector2(), pieces[12 % pieces.size()], 30.0, 1.0)
	_reset_xf()


func _draw_main() -> void:
	var cx := vs.x / 2.0
	var has_save: bool = last_mode == 0 and typeof(classic_save) == TYPE_DICTIONARY
	var sub := "%s  -  continue %d" % [MODES[0].name, int(classic_save.get("score", 0))] if has_save else "%s  -  best %d" % [MODES[last_mode].name, bests[last_mode]]
	if compact:
		_draw_title(head_y + dia * 0.18)
		var ps := _button("play", COLORS[4], dia * 0.04, (1.0 + 0.025 * sin(t_now * 4.0)) * _back((menu_t - 0.1) / 0.35))
		_text("PLAY", Vector2(0, -ps.y * 0.1), int(dia * 0.07), INK)
		_text(MODES[last_mode].name, Vector2(0, ps.y * 0.28), int(dia * 0.026), INK)
		var labels := {"modes": "MODES", "help": "HELP", "settings": "SETUP"}
		var n := 0
		for id in ["modes", "help", "settings"]:
			_button(id, CREAM, dia * 0.03, _back((menu_t - 0.2 - n * 0.06) / 0.35))
			_text(labels[id], Vector2(), int(dia * 0.034), INK)
			n += 1
		_reset_xf()
		return
	var py: float = rects["play"].position.y
	_draw_title(max(170.0, py * 0.5))
	# a little row of tiles marching under the title
	for i in range(7):
		var bx := cx - 3.5 * 62.0 + i * 62.0
		var hop := max(0.0, sin(t_now * 3.0 - i * 0.6)) * 14.0
		_blockc(Vector2(bx, py - 108.0 - hop), 58.0, COLORS[1 + i], 1.0, _back((menu_t - 0.2 - i * 0.04) / 0.3))
	var ps2 := _button("play", COLORS[4], 30.0, (1.0 + 0.02 * sin(t_now * 4.0)) * _back((menu_t - 0.15) / 0.35))
	_text("PLAY", Vector2(0, -16.0), 72, INK)
	_text(sub, Vector2(0, 38.0), 30 if wide else 24, Color(INK.r, INK.g, INK.b, 0.75))
	var names := {"modes": "GAME MODES", "help": "HOW TO PLAY", "settings": "SETTINGS"}
	var k := 0
	for id in ["modes", "help", "settings"]:
		var slide := (1.0 - _back((menu_t - 0.25 - k * 0.07) / 0.4)) * vs.x
		_button(id, CREAM, 999.0, 1.0, Vector2(slide if k % 2 == 0 else -slide, 0))
		_text(names[id], Vector2(), 38, INK)
		k += 1
	_reset_xf()
	_text("v1.11", Vector2(cx, vs.y - 34.0), 20, Color(CREAM.r, CREAM.g, CREAM.b, 0.45))


func _draw_sub_head(title: String) -> void:
	var cx := vs.x / 2.0
	if compact:
		draw_set_transform(Vector2(cx, head_y + dia * 0.16), 0.0, Vector2.ONE * _back(menu_t / 0.35))
		_text(title, Vector2(), int(dia * 0.065), CREAM, int(dia * 0.006))
		_button("back", CREAM, 999.0, _back((menu_t - 0.3) / 0.35))
		_text("BACK", Vector2(), int(dia * 0.036), INK)
	else:
		var br: Rect2 = rects["back"]
		var u := _button("back", CREAM, 18.0).x / 76.0
		draw_colored_polygon(PoolVector2Array([Vector2(-20, 0) * u, Vector2(4, -20) * u, Vector2(4, -8) * u, Vector2(20, -8) * u, Vector2(20, 8) * u, Vector2(4, 8) * u, Vector2(4, 20) * u]), INK)
		draw_set_transform(Vector2(cx + 20.0, br.position.y + 42.0), -0.02, Vector2.ONE * _back(menu_t / 0.35))
		_text(title, Vector2(), 64, CREAM, 7)
	_reset_xf()


func _draw_modes() -> void:
	_draw_sub_head("GAME MODES")
	for i in range(4):
		var id := "mode%d" % i
		var m: Dictionary = MODES[i]
		var slide := (1.0 - _back((menu_t - 0.05 - i * 0.07) / 0.4)) * vs.x
		var size := _button(id, CREAM, dia * 0.03 if compact else 22.0, 1.0, Vector2(slide, 0))
		var has_save: bool = i == 0 and typeof(classic_save) == TYPE_DICTIONARY
		if compact:
			_text(m.name, Vector2(0, -size.y * 0.14), int(dia * 0.042), INK)
			_text("BEST %d" % bests[i], Vector2(0, size.y * 0.22), int(dia * 0.026), MUTED)
		else:
			_block(Vector2(-size.x / 2.0 + 22.0, -42.0), 84.0, COLORS[m.c])
			_textl(m.name, Vector2(-size.x / 2.0 + 128.0, -22.0), 44, INK)
			_textl("Continue - %d pts" % int(classic_save.get("score", 0)) if has_save else m.desc, Vector2(-size.x / 2.0 + 128.0, 28.0), 34 if wide else 23, MUTED)
			_textr("BEST", Vector2(size.x / 2.0 - 24.0, -28.0), 28 if wide else 20, MUTED)
			_textr(str(bests[i]), Vector2(size.x / 2.0 - 24.0, 12.0), 38, INK)
	_reset_xf()


func _panel(r: Rect2, k: float) -> void:
	draw_set_transform(r.position + r.size / 2.0, 0.0, Vector2.ONE * _back(k))
	_rr(Rect2(-r.size / 2.0 + Vector2(0, 8), r.size), INK, 22.0)
	_box(Rect2(-r.size / 2.0, r.size), CREAM, 22.0, 5.0, INK)
	draw_set_transform(r.position + r.size / 2.0, 0.0, Vector2.ONE * _back(k))


func _draw_help() -> void:
	_draw_sub_head("HOW TO PLAY")
	var lines := [
		[3, "Drag a piece from the tray", "onto the board."],
		[5, "Fill a whole row or column", "and it clears."],
		[1, "Clear on back-to-back moves", "to build a combo."],
		[6, "Pieces never rotate. Out of", "room means game over."],
	]
	if compact:
		for i in range(4):
			var y: float = head_y + dia * (0.3 + i * 0.09)
			_text(lines[i][1] + " " + lines[i][2], Vector2(vs.x / 2.0, y), int(dia * 0.028), CREAM)
		return
	for i in range(4):
		var r: Rect2 = rects["mode%d" % i]
		_panel(r, (menu_t - 0.05 - i * 0.07) / 0.35)
		var hop := max(0.0, sin(t_now * 3.0 - i * 0.8)) * 6.0
		_block(Vector2(-r.size.x / 2.0 + 22.0, -42.0 - hop), 84.0, COLORS[lines[i][0]])
		_text(str(i + 1), Vector2(-r.size.x / 2.0 + 64.0, -4.0 - hop), 44, INK)
		_textl(lines[i][1], Vector2(-r.size.x / 2.0 + 128.0, -20.0), 32, INK)
		_textl(lines[i][2], Vector2(-r.size.x / 2.0 + 128.0, 22.0), 32, INK)
	_reset_xf()


func _draw_settings() -> void:
	_draw_sub_head("SETTINGS")
	var rows := [
		["set_sound", "SOUND", "Clicks, thuds and chimes", sound_on],
		["set_music", "MUSIC", "Background tune", music_on],
		["set_vib", "VIBRATION", "A little buzz on moves", vib_on],
	]
	if not compact:
		for i in range(4):
			var r: Rect2 = rects["mode%d" % i]
			_panel(r, (menu_t - 0.05 - i * 0.07) / 0.35)
			_textl(rows[i][1] if i < 3 else "BEST SCORES", Vector2(-r.size.x / 2.0 + 28.0, -22.0), 40, INK)
			_textl(rows[i][2] if i < 3 else "Wipe every mode's record", Vector2(-r.size.x / 2.0 + 28.0, 26.0), 34 if wide else 23, MUTED)
		_reset_xf()
	var k := _back((menu_t - 0.2) / 0.3)
	for row in rows:
		var sz := _button(row[0], GOLD if row[3] else CELL, 999.0, k)
		_text((row[1] + (" ON" if row[3] else " OFF")) if compact else ("ON" if row[3] else "OFF"), Vector2(), int(sz.y * 0.44), INK)
	var s2 := _button("set_reset", COLORS[1] if armed == "reset" else CREAM, 999.0, k)
	_text("SURE?" if armed == "reset" else ("RESET SCORES" if compact else "RESET"), Vector2(), int(s2.y * 0.4), INK)
	_reset_xf()
	if compact:
		_text("Made by sehrn.xyz", Vector2(vs.x / 2.0, head_y + dia * 0.81), int(dia * 0.032), GOLD)
	else:
		var r3: Rect2 = rects["mode3"]
		draw_set_transform(Vector2(vs.x / 2.0, r3.position.y + r3.size.y + 58.0), -0.015, Vector2.ONE * _back((menu_t - 0.35) / 0.35))
		_text("Made by sehrn.xyz", Vector2(), 46 if wide else 40, GOLD, 6)
		_reset_xf()
		_text("Built with Godot Engine  -  Typeface: Lilita One (OFL)", Vector2(vs.x / 2.0, r3.position.y + r3.size.y + 112.0), 30 if wide else 20, Color(CREAM.r, CREAM.g, CREAM.b, 0.55))


# First-run coaching, shown instead of written instructions: a hand drags a real piece to a real
# spot, then the row or column nearest to full gets a pulsing outline.
func _draw_coach(o: Vector2, bw: float) -> void:
	var fsz := int(max(18.0, cell * 0.42))
	var pulse := 0.5 + 0.5 * sin(t_now * 5.0)
	if tut == 0:
		var slot := -1
		for i in range(3):
			if tray[i] >= 0 and tray_t[i] > 0.35 and _fits_anywhere(pieces[tray[i]]):
				slot = i
				break
		if slot < 0:
			return
		var p: Dictionary = pieces[tray[slot]]
		var best_d := 1e9
		var tc := -1
		var tr := -1
		for r in range(N - p.h + 1):
			for c in range(N - p.w + 1):
				if _fits_g(grid, p, c, r):
					var d := Vector2(c + p.w / 2.0 - 4.0, r + p.h / 2.0 - 4.5).length()
					if d < best_d:
						best_d = d
						tc = c
						tr = r
		if tc < 0:
			return
		for c in p.cells:
			_blockc(o + Vector2(tc + c.x, tr + c.y) * cell, cell, COLORS[p.color], 0.22 + 0.16 * pulse, 0.94)
		var sr := _slot_rect(slot)
		var from := sr.position + sr.size / 2.0
		var to := o + Vector2(tc + p.w / 2.0, tr + p.h / 2.0) * cell
		var ph := fmod(t_now, 2.0) / 2.0
		var k: float = clamp((ph - 0.15) / 0.5, 0.0, 1.0)
		k = k * k * (3.0 - 2.0 * k)
		var a: float = clamp(ph / 0.1, 0.0, 1.0) * clamp((1.0 - ph) / 0.15, 0.0, 1.0)
		var at := from.linear_interpolate(to, k)
		var sz: float = cell * lerp(mini, 1.0, k)
		_piece(at, p, sz, 0.85 * a)
		# the hand
		var h := at + Vector2(sz * 0.2, p.h * sz / 2.0 + cell * 0.25)
		var hr := cell * 0.24
		draw_set_transform(h, -0.35, Vector2.ONE)
		_box(Rect2(-hr * 0.42, -hr * 2.2, hr * 0.84, hr * 2.4), Color(CREAM.r, CREAM.g, CREAM.b, a), hr * 0.42, 4.0, Color(INK.r, INK.g, INK.b, a))
		_box(Rect2(-hr, -hr * 0.6, hr * 2.0, hr * 2.0), Color(CREAM.r, CREAM.g, CREAM.b, a), hr * 0.7, 4.0, Color(INK.r, INK.g, INK.b, a))
		_reset_xf()
		_text("DRAG A PIECE ONTO THE BOARD", Vector2(vs.x / 2.0, o.y + bw - cell * 0.55), fsz, Color(CREAM.r, CREAM.g, CREAM.b, 0.75 + 0.25 * pulse), int(fsz * 0.2))
	else:
		var best_n := -1
		var is_row := true
		var idx := 0
		for i in range(N):
			var nr := 0
			var nc := 0
			for j in range(N):
				if grid[i * N + j] != 0:
					nr += 1
				if grid[j * N + i] != 0:
					nc += 1
			if nr > best_n:
				best_n = nr
				is_row = true
				idx = i
			if nc > best_n:
				best_n = nc
				is_row = false
				idx = i
		var rect := Rect2(o.x, o.y + idx * cell, bw, cell) if is_row else Rect2(o.x + idx * cell, o.y, cell, bw)
		sb.bg_color = Color(GOLD.r, GOLD.g, GOLD.b, 0.10 + 0.12 * pulse)
		sb.border_color = Color(GOLD.r, GOLD.g, GOLD.b, 0.6 + 0.4 * pulse)
		sb.set_border_width_all(int(max(4.0, cell * 0.08)))
		sb.set_corner_radius_all(int(cell * 0.2))
		draw_style_box(sb, rect.grow(2.0))
		var ty: float = o.y + bw - cell * 0.55 if (not is_row or idx < 6) else o.y + cell * 0.55
		_text("FILL A LINE TO CLEAR IT", Vector2(vs.x / 2.0, ty), fsz, Color(CREAM.r, CREAM.g, CREAM.b, 0.75 + 0.25 * pulse), int(fsz * 0.2))


func _info() -> String:
	if mode == 1:
		return "%d:%02d" % [int(ceil(time_left)) / 60, int(ceil(time_left)) % 60]
	if mode == 2:
		return "%d MOVES LEFT" % moves_left
	if mode == 3:
		return "STONES IN %d" % rubble_in
	return "BEST %d" % bests[0]


func _draw_hud() -> void:
	var cx := vs.x / 2.0
	var pulse := 1.0 + 0.22 * score_pulse * score_pulse
	var warn := mode == 1 and time_left < 10.0 and not over
	var icol: Color = COLORS[1].linear_interpolate(CREAM, 0.5 + 0.5 * sin(t_now * 12.0)) if warn else GOLD
	if compact:
		draw_set_transform(Vector2(cx, head_y + dia * 0.07), 0.0, Vector2.ONE * pulse)
		_text(str(int(shown)), Vector2(), int(dia * 0.07), CREAM, int(dia * 0.006))
		_reset_xf()
		_text(_info(), Vector2(cx, head_y + dia * 0.125), int(dia * 0.032), icol)
	elif wide:
		var bwl := cell * 8.0
		var side := min(origin.x - 30.0, 560.0)
		var lx := origin.x - 30.0 - side / 2.0
		_text(MODES[mode].name, Vector2(lx, origin.y + 40.0), 44, Color(CREAM.r, CREAM.g, CREAM.b, 0.7))
		draw_set_transform(Vector2(lx, origin.y + 170.0), 0.0, Vector2.ONE * pulse)
		_text(str(int(shown)), Vector2(), 150, CREAM, 10)
		_reset_xf()
		_text(_info(), Vector2(lx, origin.y + 300.0), 60 if mode == 1 else 46, icol)
		if mode == 1:
			var tw := min(side - 60.0, 400.0)
			_box(Rect2(lx - tw / 2.0, origin.y + 350.0, tw, 20.0), INK, 10.0, 4.0, INK)
			var w2 := (tw - 8.0) * clamp(time_left / 120.0, 0.0, 1.0)
			if w2 > 8.0:
				_rr(Rect2(lx - tw / 2.0 + 4.0, origin.y + 354.0, w2, 12.0), icol, 6.0)
		if mode != 0:
			_text("BEST %d" % bests[mode], Vector2(lx, origin.y + (420.0 if mode == 1 else 370.0)), 36, Color(CREAM.r, CREAM.g, CREAM.b, 0.7))
	else:
		draw_set_transform(Vector2(cx, head_y + 62.0), 0.0, Vector2.ONE * pulse)
		_text(str(int(shown)), Vector2(), 92, CREAM, 7)
		_reset_xf()
		_text(_info(), Vector2(cx, head_y + 136.0), 34 if mode == 1 else 28, icol)
		if mode == 1:
			var bw := cell * 8.0
			_box(Rect2(origin.x, head_y + 160.0, bw, 14.0), INK, 7.0, 3.0, INK)
			var w := (bw - 6.0) * clamp(time_left / 120.0, 0.0, 1.0)
			if w > 6.0:
				_rr(Rect2(origin.x + 3.0, head_y + 163.0, w, 8.0), icol, 4.0)
	var hs := _button("home", GOLD if armed == "home" else CREAM, 18.0)
	var u := hs.x / 76.0
	if armed == "home":
		_text("?", Vector2(), int(44 * u), INK)
	else:
		draw_colored_polygon(PoolVector2Array([Vector2(0, -20) * u, Vector2(22, 0) * u, Vector2(14, 0) * u, Vector2(14, 18) * u, Vector2(-14, 18) * u, Vector2(-14, 0) * u, Vector2(-22, 0) * u]), INK)
	_button("new", GOLD if armed == "new" else CREAM, 18.0)
	if armed == "new":
		_text("?", Vector2(), int(44 * u), INK)
	else:
		draw_arc(Vector2(), 15.0 * u, -1.2, 3.9, 20, INK, 5.5 * u, true)
		var a := Vector2(15.0 * cos(-1.2), 15.0 * sin(-1.2)) * u
		draw_colored_polygon(PoolVector2Array([a + Vector2(-11, -10) * u, a + Vector2(9, -2) * u, a + Vector2(-7, 10) * u]), INK)
	_reset_xf()


func _draw_board() -> void:
	var bw := cell * 8.0
	var ks := cell / 85.0 if wide else 1.0
	var o := origin + shake + Vector2(0, sin(bump * PI) * 5.0)
	_rr(Rect2(o - Vector2(10, 0), Vector2(bw + 20, bw + 22)), INK, 20.0)
	_box(Rect2(o - Vector2(10, 10), Vector2(bw + 20, bw + 20)), CREAM, 20.0, 5.0, INK)
	var ghost := {}
	var will := {}
	if drag_slot >= 0 and drag_c >= 0:
		var p: Dictionary = pieces[tray[drag_slot]]
		ghost = _mine(p, drag_c, drag_r)
		var f := _lines_if(grid, ghost, drag_c, drag_r, p.w, p.h)
		for r in f[0]:
			for j in range(N):
				will[r * N + j] = true
		for c in f[1]:
			for j in range(N):
				will[j * N + c] = true
	var pending := {}
	for e in fx:
		if e.t < 0.0:
			pending[e.i] = e.color
	var glow := 0.5 + 0.5 * sin(t_now * 12.0)
	for i in range(N * N):
		var c := i % N
		var r := int(i / N)
		var pos := o + Vector2(c, r) * cell
		var k_in := _back((intro_t - (c + r) * 0.03) / 0.3) if intro_t < 0.8 else 1.0
		var g := cell * 0.05
		var es := (cell - g * 2.0) * max(0.0, k_in)
		_rr(Rect2(pos + Vector2(cell - es, cell - es) / 2.0, Vector2(es, es)), CELL, es * 0.16)
		if will.has(i):
			_blockc(pos, cell, GOLD.linear_interpolate(Color.white, 0.4 + 0.6 * glow), 1.0, 1.0 + 0.04 * glow)
		elif pending.has(i):
			_block(pos, cell, pending[i])
		elif grid[i] != 0:
			if place_t[i] < 0.0:
				if place_t[i] > -0.1:
					_blockc(pos + Vector2(0, place_t[i] * 2400.0), cell, COLORS[grid[i]], 1.0 + place_t[i] * 6.0, 1.0)
				continue
			var col: Color = COLORS[grid[i]]
			if over:
				var gk := clamp((over_t - r * 0.07) / 0.25, 0.0, 1.0)
				var gray := col.r * 0.3 + col.g * 0.5 + col.b * 0.2
				col = col.linear_interpolate(Color(gray * 0.8, gray * 0.78, gray * 0.7), gk)
			var sc := 1.0
			if place_t[i] < 0.25:
				sc = 0.72 + 0.28 * _back(place_t[i] / 0.25)
			_blockc(pos, cell, col, 1.0, sc * max(0.0, k_in))
		elif ghost.has(i):
			_blockc(pos, cell, COLORS[ghost[i]], 0.38 + 0.1 * glow, 0.94)
	for e in fx:
		if e.t < 0.0:
			continue
		var k: float = e.t / 0.32
		var pos2 := o + Vector2(e.i % N, int(e.i / N)) * cell
		_blockc(pos2, cell, Color.white.linear_interpolate(e.color, k), 1.0 - k * k, (1.0 + 0.35 * sin(k * PI)) * (1.0 - k * k))
	for b in beams:
		var k: float = b.t / 0.3
		var grow := cell * (0.5 + 0.9 * k)
		var colb := Color(1.0, 0.97, 0.8, (1.0 - k) * (1.0 - k) * 0.85)
		var mid: float = (b.i + 0.5) * cell
		if b.row:
			_rr(Rect2(o.x - 8.0, o.y + mid - grow / 2.0, bw + 16.0, grow), colb, grow / 2.0)
		else:
			_rr(Rect2(o.x + mid - grow / 2.0, o.y - 8.0, grow, bw + 16.0), colb, grow / 2.0)
	for q in parts:
		var a: float = 1.0 - q.t / q.life
		var s2: float = q.s * (0.5 + 0.5 * a)
		draw_set_transform(q.p + shake, q.r, Vector2(1.0, abs(sin(q.r * 1.3)) * 0.8 + 0.2) if q.has("conf") else Vector2.ONE)
		if q.has("dust"):
			_rr(Rect2(-s2 / 2.0, -s2 / 2.0, s2, s2), Color(q.c.r, q.c.g, q.c.b, a * 0.8), s2 / 2.0)
		else:
			_box(Rect2(-s2 / 2.0, -s2 / 2.0, s2, s2), q.c, s2 * 0.2, 2.0, INK)
	_reset_xf()
	if combo > 1 and not over:
		var cb := origin + Vector2(bw - cell * 0.2, -cell * 0.1)
		draw_set_transform(cb, 0.12 + sin(t_now * 6.0) * 0.05, Vector2.ONE * (1.0 + 0.3 * score_pulse + 0.05 * sin(t_now * 9.0)))
		var rad := cell * 0.62
		_rr(Rect2(-rad, -rad + 6.0, rad * 2.0, rad * 2.0), INK, rad)
		_box(Rect2(-rad, -rad, rad * 2.0, rad * 2.0), COLORS[1].linear_interpolate(GOLD, clamp((3.0 - dry) / 3.0, 0.0, 1.0)), rad, 5.0, INK)
		_text("x%d" % combo, Vector2(0, -2.0), int(cell * 0.56), INK)
		_reset_xf()
	if mode == 1 and time_left < 10.0 and not over:
		var va := 0.16 * (0.5 + 0.5 * sin(t_now * 12.0))
		var red := Color(COLORS[1].r, COLORS[1].g, COLORS[1].b, va)
		draw_rect(Rect2(0, 0, vs.x, 26.0), red)
		draw_rect(Rect2(0, vs.y - 26.0, vs.x, 26.0), red)
		draw_rect(Rect2(0, 26.0, 26.0, vs.y - 52.0), red)
		draw_rect(Rect2(vs.x - 26.0, 26.0, 26.0, vs.y - 52.0), red)
	for i in range(3):
		if tray[i] < 0 or i == drag_slot or (not ret.empty() and ret.slot == i) or tray_t[i] <= 0.0:
			continue
		var p: Dictionary = pieces[tray[i]]
		var r := _slot_rect(i)
		var ok := _fits_anywhere(p)
		var sc2 := _back(tray_t[i] / 0.35) if tray_t[i] < 0.35 else 1.0
		var bob := sin(t_now * 2.2 + i * 1.7) * cell * 0.05 if ok and not over else 0.0
		_piece(r.position + r.size / 2.0 + Vector2(0, bob), p, cell * mini * sc2, 1.0 if ok else 0.3)
	if not ret.empty() and tray[ret.slot] >= 0:
		var p: Dictionary = pieces[tray[ret.slot]]
		var r := _slot_rect(ret.slot)
		var k: float = ret.t / 0.16
		k = 1.0 - (1.0 - k) * (1.0 - k)
		_piece(ret.from.linear_interpolate(r.position + r.size / 2.0, k), p, cell * lerp(ret.scale, mini, k), 0.95)
	if drag_slot >= 0:
		var p: Dictionary = pieces[tray[drag_slot]]
		var tl := drag_center - Vector2(p.w, p.h) * cell * drag_scale / 2.0
		for c in p.cells:
			var g2 := cell * drag_scale
			_rr(Rect2(tl + c * g2 + Vector2(g2 * 0.04, g2 * 0.16), Vector2(g2 * 0.92, g2 * 0.92)), Color(INK.r, INK.g, INK.b, 0.35), g2 * 0.17)
		_piece(drag_center, p, cell * drag_scale, 1.0)
	if tut < 2 and not over and drag_slot < 0 and intro_t > 0.7:
		_draw_coach(o, bw)
	for q in popups:
		var k: float = q.t / 0.9
		var a: float = clamp((1.0 - k) * 2.5, 0.0, 1.0)
		var pp: Vector2 = q.p + Vector2(0, -cell * 1.2 * (1.0 - (1.0 - k) * (1.0 - k)))
		draw_set_transform(pp, 0.0, Vector2.ONE * _back(q.t / 0.25))
		_text(q.s, Vector2(), int((50 if q.big else 34) * ks), Color(GOLD.r, GOLD.g, GOLD.b, a) if q.big else Color(CREAM.r, CREAM.g, CREAM.b, a), 5)
	_reset_xf()
	if toast_t > 0.0:
		var age := 1.2 - toast_t
		var a := clamp(toast_t * 3.0, 0.0, 1.0)
		draw_set_transform(Vector2(vs.x / 2.0, origin.y + bw * 0.4 - age * 30.0), -0.06 + sin(age * 9.0) * 0.03, Vector2.ONE * _back(age / 0.3))
		_text(toast, Vector2(), int(64 * ks), Color(CREAM.r, CREAM.g, CREAM.b, a), 8)
		_reset_xf()
	if over:
		var a := clamp((over_t - 0.8) / 0.35, 0.0, 1.0)
		if a <= 0.0:
			return
		_rr(Rect2(origin - Vector2(5, 5), Vector2(bw + 10, bw + 10)), Color(CREAM.r, CREAM.g, CREAM.b, 0.93 * a), 15.0)
		var cx := vs.x / 2.0
		var dy := (1.0 - _back(a)) * 60.0
		var ink := Color(INK.r, INK.g, INK.b, a)
		draw_set_transform(Vector2(cx, origin.y + bw * 0.16 + dy), -0.03, Vector2.ONE)
		_text(over_title, Vector2(), int(62 * ks), Color(COLORS[1].r, COLORS[1].g, COLORS[1].b, a), 0)
		_reset_xf()
		_text(MODES[mode].name + " SCORE", Vector2(cx, origin.y + bw * 0.28 + dy), int(26 * ks), Color(MUTED.r, MUTED.g, MUTED.b, a))
		_text(str(score), Vector2(cx, origin.y + bw * 0.4 + dy), int(104 * ks), ink)
		_text("NEW BEST!" if new_best and score > 0 else "BEST %d" % bests[mode], Vector2(cx, origin.y + bw * 0.53 + dy), int(32 * ks), Color(0.85, 0.5, 0.05, a) if new_best else Color(MUTED.r, MUTED.g, MUTED.b, a))
		if over_t > 1.0:
			_button("again", COLORS[4], 999.0, (1.0 + 0.03 * sin(t_now * 5.0)) * _back((over_t - 1.0) / 0.3))
			_text("PLAY AGAIN", Vector2(), int(42 * ks), INK)
			_button("menu", CREAM, 999.0, _back((over_t - 1.1) / 0.3))
			_text("MENU", Vector2(), int(32 * ks), INK)
			_reset_xf()


# ---------- self test (BP_TEST=dir, BP_MODE=0..3) ----------
func _shot(name: String) -> void:
	yield(VisualServer, "frame_post_draw")
	var img := get_viewport().get_texture().get_data()
	img.flip_y()
	img.save_png(OS.get_environment("BP_TEST") + "/" + name)


func _tap(pos: Vector2, down: bool) -> void:
	var k: float = get_viewport().get_visible_rect().size.x / OS.window_size.x
	var e := InputEventScreenTouch.new()
	e.index = 0
	e.pressed = down
	e.position = pos / k
	Input.parse_input_event(e)


func _selftest() -> void:
	var m := int(OS.get_environment("BP_MODE"))
	yield(get_tree().create_timer(1.2), "timeout")
	yield(_shot("menu.png"), "completed")
	for scr in ["help", "settings", "modes"]:
		var sr: Rect2 = rects[scr]
		_tap(sr.position + sr.size / 2.0, true)
		yield(get_tree(), "idle_frame")
		yield(get_tree(), "idle_frame")
		_tap(sr.position + sr.size / 2.0, false)
		yield(get_tree().create_timer(1.0), "timeout")
		print("screen=", state)
		yield(_shot(scr + ".png"), "completed")
		if scr != "modes":
			var bk: Rect2 = rects["back"]
			_tap(bk.position + bk.size / 2.0, true)
			yield(get_tree(), "idle_frame")
			yield(get_tree(), "idle_frame")
			_tap(bk.position + bk.size / 2.0, false)
			yield(get_tree().create_timer(0.3), "timeout")
	var mr: Rect2 = rects["mode%d" % m]
	_tap(mr.position + mr.size / 2.0, true)
	yield(get_tree(), "idle_frame")
	yield(get_tree(), "idle_frame")
	_tap(mr.position + mr.size / 2.0, false)
	yield(get_tree().create_timer(1.0), "timeout")
	print("state=", state, " mode=", mode, " tut=", tut)
	yield(get_tree().create_timer(1.35), "timeout")
	yield(_shot("coach0.png"), "completed")
	var moves := 0
	var lastcombo := 0
	var shotc := false
	while not over and moves < 300:
		var opts := []
		for s in range(3):
			if tray[s] < 0:
				continue
			var p: Dictionary = pieces[tray[s]]
			for r in range(N - p.h + 1):
				for c in range(N - p.w + 1):
					if _fits_g(grid, p, c, r):
						opts.append([s, c, r])
		if opts.empty():
			break
		var o: Array = opts[randi() % opts.size()]
		if tray_t[o[0]] < 0.05:
			yield(get_tree().create_timer(0.3), "timeout")
		var p2: Dictionary = pieces[tray[o[0]]]
		var before := score
		var r0 := _slot_rect(o[0])
		var target := origin + Vector2(o[1], o[2]) * cell + Vector2(p2.w * cell / 2.0, p2.h * cell + cell * 1.5)
		_tap(r0.position + r0.size / 2.0, true)
		var k: float = get_viewport().get_visible_rect().size.x / OS.window_size.x
		var e2 := InputEventScreenDrag.new()
		e2.index = 0
		e2.position = target / k
		Input.parse_input_event(e2)
		yield(get_tree(), "idle_frame")
		yield(get_tree(), "idle_frame")
		if moves == 5:
			yield(_shot("play.png"), "completed")
		if moves == 1 and tut == 1:
			yield(get_tree().create_timer(0.5), "timeout")
			yield(_shot("coach1.png"), "completed")
		_tap(target, false)
		yield(get_tree(), "idle_frame")
		yield(get_tree(), "idle_frame")
		if score <= before and not over:
			print("MOVE FAILED ", o)
		if lastcombo != combo and combo > 0 and not shotc and moves > 5:
			shotc = true
			yield(get_tree().create_timer(0.12), "timeout")
			yield(_shot("clear.png"), "completed")
		lastcombo = combo
		moves += 1
	print("tut after game=", tut)
	print("selftest mode=", mode, " moves=", moves, " score=", score, " over=", over, " title=", over_title)
	yield(get_tree().create_timer(2.0), "timeout")
	yield(_shot("over.png"), "completed")
	get_tree().quit()
