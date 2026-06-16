import numpy as np
from scipy.signal import find_peaks
from scipy.ndimage import gaussian_filter1d
import os, json, subprocess, tempfile, warnings
warnings.filterwarnings('ignore')

NOTES = ['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']
GENRES = ['Pop','Rock','Jazz','Classical','Electronic','Folk','R&B','Hip Hop','Metal','Blues','Country','Latin','Reggae']
KEY_MAJOR = np.array([6.35,2.23,3.48,2.33,4.38,4.09,2.52,5.19,2.39,3.66,2.29,2.88])
KEY_MINOR = np.array([6.33,2.68,3.52,5.38,2.60,3.53,2.54,4.75,3.98,2.69,3.34,3.17])
FREQ_BANDS = [(20,60),(60,120),(120,250),(250,500),(500,1000),(1000,2000),(2000,4000),(4000,8000)]
FFMPEG_DIR = os.path.dirname(os.path.abspath(__file__))
if os.name == 'nt':
    FFMPEG_PATH = os.path.join(FFMPEG_DIR, "ffmpeg", "ffmpeg.exe")
else:
    FFMPEG_PATH = os.path.join(FFMPEG_DIR, "ffmpeg", "ffmpeg") if os.path.isfile(os.path.join(FFMPEG_DIR, "ffmpeg", "ffmpeg")) else "ffmpeg"

def _build_chord_library():
    def maj(b):    v=np.zeros(12); v[b%12]=1; v[(b+4)%12]=1; v[(b+7)%12]=1; return v
    def min_(b):   v=np.zeros(12); v[b%12]=1; v[(b+3)%12]=1; v[(b+7)%12]=1; return v
    def dim(b):    v=np.zeros(12); v[b%12]=1; v[(b+3)%12]=1; v[(b+6)%12]=1; return v
    def aug(b):    v=np.zeros(12); v[b%12]=1; v[(b+4)%12]=1; v[(b+8)%12]=1; return v
    def dom7(b):   v=np.zeros(12); v[b%12]=1; v[(b+4)%12]=1; v[(b+7)%12]=1; v[(b+10)%12]=1; return v
    def maj7(b):   v=np.zeros(12); v[b%12]=1; v[(b+4)%12]=1; v[(b+7)%12]=1; v[(b+11)%12]=1; return v
    def min7(b):   v=np.zeros(12); v[b%12]=1; v[(b+3)%12]=1; v[(b+7)%12]=1; v[(b+10)%12]=1; return v
    def sus2(b):   v=np.zeros(12); v[b%12]=1; v[(b+2)%12]=1; v[(b+7)%12]=1; return v
    def sus4(b):   v=np.zeros(12); v[b%12]=1; v[(b+5)%12]=1; v[(b+7)%12]=1; return v
    def dim7(b):   v=np.zeros(12); v[b%12]=1; v[(b+3)%12]=1; v[(b+6)%12]=1; v[(b+9)%12]=1; return v
    def aug7(b):   v=np.zeros(12); v[b%12]=1; v[(b+4)%12]=1; v[(b+8)%12]=1; v[(b+10)%12]=1; return v
    def halfdim7(b): v=np.zeros(12); v[b%12]=1; v[(b+3)%12]=1; v[(b+6)%12]=1; v[(b+10)%12]=1; return v
    tpl = {}
    for i, r in enumerate(['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']):
        tpl[r]=maj(i); tpl[r+'m']=min_(i); tpl[r+'7']=dom7(i)
        tpl[r+'M7']=maj7(i); tpl[r+'m7']=min7(i); tpl[r+'dim']=dim(i)
        tpl[r+'aug']=aug(i); tpl[r+'sus2']=sus2(i); tpl[r+'sus4']=sus4(i)
        tpl[r+'m7b5']=halfdim7(i); tpl[r+'6']=maj(i); tpl[r+'6'][(i+9)%12]=1
        tpl[r+'m6']=min_(i); tpl[r+'m6'][(i+9)%12]=1
        tpl[r+'sus24']=sus2(i)+sus4(i); tpl[r+'sus24']/=np.max(tpl[r+'sus24'])
    for ri in [0,2,4,5,7,9,11]:
        tpl[['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][ri]+'dim7']=dim7(ri)
    return tpl

def load_audio(path):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    try:
        if ext in ('flac','ogg','oga'):
            import soundfile as sf
            data, sr = sf.read(path)
            if len(data.shape) > 1: data = np.mean(data, axis=1)
            return sr, data.astype(np.float32)
        elif ext in ('wav',):
            from scipy.io import wavfile
            sr, data = wavfile.read(path)
            if len(data.shape) > 1: data = np.mean(data, axis=1)
            if data.dtype == np.int16: data = data.astype(np.float32) / 32768.0
            elif data.dtype == np.int32: data = data.astype(np.float32) / 2147483648.0
            return sr, data
        else:
            return _load_with_ffmpeg(path, ext)
    except:
        return _load_with_ffmpeg(path, ext)

def _load_with_ffmpeg(path, ext):
    ffmpeg_cmd = FFMPEG_PATH
    if not os.path.isfile(ffmpeg_cmd):
        try:
            import shutil
            ffmpeg_cmd = shutil.which("ffmpeg")
        except:
            ffmpeg_cmd = None
    if not ffmpeg_cmd:
        raise RuntimeError('ffmpeg not found. Cannot decode ' + ext + ' files.')
    tmp = os.path.join(tempfile.gettempdir(), 'codex_decode_%s_%s.wav' % (os.getpid(), os.path.basename(path)))
    try:
        cmd = [ffmpeg_cmd, '-y', '-i', path, '-ac', '1', '-ar', '44100', '-sample_fmt', 's16', '-f', 'wav', tmp]
        kwargs = {'capture_output': True, 'timeout': 60}
        if os.name == 'nt':
            kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        r = subprocess.run(cmd, **kwargs)
        if r.returncode != 0:
            raise RuntimeError('ffmpeg failed: ' + r.stderr.decode('utf-8', errors='replace')[:200])
        from scipy.io import wavfile
        sr, data = wavfile.read(tmp)
        data = data.astype(np.float32) / 32768.0
        return sr, data
    finally:
        if os.path.exists(tmp):
            try: os.remove(tmp)
            except: pass

def supported_formats():
    try:
        import shutil
        has_ffmpeg = os.path.isfile(FFMPEG_PATH) or shutil.which("ffmpeg") is not None
    except:
        has_ffmpeg = os.path.isfile(FFMPEG_PATH)
    basic = ['WAV', 'FLAC', 'OGG']
    extended = ['MP3', 'M4A', 'AAC', 'WMA', 'AIFF', 'MP2', 'AC3', 'AMR']
    additional = ['MP3', 'M4A', 'M4R', 'AAC', 'WMA', 'AIFF', 'MP2', 'AC3', 'AMR', '3GP', 'OGV', 'WEBM']
    if has_ffmpeg:
        return basic + additional, True
    return basic, False

def _build_chroma_filterbank(sr, n_fft=4096, sigma=0.5):
    freqs = np.fft.rfftfreq(n_fft, 1/sr)
    fb = np.zeros((12, len(freqs)))
    for i, f in enumerate(freqs):
        if 20 <= f <= 4000:
            midi = 69 + 12 * np.log2(f / 440.0)
            for c in range(12):
                target = c
                while target < midi - 6: target += 12
                while target > midi + 6: target -= 12
                weight = np.exp(-0.5 * ((midi - target) / sigma) ** 2)
                fb[c, i] = max(fb[c, i], weight)
    col_sums = np.sum(fb, axis=0, keepdims=True)
    fb = np.divide(fb, col_sums, out=np.zeros_like(fb), where=col_sums > 0)
    return fb

_chroma_fb_cache = {}

def _get_chroma_fb(sr):
    key = str(sr)
    if key not in _chroma_fb_cache:
        _chroma_fb_cache[key] = _build_chroma_filterbank(sr)
        _chroma_fb_cache[key + '_small'] = _build_chroma_filterbank(sr, n_fft=2048, sigma=0.8)
    return _chroma_fb_cache[key]

def _get_chroma_fb_small(sr):
    _get_chroma_fb(sr)
    return _chroma_fb_cache[str(sr) + '_small']

def _compute_chroma(y, sr, n_fft=4096, hop=512):
    fb = _get_chroma_fb(sr)
    nf = min(500, (len(y) - n_fft) // hop) if len(y) > n_fft else 1
    if nf < 1: nf = 1
    chroma = np.zeros(12)
    win = np.hanning(n_fft)
    for fi in range(nf):
        s = fi * hop
        if s + n_fft > len(y): break
        frame = y[s:s+n_fft] * win
        spec = np.abs(np.fft.rfft(frame))
        chroma += fb @ spec
    if np.sum(chroma) > 0:
        chroma /= np.sum(chroma)
    return chroma

def detect_key(y, sr):
    chroma = _compute_chroma(y, sr)
    if np.max(chroma) == 0: return 'C', 'major', 0.0
    chroma = chroma / np.max(chroma)
    scores = []
    for shift in range(12):
        sc = np.roll(chroma, shift)
        for mode, prof in [('major', KEY_MAJOR), ('minor', KEY_MINOR)]:
            s = float(np.dot(sc, prof))
            scores.append((s, shift, mode))
    scores.sort(reverse=True, key=lambda x: x[0])
    best_s, best_k, best_m = scores[0]
    second_s = scores[1][0] if len(scores) > 1 else best_s
    confidence = min(1.0, max(0.0, (best_s - second_s) / (prof.max() * 0.5)))
    return NOTES[best_k], best_m, round(confidence, 2)

def detect_bpm(y, sr):
    hop = max(1, sr // 200)
    env = np.abs(y[::hop])
    ns = len(env)
    if ns > 100:
        env = gaussian_filter1d(env, sigma=2)
    corr = np.correlate(env, env, mode='full')
    corr = corr[len(corr)//2:]
    corr = corr / (corr[0] + 1e-10)
    min_lag = int(len(y) * 60 / (sr * 250))
    max_lag = int(len(y) * 60 / (sr * 30))
    min_lag = max(1, min_lag)
    max_lag = min(len(corr) - 1, max_lag)
    if min_lag >= max_lag: return 120
    region = corr[min_lag:max_lag]
    bpm_candidates = []
    peaks, props = find_peaks(region, height=np.median(region)*1.5, distance=max(1, min_lag//10))
    if len(peaks) > 0:
        sorted_peaks = sorted(zip(peaks, props['peak_heights']), key=lambda x: -x[1])
        for p_idx, p_h in sorted_peaks[:5]:
            lag = p_idx + min_lag
            bpm_val = 60.0 / (lag / (sr / hop))
            if 40 <= bpm_val <= 220:
                bpm_candidates.append((bpm_val, p_h))
    nfft = 2048; hop_audio = 512
    flux = []; prev_spec = None
    for i in range(0, min(len(y) - nfft, 500 * hop_audio), hop_audio):
        if i + nfft > len(y): break
        frame = y[i:i+nfft] * np.hanning(nfft)
        spec = np.abs(np.fft.rfft(frame))
        if prev_spec is not None:
            flux.append(np.sum(np.maximum(0, spec - prev_spec)))
        prev_spec = spec
    if len(flux) > 10:
        flux = np.array(flux)
        flux_env = gaussian_filter1d(flux, sigma=1)
        onset_frames = [j for j in range(1, len(flux_env)-1) 
            if flux_env[j] > flux_env[j-1] and flux_env[j] > flux_env[j+1] and flux_env[j] > np.mean(flux_env)*2]
        if len(onset_frames) > 2:
            intervals = np.diff(onset_frames) * hop_audio / sr
            valid = intervals[(intervals > 0.25) & (intervals < 2.0)]
            if len(valid) > 0:
                bpm_from_onset = 60.0 / np.median(valid)
                if 40 <= bpm_from_onset <= 220:
                    bpm_candidates.append((bpm_from_onset, np.median(valid)))
    if not bpm_candidates: return 120
    bpm_candidates.sort(key=lambda x: -x[1])
    return max(40, min(220, round(bpm_candidates[0][0] / 5) * 5))

def detect_chords(y, sr):
    tpl = _build_chord_library()
    nfft, hop = 2048, 512
    fb_small = _get_chroma_fb_small(sr)
    found = []
    nf = min(60, (len(y)-nfft)//hop) if len(y) > nfft else 1
    win = np.hanning(nfft)
    for fi in range(nf):
        s = fi * hop
        if s + nfft > len(y): break
        frame = y[s:s+nfft] * win
        spec = np.abs(np.fft.rfft(frame))
        chroma = fb_small @ spec
        if np.sum(chroma) == 0: continue
        chroma = chroma / np.max(chroma)
        sims = [(cn, float(np.dot(chroma, t) / (np.linalg.norm(chroma)*np.linalg.norm(t)+1e-10))) for cn, t in tpl.items()]
        sims.sort(key=lambda x: -x[1])
        if sims[0][1] > 0.35:
            found.append(sims[0][0])
    if not found: return ['C','G','Am','F']
    unique = [found[0]]
    for c in found[1:]:
        if c != unique[-1]:
            unique.append(c)
    n_chords = min(len(unique), 6)
    return unique[:n_chords] if n_chords >= 4 else unique + ['C','G','Am','F','Dm','Em'][:4-n_chords]

def classify_genre(y, sr):
    nfft, hop = 4096, int(sr * 0.05)
    n_frames = min(80, max(1, len(y) // hop))
    specs = []
    for fi in range(n_frames):
        s = fi * hop
        if s + nfft > len(y): break
        frame = y[s:s+nfft] * np.hanning(nfft)
        specs.append(np.abs(np.fft.rfft(frame)))
    if not specs: return 'Pop', 70, {}
    avg_spec = np.mean(specs, axis=0)
    freqs = np.fft.rfftfreq(nfft, 1/sr)
    total = np.sum(avg_spec) + 1e-10
    centroid = float(np.sum(freqs * avg_spec) / total)
    cum = np.cumsum(avg_spec) / total
    rolloff = float(freqs[np.searchsorted(cum, 0.85)])
    band_energy = []
    for low, high in FREQ_BANDS:
        mask = (freqs >= low) & (freqs < high)
        band_energy.append(float(np.sum(avg_spec[mask]) / total))
    spread = float(np.sum((freqs - centroid)**2 * avg_spec) / total) ** 0.5
    flux_vals = []
    for j in range(1, len(specs)):
        flux_vals.append(float(np.sum(np.abs(specs[j] - specs[j-1])) / total))
    avg_flux = float(np.mean(flux_vals)) if flux_vals else 0
    low_ratio = band_energy[0] + band_energy[1] + band_energy[2]
    mid_ratio = band_energy[3] + band_energy[4] + band_energy[5]
    high_ratio = band_energy[6] + band_energy[7]
    if centroid < 400 and spread < 1000 and low_ratio > 0.7:
        return 'Classical', 65, {'Bass': 60, 'Mid': 30, 'Treble': 10}
    if centroid < 700 and rolloff < 2000 and avg_flux < 0.3 and mid_ratio > 0.5:
        return 'Folk', 60, {'Bass': 35, 'Mid': 50, 'Treble': 15}
    if avg_flux > 0.6 and high_ratio > 0.25 and centroid > 2000:
        return 'Metal', 55, {'Bass': 25, 'Mid': 35, 'Treble': 40}
    if rolloff > 6000 and avg_flux > 0.4 and centroid > 2500:
        return 'Electronic', 60, {'Bass': 30, 'Mid': 35, 'Treble': 35}
    if low_ratio > 0.5 and band_energy[1] > 0.2 and avg_flux > 0.3:
        return 'Rock', 65, {'Bass': 45, 'Mid': 35, 'Treble': 20}
    if avg_flux > 0.35 and mid_ratio > 0.4:
        return 'Pop', 75, {'Bass': 30, 'Mid': 50, 'Treble': 20}
    if band_energy[2] > 0.15 and mid_ratio > 0.45:
        return 'R&B', 55, {'Bass': 35, 'Mid': 50, 'Treble': 15}
    return 'Pop', 70, {'Bass': 30, 'Mid': 40, 'Treble': 30}

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
    genre, gc, gdist = classify_genre(y, sr)
    key, mode, kconf = detect_key(y, sr)
    bpm = detect_bpm(y, sr)
    chords = detect_chords(y, sr)
    lo, hi = detect_pitch_range(y, sr)
    nd = analyze_note_dist(y, sr)
    melody = extract_melody_pitch(y, sr)
    kd = key + (' maj' if mode=='major' else ' min')
    cs = ' -- '.join(chords[:4])
    gd = {}
    remaining = max(0, 100 - gc)
    other_genres = [g for g in GENRES if g != genre][:5]
    if other_genres:
        count = len(other_genres)
        for i, sg in enumerate(other_genres):
            gd[sg] = round(remaining * (1 - i * 0.2) / count)
    notes = ['Tempo: ' + str(bpm), 'Key: ' + kd,
             'Chord richness: ' + str(len(set(chords))) + '/' + str(len(chords)),
             'Key confidence: ' + str(int(kconf*100)) + '%']
    if len(chords)>=4 and chords[:4]==['C','G','Am','F']:
        notes.append('I-V-vi-IV progression')
    mood = {'C':'bright','G':'warm','Am':'soft','F':'open'}.get(chords[0],'neutral') if chords else 'neutral'
    notes.append('Mood: ' + mood)
    waveform = extract_waveform(y)
    return {'success':True,'filename':os.path.basename(path),'duration':round(dur,1),'sample_rate':sr,
            'genre':genre,'genre_confidence':gc,'genre_distribution':gd,
            'tempo':bpm,'key':key,'mode':mode,'key_display':kd,
            'chords':chords,'chord_progression':cs,
            'pitch_range_low':lo,'pitch_range_high':hi,'key_confidence':kconf,
            'bpm_method':'flux+acorr',
            'chord_templates':'%d chords' % len(_build_chord_library()),
            'note_distribution':nd,'analysis_notes':notes,
            'melody':melody,'melody_segments':len(melody),
            'waveform':waveform,
            'format_supported':supported_formats()[0],
            'mp3_supported':supported_formats()[1],
            'engine':'v3 improved chroma'}

def extract_waveform(y, num_points=500):
     if len(y) == 0:
         return [0.0] * num_points
     step = max(1, len(y) // num_points)
     sampled = y[::step][:num_points]
     if len(sampled) < num_points:
         sampled = np.pad(sampled, (0, num_points - len(sampled)))
     mx = max(np.max(np.abs(sampled)), 1e-10)
     return [float(v / mx) for v in sampled]
 
