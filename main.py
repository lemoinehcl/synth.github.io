import os
from music21 import converter
import src.reader
import json
import librosa

def main(input_fname='turkish_march.mxl', output_fname='output'):
    print("🎹 Starting Python Synthesizer Engine...")
    
    mxl_path = os.path.join('examples', input_fname)
    if not os.path.exists(mxl_path):
        print(f"❌ Error: Could not find {mxl_path}.")
        return

    print(f"📖 Parsing {mxl_path}...")
    score = converter.parse(mxl_path)

    print("🎵 Rendering audio to WAV...")
    events = src.reader.read_score(
        score, 
        preset='electric_piano', 
        fname=f'output/{output_fname}.wav'
    )

    print("📦 Exporting to JSON for the web playground...")
    lst = []
    for event in events:
        if event['type'] == 'note':  
            name = event['name']
            if isinstance(name, str):
                midi_num = librosa.note_to_midi(name)
                name = librosa.midi_to_note(midi_num).replace('\u266f', '#')
            elif isinstance(name, tuple):
                midi_num = [librosa.note_to_midi(n) for n in name]
                name = tuple([librosa.midi_to_note(m).replace('\u266f', '#') for m in midi_num])
            lst.append({'name': name, 'start': event['start'], 'dur': event['dur']})

    json_path = f'output/{output_fname}.json'
    os.makedirs('output', exist_ok=True)
    with open(json_path, 'w') as f:
        json.dump(lst, f, indent=2)

    print("✅ Success!")
    print(f"   - Audio saved to: output/{output_fname}.wav")
    print(f"   - JSON saved to:  output/{output_fname}.json")

if __name__ == "__main__":
    main()