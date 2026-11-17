import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
import librosa
from scipy.fft import fft, fftfreq

#Sampling Frequency:
fs = 44100

def time(T=1):
    return np.linspace(0, T, int(T * fs), endpoint=False)

def sine_wave(freq, phase=0, amp=1, T=1):
    t = time(T)
    sin = amp*np.sin(2 * np.pi * freq * t + (phase/360) * 2 * np.pi)
    return sin

def square_wave(freq, phase=0, amp=1, T=1):
    sin = sine_wave(freq, phase+90, amp, T)
    sq = []
    for val in sin:
        if val >= 0:
            sq.append(amp)
        if val < 0:
            sq.append(-amp)
    return np.array(sq)

def sawtooth_wave(freq, phase=0, amp=1, T=1):
    t = time(T)
    div = (freq*t + (phase/ 360))
    saw = amp*2 * (div - np.floor(0.5 + div))
    return saw

def triangle_wave(freq, phase=0, amp=1, T=1):
    saw = sawtooth_wave(freq, phase, amp, T)
    tri = (abs(saw) - amp/2) * 2
    return tri

def noise_wave(color = 'white', amp=1, T=1):
    n = max(1, int(T * fs))
    white = np.random.randn(n)
    if color == 'white':
        sig = white
    elif color == 'pink':
        f = np.fft.rfftfreq(n, d=1/fs)
        f[0] = 1.0
        sig = np.fft.irfft(np.fft.rfft(white) / np.sqrt(f), n)
    elif color == 'brown':
        f = np.fft.rfftfreq(n, d=1/fs)
        f[0] = 1.0
        sig = np.fft.irfft(np.fft.rfft(white) / f, n)
    else:
        raise ValueError(f'Unknown noise color: {color!r}')
    peak = np.max(np.abs(sig)) + 1e-12
    return amp * sig / peak

def fm_wave(wave_type, freq, phase=0, amp=1, T=1, fm_ratio=1.0, fm_depth=0.0):
    t = time(T)
    phase_rad = (phase / 360.0) * 2 * np.pi
    modulator = fm_depth * np.sin(2 * np.pi * freq * fm_ratio * t)
    inst_phase = 2 * np.pi * freq * t + phase_rad + modulator

    if wave_type == 'sin':
        out = np.sin(inst_phase)
    elif wave_type == 'squ':
        out = np.sign(np.sin(inst_phase))
    elif wave_type == 'tri':
        out = (2 / np.pi) * np.arcsin(np.sin(inst_phase))
    elif wave_type == 'saw':
        norm = inst_phase / (2 * np.pi)
        out = 2 * (norm - np.floor(norm + 0.5))
    else:
        raise ValueError(f'fm_wave: unknown wave {wave_type!r}')
    return amp * out

def clip_wav(wav, vset):
    phase = ((wav + vset) / (4 * vset)) % 1.0
    wav = vset - 2 * vset * np.abs(2 * phase - 1)
    return wav

to_16 = lambda wav, amp: np.int16(wav * amp * (2**15 - 1))
def wave_to_file(wav, fname="temp.wav", amp=0.5, fs = 44100):
    wav = np.array(wav)
    wav = to_16(wav, amp)
    wavfile.write(fname, fs, wav)

pitched = {'sin', 'squ', 'tri', 'saw'}
noise = {'white', 'pink', 'brown'}
wavefns = {'sin':sine_wave, 'squ':square_wave, 'tri':triangle_wave, 'saw':sawtooth_wave}

def seq(waves = ['sin'], 
        amps = [],
        phases = [],
        mults = [],
        fm_ratios = [],
        fm_indices = [],
        notes = ['E4', 'D#4', 'E4', 'D#4', 'E4', 'B3', 'D4', 'C4', 'A3'], 
        note_lens=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.75],
        fname = 'tst.wav', 
        plot = False, 
        clip = False, 
        vset = 0.9,
        save_wave = False):
    
    for wave in waves:
        if not isinstance(wave, str):
            raise ValueError(f'Oscillators must be strings, got {type(wave)}')
        if wave not in pitched|noise:
            raise ValueError(f'{wave} is not a valid oscillator, try {pitched|noise}')

    nw = len(waves)
    amps = amps or [1.0]*nw
    phases = phases or [0.0]*nw
    mults = mults or [1.0]*nw
    fm_ratios = fm_ratios or [0.0] * nw
    fm_indices = fm_indices or [0.0] * nw
    if not (len(waves)==len(amps)==len(phases)==len(mults)==len(fm_ratios)==len(fm_indices)):
        raise ValueError(f'amps, phases, and mults must match len(waves): {nw}')

    if not (len(waves) == len(amps) == len(phases) == len(mults)==len(fm_ratios)==len(fm_indices)):
            raise ValueError(f'amps, phases, mults, fm_ratios, and fm_indices must match len(waves): {nw}')
    
    pitched_cfg = [(w, p, a, m, fr, fi) for w, p, a, m, fr, fi in zip(waves, phases, amps, mults, fm_ratios, fm_indices) if w in pitched]
    noise_cfg   = [(w, p, a, m) for w, p, a, m in zip(waves, phases, amps, mults) if w in noise]
    
    osc = np.zeros(int(sum(note_lens) * fs))
    pos = 0
    first_components = None
    first_freq = None
    first_n = None
    first_len = None
    
    for note, note_len in zip(notes, note_lens):
        if note is None or (isinstance(note, str) and note.lower() in ('rest', 'r', '')):
            pitches = []
        elif isinstance(note, str):
            pitches = [note]
        elif isinstance(note, (int, float)):
            pitches = [note]
        elif isinstance(note, (list, tuple)):
            pitches = [p for p in note
                       if p is not None
                       and not (isinstance(p, str) and p.lower() in ('rest', 'r'))]
        else:
            raise TypeError(f'note must be str/list/int/float/None, got {type(note)}')
    
        freqs = []
        for p in pitches:
            if isinstance(p, str):
                p = p.replace('-', 'b')
            f = float(p) if isinstance(p, (int, float)) else float(librosa.note_to_hz(p))
            if f >= 10:
                freqs.append(f)
    
        n = int(note_len * fs)
        wav = np.zeros(n)
        comps = []
    
        for f in freqs:
            for w, ph, a, m, fr, fi in pitched_cfg:
                if fi > 0.0:
                    arr = fm_wave(w, m * f, phase=ph, amp=a,
                                             T=note_len,
                                             fm_ratio=fr, fm_depth=fi)
                else:
                    arr = wavefns[w](m * f, phase=ph, amp=a, T=note_len)
                wav += arr[:n]
                comps.append((f'{w}×{m}', arr[:n]))
    
        for w, ph, a, m in noise_cfg:
            arr = noise_wave(color=w, T=note_len, amp=a)
            wav += arr[:n]
            comps.append((f'{w} noise', arr[:n]))
    
        if clip:
            wav = clip_wav(wav, vset)

        if plot and first_components is None and comps:
            first_components = comps
            first_freq = freqs[0] if freqs else None
            first_n, first_len = n, note_len

        osc[pos:pos + n] += wav
        pos += n

    if plot and first_components:
        fig, ax = plt.subplots(1, 2, figsize = (12, 5),gridspec_kw={'width_ratios':[2, 1]})

        x = np.arange(first_n) / fs
    
        tot = np.zeros(first_n)
        for label, arr in first_components:
            ax[0].plot(x, arr, alpha=0.5, label=label)
            tot += arr
    
        if clip:
            tot = clip_wav(tot, vset)
            ax[0].plot(x, tot, color='black', lw=2, label='Sum, Clipped')
        else:
            ax[0].plot(x, tot, color='black', lw=2, label='Sum')

        n_samples = len(tot)
        tot_fft = fft(tot)
        freqs= fftfreq(n_samples, 1 / fs)
        half_samples = n_samples // 2
        fft_x = freqs[:half_samples]
        fft_y = np.abs(tot_fft[:half_samples]) * 2 / n_samples

        ax[1].plot(fft_x, fft_y, color = 'black', label = 'FFT Spectrum')
        ax[1].plot([first_freq for i in range(3)], np.linspace(-0.1, max(fft_y)+0.1, 3), color = 'red', alpha = 0.5, label = 'Base Frequency')
        ax[1].legend(loc='upper right')
    
        ax[0].legend(loc='upper right')
        ax[0].set_title(f'Oscillator Components\nNote: {librosa.hz_to_note(first_freq)}, Freq: {round(first_freq, 2)} Hz')

        ax[1].set_title('FFT')
        ax[1].yaxis.tick_right()
        ax[1].yaxis.set_label_position("right")

        ax[0].set_xlabel('Time [s]')
        ax[1].set_xlabel('Frequency [Hz]')
        ax[0].set_ylabel('Amplitude')
        ax[1].set_ylabel('FFT Amplitude')
    
        xmax = min(3 / first_freq, first_len) if first_freq else first_len
        ax[0].set_xlim(0, xmax)
        ax[1].set_xlim(0, first_freq*10)
        ax[1].set_ylim(0-0.05, max(fft_y)+0.05)
    
        fig.tight_layout()
        plt.savefig('notes.png')
        plt.close(fig)
    
    if save_wave:
        wave_to_file(osc, fname=fname)
    return osc

