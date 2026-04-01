"""
Deep spectrogram analysis for a specific FL YouTube audio file.
Focuses on finding hidden patterns, steganography, or encoded messages.
"""

import os
import sys
import subprocess
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import numpy as np
import matplotlib.pyplot as plt
import librosa
import librosa.display
from scipy import signal
from scipy.ndimage import gaussian_filter

# Paths
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "data" / "youtube_audio"
OUTPUT_DIR = BASE_DIR / "data" / "deep_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg path
FFMPEG_PATH = Path(os.environ.get('LOCALAPPDATA', '')) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-8.0.1-full_build" / "bin" / "ffmpeg.exe"


def load_audio(filename):
    """Load audio file, converting if necessary."""
    audio_file = AUDIO_DIR / filename

    if not audio_file.exists():
        # Try to find it
        matches = list(AUDIO_DIR.glob(f"*{filename}*"))
        if matches:
            audio_file = matches[0]
        else:
            raise FileNotFoundError(f"Could not find {filename}")

    print(f"Loading: {audio_file.name}")

    # Convert to WAV if needed
    if audio_file.suffix.lower() in ['.webm', '.m4a', '.opus']:
        wav_file = OUTPUT_DIR / f"{audio_file.stem}.wav"
        if not wav_file.exists():
            print("  Converting to WAV...")
            cmd = [str(FFMPEG_PATH), "-y", "-i", str(audio_file),
                   "-ar", "48000", "-ac", "1", str(wav_file)]
            subprocess.run(cmd, capture_output=True, timeout=120)
        audio_file = wav_file

    y, sr = librosa.load(str(audio_file), sr=None)
    print(f"  Duration: {len(y)/sr:.1f}s, Sample rate: {sr}Hz")
    return y, sr


def analyze_ultrasonic_region(y, sr, title="Ultrasonic Analysis"):
    """Detailed analysis of the ultrasonic frequency region (15-22kHz)."""
    print("\n=== ULTRASONIC REGION ANALYSIS ===")

    # Use larger hop for memory efficiency
    n_fft = 4096
    hop_length = 1024

    D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    mag = np.abs(D)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # Find ultrasonic frequency indices (15-22kHz)
    ultrasonic_mask = (freqs >= 15000) & (freqs <= 22000)
    ultrasonic_freqs = freqs[ultrasonic_mask]
    ultrasonic_mag = mag[ultrasonic_mask, :]

    if len(ultrasonic_freqs) == 0:
        print("  No ultrasonic frequencies available (sample rate too low)")
        return None

    print(f"  Analyzing {len(ultrasonic_freqs)} frequency bins from {ultrasonic_freqs[0]:.0f}Hz to {ultrasonic_freqs[-1]:.0f}Hz")

    # Convert to dB
    ultrasonic_dB = librosa.amplitude_to_db(ultrasonic_mag, ref=np.max(mag))

    # Create detailed visualization
    fig, axes = plt.subplots(3, 2, figsize=(20, 15))
    fig.suptitle(f"Ultrasonic Region Analysis: {title}", fontsize=14)

    # 1. Full ultrasonic spectrogram (use imshow for memory efficiency)
    ax = axes[0, 0]
    times = librosa.frames_to_time(np.arange(ultrasonic_mag.shape[1]), sr=sr, hop_length=hop_length)
    im = ax.imshow(ultrasonic_dB, aspect='auto', origin='lower', cmap='magma',
                   extent=[times[0], times[-1], ultrasonic_freqs[0]/1000, ultrasonic_freqs[-1]/1000])
    ax.set_ylabel('Frequency (kHz)')
    ax.set_xlabel('Time (s)')
    ax.set_title('Ultrasonic Spectrogram (15-22kHz)')
    plt.colorbar(im, ax=ax, format='%+2.0f dB')

    # 2. Enhanced contrast version (for hidden images)
    ax = axes[0, 1]
    enhanced = ultrasonic_dB - np.min(ultrasonic_dB)
    enhanced = enhanced / np.max(enhanced) * 255
    enhanced = gaussian_filter(enhanced, sigma=1)
    im = ax.imshow(enhanced, aspect='auto', origin='lower', cmap='gray',
                   extent=[times[0], times[-1], ultrasonic_freqs[0]/1000, ultrasonic_freqs[-1]/1000])
    ax.set_ylabel('Frequency (kHz)')
    ax.set_xlabel('Time (s)')
    ax.set_title('Enhanced Contrast (Look for hidden images/text)')
    plt.colorbar(im, ax=ax)

    # 3. Energy over time in ultrasonic range
    ax = axes[1, 0]
    ultrasonic_energy = np.mean(ultrasonic_mag, axis=0)
    ax.plot(times, ultrasonic_energy, 'b-', alpha=0.7, linewidth=0.5)
    ax.fill_between(times, ultrasonic_energy, alpha=0.3)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Mean Ultrasonic Energy')
    ax.set_title('Ultrasonic Energy Over Time (spikes may indicate data)')

    # Mark suspicious spikes
    threshold = np.mean(ultrasonic_energy) + 2 * np.std(ultrasonic_energy)
    spikes = ultrasonic_energy > threshold
    if np.any(spikes):
        spike_times = times[spikes]
        ax.scatter(spike_times, ultrasonic_energy[spikes], c='red', s=10, zorder=5, label='Suspicious spikes')
        ax.legend()
        print(f"  Found {len(spike_times)} suspicious energy spikes")

    # 4. Frequency distribution in ultrasonic range
    ax = axes[1, 1]
    mean_spectrum = np.mean(ultrasonic_mag, axis=1)
    ax.plot(ultrasonic_freqs/1000, mean_spectrum)
    ax.set_xlabel('Frequency (kHz)')
    ax.set_ylabel('Mean Amplitude')
    ax.set_title('Average Frequency Distribution (15-22kHz)')
    ax.axhline(y=np.mean(mean_spectrum), color='r', linestyle='--', alpha=0.5, label='Mean')
    ax.legend()

    # 5. Time-frequency variance (consistent patterns = potential data)
    ax = axes[2, 0]
    variance_over_time = np.var(ultrasonic_mag, axis=0)
    ax.plot(times, variance_over_time, 'g-', linewidth=0.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Variance')
    ax.set_title('Spectral Variance Over Time (low variance = structured data)')

    # 6. Binary threshold view (potential data extraction)
    ax = axes[2, 1]
    binary = ultrasonic_dB > (np.median(ultrasonic_dB) + 6)  # 6dB above median
    ax.imshow(binary, aspect='auto', cmap='binary', origin='lower',
              extent=[times[0], times[-1], ultrasonic_freqs[0]/1000, ultrasonic_freqs[-1]/1000])
    ax.set_ylabel('Frequency (kHz)')
    ax.set_xlabel('Time (s)')
    ax.set_title('Binary Threshold View (potential encoded data)')

    plt.tight_layout()
    output_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_ultrasonic.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path.name}")

    return ultrasonic_dB, times, ultrasonic_freqs


def analyze_time_segments(y, sr, title="Time Segments"):
    """Analyze the audio in time segments looking for anomalies."""
    print("\n=== TIME SEGMENT ANALYSIS ===")

    segment_length = 10  # seconds
    n_segments = int(len(y) / sr / segment_length)

    fig, axes = plt.subplots(min(n_segments, 6), 2, figsize=(16, 4*min(n_segments, 6)))
    if n_segments == 1:
        axes = axes.reshape(1, -1)

    for i in range(min(n_segments, 6)):
        start = int(i * segment_length * sr)
        end = int((i + 1) * segment_length * sr)
        segment = y[start:end]

        # Spectrogram
        ax = axes[i, 0]
        D = librosa.stft(segment, n_fft=4096, hop_length=256)
        D_dB = librosa.amplitude_to_db(np.abs(D), ref=np.max)
        librosa.display.specshow(D_dB, sr=sr, hop_length=256,
                                  x_axis='time', y_axis='linear', ax=ax,
                                  cmap='viridis')
        ax.set_title(f'Segment {i+1}: {i*segment_length}-{(i+1)*segment_length}s')
        ax.set_ylim(0, sr//2)

        # High-frequency detail
        ax = axes[i, 1]
        librosa.display.specshow(D_dB, sr=sr, hop_length=256,
                                  x_axis='time', y_axis='linear', ax=ax,
                                  cmap='magma')
        ax.set_title(f'High Freq Detail (10-20kHz)')
        ax.set_ylim(10000, min(22000, sr//2))

    plt.suptitle(f"Time Segment Analysis: {title}", fontsize=14)
    plt.tight_layout()
    output_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_segments.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path.name}")


def analyze_phase_spectrum(y, sr, title="Phase Analysis"):
    """Analyze phase information which could contain hidden data."""
    print("\n=== PHASE SPECTRUM ANALYSIS ===")

    # STFT
    D = librosa.stft(y, n_fft=4096, hop_length=512)
    magnitude = np.abs(D)
    phase = np.angle(D)

    # Phase derivative (instantaneous frequency)
    phase_diff = np.diff(phase, axis=1)

    fig, axes = plt.subplots(2, 2, figsize=(16, 12))

    # 1. Phase spectrogram
    ax = axes[0, 0]
    im = ax.imshow(phase[:500, :1000], aspect='auto', cmap='hsv', origin='lower')
    ax.set_title('Phase Spectrogram (first 500 freq bins, 1000 frames)')
    ax.set_xlabel('Time Frame')
    ax.set_ylabel('Frequency Bin')
    plt.colorbar(im, ax=ax, label='Phase (radians)')

    # 2. Phase derivative (unusual patterns may indicate data)
    ax = axes[0, 1]
    im = ax.imshow(np.abs(phase_diff[:500, :999]), aspect='auto', cmap='hot', origin='lower')
    ax.set_title('Phase Derivative Magnitude (hidden data often shows here)')
    ax.set_xlabel('Time Frame')
    ax.set_ylabel('Frequency Bin')
    plt.colorbar(im, ax=ax)

    # 3. Phase histogram (random should be uniform)
    ax = axes[1, 0]
    ax.hist(phase.flatten(), bins=100, density=True, alpha=0.7)
    ax.axhline(y=1/(2*np.pi), color='r', linestyle='--', label='Expected uniform')
    ax.set_xlabel('Phase (radians)')
    ax.set_ylabel('Density')
    ax.set_title('Phase Distribution (deviation from uniform = potential data)')
    ax.legend()

    # 4. Phase coherence over time
    ax = axes[1, 1]
    coherence = np.abs(np.mean(np.exp(1j * phase), axis=0))
    times = librosa.frames_to_time(np.arange(len(coherence)), sr=sr, hop_length=512)
    ax.plot(times, coherence)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Phase Coherence')
    ax.set_title('Phase Coherence Over Time (high = structured signal)')

    plt.suptitle(f"Phase Analysis: {title}", fontsize=14)
    plt.tight_layout()
    output_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_phase.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path.name}")


def extract_potential_data(y, sr, title="Data Extraction"):
    """Attempt to extract potential hidden binary data from ultrasonic range."""
    print("\n=== POTENTIAL DATA EXTRACTION ===")

    # Focus on 18-20kHz (common for ultrasonic data transmission)
    nyquist = sr / 2
    if nyquist < 18000:
        print("  Sample rate too low for ultrasonic data extraction")
        return

    # Bandpass filter for ultrasonic range
    low = 17000 / nyquist
    high = min(21000, nyquist - 1000) / nyquist
    b, a = signal.butter(4, [low, high], btype='band')
    ultrasonic = signal.filtfilt(b, a, y)

    # Envelope detection
    analytic = signal.hilbert(ultrasonic)
    envelope = np.abs(analytic)

    # Look for binary patterns
    threshold = np.median(envelope) + np.std(envelope)
    binary = (envelope > threshold).astype(int)

    # Find transitions (potential bit boundaries)
    transitions = np.diff(binary)
    rising_edges = np.where(transitions == 1)[0]
    falling_edges = np.where(transitions == -1)[0]

    print(f"  Found {len(rising_edges)} rising edges, {len(falling_edges)} falling edges")

    # Check for regular intervals (would indicate data encoding)
    if len(rising_edges) > 10:
        intervals = np.diff(rising_edges)
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        print(f"  Mean interval: {mean_interval:.1f} samples ({mean_interval/sr*1000:.2f}ms)")
        print(f"  Interval std: {std_interval:.1f} samples")

        # Regular intervals suggest encoded data
        if std_interval < mean_interval * 0.3:
            print("  ⚠️ REGULAR INTERVALS DETECTED - potential encoded data!")

            # Try to decode as ASCII
            bits_per_char = 8
            sample_per_bit = int(mean_interval)

            # Extract bits
            bits = []
            for i in range(0, len(binary) - sample_per_bit, sample_per_bit):
                bit = int(np.mean(binary[i:i+sample_per_bit]) > 0.5)
                bits.append(bit)

            # Try to decode as ASCII
            chars = []
            for i in range(0, len(bits) - bits_per_char, bits_per_char):
                byte = bits[i:i+bits_per_char]
                value = sum(b << (7-j) for j, b in enumerate(byte))
                if 32 <= value <= 126:  # Printable ASCII
                    chars.append(chr(value))

            if chars:
                decoded = ''.join(chars)
                print(f"  Potential decoded text: {decoded[:100]}...")

    # Visualize
    fig, axes = plt.subplots(3, 1, figsize=(16, 10))

    # Ultrasonic signal
    ax = axes[0]
    t = np.arange(len(ultrasonic[:sr*5])) / sr  # First 5 seconds
    ax.plot(t, ultrasonic[:sr*5], 'b-', linewidth=0.5, alpha=0.7)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Amplitude')
    ax.set_title('Filtered Ultrasonic Signal (17-21kHz) - First 5 seconds')

    # Envelope
    ax = axes[1]
    ax.plot(t, envelope[:sr*5], 'g-', linewidth=0.5)
    ax.axhline(y=threshold, color='r', linestyle='--', alpha=0.5, label='Threshold')
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Envelope')
    ax.set_title('Signal Envelope')
    ax.legend()

    # Binary
    ax = axes[2]
    ax.plot(t, binary[:sr*5], 'k-', linewidth=0.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Binary')
    ax.set_title('Binary Threshold Result')
    ax.set_ylim(-0.1, 1.1)

    plt.suptitle(f"Potential Data Extraction: {title}", fontsize=14)
    plt.tight_layout()
    output_path = OUTPUT_DIR / f"{title.replace(' ', '_')}_extraction.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Saved: {output_path.name}")


def main():
    print("=" * 60)
    print("Deep Analysis: A Wedding at the Last Forest")
    print("=" * 60)

    # Load audio
    y, sr = load_audio("A Wedding at the Last Forest")

    title = "A_Wedding_at_the_Last_Forest"

    # Run analyses
    analyze_ultrasonic_region(y, sr, title)
    analyze_time_segments(y, sr, title)
    analyze_phase_spectrum(y, sr, title)
    extract_potential_data(y, sr, title)

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nResults saved to: {OUTPUT_DIR}")
    print("\nFiles generated:")
    for f in OUTPUT_DIR.glob("*.png"):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
