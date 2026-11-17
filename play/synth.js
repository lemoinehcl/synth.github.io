// synth.js
const NOTE_NAMES = {
  C:0, 'C#':1, 'Db':1,
  D:2, 'D#':3, 'Eb':3,
  E:4, 'Fb':4,
  F:5, 'F#':6, 'Gb':6,
  G:7, 'G#':8, 'Ab':8,
  A:9, 'A#':10, 'Bb':10,
  B:11, 'Cb':11
};

function noteToHz(n) {
  const m = n.match(/^([A-G][#b]?)(-?\d+)$/);
  if (!m) {
      console.warn("Could not parse note:", n);
      return 440;
  }
  const midi = (parseInt(m[2]) + 1) * 12 + NOTE_NAMES[m[1]];
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function renderNote(freq, dur, opts, sampleRate = 44100, applyADSR = true) {
  const n = Math.floor(dur * sampleRate);
  const out = new Float32Array(n);
  const { waves, amps, mults, phases, fmRatios, fmIndices, adsr, sustain, vset } = opts;

  const noiseStates = waves.map(w => {
    if (w === 'pink') return { b0:0, b1:0, b2:0, b3:0, b4:0, b5:0, b6:0 };
    if (w === 'brown') return { lastOut: 0 };
    return null;
  });

  for (let i = 0; i < n; i++) {
    const t = i / sampleRate;
    let sum = 0;

    for (let w = 0; w < waves.length; w++) {
      const waveType = waves[w];
      const amp = (amps && amps[w]) ? amps[w] : 1.0;
      let s = 0;

      if (waveType === 'white' || waveType === 'pink' || waveType === 'brown') {
        // --- Noise ---
        const white = Math.random() * 2 - 1;
        
        if (waveType === 'white') {
          s = white;
        } else if (waveType === 'pink') {
          // Paul Kellet's economy pink noise filter
          const st = noiseStates[w];
          st.b0 = 0.99886 * st.b0 + white * 0.0555179;
          st.b1 = 0.99332 * st.b1 + white * 0.0750759;
          st.b2 = 0.96900 * st.b2 + white * 0.1538520;
          st.b3 = 0.86650 * st.b3 + white * 0.3104856;
          st.b4 = 0.55000 * st.b4 + white * 0.5329522;
          st.b5 = -0.7616  * st.b5 - white * 0.0168980;
          s = st.b0 + st.b1 + st.b2 + st.b3 + st.b4 + st.b5 + st.b6 + white * 0.5362;
          st.b6 = white * 0.115926;
          s *= 0.11;
        } else if (waveType === 'brown') {
          const st = noiseStates[w];
          st.lastOut = (st.lastOut + (0.02 * white)) / 1.02;
          s = st.lastOut * 3.5;
        }
      } else {
        // --- Pitched Oscillators ---
        const m = (mults && mults[w]) ? mults[w] : 1.0;
        const f = m * freq;
        const ph = (phases && phases[w]) ? phases[w] : 0;
        const phaseOffset = (ph / 360) * 2 * Math.PI;
        const basePhase = 2 * Math.PI * f * t + phaseOffset;
        
        const mod = (fmIndices && fmIndices[w] > 0)
          ? fmIndices[w] * Math.sin(2 * Math.PI * f * fmRatios[w] * t)
          : 0;
          
        const inst = basePhase + mod;
        
        switch (waveType) {
          case 'sin': s = Math.sin(inst); break;
          case 'squ': s = Math.sign(Math.sin(inst)); break;
          case 'tri': s = (2/Math.PI) * Math.asin(Math.sin(inst)); break;
          case 'saw': 
            const nm = inst / (2 * Math.PI); 
            s = 2 * (nm - Math.floor(nm + 0.5)); 
            break;
        }
      }
      sum += amp * s;
    }
    out[i] = sum;
  }
  
  let peak = 0;
  for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(out[i]));
  if (peak > 0) for (let i = 0; i < n; i++) out[i] /= peak;

  if (vset < 1) {
    for (let i = 0; i < n; i++) {
      const ph = (((out[i] + vset) / (4 * vset)) % 1 + 1) % 1;
      
      out[i] = vset - 2 * vset * Math.abs(2 * ph - 1);
    }
  }

  if (!applyADSR) return out;

  const adsrSum = (adsr[0] + adsr[1] + adsr[2] + adsr[3]) || 1.0;
  
  const aLen = Math.floor(n * (adsr[0] / adsrSum));
  const dLen = Math.floor(n * (adsr[1] / adsrSum));
  const sLen = Math.floor(n * (adsr[2] / adsrSum));
  const rLen = n - aLen - dLen - sLen; 
  
  for (let i = 0; i < n; i++) {
    let env;
    if (i < aLen)                     env = i / (aLen || 1); // Attack
    else if (i < aLen + dLen)         env = 1 - (1 - sustain) * ((i - aLen) / (dLen || 1)); // Decay
    else if (i < aLen + dLen + sLen)  env = sustain; // Sustain (flat hold)
    else                              env = sustain * (1 - (i - aLen - dLen - sLen) / (rLen || 1)); // Release
    
    out[i] *= env;
  }
  
  return out;
}

function playNote(audioCtx, freq, dur, opts, destinationNode) {
  if (!audioCtx) return;
  
  const sampleRate = audioCtx.sampleRate; 
  const samples = renderNote(freq, dur, opts, sampleRate);
  const buf = audioCtx.createBuffer(1, samples.length, sampleRate);
  buf.copyToChannel(samples, 0);
  
  const src = audioCtx.createBufferSource();
  src.buffer = buf;
  src.connect(destinationNode || audioCtx.destination);
  src.start();
}