"""
Advanced decoding attempts for FL YouTube audio.
Tries FM/PSK demodulation and image extraction from spectrograms.
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
from scipy import signal
from scipy.ndimage import gaussian_filter
from PIL import Image

# Paths
BASE_DIR = Path(__file__).parent
AUDIO_DIR = BASE_DIR / "data" / "youtube_audio"
OUTPUT_DIR = BASE_DIR / "data" / "decoded"
DEEP_DIR = BASE_DIR / "data" / "deep_analysis"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG_PATH = Path(os.environ.get('LOCALAPPDATA', '')) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-8.0.1-full_build" / "bin" / "ffmpeg.exe"


def load_audio(filename):
    """Load audio file."""
    import librosa

    # Check deep_analysis first for WAV (try both with and without underscores)
    wav_file = DEEP_DIR / f"{filename}.wav"
    if not wav_file.exists():
        wav_file = DEEP_DIR / f"{filename.replace('_', ' ')}.wav"
    if wav_file.exists():
        y, sr = librosa.load(str(wav_file), sr=None)
        return y, sr

    # Otherwise find in youtube_audio
    audio_file = AUDIO_DIR / filename
    if not audio_file.exists():
        # Try glob with partial match
        matches = list(AUDIO_DIR.glob(f"*{filename.replace('_', '*')}*"))
        if not matches:
            matches = list(AUDIO_DIR.glob(f"*{filename.split('_')[0]}*"))
        if matches:
            audio_file = matches[0]
        else:
            raise FileNotFoundError(f"Could not find {filename}")

    # Convert if needed
    if audio_file.suffix.lower() in ['.webm', '.m4a', '.opus']:
        wav_file = OUTPUT_DIR / f"{audio_file.stem}.wav"
        if not wav_file.exists():
            cmd = [str(FFMPEG_PATH), "-y", "-i", str(audio_file),
                   "-ar", "48000", "-ac", "1", str(wav_file)]
            subprocess.run(cmd, capture_output=True, timeout=120)
        audio_file = wav_file

    y, sr = librosa.load(str(audio_file), sr=None)
    return y, sr


def fm_demodulate(y, sr, center_freq=18000, bandwidth=2000):
    """
    FM demodulation - extracts frequency variations as amplitude.
    Used for FSK (Frequency Shift Keying) detection.
    """
    print(f"\n=== FM DEMODULATION ({center_freq}Hz ± {bandwidth}Hz) ===")

    nyquist = sr / 2
    low = (center_freq - bandwidth) / nyquist
    high = min((center_freq + bandwidth) / nyquist, 0.99)

    # Bandpass filter
    b, a = signal.butter(4, [low, high], btype='band')
    filtered = signal.filtfilt(b, a, y)

    # Hilbert transform for analytic signal
    analytic = signal.hilbert(filtered)

    # Instantaneous phase
    inst_phase = np.unwrap(np.angle(analytic))

    # Instantaneous frequency (derivative of phase)
    inst_freq = np.diff(inst_phase) * sr / (2 * np.pi)

    # Normalize to center frequency
    freq_deviation = inst_freq - center_freq

    print(f"  Frequency deviation range: {freq_deviation.min():.1f} to {freq_deviation.max():.1f} Hz")
    print(f"  Mean deviation: {np.mean(freq_deviation):.1f} Hz")
    print(f"  Std deviation: {np.std(freq_deviation):.1f} Hz")

    return filtered, inst_freq, freq_deviation


def psk_demodulate(y, sr, carrier_freq=17500):
    """
    PSK (Phase Shift Keying) demodulation.
    Extracts phase changes that could encode data.
    """
    print(f"\n=== PSK DEMODULATION ({carrier_freq}Hz carrier) ===")

    nyquist = sr / 2
    bandwidth = 1000
    low = (carrier_freq - bandwidth) / nyquist
    high = min((carrier_freq + bandwidth) / nyquist, 0.99)

    # Bandpass filter
    b, a = signal.butter(4, [low, high], btype='band')
    filtered = signal.filtfilt(b, a, y)

    # Generate reference carrier
    t = np.arange(len(filtered)) / sr
    carrier_i = np.cos(2 * np.pi * carrier_freq * t)
    carrier_q = np.sin(2 * np.pi * carrier_freq * t)

    # Mix with carriers (I/Q demodulation)
    i_signal = filtered * carrier_i
    q_signal = filtered * carrier_q

    # Low-pass filter to remove 2x carrier
    lpf_cutoff = 500 / nyquist
    b_lp, a_lp = signal.butter(4, lpf_cutoff, btype='low')
    i_baseband = signal.filtfilt(b_lp, a_lp, i_signal)
    q_baseband = signal.filtfilt(b_lp, a_lp, q_signal)

    # Phase extraction
    phase = np.arctan2(q_baseband, i_baseband)

    # Look for phase transitions
    phase_diff = np.diff(np.unwrap(phase))

    # Count significant phase jumps (potential bit transitions)
    threshold = np.pi / 4  # 45 degrees
    jumps = np.abs(phase_diff) > threshold
    n_jumps = np.sum(jumps)

    print(f"  Phase jumps detected: {n_jumps}")
    print(f"  Jump rate: {n_jumps / (len(y)/sr):.1f} per second")

    return phase, i_baseband, q_baseband


def extract_spectrogram_image(y, sr, freq_min=14000, freq_max=18000, title="Extracted"):
    """
    Extract a specific frequency band as a grayscale image.
    This could reveal hidden images encoded in the spectrogram.
    """
    import librosa

    print(f"\n=== EXTRACTING IMAGE FROM {freq_min/1000:.1f}-{freq_max/1000:.1f}kHz ===")

    # High resolution STFT
    n_fft = 4096
    hop_length = 256

    D = librosa.stft(y, n_fft=n_fft, hop_length=hop_length)
    mag = np.abs(D)
    freqs = librosa.fft_frequencies(sr=sr, n_fft=n_fft)

    # Extract frequency band
    mask = (freqs >= freq_min) & (freqs <= freq_max)
    band_mag = mag[mask, :]
    band_freqs = freqs[mask]

    print(f"  Extracted {len(band_freqs)} frequency bins")
    print(f"  Image dimensions: {band_mag.shape[0]} x {band_mag.shape[1]}")

    # Convert to dB and normalize to 0-255
    band_dB = librosa.amplitude_to_db(band_mag, ref=np.max)
    band_norm = band_dB - band_dB.min()
    band_norm = (band_norm / band_norm.max() * 255).astype(np.uint8)

    # Apply various image processing
    images = {}

    # 1. Raw extraction
    images['raw'] = band_norm

    # 2. Contrast enhanced
    enhanced = band_norm.copy().astype(float)
    p2, p98 = np.percentile(enhanced, (2, 98))
    enhanced = np.clip((enhanced - p2) / (p98 - p2) * 255, 0, 255).astype(np.uint8)
    images['enhanced'] = enhanced

    # 3. Edge detection (Sobel)
    from scipy.ndimage import sobel
    edges_x = sobel(band_norm.astype(float), axis=0)
    edges_y = sobel(band_norm.astype(float), axis=1)
    edges = np.sqrt(edges_x**2 + edges_y**2)
    edges = (edges / edges.max() * 255).astype(np.uint8)
    images['edges'] = edges

    # 4. Binary threshold
    threshold = np.median(band_norm) + np.std(band_norm)
    binary = (band_norm > threshold).astype(np.uint8) * 255
    images['binary'] = binary

    # 5. Inverted
    images['inverted'] = 255 - band_norm

    # Save all versions
    for name, img_data in images.items():
        # Flip vertically (low freq at bottom)
        img_data = np.flipud(img_data)
        img = Image.fromarray(img_data, mode='L')

        # Also save a scaled version for easier viewing
        aspect = img_data.shape[1] / img_data.shape[0]
        new_height = 400
        new_width = int(new_height * aspect)
        img_scaled = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        output_path = OUTPUT_DIR / f"{title}_{freq_min//1000}k-{freq_max//1000}k_{name}.png"
        img_scaled.save(output_path)
        print(f"  Saved: {output_path.name}")

    return images


def analyze_for_morse_or_patterns(y, sr, freq_band=(17000, 19000)):
    """
    Look for Morse code or other timing patterns in amplitude.
    """
    print(f"\n=== MORSE/PATTERN ANALYSIS ({freq_band[0]}-{freq_band[1]}Hz) ===")

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
    window_size = int(sr * 0.01)  # 10ms window
    envelope_smooth = np.convolve(envelope, np.ones(window_size)/window_size, mode='same')

    # Detect on/off patterns
    threshold = np.mean(envelope_smooth) + 0.5 * np.std(envelope_smooth)
    binary = envelope_smooth > threshold

    # Find transitions
    transitions = np.diff(binary.astype(int))
    on_times = np.where(transitions == 1)[0] / sr
    off_times = np.where(transitions == -1)[0] / sr

    if len(on_times) > 1 and len(off_times) > 1:
        # Calculate durations
        min_len = min(len(on_times), len(off_times))
        if on_times[0] < off_times[0]:
            on_durations = off_times[:min_len] - on_times[:min_len]
            off_durations = on_times[1:min_len] - off_times[:min_len-1] if min_len > 1 else []
        else:
            off_durations = on_times[:min_len] - off_times[:min_len]
            on_durations = off_times[1:min_len] - on_times[:min_len-1] if min_len > 1 else []

        on_durations = np.array(on_durations)
        off_durations = np.array(off_durations) if len(off_durations) > 0 else np.array([0])

        print(f"  ON events: {len(on_durations)}")
        print(f"  Mean ON duration: {np.mean(on_durations)*1000:.1f}ms")
        print(f"  Mean OFF duration: {np.mean(off_durations)*1000:.1f}ms")

        # Check for Morse-like timing (dots ~100ms, dashes ~300ms)
        short_marks = np.sum((on_durations > 0.05) & (on_durations < 0.15))
        long_marks = np.sum((on_durations > 0.2) & (on_durations < 0.4))

        if short_marks > 10 or long_marks > 5:
            print(f"  ⚠️ POTENTIAL MORSE: {short_marks} short, {long_marks} long marks")

        return on_durations, off_durations, envelope_smooth

    return None, None, envelope_smooth


def create_demodulation_report(title, y, sr):
    """Create comprehensive demodulation visualization."""

    fig, axes = plt.subplots(4, 2, figsize=(18, 16))
    fig.suptitle(f"Advanced Demodulation Analysis: {title}", fontsize=14)

    # 1. FM Demodulation at 18kHz
    filtered, inst_freq, freq_dev = fm_demodulate(y, sr, 18000, 2000)

    ax = axes[0, 0]
    t = np.arange(len(freq_dev)) / sr
    # Downsample for plotting
    step = max(1, len(t) // 10000)
    ax.plot(t[::step], freq_dev[::step], 'b-', linewidth=0.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Frequency Deviation (Hz)')
    ax.set_title('FM Demodulation - Frequency Deviation (18kHz carrier)')
    ax.set_ylim(-5000, 5000)

    # 2. FM histogram (look for FSK tones)
    ax = axes[0, 1]
    ax.hist(freq_dev, bins=200, range=(-3000, 3000), density=True, alpha=0.7)
    ax.set_xlabel('Frequency Deviation (Hz)')
    ax.set_ylabel('Density')
    ax.set_title('FM Deviation Distribution (peaks = FSK tones)')

    # 3. PSK Demodulation
    phase, i_bb, q_bb = psk_demodulate(y, sr, 17500)

    ax = axes[1, 0]
    step = max(1, len(phase) // 10000)
    ax.plot(np.arange(len(phase))[::step] / sr, phase[::step], 'g-', linewidth=0.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Phase (radians)')
    ax.set_title('PSK Demodulation - Phase (17.5kHz carrier)')

    # 4. I/Q constellation
    ax = axes[1, 1]
    step = max(1, len(i_bb) // 5000)
    ax.scatter(i_bb[::step], q_bb[::step], alpha=0.1, s=1)
    ax.set_xlabel('I (In-phase)')
    ax.set_ylabel('Q (Quadrature)')
    ax.set_title('I/Q Constellation (clusters = PSK symbols)')
    ax.set_aspect('equal')
    ax.grid(True, alpha=0.3)

    # 5. Morse/Pattern analysis
    on_dur, off_dur, envelope = analyze_for_morse_or_patterns(y, sr)

    ax = axes[2, 0]
    t_env = np.arange(len(envelope)) / sr
    step = max(1, len(t_env) // 10000)
    ax.plot(t_env[::step], envelope[::step], 'r-', linewidth=0.5)
    ax.set_xlabel('Time (s)')
    ax.set_ylabel('Envelope')
    ax.set_title('Ultrasonic Envelope (17-19kHz)')

    # 6. Duration histogram
    ax = axes[2, 1]
    if on_dur is not None and len(on_dur) > 0:
        ax.hist(on_dur * 1000, bins=50, range=(0, 500), alpha=0.7, label='ON')
        if off_dur is not None and len(off_dur) > 0:
            ax.hist(off_dur * 1000, bins=50, range=(0, 500), alpha=0.7, label='OFF')
        ax.set_xlabel('Duration (ms)')
        ax.set_ylabel('Count')
        ax.set_title('Mark/Space Duration Distribution')
        ax.legend()
        # Mark Morse timing
        ax.axvline(x=100, color='r', linestyle='--', alpha=0.5, label='Morse dot')
        ax.axvline(x=300, color='r', linestyle='--', alpha=0.5, label='Morse dash')
    else:
        ax.text(0.5, 0.5, 'No patterns detected', ha='center', va='center', transform=ax.transAxes)

    # 7. Spectrogram of filtered signal
    ax = axes[3, 0]
    import librosa
    import librosa.display
    D = librosa.stft(filtered[:sr*10], n_fft=2048, hop_length=256)  # First 10 seconds
    D_dB = librosa.amplitude_to_db(np.abs(D), ref=np.max)
    librosa.display.specshow(D_dB, sr=sr, hop_length=256, x_axis='time', y_axis='hz', ax=ax)
    ax.set_title('Filtered Signal Spectrogram (first 10s)')
    ax.set_ylim(15000, 22000)

    # 8. Autocorrelation (look for periodic patterns)
    ax = axes[3, 1]
    # Downsample envelope for autocorrelation
    env_ds = envelope[::100]
    autocorr = np.correlate(env_ds - np.mean(env_ds), env_ds - np.mean(env_ds), mode='full')
    autocorr = autocorr[len(autocorr)//2:]
    autocorr = autocorr / autocorr[0]

    t_ac = np.arange(len(autocorr)) * 100 / sr * 1000  # in ms
    ax.plot(t_ac[:5000], autocorr[:5000])
    ax.set_xlabel('Lag (ms)')
    ax.set_ylabel('Autocorrelation')
    ax.set_title('Envelope Autocorrelation (peaks = periodic patterns)')
    ax.axhline(y=0, color='k', linestyle='-', alpha=0.3)

    plt.tight_layout()
    output_path = OUTPUT_DIR / f"{title}_demodulation.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"\nSaved: {output_path.name}")


def main():
    print("=" * 60)
    print("Advanced Decoding Analysis")
    print("=" * 60)

    # 1. Analyze "A Wedding at the Last Forest"
    print("\n" + "=" * 40)
    print("TRACK 1: A Wedding at the Last Forest")
    print("=" * 40)

    y1, sr1 = load_audio("A_Wedding_at_the_Last_Forest")
    print(f"Loaded: {len(y1)/sr1:.1f}s @ {sr1}Hz")

    # FM/PSK demodulation
    create_demodulation_report("Wedding", y1, sr1)

    # Extract images from different frequency bands
    extract_spectrogram_image(y1, sr1, 14000, 18000, "Wedding")
    extract_spectrogram_image(y1, sr1, 16000, 20000, "Wedding")
    extract_spectrogram_image(y1, sr1, 18000, 22000, "Wedding")

    # 2. Analyze "Disjoint" for comparison
    print("\n" + "=" * 40)
    print("TRACK 2: Disjoint by Owayn")
    print("=" * 40)

    try:
        y2, sr2 = load_audio("Disjoint")
        print(f"Loaded: {len(y2)/sr2:.1f}s @ {sr2}Hz")

        create_demodulation_report("Disjoint", y2, sr2)
        extract_spectrogram_image(y2, sr2, 14000, 18000, "Disjoint")
        extract_spectrogram_image(y2, sr2, 16000, 20000, "Disjoint")
    except Exception as e:
        print(f"Error processing Disjoint: {e}")

    print("\n" + "=" * 60)
    print("ANALYSIS COMPLETE")
    print("=" * 60)
    print(f"\nResults saved to: {OUTPUT_DIR}")
    print("\nFiles to examine:")
    for f in sorted(OUTPUT_DIR.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
