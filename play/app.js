// app.js
let ctx = null; 

let currentPreset = {
    waves: [], amps: [], mults: [], phases: [], fmRatios: [], fmIndices: [],
    adsr: [0.001, 0.3, 0.4, 0.299],
    sustain: 0.6,
    vset: 1.0
};

const canvas = document.getElementById('waveform');
const cctx = canvas.getContext('2d');

function drawWaveform() {
    if (!canvas || !cctx) return;
    const width = canvas.width;
    const height = canvas.height;
    cctx.clearRect(0, 0, width, height);
    
    cctx.beginPath();
    cctx.moveTo(0, height / 2);
    cctx.lineTo(width, height / 2);
    cctx.strokeStyle = '#888';
    cctx.lineWidth = 1;
    cctx.stroke();

    // Render a 15 Hz wave for 1.0 second (lets you see the ADSR)
    const samples = renderNote(15, 1.0, currentPreset, 44100);
    const step = Math.ceil(samples.length / width);

    cctx.beginPath();
    cctx.strokeStyle = '#FF5F15'; 
    cctx.lineWidth = 2;

    for (let i = 0; i < width; i++) {
        const sampleIdx = i * step;
        if (sampleIdx >= samples.length) break;
        const x = i;
        const y = (height / 2) - (samples[sampleIdx] * (height / 2 - 10));
        if (i === 0) cctx.moveTo(x, y);
        else cctx.lineTo(x, y);
    }
    cctx.stroke();
}

// --- 2. OSCILLATOR LOGIC ---
function updatePresetFromUI() {
    currentPreset.waves = [];
    currentPreset.amps = [];
    currentPreset.phases = [];
    currentPreset.mults = [];
    currentPreset.fmRatios = [];
    currentPreset.fmIndices = [];
    
    document.querySelectorAll('.osc-row').forEach(row => {
        if (row.classList.contains('disabled')) return;
        
        currentPreset.waves.push(row.querySelector('.osc-wave').value);
        currentPreset.amps.push(parseFloat(row.querySelector('.osc-amp').value));
        currentPreset.phases.push(parseFloat(row.querySelector('.osc-phase').value));
        currentPreset.mults.push(parseFloat(row.querySelector('.osc-mult').value));
        currentPreset.fmRatios.push(parseFloat(row.querySelector('.osc-fm-ratio').value));
        currentPreset.fmIndices.push(parseFloat(row.querySelector('.osc-fm-depth').value));
    });
    
    if (currentPreset.waves.length === 0) {
        currentPreset.waves.push('sin');
        currentPreset.amps.push(0);
        currentPreset.phases.push(0);
        currentPreset.mults.push(1);
        currentPreset.fmRatios.push(0);
        currentPreset.fmIndices.push(0);
    }
    
    drawWaveform();
}

function toggleWaveParams(selectEl) {
    const row = selectEl.closest('.osc-row');
    const isNoise = ['white', 'pink', 'brown'].includes(selectEl.value);
    
    row.querySelector('.osc-mult').disabled = isNoise;
    row.querySelector('.osc-phase').disabled = isNoise;
    row.querySelector('.osc-fm-ratio').disabled = isNoise;
    row.querySelector('.osc-fm-depth').disabled = isNoise;
}

document.querySelectorAll('.osc-row').forEach(row => {
    const waveSelect = row.querySelector('.osc-wave');
    waveSelect.addEventListener('change', (e) => {
        toggleWaveParams(e.target);
        updatePresetFromUI();
    });
    toggleWaveParams(waveSelect);

    const btn = row.querySelector('.toggle-btn');
    btn.addEventListener('click', () => {
        row.classList.toggle('disabled');
        btn.textContent = row.classList.contains('disabled') ? 'OFF' : 'ON';
        updatePresetFromUI();
    });
    
    row.querySelectorAll('input, select').forEach(input => {
        input.addEventListener('input', () => {
            if (input.type === 'range') {
                const valOutput = input.closest('label').querySelector('.osc-val');
                if (valOutput) {
                    if (input.classList.contains('osc-phase')) {
                        valOutput.textContent = input.value;
                    } else {
                        valOutput.textContent = parseFloat(input.value).toFixed(2);
                    }
                }
            }
            updatePresetFromUI();
        });
    });
});

// --- 3. ENVELOPE SLIDERS ---
function bindSlider(id, outId, key, index) {
    const s = document.getElementById(id);
    const o = document.getElementById(outId);
    
    const update = () => {
        const v = parseFloat(s.value);
        o.textContent = v.toFixed(2);
        
        if (key === 'sustain') currentPreset.sustain = v;
        else currentPreset.adsr[index] = v;
        
        drawWaveform(); 
    };
    
    s.addEventListener('input', update);
    update(); 
}

bindSlider('attack',  'a-out', 'attack',        0);
bindSlider('decay',   'd-out', 'decay',         1);
bindSlider('s-time',  'st-out', 'sustain_time', 2);
bindSlider('sustain', 's-out', 'sustain', -1);
bindSlider('release', 'r-out', 'release',       3);

updatePresetFromUI();

// --- WAVEFOLDER LOGIC ---
const wfToggle = document.getElementById('wavefolder-toggle');
const vsetSlider = document.getElementById('vset');
const vsetOut = document.getElementById('vset-out');

wfToggle.addEventListener('change', () => {
    vsetSlider.disabled = !wfToggle.checked;
    
    if (wfToggle.checked) {
        currentPreset.vset = parseFloat(vsetSlider.value);
    } else {
        currentPreset.vset = 1.0;
    }
    drawWaveform(); 
});

vsetSlider.addEventListener('input', () => {
    const v = parseFloat(vsetSlider.value);
    vsetOut.textContent = v.toFixed(2);
    currentPreset.vset = v;
    drawWaveform();
});

// --- 4. KEYBOARD & AUDIO ---
const NOTES = ['C4','C#4','D4','D#4','E4','F4','F#4','G4','G#4','A4','A#4','B4','C5'];
const kb = document.getElementById('keyboard');
NOTES.forEach(n => {
    const el = document.createElement('div');
    el.className = 'key' + (n.includes('#') ? ' black' : '');
    el.textContent = n;
    el.dataset.note = n;
    
    el.addEventListener('mousedown', () => {
        if (!ctx) { 
            alert('Please click "Enable Audio" first!'); 
            return; 
        }
        playNote(ctx, noteToHz(n), 1.2, currentPreset, masterGain);
    });
    
    kb.appendChild(el);
});

let masterGain = null;
let compressor = null;

document.getElementById('unlock').addEventListener('click', () => {
    if (!ctx) {
        try {
            if (navigator.audioSession) {
                navigator.audioSession.type = 'playback';
            }
        } catch (e) { /* silent fail */ }


        try {
            const silence = new Audio();
            silence.src = 'data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA';
            silence.play().catch(() => {});
        } catch (e) { /* silent fail */ }

        ctx = new (window.AudioContext || window.webkitAudioContext)();

        if (ctx && ctx.sampleRate) {
            const buffer = ctx.createBuffer(1, 1, 22050);
            const source = ctx.createBufferSource();
            source.buffer = buffer;
            source.connect(ctx.destination);
            source.start(0);
        }
        
        masterGain = ctx.createGain();
        const isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        masterGain.gain.value = isMobile ? 0.8 : 0.3; 
        
        compressor = ctx.createDynamicsCompressor();
        compressor.threshold.value = -10;
        compressor.knee.value = 10;
        compressor.ratio.value = 12;
        compressor.attack.value = 0.003;
        compressor.release.value = 0.25;
        
        masterGain.connect(compressor);
        compressor.connect(ctx.destination);
        
        document.getElementById('unlock').textContent = '🔊 Audio Enabled';
        document.getElementById('unlock').disabled = true;
    }
    if (ctx.state === 'suspended') ctx.resume();
});

let isPlaying = false;
let activeSources = [];
let playbackTimeout = null;

const scoreSelect = document.getElementById('score-select');
const playBtn = document.getElementById('play-score');

function stopPlayback() {
    activeSources.forEach(src => {
        try { src.stop(); } catch(e) {} 
    });
    activeSources = [];
    if (playbackTimeout) clearTimeout(playbackTimeout);
    
    isPlaying = false;
    playBtn.textContent = "▶ Play Excerpt";
}

scoreSelect.addEventListener('change', () => {
    if (isPlaying) stopPlayback();
});

playBtn.addEventListener('click', async () => {
    if (!ctx) { alert('Click "Enable Audio" first.'); return; }

    if (isPlaying) {
        stopPlayback();
        return;
    }

    isPlaying = true;
    playBtn.textContent = "⏹ Stop";

    const scoreName = scoreSelect.value;
    
    try {
        const res = await fetch(`scores/${scoreName}.json`);
        if (!res.ok) throw new Error("Score not found");
        
        const notes = await res.json();
        const t0 = ctx.currentTime + 0.1; 

        for (const n of notes) {
            const notesToPlay = Array.isArray(n.name) ? n.name : [n.name];
            const numNotes = notesToPlay.length; 
            
            for (const noteName of notesToPlay) {
                const freq = noteToHz(noteName);
                const samples = renderNote(freq, n.dur, currentPreset);
                const buf = ctx.createBuffer(1, samples.length, 44100);
                buf.copyToChannel(samples, 0);
                
                const src = ctx.createBufferSource();
                src.buffer = buf;
                
                const noteGain = ctx.createGain();
    
                noteGain.gain.value = 1.0 / Math.sqrt(numNotes); 
                
                noteGain.connect(masterGain);
                src.connect(noteGain);
                
                src.start(t0 + n.start);
                
                activeSources.push(src);
                activeSources.push(noteGain);
            }
        }
        const lastNote = notes[notes.length - 1];
        const totalDuration = (lastNote.start + lastNote.dur + 1.0) * 1000;
        
        playbackTimeout = setTimeout(() => {
            isPlaying = false;
            playBtn.textContent = "▶ Play Excerpt";
        }, totalDuration);
        
    } catch (err) {
        console.error(err);
        alert(`Could not load ${scoreName}.json. Did you export it to the scores folder?`);
        stopPlayback();
    }
});

// --- PRESET LOADER LOGIC ---
let availablePresets = {};

async function initPresets() {
    try {
        const res = await fetch('play/presets.json');
        availablePresets = await res.json();
        
        if (Array.isArray(availablePresets)) {
            const dict = {};
            availablePresets.forEach(p => {
                if (p.name) dict[p.name] = p;
            });
            availablePresets = dict;
        }

        const select = document.getElementById('preset-select');
        
        for (const name in availablePresets) {
            const opt = document.createElement('option');
            opt.value = name;
            // Format name: "electric_piano" -> "Electric Piano"
            opt.textContent = name.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
            select.appendChild(opt);
        }

        select.addEventListener('change', (e) => {
            if (e.target.value) {
                applyPresetToUI(availablePresets[e.target.value]);
            }
        });
    } catch (err) {
        console.warn("Could not load presets.json. Make sure the file is in the same folder.", err);
    }
}

function applyPresetToUI(preset) {
    const rows = document.querySelectorAll('.osc-row');

    rows.forEach(r => {
        r.classList.add('disabled');
        r.querySelector('.toggle-btn').textContent = 'OFF';
    });

    const nOsc = Math.min(preset.waves.length, 4);
    
    const setSlider = (row, cssClass, val, isPhase) => {
        const input = row.querySelector(cssClass);
        if (!input) return;
        input.value = val;
        const out = input.closest('label').querySelector('.osc-val');
        if (out) out.textContent = isPhase ? val : parseFloat(val).toFixed(2);
    };

    for (let i = 0; i < nOsc; i++) {
                const row = rows[i];
        row.classList.remove('disabled');
        row.querySelector('.toggle-btn').textContent = 'ON';
        
        const waveSelect = row.querySelector('.osc-wave');
        waveSelect.value = preset.waves[i];
        
        toggleWaveParams(waveSelect); 
        
        setSlider(row, '.osc-amp',      preset.amps ? preset.amps[i] : 1.0, false);
        setSlider(row, '.osc-phase',    preset.phases ? preset.phases[i] : 0, true);
        setSlider(row, '.osc-mult',     preset.mults ? preset.mults[i] : 1.0, false);
        setSlider(row, '.osc-fm-ratio', preset.fm_ratios ? preset.fm_ratios[i] : 0, false);
        setSlider(row, '.osc-fm-depth', preset.fm_indices ? preset.fm_indices[i] : 0, false);
    }
    if (preset.adsr_vals) {
        const setEnv = (id, outId, val) => {
            document.getElementById(id).value = val;
            document.getElementById(outId).textContent = parseFloat(val).toFixed(2);
        };
        setEnv('attack', 'a-out', preset.adsr_vals[0]);
        setEnv('decay', 'd-out', preset.adsr_vals[1]);
        setEnv('s-time', 'st-out', preset.adsr_vals[2]);
        setEnv('release', 'r-out', preset.adsr_vals[3]);
    }
    if (preset.sustain_val !== undefined) {
        document.getElementById('sustain').value = preset.sustain_val;
        document.getElementById('s-out').textContent = parseFloat(preset.sustain_val).toFixed(2);
    }

    const wfToggle = document.getElementById('wavefolder-toggle');
    const vsetSlider = document.getElementById('vset');
    const vsetOut = document.getElementById('vset-out');
    
    const isClipped = preset.clip === true || (preset.vset !== undefined && preset.vset < 1.0);
    
    if (isClipped) {
        wfToggle.checked = true;
        vsetSlider.disabled = false;
        
        const vsetVal = preset.vset !== undefined ? preset.vset : 0.8;
        vsetSlider.value = vsetVal;
        vsetOut.textContent = parseFloat(vsetVal).toFixed(2);
        
        currentPreset.vset = parseFloat(vsetVal);
    } else {
        wfToggle.checked = false;
        vsetSlider.disabled = true;
        
        currentPreset.vset = 1.0;
    }

    updatePresetFromUI(); 
}
// --- MIDI KEYBOARD SUPPORT ---
document.getElementById('connect-midi').addEventListener('click', async () => {
    if (!navigator.requestMIDIAccess) {
        alert('Web MIDI API is not supported in this browser. Please use Chrome or Edge.');
        return;
    }

    try {
        const midiAccess = await navigator.requestMIDIAccess();
        const btn = document.getElementById('connect-midi');
        btn.textContent = '🎹 MIDI Connected';
        btn.disabled = true;

        const inputs = midiAccess.inputs.values();
        let hasDevice = false;

        for (let input = inputs.next(); input && !input.done; input = inputs.next()) {
            hasDevice = true;
            input.value.onmidimessage = onMIDIMessage;
            console.log(`Listening to MIDI input: ${input.value.name}`);
        }

        if (!hasDevice) {
            alert('No MIDI input devices found. Please connect your keyboard.');
        }

    } catch (err) {
        console.error('MIDI access denied:', err);
        alert('Could not access MIDI devices.');
    }
});

// --- MIDI VOICE MANAGEMENT ---
const activeVoices = {};

function midiToHz(n) { return 440 * Math.pow(2, (n - 69) / 12); }

function startMidiVoice(noteNumber, velocity) {
    if (!ctx) return;
    if (activeVoices[noteNumber]) stopMidiVoice(noteNumber);
    
    const rawSamples = renderNote(midiToHz(noteNumber), 2.0, currentPreset, 44100, false);
    const buf = ctx.createBuffer(1, rawSamples.length, 44100);
    buf.copyToChannel(rawSamples, 0);
    
    const src = ctx.createBufferSource();
    src.buffer = buf;
    
    const gain = ctx.createGain();
    gain.gain.value = 0;
    src.connect(gain);
    gain.connect(masterGain);

    const vel = Math.max(velocity / 127, 0.05);
    const targetPeak = vel * 0.8;
    
    const [a, d, s, r] = currentPreset.adsr;
    const sum = (a + d + s + r) || 1.0;
    const attackT  = (a / sum) * 1.0;
    const decayT   = (d / sum) * 1.0;
    const releaseT = (r / sum) * 1.0;
    const sustainLevel = currentPreset.sustain * targetPeak;
    
    const now = ctx.currentTime;
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(targetPeak, now + attackT);
    gain.gain.linearRampToValueAtTime(sustainLevel, now + attackT + decayT);
    
    src.start(now);
    
    activeVoices[noteNumber] = { src, gain, releaseTime: releaseT };
}

function stopMidiVoice(noteNumber) {
    const voice = activeVoices[noteNumber];
    if (!voice) return;
    
    const now = ctx.currentTime;
    voice.gain.gain.cancelScheduledValues(now);
    voice.gain.gain.setValueAtTime(voice.gain.gain.value, now);
    voice.gain.gain.linearRampToValueAtTime(0, now + voice.releaseTime);
    
    voice.src.stop(now + voice.releaseTime + 0.05);
    delete activeVoices[noteNumber];
}

function onMIDIMessage(event) {
    const command = event.data[0] & 0xf0;
    const noteNumber = event.data[1];
    const velocity = event.data[2];
    
    if (!ctx) {
        console.warn('Enable audio first.');
        return;
    }
    
    if (command === 0x90 && velocity > 0) {
        startMidiVoice(noteNumber, velocity);
    }
    else if (command === 0x80 || (command === 0x90 && velocity === 0)) {
        stopMidiVoice(noteNumber);
    }
}
initPresets();