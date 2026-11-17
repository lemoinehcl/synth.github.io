import numpy as np
import matplotlib.pyplot as plt
from scipy.io import wavfile
import librosa
import src.oscillator
import json
from pathlib import Path
from scipy.fft import fft, fftfreq

fs = 44100 

pitched = {'sin', 'squ', 'tri', 'saw'}
noise = {'white', 'pink', 'brown'}
wavefns = {'sin':src.oscillator.sine_wave, 'squ':src.oscillator.square_wave, 'tri':src.oscillator.triangle_wave, 'saw':src.oscillator.sawtooth_wave}

def load_presets():
    current_dir = Path(__file__).resolve().parent
    
    possible_paths = [
        current_dir / 'presets.json',
        current_dir.parent / 'presets.json',
        current_dir.parent / 'play' / 'presets.json']

    for p in possible_paths:
        if p.exists():
            with open(p) as f:
                return json.load(f)
                
    raise FileNotFoundError(f"Could not find presets.json. Looked in:\n" + "\n".join([str(p) for p in possible_paths]))

def get_preset(name, presets):
    if name not in presets:
        raise KeyError(f"Unknown preset {name!r}. Available: {sorted(presets)}")
    return presets[name]

def get_fft(signal):
    n_samples = len(signal)
    tot_fft = fft(signal)
    freqs= fftfreq(n_samples, 1 / fs)
    half_samples = n_samples // 2
    fft_x = freqs[:half_samples]
    fft_y = np.abs(tot_fft[:half_samples]) * 2 / n_samples
    return fft_x, fft_y

def clip_wav(wav, vset):
    phase = ((wav + vset) / (4 * vset)) % 1.0
    wav = vset - 2 * vset * np.abs(2 * phase - 1)
    return wav
    
def adsr(waves = ['sin'], 
        amps = [],
        phases = [],
        mults = [],
        fm_ratios=[], 
        fm_indices=[],
        adsr_vals = [0.05, 0.15, 0.45, 0.35],
        sustain_val = 0.8,
        notes = ['E4', 'D#4', 'E4', 'D#4', 'E4', 'B3', 'D4', 'C4', 'A3'], 
        note_lens=[0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 0.75],
        fname = 'tst_mod.wav', 
        plot = False, 
        clip = False, 
        vset = 0.8,
        save_wave = False):

    if abs(sum(adsr_vals) - 1) > 1e-9:
        raise ValueError('ADSR values must equal 1!')

    for wave in waves:
        if not isinstance(wave, str) or wave not in pitched | noise:
            raise ValueError(f'{wave!r} is not a valid oscillator, try {pitched | noise}')

    nw = len(waves)
    amps   = amps   or [1.0] * nw
    phases = phases or [0.0] * nw
    mults  = mults  or [1.0] * nw
    fm_ratios = fm_ratios or [0.0] * nw
    fm_indices = fm_indices or [0.0] * nw

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
                    arr = src.oscillator.fm_wave(w, m * f, phase=ph, amp=a,
                                             T=note_len,
                                             fm_ratio=fr, fm_depth=fi)
                else:
                    arr = wavefns[w](m * f, phase=ph, amp=a, T=note_len)
                wav += arr[:n]
                comps.append((f'{w}×{m}', arr[:n]))

        for w, ph, a, m in noise_cfg:
            arr = src.oscillator.noise_wave(color=w, T=note_len, amp=a)
            wav += arr[:n]
            comps.append((f'{w} noise', arr[:n]))

        if clip:
            wav = clip_wav(wav, vset)

        peak = np.max(np.abs(wav))
        if peak > 0:
            wav = wav / peak

        a_len = int(n * adsr_vals[0])
        d_len = int(n * adsr_vals[1])
        s_len = int(n * adsr_vals[2])
        r_len = n - a_len - d_len - s_len
        env = np.concatenate([np.linspace(0, 1, a_len),
                              np.linspace(1, sustain_val, d_len),
                              np.full(s_len, sustain_val),
                              np.linspace(sustain_val, 0, max(1, r_len))])[:n]
        mod_wav = wav * env

        if plot and first_components is None and comps:
            first_components = comps
            first_freq = freqs[0] if freqs else None
            first_n, first_len = n, note_len

        osc[pos:pos + n] += mod_wav
        pos += n

    if plot and first_components:
        fig = plt.figure(figsize=(12, 8))
        ax1 = plt.subplot2grid((2, 3), (0, 0), colspan=3)
        ax2 = plt.subplot2grid((2, 3), (1, 0), colspan=2)
        ax3 = plt.subplot2grid((2, 3), (1, 2), rowspan=1)

        ax = [ax1, ax2, ax3]
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

        fft_x, fft_y = get_fft(tot)

        ax[1].plot(x, tot, color='C0', alpha=0.5, label='pre-ADSR')
        ax[1].plot(x, osc[:first_n], color='black', label='post-ADSR')

        ax[2].plot(fft_x, fft_y, color = 'black', label = 'FFT Spectrum')
        ax[2].plot([first_freq for i in range(3)], np.linspace(-0.1, max(fft_y)+0.1, 3), color = 'red', alpha = 0.5, label = 'Base Frequency')

        ax[0].legend(loc='upper right')
        ax[0].set_title(f'Oscillator Components\nNote: {librosa.hz_to_note(first_freq)}, Freq: {round(first_freq, 2)} Hz')
        ax[1].legend(loc='upper right')
        ax[1].set_title('ADSR')
        ax[2].legend(loc='upper right')
        ax[2].set_title('FFT')

        ax[2].yaxis.tick_right()
        ax[2].yaxis.set_label_position("right")

        ax[0].set_xlabel('Time [s]')
        ax[1].set_xlabel('Time [s]')
        ax[2].set_xlabel('Frequency [Hz]')
        ax[0].set_ylabel('Amplitude')
        ax[1].set_ylabel('Amplitude')
        ax[2].set_ylabel('FFT Amplitude')

        xmax = min(3 / first_freq, first_len) if first_freq else first_len
        ax[0].set_xlim(0, xmax)
        ax[2].set_xlim(0, first_freq*10)
        ax[2].set_ylim(-0.1, max(fft_y)+0.1)

        fig.tight_layout()
        plt.savefig(f'notes_mod.png')
        plt.close(fig)

    if save_wave:
        src.oscillator.wave_to_file(osc, fname=fname)
    return osc

def mod_seq(notes_lst, 
            note_lens_lst, 
            waves=['sin'], 
            amps=[], 
            phases=[], 
            mults=[], 
            fm_ratios=[], 
            fm_indices=[],
            adsr_vals = [0.05, 0.15, 0.45, 0.35], 
            sustain_val = 0.8, 
            clip=False, 
            fname="temp.wav", 
            vol=0.4):
    lens = [sum(nl) for nl in note_lens_lst]
    if not np.allclose(lens, lens[0], atol=1e-6):
        raise ValueError(f'Sum of the note lengths must be equal, sums are: {lens}')

    oscs = []
    for notes, note_lens in zip(notes_lst, note_lens_lst):
        if len(notes) != len(note_lens):
            raise ValueError(f'Must have same number of notes and note lengths: {len(notes), len(note_lens)}')
        osc = adsr(waves = waves, 
                   amps = amps,
                   phases = phases,
                   mults = mults,
                   fm_ratios=fm_ratios,
                   fm_indices=fm_indices,
                   adsr_vals = adsr_vals,
                   sustain_val = sustain_val,
                   notes = notes, 
                   note_lens=note_lens,
                   clip = clip, save_wave = False)
        oscs.append(np.asarray(osc, dtype=np.float64))

    n = max(len(o) for o in oscs)
    mix = np.zeros(n, dtype=np.float64)
    for o in oscs:
        mix[:len(o)] += o

    peak = np.max(np.abs(mix))
    if peak > 0:
        mix *= vol / peak

    combo_wav = np.int16(np.clip(mix, -1, 1) * (2**15 - 1))
    fname = f"{fname}"
    wavfile.write(fname, fs, combo_wav)

def fur_elise(waves=['sin'], 
              amps=[], 
              phases=[], 
              mults=[], 
              fm_ratios = [],
              fm_indices = [],
              adsr_vals = [0.05, 0.15, 0.45, 0.35], 
              sustain_val = 0.8, 
              clip=False, 
              vol=0.4):
    fname="fur_elise.wav"
    treble_notes = ['E5', 'D#5', 
                    'E5', 'D#5', 'E5', 'B4', 'D5', 'C5', 
                    'A4', 'rest', 'C3', 'E4', 'A4', 
                    'B4', 'rest', 'E4', 'G#4', 'B4',
                    'C5', 'rest', 'E4', 'E5', 'D#5',
                    'E5', 'D#5', 'E5', 'B4', 'D5', 'C5',
                    'A4', 'rest', 'C3', 'E4', 'A4', 
                    'B4', 'rest', 'E4', 'C5', 'B4',
                    'A4']
    treble_note_lens=[0.25, 0.25, 
                      0.25, 0.25, 0.25, 0.25, 0.25, 0.25, 
                      0.5, 0.25, 0.25, 0.25, 0.25, 
                      0.5, 0.25, 0.25, 0.25, 0.25,
                      0.5, 0.25, 0.25, 0.25, 0.25,
                      0.25, 0.25, 0.25, 0.25, 0.25, 0.25,
                      0.5, 0.25, 0.25, 0.25, 0.25,
                      0.5, 0.25, 0.25, 0.25, 0.25,
                      1.5]

    bass_notes = ['rest',
                  'rest',
                  'A2', 'E3', 'A3', 'rest',
                  'B2', 'E3', 'G#3', 'rest',
                  'A2', 'E3', 'A3', 'rest',
                  'rest',
                  'A2', 'E3', 'A3', 'rest',
                  'B2', 'E3', 'G#3', 'rest',
                  'A2', 'E3', 'A3', 'rest']
    bass_note_lens = [0.5,
                      1.5,
                      0.25, 0.25, 0.25, 0.75,
                      0.25, 0.25, 0.25, 0.75,
                      0.25, 0.25, 0.25, 0.75,
                      1.5,
                      0.25, 0.25, 0.25, 0.75,
                      0.25, 0.25, 0.25, 0.75,
                      0.25, 0.25, 0.25, 0.75]

    mod_seq(notes_lst=[treble_notes, bass_notes], note_lens_lst=[treble_note_lens, bass_note_lens], 
            waves=waves, amps=amps, phases=phases, mults=mults, fm_ratios=fm_ratios, fm_indices=fm_indices, adsr_vals=adsr_vals, 
            sustain_val=sustain_val, clip=clip, fname=fname, vol=vol)