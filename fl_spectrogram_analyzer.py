"""
FL YouTube Audio Spectrogram Analyzer
Analyzes audio from the Forgotten Languages YouTube channel for hidden patterns.
"""

import os
import sys
import subprocess
from pathlib import Path

# Set UTF-8 encoding for console output
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# Paths
AUDIO_DIR = Path(__file__).parent / "data" / "youtube_audio"
SPECTRO_DIR = Path(__file__).parent / "data" / "spectrograms"
TEMP_DIR = Path(__file__).parent / "data" / "temp_wav"

# FFmpeg path (Windows WinGet installation)
FFMPEG_PATH = Path(os.environ.get('LOCALAPPDATA', '')) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe" / "ffmpeg-8.0.1-full_build" / "bin" / "ffmpeg.exe"
if not FFMPEG_PATH.exists():
    FFMPEG_PATH = "ffmpeg"  # Fall back to PATH

def ensure_dirs():
    """Create necessary directories."""
    SPECTRO_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

def convert_to_wav(input_file: Path, output_file: Path) -> bool:
    """Convert audio file to WAV using ffmpeg."""
    try:
        cmd = [
            str(FFMPEG_PATH), "-y", "-i", str(input_file),
            "-ar", "44100", "-ac", "1",  # 44.1kHz mono
            str(output_file)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"  ffmpeg stderr: {result.stderr[:200]}")
        return result.returncode == 0
    except Exception as e:
        print(f"Error converting {input_file.name}: {e}")
        return False

def analyze_audio(wav_file: Path, output_prefix: str):
    """Generate multiple spectrogram analyses for an audio file."""
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import librosa
        import librosa.display

        # Load audio
        y, sr = librosa.load(str(wav_file), sr=None)
        duration = librosa.get_duration(y=y, sr=sr)

        print(f"  Duration: {duration:.1f}s, Sample rate: {sr}Hz")

        # Create figure with multiple spectrograms
        fig, axes = plt.subplots(3, 2, figsize=(16, 12))
        fig.suptitle(f"Spectrogram Analysis: {output_prefix[:50]}...", fontsize=12)

        # 1. Standard Mel Spectrogram
        ax = axes[0, 0]
        S = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=128, fmax=8000)
        S_dB = librosa.power_to_db(S, ref=np.max)
        img = librosa.display.specshow(S_dB, x_axis='time', y_axis='mel',
                                        sr=sr, fmax=8000, ax=ax)
        ax.set_title('Mel Spectrogram (0-8kHz)')
        fig.colorbar(img, ax=ax, format='%+2.0f dB')

        # 2. Full Frequency Spectrogram (STFT)
        ax = axes[0, 1]
        D = librosa.stft(y)
        D_dB = librosa.amplitude_to_db(np.abs(D), ref=np.max)
        img = librosa.display.specshow(D_dB, x_axis='time', y_axis='log',
                                        sr=sr, ax=ax)
        ax.set_title('STFT Spectrogram (Log Frequency)')
        fig.colorbar(img, ax=ax, format='%+2.0f dB')

        # 3. High-frequency detail (15-22kHz - where hidden data might be)
        ax = axes[1, 0]
        S_high = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=64,
                                                  fmin=15000, fmax=22000)
        S_high_dB = librosa.power_to_db(S_high, ref=np.max)
        img = librosa.display.specshow(S_high_dB, x_axis='time', y_axis='mel',
                                        sr=sr, fmin=15000, fmax=22000, ax=ax)
        ax.set_title('High Frequency Detail (15-22kHz) - Hidden Data Zone')
        fig.colorbar(img, ax=ax, format='%+2.0f dB')

        # 4. Chromagram (pitch class analysis)
        ax = axes[1, 1]
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        img = librosa.display.specshow(chroma, x_axis='time', y_axis='chroma', ax=ax)
        ax.set_title('Chromagram (Pitch Classes)')
        fig.colorbar(img, ax=ax)

        # 5. Spectral Centroid & Bandwidth over time
        ax = axes[2, 0]
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
        bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
        frames = range(len(centroid))
        t = librosa.frames_to_time(frames, sr=sr)
        ax.plot(t, centroid, label='Spectral Centroid', alpha=0.8)
        ax.plot(t, bandwidth, label='Spectral Bandwidth', alpha=0.8)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Hz')
        ax.set_title('Spectral Features Over Time')
        ax.legend()

        # 6. Waveform with envelope
        ax = axes[2, 1]
        librosa.display.waveshow(y, sr=sr, ax=ax, alpha=0.5)
        envelope = np.abs(librosa.effects.preemphasis(y))
        # Downsample envelope for plotting
        hop = len(envelope) // 1000
        if hop > 0:
            envelope_ds = envelope[::hop]
            t_env = np.linspace(0, duration, len(envelope_ds))
            ax.plot(t_env, envelope_ds * 0.5, 'r-', alpha=0.7, label='Envelope')
        ax.set_title('Waveform')
        ax.set_xlabel('Time (s)')

        plt.tight_layout()

        # Save figure
        output_path = SPECTRO_DIR / f"{output_prefix}_analysis.png"
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()

        print(f"  Saved: {output_path.name}")

        # Also create a detailed high-res spectrogram for visual inspection
        create_detailed_spectrogram(y, sr, output_prefix)

        return True

    except Exception as e:
        print(f"Error analyzing {wav_file.name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_detailed_spectrogram(y, sr, output_prefix):
    """Create a high-resolution detailed spectrogram for visual pattern detection."""
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import librosa
        import librosa.display

        fig, axes = plt.subplots(2, 1, figsize=(20, 10))

        # Very detailed STFT spectrogram
        ax = axes[0]
        D = librosa.stft(y, n_fft=4096, hop_length=512)
        D_dB = librosa.amplitude_to_db(np.abs(D), ref=np.max)
        img = librosa.display.specshow(D_dB, x_axis='time', y_axis='linear',
                                        sr=sr, hop_length=512, ax=ax,
                                        cmap='viridis')
        ax.set_title('High-Resolution Linear Spectrogram (Look for visual patterns/text)')
        ax.set_ylim(0, sr//2)
        fig.colorbar(img, ax=ax, format='%+2.0f dB')

        # Zoomed high frequency region
        ax = axes[1]
        img = librosa.display.specshow(D_dB, x_axis='time', y_axis='linear',
                                        sr=sr, hop_length=512, ax=ax,
                                        cmap='magma')
        ax.set_title('High Frequency Region (10-22kHz) - Check for steganography')
        ax.set_ylim(10000, min(22000, sr//2))
        fig.colorbar(img, ax=ax, format='%+2.0f dB')

        plt.tight_layout()

        output_path = SPECTRO_DIR / f"{output_prefix}_detailed.png"
        plt.savefig(output_path, dpi=200, bbox_inches='tight')
        plt.close()

        print(f"  Saved: {output_path.name}")

    except Exception as e:
        print(f"Error creating detailed spectrogram: {e}")

def analyze_for_hidden_messages(wav_file: Path, output_prefix: str):
    """Look for potential hidden messages in specific frequency bands."""
    try:
        import numpy as np
        import matplotlib.pyplot as plt
        import librosa

        y, sr = librosa.load(str(wav_file), sr=44100)  # Standardize to 44.1kHz

        # Check for unusual energy patterns in ultrasonic range
        D = librosa.stft(y, n_fft=8192)
        freqs = librosa.fft_frequencies(sr=sr, n_fft=8192)

        # Find indices for different frequency bands
        ultrasonic_mask = freqs > 18000  # Above normal hearing
        high_mask = (freqs > 15000) & (freqs <= 18000)

        # Calculate energy in different bands
        mag = np.abs(D)
        ultrasonic_energy = np.mean(mag[ultrasonic_mask, :], axis=0) if np.any(ultrasonic_mask) else np.zeros(mag.shape[1])
        high_energy = np.mean(mag[high_mask, :], axis=0) if np.any(high_mask) else np.zeros(mag.shape[1])
        total_energy = np.mean(mag, axis=0)

        # Check for suspiciously high ultrasonic energy (potential hidden data)
        ultrasonic_ratio = np.mean(ultrasonic_energy) / (np.mean(total_energy) + 1e-10)
        high_ratio = np.mean(high_energy) / (np.mean(total_energy) + 1e-10)

        # Report findings
        findings = {
            'file': output_prefix,
            'duration': librosa.get_duration(y=y, sr=sr),
            'ultrasonic_ratio': ultrasonic_ratio,
            'high_freq_ratio': high_ratio,
            'suspicious': ultrasonic_ratio > 0.01 or high_ratio > 0.05
        }

        if findings['suspicious']:
            print(f"  ⚠️  SUSPICIOUS: High energy in ultrasonic range detected!")
            print(f"      Ultrasonic ratio: {ultrasonic_ratio:.4f}")
            print(f"      High-freq ratio: {high_ratio:.4f}")

        return findings

    except Exception as e:
        print(f"Error in hidden message analysis: {e}")
        return None

def main():
    """Main analysis function."""
    print("=" * 60)
    print("FL YouTube Audio Spectrogram Analyzer")
    print("=" * 60)

    ensure_dirs()

    # Find all audio files
    audio_extensions = {'.webm', '.m4a', '.mp3', '.wav', '.ogg', '.opus'}
    audio_files = [f for f in AUDIO_DIR.iterdir()
                   if f.suffix.lower() in audio_extensions]

    if not audio_files:
        print(f"No audio files found in {AUDIO_DIR}")
        return

    print(f"\nFound {len(audio_files)} audio files to analyze.\n")

    results = []

    for i, audio_file in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] Processing: {audio_file.name[:60]}...")

        # Create safe filename for output
        safe_name = "".join(c if c.isalnum() or c in ' -_' else '_' for c in audio_file.stem)
        safe_name = safe_name[:80]  # Truncate long names

        # Convert to WAV first
        wav_file = TEMP_DIR / f"{safe_name}.wav"

        if not wav_file.exists():
            print("  Converting to WAV...")
            if not convert_to_wav(audio_file, wav_file):
                print("  Failed to convert, skipping...")
                continue

        # Analyze
        print("  Generating spectrograms...")
        analyze_audio(wav_file, safe_name)

        print("  Checking for hidden messages...")
        findings = analyze_for_hidden_messages(wav_file, safe_name)
        if findings:
            results.append(findings)

    # Summary report
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)

    suspicious_files = [r for r in results if r.get('suspicious')]
    if suspicious_files:
        print(f"\n⚠️  Found {len(suspicious_files)} files with suspicious frequency patterns:")
        for f in suspicious_files:
            print(f"  - {f['file']}")
            print(f"    Ultrasonic ratio: {f['ultrasonic_ratio']:.4f}")
    else:
        print("\nNo obviously suspicious frequency patterns detected.")

    print(f"\nSpectrograms saved to: {SPECTRO_DIR}")
    print("\nReview the *_detailed.png files for potential visual patterns or steganography.")

if __name__ == "__main__":
    main()
