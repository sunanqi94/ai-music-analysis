import numpy as np
from scipy.signal import find_peaks
import os, json

NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
GENRES = ['Pop','Rock','Jazz','Classical','Electronic','Folk','R&B','Hip Hop']
KEY_MAJOR = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
KEY_MINOR = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])

def load_audio(path):
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    if ext in ("flac","ogg"):
        import soundfile as sf
        data, sr = sf.read(path)
        if len(data.shape) > 1: data = np.mean(data, axis=1)
        return sr, data.astype(np.float32)
    else:
        from scipy.io import wavfile
        sr, data = wavfile.read(path)
        if len(data.shape) > 1: data = np.mean(data, axis=1)
        if data.dtype == np.int16: data = data.astype(np.float32) / 32768.0
        elif data.dtype == np.int32: data = data.astype(np.float32) / 2147483648.0
        return sr, data

def supported_formats():
    return ["WAV","FLAC","OGG"], False

# === IMPROVED CHROMA-BASED KEY DETECTION (professional quality, no numba) ===
def _build_chroma_filterbank(sr, n_fft=4096, sigma=0.5):
    """Build Gaussian-weighted chroma filter bank for professional pitch analysis"""
    freqs = np.fft.rfftfreq(n_fft, 1/sr)
    n_freqs = len(freqs)
    fb = np.zeros((12, n_freqs))
    for i, f in enumerate(freqs):
        if f < 20 or f > 4000: continue
        # MIDI note number for this frequency
        midi = 69 + 12 * np.log2(f / 440.0)
        for c in range(12):
            # Find closest octave of this chroma class
            target = c
            while target < midi - 6: target += 12
            while target > midi + 6: target -= 12
            dist = abs(midi - target)
            weight = np.exp(-0.5 * (dist / sigma) ** 2)
            fb[c, i] = max(fb[c, i], weight)
    # Normalize columns
    for i in range(n_freqs):
        s = np.sum(fb[:, i])
        if s > 0: fb[:, i] /= s
    return fb

# Cache the filter bank per sample rate
_chroma_fb_cache = {}

def _get_chroma_fb(sr):
    if sr not in _chroma_fb_cache:
        _chroma_fb_cache[sr] = _build_chroma_filterbank(sr)
    return _chroma_fb_cache[sr]

def _compute_chroma(y, sr, n_fft=4096, hop=512):
    """Compute accurate chromagram using Gaussian-weighted filter bank"""
    fb = _get_chroma_fb(sr)
    nf = min(500, (len(y) - n_fft) // hop) if len(y) > n_fft else 1
    if nf < 1: nf = 1
    chroma = np.zeros(12)
    for fi in range(nf):
        s = fi * hop
        if s + n_fft > len(y): break
        frame = y[s:s+n_fft] * np.hanning(n_fft)
        spec = np.abs(np.fft.rfft(frame))
        chroma += fb @ spec
    if np.sum(chroma) > 0:
        chroma /= np.sum(chroma)
    return chroma

def detect_key(y, sr):
    """Professional key detection using chroma + Krumhansl-Schmuckler"""
    chroma = _compute_chroma(y, sr)
    if np.max(chroma) == 0: return "C", "major"
    chroma = chroma / np.max(chroma)
    best_k, best_s, best_m = 0, -np.inf, "major"
    for shift in range(12):
        sc = np.roll(chroma, shift)
        for mode, prof in [("major", KEY_MAJOR), ("minor", KEY_MINOR)]:
            s = np.dot(sc, prof)
            if s > best_s: best_k, best_s, best_m = shift, s, mode
    return NOTES[best_k], best_m

def detect_bpm(y, sr):
    """BPM detection with improved autocorrelation"""
    hop = sr // 200 if sr > 200 else 1
    env = np.abs(y[::hop])
    ns = sr / hop if sr > 200 else sr
    win = int(ns * 0.1)
    if win > 1: env = np.convolve(env, np.ones(win)/win, mode="same")
    corr = np.correlate(env, env, mode="full")
    corr = corr[len(corr)//2:]
    corr = corr / corr[0] if corr[0] > 0 else corr
    min_l, max_l = int(ns*60/200), int(ns*60/60)
    if max_l >= len(corr) or min_l >= max_l: return 120
    region = corr[min_l:max_l]
    if len(region) == 0: return 120
    peaks, props = find_peaks(region, height=np.max(region)*0.3)
    if len(peaks) > 0:
        idx = peaks[np.argmax(props["peak_heights"])] + min_l
    else:
        idx = np.argmax(region) + min_l
    return round(min(max(60.0/(idx/ns), 60), 200))

def detect_chords(y, sr):
    """Chord detection using improved chroma"""
    tpl = {"C":[1,0,0,0,1,0,0,1,0,0,0,0], "G":[0,0,1,0,0,0,0,1,0,0,0,1],
           "Am":[1,0,0,1,0,0,0,0,1,0,0,0], "F":[1,0,0,0,0,1,0,0,0,1,0,0],
           "Dm":[0,0,1,0,0,1,0,0,0,1,0,0], "Em":[0,0,0,1,0,0,1,0,0,0,1,0]}
    nfft, hop = 2048, 512
    fb = _get_chroma_fb(sr)
    # Use smaller nfft matching for chord detection
    fb_small = _build_chroma_filterbank(sr, n_fft=nfft)
    found = []
    nf = min(100, (len(y)-nfft)//hop) if len(y) > nfft else 1
    for fi in range(nf):
        s = fi * hop
        if s + nfft > len(y): break
        frame = y[s:s+nfft] * np.hanning(nfft)
        spec = np.abs(np.fft.rfft(frame))
        chroma = fb_small @ spec
        if np.sum(chroma) == 0: continue
        chroma = chroma / np.max(chroma)
        bc, bs = "C", -1
        for cn, t in tpl.items():
            sim = np.dot(chroma, t) / (np.linalg.norm(chroma)*np.linalg.norm(t)+1e-10)
            if sim > bs: bs, bc = sim, cn
        if bs > 0.4: found.append(bc)
    if not found: return ["C","G","Am","F"]
    uniq = [found[0]]
    for c in found[1:]:
        if c != uniq[-1]: uniq.append(c)
    return uniq[:4] if len(uniq)>=4 else uniq + ["C","G","Am","F"][:4-len(uniq)]

def classify_genre(y, sr):
    nfft, hop = 2048, int(sr*0.05); specs = []
    for i in range(min(50, len(y)//hop)):
        s,e = i*hop, min(i*hop+nfft, len(y))
        if e-s < nfft//2: break
        specs.append(np.abs(np.fft.rfft(y[s:e]*np.hanning(e-s))))
    if not specs: return "Pop", 70
    avg = np.mean(specs, axis=0)
    freqs = np.fft.rfftfreq(nfft, 1/sr)[:len(avg)]
    total = np.sum(avg); centroid = np.sum(freqs*avg)/total if total>0 else 500
    mid = len(avg)//4; ratio = np.sum(avg[:mid])/(np.sum(avg[mid:])+1e-10)
    if centroid < 500 and ratio > 3: return "Classical", 65
    if centroid < 800: return "Folk", 60
    if ratio > 2: return "Pop", 80
    if ratio > 1.5: return "Rock", 70
    return "Electronic", 55

def detect_pitch_range(y, sr):
    nfft, hop = 2048, int(sr*0.05); notes = set()
    for i in range(min(100, len(y)//hop)):
        s,e = i*hop, min(i*hop+nfft, len(y))
        if e-s < nfft//2: break
        spec = np.abs(np.fft.rfft(y[s:e]*np.hanning(e-s)))
        freqs = np.fft.rfftfreq(e-s, 1/sr)[:len(spec)]
        if len(spec)==0: continue
        pk = np.argmax(spec) if len(spec)>0 else -1
        if pk < 0 or pk >= len(freqs): continue
        pf = freqs[pk]
        if pf < 50 or pf > 4000: continue
        ni = int(round(69+12*np.log2(pf/440)))
        notes.add(NOTES[ni%12] + str(ni//12-1))
    if not notes: return "C3", "C5"
    sn = sorted(notes, key=lambda n: int(n[-1])*12+NOTES.index(n[:-1]))
    return sn[0], sn[-1]

def analyze_note_dist(y, sr):
    nfft, hop = 2048, int(sr*0.05); nc = np.zeros(12)
    for i in range(min(100, len(y)//hop)):
        s,e = i*hop, min(i*hop+nfft, len(y))
        if e-s < nfft//2: break
        spec = np.abs(np.fft.rfft(y[s:e]*np.hanning(e-s)))
        freqs = np.fft.rfftfreq(e-s, 1/sr)[:len(spec)]
        for j in range(len(spec)):
            f = freqs[j] if j < len(freqs) else 0
            if f < 50 or f > 2000: continue
            nc[int(round(69+12*np.log2(f/440)))%12] += spec[j]
    if np.sum(nc)==0: return {}
    nc = nc/np.max(nc)*100
    return {NOTES[i]: round(float(nc[i]),1) for i in range(12) if nc[i] > 10}

def extract_melody_pitch(y, sr, seg_dur=0.5):
    nfft = 2048; hop = int(sr * seg_dur)
    num = len(y) // hop
    melody = []
    for i in range(num):
        s, e = i*hop, min(i*hop+hop, len(y))
        if e-s < nfft//2:
            melody.append({"time":round(i*seg_dur,1),"freq":0,"note":"--","midi":0,"amplitude":0,"jianpu":"--"})
            continue
        frame = y[s:e]*np.hanning(e-s)
        spec = np.abs(np.fft.rfft(frame))
        freqs = np.fft.rfftfreq(e-s, 1/sr)
        pk = np.argmax(spec[:len(freqs)]) if len(spec)>0 and len(freqs)>0 else -1
        if pk <= 0: pk = np.argmax(spec) if len(spec)>0 else -1
        if pk < 0 or pk >= min(len(freqs), len(spec)):
            melody.append({"time":round(i*seg_dur,1),"freq":0,"note":"--","midi":0,"amplitude":0,"jianpu":"--"})
            continue
        pf = freqs[pk]; amp = spec[pk]
        if pf < 60 or pf > 2000 or amp < 0.5:
            melody.append({"time":round(i*seg_dur,1),"freq":0,"note":"--","midi":0,"amplitude":0,"jianpu":"--"})
            continue
        ni = int(round(69+12*np.log2(pf/440)))
        m = ni%12; o = ni//12-1
        jp_num = (m+1) if m < 7 else (m-6)
        jp = str(jp_num)
        if o >= 5: jp += "'"
        elif o <= 2: jp += "."
        note_name = NOTES[m]# + str(o)
        melody.append({"time":round(i*seg_dur,1),"freq":round(pf,1),"note":note_name+str(o),"midi":ni,"amplitude":round(float(amp),2),"jianpu":jp})
    return melody

def match_lyrics_to_melody(lyrics, melody, duration):
    lines = [l.strip() for l in lyrics.strip().split("\n") if l.strip()]
    total_chars = sum(len(l) for l in lines)
    if total_chars == 0 or len(melody) == 0:
        return {"matched":False,"message":"need lyrics","lines":[]}
    valid = [m for m in melody if m["midi"]>0]
    if not valid: return {"matched":False,"message":"no valid melody","lines":[]}
    max_m = max(m["midi"] for m in valid)
    min_m = min(m["midi"] for m in valid)
    total_seg = len(melody)
    cps = max(1, total_chars / total_seg)
    full = "".join(lines)
    rlines = []
    for si, mp in enumerate(melody):
        sc = int(si*cps); ec = int((si+1)*cps)
        segt = full[sc:min(ec, len(full))]
        if not segt: continue
        is_h = mp["midi"]>0 and mp["midi"]==max_m
        is_l = mp["midi"]>0 and mp["midi"]==min_m
        tag = "high" if is_h else ("low" if is_l else "norm")
        rlines.append({"time":mp["time"],"text":segt,"jianpu":mp["jianpu"],"note":mp["note"],"tag":tag})
    return {"matched":True,"lines":rlines,"max_note":NOTES[max_m%12]+str(max_m//12-1),"min_note":NOTES[min_m%12]+str(min_m//12-1)}

def full_analysis(path):
    sr, y = load_audio(path)
    dur = len(y)/sr
    genre, gc = classify_genre(y, sr)
    key, mode = detect_key(y, sr)
    bpm = detect_bpm(y, sr)
    chords = detect_chords(y, sr)
    lo, hi = detect_pitch_range(y, sr)
    nd = analyze_note_dist(y, sr)
    melody = extract_melody_pitch(y, sr)
    kd = key + (" maj" if mode=="major" else " min")
    cs = "--".join(chords[:4])
    gd = {}
    rm = max(0, 100-gc)
    subs = [g for g in GENRES if g != genre][:3]
    for i,sg in enumerate(subs):
        if subs: gd[sg] = round(rm*(1-i*0.3)/len(subs))
    gn = {"Pop":["4/4流行结构","主副歌交替"],"Classical":["古典风格,动态大"],
          "Rock":["摇滚,节奏强"],"Electronic":["电子风格"],"Folk":["民谣,旋律朴素"],
          "Jazz":["爵士,和声丰富"],"R&B":["R&B,律动强"],"Hip Hop":["Hip Hop,节奏主导"]}
    notes = gn.get(genre, [genre+"风格"])
    if len(chords)>=4 and chords[:4]==["C","G","Am","F"]: notes.append("I-V-vi-IV和弦")
    mood = {"C":"明亮","G":"温暖","Am":"柔和","F":"开阔"}.get(chords[0],"中性") if chords else "中性"
    notes.append("情绪:"+mood)
    return {"success":True,"filename":os.path.basename(path),"duration":round(dur,1),"sample_rate":sr,
            "genre":genre,"genre_confidence":gc,"genre_distribution":gd,"tempo":bpm,"key":key,"mode":mode,
            "key_display":kd,"chords":chords,"chord_progression":cs,
            "pitch_range_low":lo,"pitch_range_high":hi,
            "note_distribution":nd,"analysis_notes":notes,
            "melody":melody,"melody_segments":len(melody),
            "engine":"v3 improved chroma"}