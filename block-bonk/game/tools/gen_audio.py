"""Renders the game's music loop and sound effects to WAV. Everything is synthesized here; no samples."""
import numpy as np, wave, os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "audio"
rng = np.random.default_rng(7)

def save(name, x, sr):
    x = np.clip(x, -1, 1)
    with wave.open(os.path.join(OUT, name + ".wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype("<i2").tobytes())

def hz(m): return 440.0 * 2 ** ((m - 69) / 12)
def t_(n, sr): return np.arange(n) / sr
def lowpass(x, a):
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc += a * (x[i] - acc); y[i] = acc
    return y

# ---------------- music ----------------
SR = 32000; BPM = 104; BEAT = 60 / BPM; BARS = 16
N = int(round(BARS * 4 * BEAT * SR)); TAIL = SR * 3
buf = np.zeros(N + TAIL)
def add(start_beats, x, gain=1.0):
    i = int(round(start_beats * BEAT * SR)); buf[i:i + len(x)] += x[:len(buf) - i] * gain

def pluck(m, dur, bright=0.35):
    n = int(dur * SR); t = t_(n, SR); f = hz(m)
    return (np.sin(2*np.pi*f*t) * np.exp(-t*5) + bright*np.sin(2*np.pi*f*4*t) * np.exp(-t*18) + 0.15*np.sin(2*np.pi*f*2*t)*np.exp(-t*8)) * np.minimum(1, t*400)
def lead(m, dur):
    n = int((dur + 0.5) * SR); t = t_(n, SR); f = hz(m) * (1 + 0.004*np.sin(2*np.pi*5.5*t))
    ph = 2*np.pi*np.cumsum(f)/SR
    env = np.minimum(1, t*60) * np.exp(-np.maximum(0, t - dur)*9) * (0.55 + 0.45*np.exp(-t*3))
    return (np.sin(ph) + 0.33*np.sin(3*ph) + 0.12*np.sin(5*ph)) * env
def bass(m, dur):
    n = int((dur + 0.15) * SR); t = t_(n, SR); f = hz(m)
    env = np.minimum(1, t*200) * np.exp(-np.maximum(0, t - dur)*30) * (0.7 + 0.3*np.exp(-t*6))
    return (np.sin(2*np.pi*f*t) + 0.35*np.sin(2*np.pi*2*f*t) + 0.1*np.sin(2*np.pi*3*f*t)) * env
def pad(ms, dur):
    n = int((dur + 0.8) * SR); t = t_(n, SR); x = np.zeros(n)
    for m in ms:
        for d in (-0.003, 0.003):
            x += np.sin(2*np.pi*hz(m)*(1+d)*t)
    return x * np.minimum(1, t*2.5) * np.exp(-np.maximum(0, t - dur)*4) / (2*len(ms))
def kick():
    n = int(0.22*SR); t = t_(n, SR); f = 45 + 90*np.exp(-t*30)
    return np.sin(2*np.pi*np.cumsum(f)/SR) * np.exp(-t*16)
def clap():
    n = int(0.12*SR); t = t_(n, SR); x = rng.standard_normal(n)
    x = x - lowpass(x, 0.25)
    return x * np.exp(-t*38) * 0.6
def shaker(g):
    n = int(0.05*SR); t = t_(n, SR); x = rng.standard_normal(n); x = x - lowpass(x, 0.5)
    return x * np.exp(-t*70) * g

CH = {"C": [48, 60, 64, 67], "Am": [45, 57, 60, 64], "F": [41, 57, 60, 65], "G": [43, 59, 62, 67], "Em": [40, 59, 64, 67]}
PROG = ["C", "Am", "F", "G", "C", "Am", "F", "G", "F", "G", "Em", "Am", "F", "G", "C", "C"]
ARP = [0, 2, 1, 2, 0, 2, 1, 2]
MEL = {
 4: [(0, 76, 1), (1, 79, 1), (2, 76, .5), (2.5, 74, .5), (3, 72, 1)],
 5: [(0, 69, 1.5), (1.5, 72, .5), (2, 76, 2)],
 6: [(0, 77, 1), (1, 76, 1), (2, 74, 1), (3, 72, 1)],
 7: [(0, 74, 2), (2, 67, 1), (3, 71, 1)],
 8: [(0, 81, 1), (1, 79, .5), (1.5, 77, .5), (2, 81, 2)],
 9: [(0, 79, 1), (1, 74, 1), (2, 79, 1), (3, 83, 1)],
 10: [(0, 79, 1.5), (1.5, 76, .5), (2, 71, 2)],
 11: [(0, 72, 1), (1, 76, 1), (2, 81, 2)],
 12: [(0, 77, 1), (1, 81, 1), (2, 84, 1), (3, 81, 1)],
 13: [(0, 79, 1), (1, 83, 1), (2, 86, 2)],
 14: [(0, 76, .5), (.5, 79, .5), (1, 84, 1), (2, 79, 1), (3, 76, 1)],
 15: [(0, 72, 3)],
}
for b, name in enumerate(PROG):
    c = CH[name]; s = b * 4
    add(s, pad(c[1:], 4 * BEAT), 0.16)
    add(s, bass(c[0], 1.4 * BEAT), 0.42); add(s + 2.5, bass(c[0], 0.4 * BEAT), 0.34)
    add(s + 3, bass(c[0] + 7, 0.8 * BEAT), 0.34)
    tones = [c[1] + 12, c[2] + 12, c[3] + 12]
    for k, a in enumerate(ARP):
        if b < 2 and k % 2 == 1: continue
        add(s + k * 0.5, pluck(tones[a % 3], 0.6), 0.2 if k % 2 == 0 else 0.14)
    for (bt, m, d) in MEL.get(b, []):
        add(s + bt, lead(m, d * BEAT), 0.15)
    add(s, kick(), 0.5); add(s + 2, kick(), 0.42)
    if b >= 4:
        add(s + 1, clap(), 0.2); add(s + 3, clap(), 0.2)
    if b >= 2:
        for k in range(8): add(s + k * 0.5, shaker(0.07 if k % 2 else 0.04))
    if b in (7, 15): add(s + 3.5, kick(), 0.3)
loop = buf[:N].copy(); loop[:TAIL] += buf[N:]
d = int(round(0.75 * BEAT * SR)); wet = np.zeros(N)
src = loop.copy()
for k in range(1, 4):
    wet += np.roll(src, d * k) * (0.28 ** k)
loop = loop + wet
loop = loop / np.max(np.abs(loop)) * 0.8
save("music", loop, SR)   # then: ffmpeg -i music.wav -c:a libvorbis -q:a 4 music.ogg

# ---------------- sound effects ----------------
R = 22050
def sweep(f0, f1, dur, decay, harm=0.0):
    n = int(dur*R); t = t_(n, R); f = f0 + (f1 - f0) * (t / dur)
    ph = 2*np.pi*np.cumsum(f)/R
    return (np.sin(ph) + harm*np.sin(2*ph)) * np.exp(-t*decay) * np.minimum(1, t*500)
def bell(m, dur):
    n = int(dur*R); t = t_(n, R); f = hz(m)
    return (np.sin(2*np.pi*f*t)*np.exp(-t*7) + 0.4*np.sin(2*np.pi*f*2.76*t)*np.exp(-t*14) + 0.2*np.sin(2*np.pi*f*5.4*t)*np.exp(-t*25)) * np.minimum(1, t*600)
def noise(dur, decay, hp=0.0, lp=1.0):
    n = int(dur*R); t = t_(n, R); x = rng.standard_normal(n)
    if lp < 1.0: x = lowpass(x, lp)
    if hp > 0.0: x = x - lowpass(x, hp)
    return x * np.exp(-t*decay)
def seq(parts, total):
    x = np.zeros(int(total*R))
    for (at, s, g) in parts:
        i = int(at*R); m = min(len(s), len(x) - i); x[i:i+m] += s[:m]*g
    return x
def norm(x, peak=0.8): return x / np.max(np.abs(x)) * peak

save("click", norm(sweep(1100, 700, 0.05, 70) + noise(0.05, 160, hp=0.4)*0.3, 0.5), R)
save("pick", norm(sweep(480, 920, 0.09, 22, 0.2), 0.5), R)
save("place", norm(sweep(240, 95, 0.14, 26, 0.3) + noise(0.14, 80, lp=0.3)*0.5, 0.75), R)
save("back", norm(sweep(420, 210, 0.13, 20, 0.2), 0.45), R)
save("tick", norm(sweep(1500, 1300, 0.05, 80), 0.5), R)
save("whoosh", norm(noise(0.26, 9, hp=0.08, lp=0.35) * np.sin(np.pi*np.linspace(0, 1, int(0.26*R)))**2, 0.3), R)
save("stone", norm(noise(0.22, 22, lp=0.12)*1.5 + sweep(110, 60, 0.22, 20), 0.8), R)
save("clear", norm(seq([(0, bell(84, .5), 1), (.06, bell(88, .5), .9), (.12, bell(91, .5), .9), (.18, bell(96, .45), 1)], 0.65), 0.7), R)
save("big", norm(seq([(0, bell(84, .9), 1), (.05, bell(88, .9), .9), (.1, bell(91, .9), .9), (.15, bell(96, .9), 1), (.22, bell(100, .8), .9), (.3, bell(103, .7), .9),
                      (0, bell(72, 1.0), .7), (0, noise(0.5, 10, hp=0.6), .12)], 1.05), 0.8), R)
def tone(m, dur, harm):
    n = int(dur*R); t = t_(n, R); f = hz(m); x = np.zeros(n)
    for k, g in enumerate(harm): x += g*np.sin(2*np.pi*f*(k+1)*t)
    return x * np.minimum(1, t*120) * np.exp(-t*5)
save("over", norm(seq([(0, tone(67, .5, [1, .3, .1]), 1), (.16, tone(64, .5, [1, .3, .1]), 1), (.32, tone(60, .5, [1, .3, .1]), 1), (.5, tone(57, .7, [1, .4, .15]), 1.1)], 1.2), 0.7), R)
save("best", norm(seq([(0, tone(72, .3, [1, .5, .33, .25]), 1), (.1, tone(76, .3, [1, .5, .33, .25]), 1), (.2, tone(79, .3, [1, .5, .33, .25]), 1),
                       (.32, tone(84, .8, [1, .5, .33, .25]), 1.1), (.32, tone(76, .8, [1, .4]), .6), (.32, bell(96, .8), .5)], 1.2), 0.75), R)
save("start", norm(seq([(0, tone(72, .25, [1, .4, .2]), 1), (.09, tone(79, .4, [1, .4, .2]), 1)], 0.5), 0.6), R)
print("ok", N / SR, "s")
