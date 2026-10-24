"""Sound design, fully synthesised (no samples -> no licence questions). 48 kHz stereo.

Timeline matches the picture: impact 4.2 s, freeze 9.2-11.2 s, labels 11.5..16.0 s, title 18.6 s, end 22 s.
Santur (Karplus-Strong courses) plays a Shur-mode phrase (D, E-koron, F, G, A) - one note per project label.
"""
import os as _os
ROOT = _os.environ.get("GIRIH_ROOT", _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt, resample_poly, stft, istft
import soundfile as sf

SR = 48000
DUR = 22.0
N = int(SR * DUR)
rng = np.random.default_rng(20261024)
IMPACT = 4.2
LABELS = [11.5, 12.4, 13.3, 14.4, 15.1, 16.0]
TITLE = 18.6

def t_axis(n):
    return np.arange(n) / SR

def env_exp(n, tau):
    return np.exp(-t_axis(n) / tau)

def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)

def bp(x, lo, hi, order=4):
    return sosfilt(butter(order, [lo, hi], btype="band", fs=SR, output="sos"), x)

def lp(x, f, order=4):
    return sosfilt(butter(order, f, btype="low", fs=SR, output="sos"), x)

def hp(x, f, order=4):
    return sosfilt(butter(order, f, btype="high", fs=SR, output="sos"), x)

def place(bus, sig, at, pan=0.0, gain=1.0):
    """Mix mono/stereo sig into stereo bus at time `at` with constant-power pan (-1..1)."""
    i = int(at * SR)
    if sig.ndim == 1:
        a = (pan + 1) * np.pi / 4
        sig = np.stack([sig * np.cos(a), sig * np.sin(a)], axis=1)
    j = min(len(bus), i + len(sig))
    if j > i:
        bus[i:j] += gain * sig[: j - i]

# ------------------------------------------------------------------ reverb (synthetic hall, ~3.4 s)
def make_ir(rt60=3.4, pre=0.025, length=5.0):
    n = int(length * SR)
    t = t_axis(n)
    ir = np.zeros((n, 2))
    bands = [(60, 250, 1.10), (250, 1000, 1.00), (1000, 4000, 0.78), (4000, 12000, 0.50)]
    for ch in range(2):
        noise = rng.standard_normal(n)
        acc = np.zeros(n)
        for lo, hi, k in bands:
            acc += bp(noise, lo, hi, 2) * np.exp(-6.91 * t / (rt60 * k))
        acc *= smooth(t / 0.08)                    # soft onset (diffuse build-up)
        ir[:, ch] = acc
    # sparse early reflections
    for d, g in ((0.011, 0.5), (0.019, 0.38), (0.027, 0.3), (0.041, 0.22), (0.057, 0.16)):
        k = int(d * SR)
        ir[k, 0] += g * rng.choice([-1, 1]); ir[k + int(0.0013 * SR), 1] += g * rng.choice([-1, 1])
    ir = np.concatenate([np.zeros((int(pre * SR), 2)), ir])
    return ir / np.sqrt((ir ** 2).sum(axis=0).mean())

def reverb(dry, ir):
    out = np.zeros((len(dry) + len(ir) - 1, 2))
    for ch in range(2):
        out[:, ch] = fftconvolve(dry[:, ch], ir[:, ch])
    return out[: len(dry)]

# ------------------------------------------------------------------ instruments
def ks(x, L, g, b):
    """Karplus-Strong loop y[n] = x[n] + g*b*y[n-L] + g*(1-b)*y[n-L-1], vectorised per period."""
    n = len(x)
    y = np.zeros(n + L + 1)
    xp = np.concatenate([np.zeros(L + 1), x])
    for s0 in range(L + 1, n + L + 1, L):
        s1 = min(s0 + L, n + L + 1)
        y[s0:s1] = xp[s0:s1] + g * b * y[s0 - L:s1 - L] + g * (1 - b) * y[s0 - L - 1:s1 - L - 1]
    return y[L + 1:]

_santur_cache = {}
def santur_note(freq, dur=6.0, vel=1.0, bright=0.6, fs=192000, variants=3):
    """Hammered dulcimer: 4 slightly detuned strings per course, KS strings, wood-hammer excitation."""
    key = (round(freq, 3), dur)
    if key not in _santur_cache:
        vs = []
        for _ in range(variants):
            n = int(dur * fs)
            out = np.zeros(n)
            for k, cents in enumerate((-2.2, -0.6, 0.8, 2.4)):
                f = freq * 2 ** ((cents + rng.normal(0, 0.3)) / 1200)
                L = int(round(fs / f - (1 - bright)))
                exc_len = max(8, int(fs * 0.0016))
                exc = rng.standard_normal(exc_len) * np.hanning(exc_len)
                exc = np.convolve(exc, np.ones(3) / 3, mode="same")
                x = np.zeros(n); x[:exc_len] = exc
                g = 0.99985 - 0.00002 * (freq / 100)
                out += ks(x, L, g, bright) * (1 + 0.04 * k)
            out = resample_poly(out, 1, 4)
            out = hp(out, 70, 2)
            out = 0.55 * out + 0.45 * lp(out, min(7000.0, freq * 14), 2)
            out = out + 0.25 * bp(out, freq * 2.9, freq * 3.1, 2)
            out *= env_exp(len(out), 3.2)
            vs.append(out / (np.abs(out).max() + 1e-9))
        _santur_cache[key] = vs
    vs = _santur_cache[key]
    return vel * vs[rng.integers(len(vs))]

def glass_tink(f0, tau, n_part=5):
    """Modal glass shard: inharmonic plate partials, high modes die fast."""
    ratios = np.array([1.0, 2.32, 4.25, 6.63, 9.38, 12.7])[:n_part]
    dur = min(6.0, tau * 6)
    n = int(dur * SR); t = t_axis(n)
    y = np.zeros(n)
    for i, r in enumerate(ratios):
        f = f0 * r * (1 + rng.normal(0, 0.006))
        if f > 16000:
            break
        y += (0.8 ** i) * rng.uniform(0.5, 1.0) * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / (tau / (1 + 0.55 * i)))
    click = np.zeros(n); cl = int(0.002 * SR); click[:cl] = rng.standard_normal(cl) * np.hanning(cl) * 0.35
    return (y + hp(click, 2000, 2)) * smooth(t / 0.0015)

def whoosh(dur, f_from, f_to, width=0.6, curve=1.0):
    n = int(dur * SR)
    noise = rng.standard_normal(n)
    f, tt, Z = stft(noise, SR, nperseg=2048)
    u = np.clip(tt / dur, 0, 1) ** curve
    fc = f_from * (f_to / f_from) ** u
    mask = np.exp(-0.5 * (np.log(np.maximum(f[:, None], 1) / fc[None, :]) / width) ** 2)
    _, y = istft(Z * mask, SR, nperseg=2048)
    y = y[:n]
    return y / (np.abs(y).max() + 1e-9)

def tape_slow(x, rate_from=1.0, rate_to=0.22):
    """Read x with a decelerating playhead: the 'time is stopping' pitch-down."""
    n = len(x)
    r = rate_from + (rate_to - rate_from) * smooth(t_axis(n) / (n / SR))
    ph = np.cumsum(r); ph = ph[ph < n - 1]
    return np.interp(ph, np.arange(n), x)

def pad(freqs, dur, attack=2.0, release=2.5, detune=5.0, bright=900.0):
    n = int(dur * SR); t = t_axis(n)
    y = np.zeros((n, 2))
    for f in freqs:
        for ch, c in enumerate((-detune, detune)):
            for v in (-0.5, 0.5):
                ff = f * 2 ** ((c + v * 2) / 1200)
                lfo = 1 + 0.12 * np.sin(2 * np.pi * rng.uniform(0.05, 0.13) * t + rng.uniform(0, 6))
                y[:, ch] += lfo * (np.sin(2 * np.pi * ff * t) + 0.18 * np.sin(4 * np.pi * ff * t) + 0.06 * np.sin(6 * np.pi * ff * t))
    for ch in range(2):
        y[:, ch] = lp(y[:, ch], bright, 2)
    e = smooth(t / attack) * (1 - smooth((t - (dur - release)) / release))
    return y * e[:, None] / (np.abs(y).max() + 1e-9)

def boom(f_top=80, f_low=31, tau=1.1, drive=1.8):
    n = int(4.5 * SR); t = t_axis(n)
    f = f_low + (f_top - f_low) * np.exp(-t / 0.14)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * np.exp(-t / tau) * smooth(t / 0.004)
    y = np.tanh(drive * y) / np.tanh(drive)
    body = lp(rng.standard_normal(n), 220, 4) * np.exp(-t / 0.25) * 0.6
    y = y + body / (np.abs(body).max() + 1e-9) * 0.35
    return y * (1 - smooth((t - 3.0) / 1.5))          # tail reaches true zero

# ------------------------------------------------------------------ composition
def compose():
    dry = np.zeros((N, 2)); wet = np.zeros((N, 2))         # wet = reverb send

    # 1. room / outside air: soft noise bed, filtered down as time freezes
    air = lp(hp(rng.standard_normal(N), 120, 2), 2500, 2) * 0.02
    t = t_axis(N)
    air *= smooth(t / 2.5)
    air_freeze = lp(air, 380, 2)
    k = smooth((t - 9.4) / 1.6) * (1 - smooth((t - 17.6) / 2.0))
    air = air * (1 - k) + air_freeze * k * 1.4
    place(dry, np.stack([air, np.roll(air, 977)], axis=1), 0.0, gain=1.0)

    # 2. low drone in D (tension), swells into the impact, returns softly after
    drone = pad([73.42, 110.0, 146.83], 22.0, attack=3.0, release=3.0, detune=4.0, bright=520)
    de = np.interp(t, [0, 2.0, 4.1, 4.4, 8.0, 11.0, 17.0, 18.6, 22.0], [0, 0.55, 0.9, 0.25, 0.35, 0.5, 0.55, 0.2, 0.0])
    place(dry, drone * de[:, None], 0.0, gain=0.16)
    place(wet, drone * de[:, None], 0.0, gain=0.05)

    # 3. the ball: approaching air-rip (doppler rise) right into the hit
    w = whoosh(1.5, 300, 2600, width=0.45, curve=2.2) * smooth(t_axis(int(1.5 * SR)) / 1.5) ** 2
    place(dry, w, IMPACT - 1.5, pan=0.15, gain=0.16)
    # reverse swell (sucked-in reverb) into the impact
    sw = whoosh(1.2, 900, 5000, width=0.9) * smooth(t_axis(int(1.2 * SR)) / 1.2) ** 3
    place(wet, sw, IMPACT - 1.2, gain=0.10)

    # 4. IMPACT: sub boom + crack + slowed shatter body
    b = boom()
    place(dry, b, IMPACT, gain=0.62); place(wet, b, IMPACT, gain=0.12)
    crack_n = int(0.06 * SR)
    crack = hp(rng.standard_normal(crack_n), 1800, 2) * np.exp(-t_axis(crack_n) / 0.012)
    place(dry, crack, IMPACT, gain=0.22); place(wet, crack, IMPACT, gain=0.25)
    crunch_n = int(1.6 * SR)
    crunch = bp(rng.standard_normal(crunch_n), 600, 5200, 2)
    gran = (rng.random(crunch_n) < 0.004).astype(float)
    gran = np.convolve(gran, np.hanning(int(0.004 * SR)), mode="same")
    crunch = crunch * (0.25 + gran) * np.exp(-t_axis(crunch_n) / 0.45)
    crunch = lp(crunch, 3800, 2)
    place(dry, crunch / np.abs(crunch).max(), IMPACT + 0.01, gain=0.12)
    place(wet, crunch / np.abs(crunch).max(), IMPACT + 0.01, gain=0.10)

    # 5. glass cloud: hundreds of low, slowed shard resonances, thinning out
    shards = np.zeros((int(9.0 * SR), 2))
    tt = 0.0
    while tt < 6.8:
        rate = 70 * np.exp(-tt / 1.1) + 5
        tt += rng.exponential(1 / rate)
        f0 = np.exp(rng.uniform(np.log(260), np.log(1700)))
        tau = rng.uniform(0.35, 1.4) * (600 / f0) ** 0.35
        amp = np.exp(rng.normal(0, 0.5)) * (0.5 + 0.5 * np.exp(-tt / 2.0))
        place(shards, glass_tink(f0, tau), tt, pan=float(np.clip(rng.normal(0, 0.55), -1, 1)), gain=amp)
    shards /= np.abs(shards).max() + 1e-9
    # time freezing: the tail of the cloud slows down and drops in pitch
    cut = int((9.2 - IMPACT) * SR)
    head, tail = shards[:cut], shards[cut:]
    place(dry, head, IMPACT, gain=0.20); place(wet, head, IMPACT, gain=0.22)
    slowed = np.stack([tape_slow(tail[:, 0]), tape_slow(tail[:, 1])], axis=1)
    slowed *= (1 - smooth(t_axis(len(slowed)) / (len(slowed) / SR)))[:, None]
    place(dry, slowed, 9.2, gain=0.20); place(wet, slowed, 9.2, gain=0.30)

    # 6. fragments flying past the camera: slow low whooshes, panned across
    for st, d, pan, g in ((5.4, 2.6, -0.6, 0.11), (6.6, 2.2, 0.55, 0.09), (8.4, 2.6, -0.2, 0.08)):
        wv = whoosh(d, 180, 900, width=0.5, curve=0.8)
        wv *= np.sin(np.pi * t_axis(len(wv)) / d) ** 2
        place(dry, wv, st, pan=pan, gain=g); place(wet, wv, st, pan=pan, gain=0.05)

    # 7. bullet time: frozen crystal pad + slow heartbeat
    frozen = pad([146.83, 220.0, 293.66, 440.0], 9.6, attack=2.2, release=2.8, detune=6.0, bright=2400)
    shimmer_t = t_axis(len(frozen))
    frozen *= (1 + 0.25 * np.sin(2 * np.pi * 4.3 * shimmer_t))[:, None] ** 0.5
    place(dry, frozen, 10.4, gain=0.075); place(wet, frozen, 10.4, gain=0.09)
    beat_n = int(0.5 * SR)
    for i, bt in enumerate(np.arange(11.4, 17.6, 60 / 52)):
        for off, g in ((0.0, 1.0), (0.22, 0.6)):
            thump = np.sin(2 * np.pi * 52 * t_axis(beat_n)) * np.exp(-t_axis(beat_n) / 0.09) * smooth(t_axis(beat_n) / 0.004)
            place(dry, thump, bt + off, gain=0.11 * g)

    # 8. santur: one note per project label (Shur on D, E-koron = +150 cents over D)
    D4 = 293.66
    koron = D4 * 2 ** (150 / 1200)
    melody = [440.0, 392.0, 349.23, 392.0, koron, D4]           # A G F G E-koron D
    for i, (st, f) in enumerate(zip(LABELS, melody)):
        note = santur_note(f, dur=6.0, vel=1.0)
        pan = [-0.25, 0.3, -0.35, 0.2, -0.1, 0.0][i]
        place(dry, note, st, pan=pan, gain=0.13); place(wet, note, st, pan=pan, gain=0.12)
        # grace note (a tiny 'riz' feel) on the strong beats
        if i in (0, 3):
            place(dry, santur_note(f, 2.0, 0.5), st + 0.11, pan=pan, gain=0.06)

    # 9. time resumes: rising reverse swell into the title
    sw2 = whoosh(2.4, 200, 4200, width=0.8, curve=1.6) * smooth(t_axis(int(2.4 * SR)) / 2.4) ** 3
    place(wet, sw2, TITLE - 2.4, gain=0.13)

    # 10. title: warm low hit + santur tremolo (riz) on D3/A3 + final D
    b2 = boom(f_top=60, f_low=36, tau=1.5, drive=1.3)
    place(dry, b2, TITLE, gain=0.42); place(wet, b2, TITLE, gain=0.10)
    for f, pan in ((146.83, -0.2), (220.0, 0.2)):
        for k, rt in enumerate(np.arange(0, 1.4, 1 / 11.0)):
            v = 0.9 * np.exp(-rt / 0.8) * (0.85 + 0.15 * rng.random())
            place(dry, santur_note(f, 4.0, v), TITLE + rt, pan=pan, gain=0.055)
            place(wet, santur_note(f, 4.0, v), TITLE + rt, pan=pan, gain=0.04)
    place(dry, santur_note(D4, 6.0, 1.0), TITLE + 1.45, pan=0.0, gain=0.10)
    place(wet, santur_note(D4, 6.0, 1.0), TITLE + 1.45, pan=0.0, gain=0.14)
    pad_end = pad([73.42, 146.83, 220.0, 293.66], 4.2, attack=0.6, release=3.0, detune=5.0, bright=1500)
    place(dry, pad_end, TITLE, gain=0.10); place(wet, pad_end, TITLE, gain=0.08)

    return dry, wet

def master(dry, wet):
    ir = make_ir()
    mix = dry + reverb(wet, ir)
    mix -= mix.mean(axis=0)
    # gentle glue compression (RMS, 4:1 above threshold, slow)
    env = np.sqrt(lp(np.mean(mix ** 2, axis=1), 8, 1).clip(1e-12))
    thr = 0.12
    gain = np.where(env > thr, (thr / env) ** (1 - 1 / 3.0), 1.0)
    mix *= gain[:, None]
    # end fade so the last frame is silent
    t = t_axis(len(mix))
    mix *= (1 - smooth((t - 20.9) / 1.05))[:, None]
    mix *= smooth(t / 0.05)[:, None]
    # loudness to -16 LUFS, then true-peak safe limiting at -1 dBTP
    import pyloudnorm as pyln
    meter = pyln.Meter(SR)
    lufs = meter.integrated_loudness(mix)
    mix *= 10 ** ((-16.0 - lufs) / 20)
    up = resample_poly(mix, 4, 1, axis=0)
    peak = np.abs(up).max()
    lim = 10 ** (-1.0 / 20)
    if peak > lim:
        # soft-knee limiter on the oversampled envelope
        env = np.abs(up).max(axis=1)
        from scipy.ndimage import maximum_filter1d, uniform_filter1d
        g = np.minimum(1.0, lim / np.maximum(env, 1e-9))
        g = maximum_filter1d(1 - g, size=int(0.006 * SR * 4))
        g = 1 - uniform_filter1d(g, size=int(0.006 * SR * 4))
        up = up * g[:, None]
        mix = resample_poly(up, 1, 4, axis=0)[: len(mix)]
    return mix, meter.integrated_loudness(mix), 20 * np.log10(np.abs(resample_poly(mix, 4, 1, axis=0)).max())

if __name__ == "__main__":
    dry, wet = compose()
    mix, lufs, tp = master(dry, wet)
    sf.write(ROOT + "/audio/score.wav", mix.astype(np.float32), SR, subtype="PCM_24")
    print(f"written: {len(mix)/SR:.2f}s  integrated {lufs:.1f} LUFS  true-peak {tp:.2f} dBTP")
