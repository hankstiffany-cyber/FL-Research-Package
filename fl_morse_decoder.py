"""
Morse Code Decoder for FL YouTube Audio
Attempts to decode potential Morse patterns from ultrasonic frequencies.
"""

import os
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import matplotlib.pyplot as plt
from scipy import signal
from scipy.ndimage import gaussian_filter1d

# Paths
BASE_DIR = Path(__file__).parent
DEEP_DIR = BASE_DIR / "data" / "deep_analysis"
OUTPUT_DIR = BASE_DIR / "data" / "morse_decode"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Morse code dictionary
MORSE_TO_CHAR = {
    '.-': 'A', '-...': 'B', '-.-.': 'C', '-..': 'D', '.': 'E',
    '..-.': 'F', '--.': 'G', '....': 'H', '..': 'I', '.---': 'J',
    '-.-': 'K', '.-..': 'L', '--': 'M', '-.': 'N', '---': 'O',
    '.--.': 'P', '--.-': 'Q', '.-.': 'R', '...': 'S', '-': 'T',
    '..-': 'U', '...-': 'V', '.--': 'W', '-..-': 'X', '-.--': 'Y',
    '--..': 'Z', '.----': '1', '..---': '2', '...--': '3', '....-': '4',
    '.....': '5', '-....': '6', '--...': '7', '---..': '8', '----.': '9',
    '-----': '0', '.-.-.-': '.', '--..--': ',', '..--..': '?',
    '.----.': "'", '-.-.--': '!', '-..-.': '/', '-.--.': '(',
    '-.--.-': ')', '.-...': '&', '---...': ':', '-.-.-.': ';',
    '-...-': '=', '.-.-.': '+', '-....-': '-', '..--.-': '_',
    '.-..-.': '"', '...-..-': '$', '.--.-.': '@', '...---...': 'SOS'
}


def load_audio(filename):
    """Load audio file."""
    import librosa

    wav_file = DEEP_DIR / f"{filename.replace('_', ' ')}.wav"
    if not wav_file.exists():
        wav_file = DEEP_DIR / f"{filename}.wav"

    if wav_file.exists():
        y, sr = librosa.load(str(wav_file), sr=None)
        return y, sr

    raise FileNotFoundError(f"Could not find {filename}")


def extract_morse_envelope(y, sr, freq_band=(17000, 19000)):
    """Extract envelope from ultrasonic frequency band."""
    nyquist = sr / 2
    low = freq_band[0] / nyquist
    high = min(freq_band[1] / nyquist, 0.99)

    # Bandpass filter
    b, a = signal.butter(4, [low, high], btype='band')
    filtered = signal.filtfilt(b, a, y)

    # Envelope detection
    analytic = signal.hilbert(filtered)
    envelope = np.abs(analytic)

    # Smooth envelope
    window_ms = 5  # 5ms smoothing
    window_samples = int(sr * window_ms / 1000)
    envelope_smooth = gaussian_filter1d(envelope, window_samples)

    return envelope_smooth


def detect_morse_timing(envelope, sr, threshold_factor=1.5):
    """
    Detect marks (signals) and spaces from envelope.
    Returns timing information for Morse decoding.
    """
    # Adaptive threshold
    threshold = np.mean(envelope) + threshold_factor * np.std(envelope)

    # Binary signal
    binary = envelope > threshold

    # Find transitions
    diff = np.diff(binary.astype(int))
    rising = np.where(diff == 1)[0]
    falling = np.where(diff == -1)[0]

    if len(rising) == 0 or len(falling) == 0:
        return [], [], []

    # Align rising and falling edges
    if falling[0] < rising[0]:
        falling = falling[1:]

    min_len = min(len(rising), len(falling))
    rising = rising[:min_len]
    falling = falling[:min_len]

    # Calculate durations in milliseconds
    mark_durations = (falling - rising) / sr * 1000

    # Calculate spaces (gaps between marks)
    if len(rising) > 1:
        space_durations = (rising[1:] - falling[:-1]) / sr * 1000
    else:
        space_durations = np.array([])

    # Get timestamps
    mark_times = rising / sr

    return mark_durations, space_durations, mark_times


def adaptive_morse_decode(mark_durations, space_durations, speed_factor=1.0):
    """
    Decode Morse code with adaptive timing.
    Standard Morse: dot=1 unit, dash=3 units, inter-element=1 unit,
                   inter-letter=3 units, inter-word=7 units
    """
    if len(mark_durations) == 0:
        return "", []

    # Estimate timing from data
    # Assume most marks are dots (short)
    sorted_marks = np.sort(mark_durations)

    # Find natural clustering between dots and dashes
    if len(sorted_marks) > 10:
        # Use histogram to find clusters
        hist, bins = np.histogram(sorted_marks, bins=50)

        # Find valleys (potential boundary between dot/dash)
        smoothed = gaussian_filter1d(hist.astype(float), 2)

        # Simple approach: use median as initial estimate
        dot_estimate = np.percentile(sorted_marks, 25)
        dash_threshold = dot_estimate * 2.5 * speed_factor
    else:
        dot_estimate = np.median(mark_durations)
        dash_threshold = dot_estimate * 2.5 * speed_factor

    print(f"  Timing estimates:")
    print(f"    Dot duration: ~{dot_estimate:.1f}ms")
    print(f"    Dash threshold: >{dash_threshold:.1f}ms")

    # Decode marks
    morse_elements = []
    for duration in mark_durations:
        if duration > dash_threshold:
            morse_elements.append('-')
        else:
            morse_elements.append('.')

    # Use spaces to group into letters and words
    if len(space_durations) == 0:
        return ''.join(morse_elements), morse_elements

    # Estimate space timing
    inter_element = dot_estimate * speed_factor  # 1 unit
    inter_letter = dot_estimate * 3 * speed_factor  # 3 units
    inter_word = dot_estimate * 6 * speed_factor  # 7 units (use 6 for tolerance)

    print(f"    Inter-letter threshold: >{inter_letter:.1f}ms")
    print(f"    Inter-word threshold: >{inter_word:.1f}ms")

    # Build morse string with separators
    morse_string = morse_elements[0]
    for i, space in enumerate(space_durations):
        if i + 1 < len(morse_elements):
            if space > inter_word:
                morse_string += ' / '  # Word separator
            elif space > inter_letter:
                morse_string += ' '  # Letter separator
            morse_string += morse_elements[i + 1]

    return morse_string, morse_elements


def morse_to_text(morse_string):
    """Convert Morse string to text."""
    words = morse_string.split(' / ')
    decoded_words = []

    for word in words:
        letters = word.strip().split(' ')
        decoded_letters = []
        for letter in letters:
            letter = letter.strip()
            if letter in MORSE_TO_CHAR:
                decoded_letters.append(MORSE_TO_CHAR[letter])
            elif letter:
                decoded_letters.append(f'[{letter}]')  # Unknown sequence
        decoded_words.append(''.join(decoded_letters))

    return ' '.join(decoded_words)


def analyze_morse_patterns(mark_durations, space_durations, title):
    """Visualize Morse timing patterns."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(f"Morse Timing Analysis: {title}", fontsize=14)

    # 1. Mark duration histogram
    ax = axes[0, 0]
    if len(mark_durations) > 0:
        ax.hist(mark_durations, bins=50, range=(0, max(100, np.percentile(mark_durations, 95))),
                alpha=0.7, edgecolor='black')

        # Mark typical Morse timing
        median = np.median(mark_durations)
        ax.axvline(x=median, color='r', linestyle='--', label=f'Median: {median:.1f}ms')
        ax.axvline(x=median*2.5, color='g', linestyle='--', label=f'Dash threshold: {median*2.5:.1f}ms')
    ax.set_xlabel('Duration (ms)')
    ax.set_ylabel('Count')
    ax.set_title('Mark (ON) Duration Distribution')
    ax.legend()

    # 2. Space duration histogram
    ax = axes[0, 1]
    if len(space_durations) > 0:
        ax.hist(space_durations, bins=50, range=(0, min(500, np.percentile(space_durations, 95))),
                alpha=0.7, edgecolor='black', color='orange')

        median_space = np.median(space_durations)
        ax.axvline(x=median_space, color='r', linestyle='--', label=f'Median: {median_space:.1f}ms')
    ax.set_xlabel('Duration (ms)')
    ax.set_ylabel('Count')
    ax.set_title('Space (OFF) Duration Distribution')
    ax.legend()

    # 3. Mark vs following space scatter
    ax = axes[1, 0]
    if len(mark_durations) > 1 and len(space_durations) > 0:
        min_len = min(len(mark_durations)-1, len(space_durations))
        ax.scatter(mark_durations[:min_len], space_durations[:min_len], alpha=0.5, s=10)
        ax.set_xlabel('Mark Duration (ms)')
        ax.set_ylabel('Following Space Duration (ms)')
        ax.set_title('Mark vs Space Correlation')

    # 4. Sequence of first 200 elements
    ax = axes[1, 1]
    n_show = min(200, len(mark_durations))
    if n_show > 0:
        x = np.arange(n_show)
        ax.bar(x, mark_durations[:n_show], width=0.8, alpha=0.7, label='Marks')

        # Color code dots vs dashes
        median = np.median(mark_durations)
        colors = ['blue' if d < median*2 else 'red' for d in mark_durations[:n_show]]
        ax.bar(x, mark_durations[:n_show], width=0.8, color=colors, alpha=0.7)

        ax.set_xlabel('Element Index')
        ax.set_ylabel('Duration (ms)')
        ax.set_title(f'First {n_show} Elements (blue=dot, red=dash)')

    plt.tight_layout()
    output_path = OUTPUT_DIR / f"{title}_morse_timing.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path.name}")


def try_multiple_speeds(mark_durations, space_durations):
    """Try decoding at multiple speed factors."""
    results = []

    for speed in [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
        morse_string, elements = adaptive_morse_decode(mark_durations, space_durations, speed)
        text = morse_to_text(morse_string)

        # Score based on recognizable characters
        recognized = sum(1 for c in text if c.isalnum() or c == ' ')
        total = len(text.replace('[', '').replace(']', ''))
        score = recognized / max(1, total)

        results.append({
            'speed': speed,
            'morse': morse_string[:200] + '...' if len(morse_string) > 200 else morse_string,
            'text': text[:100] + '...' if len(text) > 100 else text,
            'score': score,
            'n_chars': len(text)
        })

    return results


def main():
    print("=" * 60)
    print("Morse Code Decoder for FL Audio")
    print("=" * 60)

    # Load "A Wedding at the Last Forest"
    print("\nLoading audio...")
    y, sr = load_audio("A Wedding at the Last Forest")
    print(f"  Duration: {len(y)/sr:.1f}s @ {sr}Hz")

    # Try multiple frequency bands
    freq_bands = [
        (16000, 18000),
        (17000, 19000),
        (18000, 20000),
        (15000, 17000),
    ]

    all_results = {}

    for freq_band in freq_bands:
        print(f"\n{'='*50}")
        print(f"Analyzing frequency band: {freq_band[0]/1000:.0f}-{freq_band[1]/1000:.0f}kHz")
        print('='*50)

        # Extract envelope
        envelope = extract_morse_envelope(y, sr, freq_band)

        # Try different threshold factors
        for thresh in [1.0, 1.5, 2.0, 2.5]:
            print(f"\n  Threshold factor: {thresh}")

            # Detect timing
            mark_dur, space_dur, mark_times = detect_morse_timing(envelope, sr, thresh)

            if len(mark_dur) < 10:
                print(f"    Too few marks detected ({len(mark_dur)}), skipping...")
                continue

            print(f"    Detected {len(mark_dur)} marks")
            print(f"    Mark duration range: {mark_dur.min():.1f} - {mark_dur.max():.1f}ms")
            print(f"    Mean mark duration: {np.mean(mark_dur):.1f}ms")

            # Visualize timing
            title = f"Wedding_{freq_band[0]//1000}k-{freq_band[1]//1000}k_thresh{thresh}"
            analyze_morse_patterns(mark_dur, space_dur, title)

            # Try decoding at multiple speeds
            print("\n    Attempting decode at various speeds:")
            results = try_multiple_speeds(mark_dur, space_dur)

            for r in results:
                if r['score'] > 0.3 or r['n_chars'] > 20:
                    print(f"\n    Speed {r['speed']}x (score: {r['score']:.2f}):")
                    print(f"      Morse: {r['morse'][:80]}...")
                    print(f"      Text:  {r['text']}")

            all_results[f"{freq_band}_{thresh}"] = results

    # Summary of best results
    print("\n" + "=" * 60)
    print("BEST DECODING ATTEMPTS")
    print("=" * 60)

    best_results = []
    for key, results in all_results.items():
        for r in results:
            if r['score'] > 0.2 and r['n_chars'] > 10:
                best_results.append((key, r))

    best_results.sort(key=lambda x: x[1]['score'], reverse=True)

    for key, r in best_results[:10]:
        print(f"\n{key} @ {r['speed']}x speed:")
        print(f"  Score: {r['score']:.2f}")
        print(f"  Text: {r['text']}")

    # Save detailed results
    output_file = OUTPUT_DIR / "morse_decode_results.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("FL Audio Morse Decoding Results\n")
        f.write("=" * 60 + "\n\n")

        for key, results in all_results.items():
            f.write(f"\n{key}\n")
            f.write("-" * 40 + "\n")
            for r in results:
                f.write(f"  Speed {r['speed']}x: {r['text']}\n")

    print(f"\n\nDetailed results saved to: {output_file}")
    print(f"Visualizations saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
