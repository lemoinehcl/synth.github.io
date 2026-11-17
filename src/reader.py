from music21 import *
import src.modulator
import numpy as np
from scipy.io import wavfile
import os
import json
import librosa

fs = 44100

def kind_priority(kind):
    return {'dyn': 0, 'crescendo': 1, 'diminuendo': 1, 'stop': 2}.get(kind, 1)

def read_score(score,
               waves=['sin'], 
               amps=[], 
               phases=[], 
               mults=[],
               fm_ratios=[], 
               fm_indices=[],
               adsr_vals=[0.05, 0.15, 0.45, 0.35], 
               sustain_val=0.8,
               clip=False, 
               vset = 0.8,
               fname="read_tst.wav",
               inherit_dynamics=True,
               preset = None):

    events = []
    max_end = 0

    global_temp = score.recurse().getElementsByClass(tempo.MetronomeMark).first()
    if not global_temp:
        global_temp = tempo.MetronomeMark(number=120.0)

    part_segments = [None] * len(score.parts)

    for part_idx, part in enumerate(score.parts):
        part.stripTies(inPlace=True)
        current_ql = 0.0
        main_ts = part.recurse().getElementsByClass(meter.TimeSignature).first()

        timeline = []

        for m in part.getElementsByClass('Measure'):
            ts = m.timeSignature or main_ts
            if not ts:
                continue
            if m.number == 1 and m.duration.quarterLength < ts.barDuration.quarterLength:
                max_len = m.duration.quarterLength
            else:
                max_len = ts.barDuration.quarterLength

            for d in m.recurse().getElementsByClass(dynamics.Dynamic):
                try:
                    local_off = d.getOffsetInHierarchy(m)
                except Exception:
                    local_off = d.offset
                vol = d.volumeScalar if d.volumeScalar is not None else 1.0
                timeline.append((current_ql + local_off, 'dyn', vol))
                events.append({
                    'name': d.value,
                    'start': global_temp.durationToSeconds(current_ql + local_off),
                    'dur': 0.0, 'type': 'dynamic', 'part': part_idx,
                    'offset_ql': current_ql + local_off, 'volume': vol,
                })

            for w in m.recurse().getElementsByClass(dynamics.DynamicWedge):
                try:
                    local_off = w.getOffsetInHierarchy(m)
                except Exception:
                    local_off = w.offset
                timeline.append((current_ql + local_off, w.type, None))

            streams = m.voices if m.voices else [m]
            max_actual_ql = 0.0
            
            for v in streams:
                removed = 0
                for r in list(v.getElementsByClass(note.Rest)):
                    style = getattr(r, 'style', None)
                    is_hidden = False
                    
                    if style:
                        if getattr(style, 'hideObjectOnPrint', False):
                            is_hidden = True
                        color = getattr(style, 'color', None)
                        if isinstance(color, str) and color.lower() in ('gray', 'grey', '#808080', '#a0a0a0'):
                            is_hidden = True
                    
                    if is_hidden:
                        if r.offset == 0:
                            removed += r.duration.quarterLength
                        r.activeSite.remove(r)

                if removed > 0:
                    for e in v.notesAndRests:
                        e.offset = max(0, e.offset - removed)

                for e in v.notesAndRests:
                    max_actual_ql = max(max_actual_ql, e.offset + e.duration.quarterLength)

            if max_actual_ql > 0:
                max_len = min(max_actual_ql, ts.barDuration.quarterLength)
            else:
                max_len = ts.barDuration.quarterLength

            for v in streams:
                for n in v.notesAndRests:
                    if not isinstance(n, (note.Note, chord.Chord)):
                        continue
                    offset = n.offset
                    dur = n.duration.quarterLength
                    
                    while offset >= max_len:
                        offset -= max_len
                        
                    if offset < 0:
                        continue
                    if dur > 4 * max_len:
                        dur = 4 * max_len
                    if dur <= 0:
                        continue

                    start_ql = current_ql + offset
                    start = global_temp.durationToSeconds(start_ql)
                    dur_s = global_temp.durationToSeconds(dur)
                    if start + dur_s > max_end:
                        max_end = start + dur_s

                    if isinstance(n, note.Note):
                        name = n.nameWithOctave.replace('-', 'b')
                    else:
                        name = tuple(p.nameWithOctave.replace('-', 'b') for p in n.pitches)

                    events.append({
                        'name': name, 'start': start, 'dur': dur_s,
                        'start_ql': start_ql, 'dur_ql': dur,
                        'type': 'note', 'part': part_idx,
                    })

            current_ql += max_len

        part_end_ql = current_ql

        timeline.sort(key=lambda x: (x[0], kind_priority(x[1])))
        segments = []
        current_vol = 1.0
        active_wedge = None

        for offset, kind, val in timeline:
            if kind == 'dyn':
                if active_wedge:
                    _, wstart, wstart_vol = active_wedge
                    segments.append((wstart, offset, wstart_vol, val))
                    active_wedge = None
                current_vol = val
                segments.append((offset, offset, val, val))

            elif kind in ('crescendo', 'diminuendo'):
                if active_wedge:
                    _, wstart, wstart_vol = active_wedge
                    segments.append((wstart, offset, wstart_vol, current_vol))
                active_wedge = (kind, offset, current_vol)

            elif kind == 'stop':
                if active_wedge:
                    _, wstart, wstart_vol = active_wedge
                    segments.append((wstart, offset, wstart_vol, current_vol))
                    active_wedge = None

        if active_wedge:
            _, wstart, wstart_vol = active_wedge
            segments.append((wstart, part_end_ql, wstart_vol, current_vol))

        part_segments[part_idx] = segments

    if inherit_dynamics and part_segments and part_segments[0]:
        master = list(part_segments[0])
        for i in range(1, len(part_segments)):
            if not part_segments[i]:
                part_segments[i] = list(master)

    events.sort(key=lambda e: e['start'])

    def volume_at(ql_pos, part_idx):
        segs = part_segments[part_idx]
        if not segs:
            return 1.0
        vol = 1.0
        for s, e, sv, ev in segs:
            if s > ql_pos:
                break
            if s == e:
                vol = sv
            elif ql_pos <= e:
                p = (ql_pos - s) / (e - s) if e > s else 1.0
                return sv + (ev - sv) * p
            else:
                vol = ev
        return vol

    wav = np.zeros(int(max_end * fs) + 1)

    for event in events:
        if event['type'] != 'note':
            continue

        p = event['part']
        dyn_start = volume_at(event['start_ql'], p)
        dyn_end = volume_at(event['start_ql'] + event['dur_ql'], p)

        if preset == None:
            audio = src.modulator.adsr(waves=waves, 
                                       amps=amps, 
                                       phases=phases, 
                                       mults=mults, 
                                       fm_ratios=fm_ratios, 
                                       fm_indices=fm_indices,
                                       adsr_vals=adsr_vals, 
                                       sustain_val=sustain_val,
                                       notes=[event['name']], 
                                       note_lens=[event['dur']],
                                       clip=clip, 
                                       vset = vset,
                                       save_wave=False)
        else:
            presets = src.modulator.load_presets()
            audio = src.modulator.adsr(**presets[preset],
                                       notes=[event['name']], 
                                       note_lens=[event['dur']],
                                       save_wave=False)
        
        audio = np.asarray(audio)
        n = len(audio)

        if n > 0:
            if abs(dyn_end - dyn_start) > 1e-6:
                audio = audio * np.linspace(dyn_start, dyn_end, n)
            else:
                audio = audio * dyn_start

        start_idx = round(event['start'] * fs)
        end_idx = start_idx + n
        if end_idx > len(wav):
            wav = np.pad(wav, (0, end_idx - len(wav)))
        wav[start_idx:end_idx] += audio

    vol = 0.5
    peak = np.max(np.abs(wav))
    if peak > 0:
        wav *= vol / peak

    combo_wav = np.int16(np.clip(wav, -1, 1) * (2**15 - 1))
    script_dir = os.path.dirname(os.path.realpath(__file__))
    out_path = f"{fname}"
    wavfile.write(out_path, fs, combo_wav)

    return events

def save_json(score, fname='tst.json'):
    events = read_score(score, 
               preset='electric_piano',
               fname='output.wav')
    lst = []
    for event in events:
        if event['type']=='note':  
            name = event['name']
            if isinstance(name, str):
                midi_num = librosa.note_to_midi(name)
                name = librosa.midi_to_note(midi_num).replace('\u266f', '#')
            elif isinstance(name, tuple):
                midi_num = [librosa.note_to_midi(n) for n in name]
                name = tuple([librosa.midi_to_note(m).replace('\u266f', '#') for m in midi_num])
            lst.append({'name':name, 'start':event['start'], 'dur':event['dur']})

    with open(fname, 'w') as f:
        json.dump(lst, f, indent=2)