"""Blocky Puzzle theme, second version: 32 bars at 96 BPM (80 s), stereo, seamless loop. All synthesized.

Form: A (8 bars) - A' (8) - B (8) - A'' (8).   Run: python3 gen_music2.py out.wav
"""
import numpy as np, wave, sys
SR = 44100; BPM = 96.0; BEAT = 60.0 / BPM; BARS = 32
N = int(round(BARS * 4 * BEAT * SR)); TAIL = SR * 4
L = np.zeros(N + TAIL); R = np.zeros(N + TAIL); SEND = np.zeros(N + TAIL)      # dry left/right and reverb send
rng = np.random.default_rng(11)
def hz(m): return 440.0 * 2 ** ((m - 69) / 12.0)
def tt(dur): return np.arange(int(dur * SR)) / SR
def swing(b):                                   # push off-beat eighths a little late
    f = b % 1.0
    return b + (0.045 if abs(f - 0.5) < 1e-6 else 0.0)
def put(beat, x, gain=1.0, pan=0.0, send=0.0):
    i = int(round(swing(beat) * BEAT * SR)); n = min(len(x), len(L) - i)
    l = np.cos((pan + 1) * np.pi / 4); r = np.sin((pan + 1) * np.pi / 4)
    L[i:i + n] += x[:n] * gain * l; R[i:i + n] += x[:n] * gain * r; SEND[i:i + n] += x[:n] * gain * send
def onepole(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y

# ---- instruments
def epiano(m, dur, vel=1.0):                    # two-operator FM bell-piano with a slow tremolo
    t = tt(dur + 1.2); f = hz(m)
    idx = 3.0 * vel * np.exp(-t * 4.5) + 0.3
    env = np.minimum(1, t * 250) * np.exp(-t * 1.9) * np.exp(-np.maximum(0, t - dur) * 5.0)
    x = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t)) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 6)
    return x * env * (1 + 0.12 * np.sin(2 * np.pi * 4.6 * t))
def marimba(m, dur, vel=1.0):
    t = tt(max(dur, 0.25) + 0.6); f = hz(m)
    x = (np.sin(2 * np.pi * f * t) * np.exp(-t * 6.0) + 0.6 * vel * np.sin(2 * np.pi * f * 3.93 * t) * np.exp(-t * 20)
         + 0.2 * np.sin(2 * np.pi * f * 2 * t) * np.exp(-t * 10) + 0.08 * np.sin(2 * np.pi * f * 9.2 * t) * np.exp(-t * 40))
    return x * np.minimum(1, t * 500)
def bell(m, dur):
    t = tt(dur + 1.5); f = hz(m)
    x = np.sin(2 * np.pi * f * t) * np.exp(-t * 2.6) + 0.35 * np.sin(2 * np.pi * f * 2.76 * t) * np.exp(-t * 6) + 0.15 * np.sin(2 * np.pi * f * 5.4 * t) * np.exp(-t * 11)
    return x * np.minimum(1, t * 300)
def bass(m, dur):
    t = tt(dur + 0.12); f = hz(m)
    env = np.minimum(1, t * 220) * np.exp(-np.maximum(0, t - dur) * 35) * (0.75 + 0.25 * np.exp(-t * 5))
    x = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 4) + 0.15 * np.sin(2 * np.pi * 3 * f * t) * np.exp(-t * 7)
    return np.tanh(x * 1.3) * env
def pad(ms, dur):
    t = tt(dur + 1.5); x = np.zeros(len(t))
    for m in ms:
        for d in (-0.004, 0.0, 0.004):
            x += np.sin(2 * np.pi * hz(m) * (1 + d) * t + rng.uniform(0, 6.28))
    env = np.minimum(1, t * 1.6) * np.exp(-np.maximum(0, t - dur) * 2.2)
    return x * env / (3 * len(ms))
def kick():
    t = tt(0.3); f = 46 + 110 * np.exp(-t * 34)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 13) * np.minimum(1, t * 900)
def snare():
    t = tt(0.22); n = rng.standard_normal(len(t)); n = n - onepole(n, 0.12)
    return (n * np.exp(-t * 24) * 0.7 + np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30) * 0.5) * np.minimum(1, t * 900)
def rim():
    t = tt(0.06)
    return (np.sin(2 * np.pi * 1700 * t) + 0.6 * np.sin(2 * np.pi * 820 * t)) * np.exp(-t * 90)
def hat(open_=False):
    t = tt(0.25 if open_ else 0.06); n = rng.standard_normal(len(t)); n = n - onepole(n, 0.55)
    return n * np.exp(-t * (16 if open_ else 75))
def shaker():
    t = tt(0.07); n = rng.standard_normal(len(t)); n = n - onepole(n, 0.4)
    return n * np.sin(np.pi * np.minimum(1, t / 0.07)) ** 2

# ---- harmony: (bass note, chord voicing)
CH = {"C": (36, [52, 55, 59, 62]), "Am": (33, [55, 60, 64, 67]), "Dm": (38, [53, 57, 60, 64]), "G7": (31, [53, 57, 59, 62]),
      "F": (29, [52, 57, 60, 64]), "Em": (28, [55, 59, 62, 66 - 2]), "G": (31, [55, 59, 62, 67])}
A_ = ["C", "Am", "Dm", "G7", "F", "Em", "Dm", "G7"]
B_ = ["Am", "F", "C", "G", "Am", "F", "Dm", "G7"]
PROG = A_ + A_ + B_ + A_
# ---- melody: per bar, (beat, midi note, length in beats)
MA = [[(0, 76, 1), (1, 79, .5), (1.5, 81, .5), (2, 79, 1), (3, 76, 1)],
      [(0, 72, 1.5), (1.5, 74, .5), (2, 76, 2)],
      [(0, 77, 1), (1, 81, .5), (1.5, 79, .5), (2, 77, 1), (3, 74, 1)],
      [(0, 74, 1.5), (1.5, 76, .5), (2, 74, 1), (3, 71, 1)],
      [(0, 81, 1), (1, 84, .5), (1.5, 81, .5), (2, 79, 1), (3, 77, 1)],
      [(0, 79, 1.5), (1.5, 76, .5), (2, 71, 1), (3, 74, 1)],
      [(0, 77, .5), (.5, 76, .5), (1, 74, 1), (2, 69, 1), (3, 74, 1)],
      [(0, 79, 2), (3, 79, .5), (3.5, 81, .5)]]
MA2 = [MA[0], MA[1], MA[2], [(0, 74, 1), (1, 79, 1), (2, 83, 2)], MA[4],
       [(0, 79, 1), (1, 83, .5), (1.5, 79, .5), (2, 76, 2)], [(0, 77, 1), (1, 74, 1), (2, 76, .5), (2.5, 77, .5), (3, 81, 1)], [(0, 79, 3)]]
MB = [[(0, 81, 1.5), (1.5, 79, .5), (2, 76, 2)], [(0, 77, 1), (1, 81, 1), (2, 84, 2)],
      [(0, 88, 1), (1, 86, .5), (1.5, 84, .5), (2, 79, 2)], [(0, 86, 1.5), (1.5, 83, .5), (2, 79, 2)],
      [(0, 81, .5), (.5, 84, .5), (1, 88, 1), (2, 84, 1), (3, 81, 1)], [(0, 81, 1), (1, 77, 1), (2, 84, 1.5), (3.5, 81, .5)],
      [(0, 77, 1), (1, 76, .5), (1.5, 74, .5), (2, 77, 1), (3, 81, 1)], [(0, 79, 1), (1, 83, 1), (2, 86, 1.5)]]
MA3 = MA[:7] + [[(0, 74, 1), (1, 76, 1), (2, 79, 1), (3, 83, 1)]]        # last bar climbs to the leading note and back to the top
MEL = MA + MA2 + MB + MA3

for b, name in enumerate(PROG):
    root, voic = CH[name]; s = b * 4; sec = b // 8                       # 0 = A, 1 = A', 2 = B, 3 = A''
    quiet = sec == 2 and b % 8 < 4                                       # first half of B breathes
    # chords: electric piano comping, on 1 and pushed before 3
    for k, m in enumerate(voic):
        put(s + 0.0, epiano(m, 1.4 * BEAT, 0.9), 0.085, pan=-0.35 + 0.23 * k, send=0.35)
        put(s + 2.5, epiano(m, 1.2 * BEAT, 0.7), 0.065, pan=-0.35 + 0.23 * k, send=0.35)
    if sec >= 2:
        x = pad([v + 12 for v in voic[:3]], 4 * BEAT)
        put(s, x, 0.10, pan=-0.5, send=0.5); put(s, x, 0.10, pan=0.5, send=0.5)
    # bass
    if quiet:
        put(s, bass(root + 12, 3.2 * BEAT), 0.19)
    else:
        put(s, bass(root + 12, 0.9 * BEAT), 0.22); put(s + 1.5, bass(root + 12, 0.4 * BEAT), 0.16)
        put(s + 2.5, bass(root + 19, 0.45 * BEAT), 0.17); put(s + 3, bass(root + 12, 0.45 * BEAT), 0.19)
        put(s + 3.5, bass(root + 24 if b % 2 else root + 19, 0.35 * BEAT), 0.15)
    # arpeggio sparkle from A' on
    if sec >= 1:
        arp = [voic[1] + 12, voic[2] + 12, voic[3] + 12, voic[2] + 12]
        for k in range(8):
            if quiet and k % 2: continue
            put(s + k * 0.5, marimba(arp[k % 4] + (12 if sec == 3 and k % 4 == 2 else 0), 0.3, 0.6), 0.055 if k % 2 == 0 else 0.04, pan=0.55 if k % 2 else -0.55, send=0.4)
    # melody: marimba in the A sections, bell in B, doubled an octave down the last time round
    for (bt, m, d) in MEL[b]:
        if sec == 2:
            put(s + bt, bell(m, d * BEAT), 0.13, pan=0.1, send=0.6)
        else:
            put(s + bt, marimba(m, d * BEAT), 0.23, pan=0.08, send=0.45)
            put(s + bt, bell(m, d * BEAT), 0.03, pan=-0.1, send=0.5)
            if sec == 3: put(s + bt, marimba(m - 12, d * BEAT, 0.7), 0.09, pan=-0.2, send=0.4)
    # drums
    if not quiet:
        put(s, kick(), 0.38); put(s + 2, kick(), 0.32)
        if sec != 0 or b >= 4: put(s + 1.5, kick(), 0.2)
        put(s + 1, rim() if sec == 0 else snare(), 0.20 if sec == 0 else 0.18, pan=0.05, send=0.25)
        put(s + 3, rim() if sec == 0 else snare(), 0.20 if sec == 0 else 0.18, pan=0.05, send=0.25)
    for k in range(8):
        put(s + k * 0.5, hat(), (0.11 if k % 2 == 0 else 0.07) * (0.6 if quiet else 1.0), pan=0.3)
    if sec in (1, 3):
        for k in range(16):
            L_gain = 0.055 if k % 4 == 2 else 0.033
            i = int(round((s + k * 0.25 + (0.03 if k % 2 else 0)) * BEAT * SR)); x = shaker(); L[i:i + len(x)] += x * L_gain * 0.6; R[i:i + len(x)] += x * L_gain
    if b % 8 == 7:
        put(s + 3.5, hat(True), 0.06, pan=0.3, send=0.2)
        if sec != 2: put(s + 3.25, snare(), 0.09, send=0.2); put(s + 3.75, snare(), 0.12, send=0.2)

# ---- fold the tails back so the loop is seamless, then add a periodic reverb
def fold(x):
    y = x[:N].copy(); y[:TAIL] += x[N:]; return y
L, R, SEND = fold(L), fold(R), fold(SEND)
def comb(x, D, fb, damp):
    y = np.zeros_like(x); lp = np.zeros(D)
    for s in range(0, len(x), D):
        e = min(s + D, len(x)); prev = y[s - D:s] if s >= D else np.zeros(D)
        lp = lp + damp * (prev - lp)
        y[s:e] = x[s:e] + fb * lp[:e - s]
    return y
def allpass(x, D, g):
    y = np.zeros_like(x)
    for s in range(0, len(x), D):
        e = min(s + D, len(x)); xd = x[s - D:s][:e - s] if s >= D else np.zeros(e - s); yd = y[s - D:s][:e - s] if s >= D else np.zeros(e - s)
        y[s:e] = -g * x[s:e] + xd + g * yd
    return y
def reverb(x, spread):
    x2 = np.tile(x, 3)                                                   # run the loop three times; the last pass is steady state
    out = sum(comb(x2, d + spread, 0.80, 0.45) for d in (1557, 1617, 1491, 1422, 1277, 1356)) / 6.0
    out = allpass(allpass(out, 225 + spread // 2, 0.5), 556 + spread, 0.5)
    return out[2 * N:]
L = L + 0.30 * reverb(SEND, 0); R = R + 0.30 * reverb(SEND, 23)
peak = max(np.max(np.abs(L)), np.max(np.abs(R)))
L, R = np.tanh(L / peak * 1.25) / np.tanh(1.25) * 0.89, np.tanh(R / peak * 1.25) / np.tanh(1.25) * 0.89
out = np.empty(2 * N, dtype="<i2"); out[0::2] = (L * 32767).astype("<i2"); out[1::2] = (R * 32767).astype("<i2")
with wave.open(sys.argv[1], "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(out.tobytes())
# a few numbers to sanity-check the mix without ears
mono = (L + R) / 2; spec = np.abs(np.fft.rfft(mono[:SR * 20])) ** 2; fr = np.fft.rfftfreq(SR * 20, 1 / SR)
band = lambda a, b: 10 * np.log10(spec[(fr >= a) & (fr < b)].sum() / spec.sum() + 1e-12)
print("length %.2f s | peak %.2f | rms %.1f dB | bands dB: <120 Hz %.1f, 120-500 %.1f, 500-2k %.1f, 2k-8k %.1f, >8k %.1f | seam jump L %.4f R %.4f"
      % (N / SR, max(np.max(np.abs(L)), np.max(np.abs(R))), 20 * np.log10(np.sqrt(np.mean(mono ** 2))), band(0, 120), band(120, 500), band(500, 2000), band(2000, 8000), band(8000, 22050),
         abs(L[0] - L[-1]), abs(R[0] - R[-1])))
