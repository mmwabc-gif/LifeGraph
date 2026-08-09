from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

from app.services.large_files import ChunkedMediaStore, LargeFileError


AUDIO_COMPAT_FORMAT_VERSION = 1
AUDIO_COMPAT_CHUNK_SIZE = 4 * 1024 * 1024
AUDIO_PROBE_BYTES = 16 * 1024 * 1024
AUDIO_READ_SIZE = 1024 * 1024

# Browser support varies by OS/container. These codecs are deliberately treated
# as incompatible because Chrome/Edge commonly play the video track while the
# embedded audio remains silent.
_BROWSER_INCOMPATIBLE = {
    "dts",
    "dca",
    "ac3",
    "eac3",
    "truehd",
    "mlp",
}

_CODEC_LABELS = {
    "dts": "DTS",
    "dca": "DTS",
    "ac3": "AC-3",
    "eac3": "E-AC-3",
    "truehd": "Dolby TrueHD",
    "mlp": "MLP / TrueHD",
    "aac": "AAC",
    "opus": "Opus",
    "vorbis": "Vorbis",
    "mp3": "MP3",
    "mp2": "MP2",
    "flac": "FLAC",
    "pcm_s16le": "PCM",
}


class AudioCompatibilityError(ValueError):
    pass


class AudioCompatibilityCancelled(AudioCompatibilityError):
    pass


@dataclass(frozen=True, slots=True)
class FFmpegTools:
    ffmpeg: Path | None
    ffprobe: Path | None

    @property
    def available(self) -> bool:
        return self.ffmpeg is not None


@dataclass(frozen=True, slots=True)
class BrowserAudioTarget:
    codec_id: str
    codec_label: str
    encoder: str
    media_type: str
    format_name: str
    extension: str
    bitrate: str

    def manifest_extra(self) -> dict[str, Any]:
        return {
            "asset_kind": "audio-compat",
            "audio_codec": self.codec_label,
            "audio_codec_id": self.codec_id,
            "media_type": self.media_type,
            "format_version": AUDIO_COMPAT_FORMAT_VERSION,
        }


@dataclass(slots=True)
class AudioProbe:
    codec_id: str = ""
    codec_label: str = ""
    channels: int | None = None
    channel_layout: str = ""
    sample_rate: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "audio_codec_id": self.codec_id or None,
            "audio_codec": self.codec_label or None,
            "audio_channels": self.channels,
            "audio_channel_layout": self.channel_layout or None,
            "audio_sample_rate": self.sample_rate,
        }


def _path_if_file(value: str | os.PathLike[str] | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    try:
        return path if path.is_file() else None
    except OSError:
        return None


def _candidate_tool_paths(name: str) -> list[Path]:
    exe = f"{name}.exe"
    candidates: list[Path] = []
    hint = str(os.getenv("LIFEGRAPH_FFMPEG_PATH") or "").strip()
    if hint:
        hinted = Path(hint)
        if hinted.suffix.lower() == ".exe":
            candidates.append(hinted.with_name(exe))
        else:
            candidates.extend([hinted / "bin" / exe, hinted / exe])
    # User's standard Windows installation location.
    candidates.extend([
        Path("C:/ffmpeg/bin") / exe,
        Path("C:/ffmpeg") / exe,
    ])
    resolved = shutil.which(name)
    if resolved:
        candidates.append(Path(resolved))
    return candidates


def discover_ffmpeg_tools() -> FFmpegTools:
    ffmpeg = next((_path_if_file(path) for path in _candidate_tool_paths("ffmpeg") if _path_if_file(path)), None)
    ffprobe = next((_path_if_file(path) for path in _candidate_tool_paths("ffprobe") if _path_if_file(path)), None)
    if ffmpeg and not ffprobe:
        sibling_name = "ffprobe.exe" if ffmpeg.suffix.lower() == ".exe" else "ffprobe"
        ffprobe = _path_if_file(ffmpeg.with_name(sibling_name))
    return FFmpegTools(ffmpeg=ffmpeg, ffprobe=ffprobe)


def normalize_codec_id(value: str | None) -> str:
    codec = str(value or "").strip().lower()
    aliases = {
        "a_dts": "dts",
        "a_ac3": "ac3",
        "a_eac3": "eac3",
        "a_truehd": "truehd",
        "a_mlp": "mlp",
        "a_aac": "aac",
        "a_opus": "opus",
        "a_vorbis": "vorbis",
        "a_flac": "flac",
        "a_mpeg/l3": "mp3",
    }
    return aliases.get(codec, codec)


def codec_label(value: str | None) -> str:
    codec = normalize_codec_id(value)
    return _CODEC_LABELS.get(codec, str(value or "").strip())


def codec_needs_compat(value: str | None) -> bool:
    return normalize_codec_id(value) in _BROWSER_INCOMPATIBLE


class AudioCompatibilityManager:
    """Build and serve encrypted browser-compatible audio derivatives.

    FFmpeg receives the original media through stdin, so LifeGraph never creates
    a full plaintext copy of a multi-GB video. FFmpeg emits fragmented MP4/AAC on
    stdout and the bytes are encrypted directly into random-access lgchunk files.
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self.store = ChunkedMediaStore(root)
        self.tools = discover_ffmpeg_tools()
        self._encoder_cache: dict[tuple[str, str], bool] = {}
        self._cleanup_incomplete_derivatives()

    def _cleanup_incomplete_derivatives(self) -> None:
        if not self.root.is_dir():
            return
        try:
            for shard in self.root.iterdir():
                if not shard.is_dir() or shard.name.startswith("."):
                    continue
                for media_dir in shard.iterdir():
                    if not media_dir.is_dir() or not media_dir.name.startswith("aud_"):
                        continue
                    if not (media_dir / "manifest.lgmedia").is_file():
                        shutil.rmtree(media_dir, ignore_errors=True)
                try:
                    shard.rmdir()
                except OSError:
                    pass
        except OSError:
            pass

    def refresh_tools(self) -> FFmpegTools:
        self.tools = discover_ffmpeg_tools()
        return self.tools

    def _encoder_available(self, encoder: str) -> bool:
        tools = self.refresh_tools()
        if not tools.ffmpeg:
            return False
        key = (str(tools.ffmpeg), str(encoder))
        if key in self._encoder_cache:
            return self._encoder_cache[key]
        try:
            completed = subprocess.run(
                [str(tools.ffmpeg), "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=10,
                check=False,
            )
            text = (completed.stdout or b"").decode("utf-8", errors="replace")
            available = any(
                line.strip().split()[1:2] == [encoder]
                for line in text.splitlines()
                if line.strip() and not line.lstrip().startswith("--")
            )
        except (OSError, subprocess.SubprocessError):
            available = False
        self._encoder_cache[key] = available
        return available

    def preferred_target(self) -> BrowserAudioTarget:
        # MP3 is only a browser-compatibility derivative; the original
        # DTS/AC-3/TrueHD track remains intact. libmp3lame is substantially
        # lighter than AAC on many Windows FFmpeg builds and CBR MP3 also seeks
        # reliably over HTTP Range. Fall back to AAC when LAME is unavailable.
        if self._encoder_available("libmp3lame"):
            return BrowserAudioTarget(
                codec_id="mp3",
                codec_label="MP3",
                encoder="libmp3lame",
                media_type="audio/mpeg",
                format_name="mp3",
                extension="mp3",
                bitrate="224k",
            )
        return BrowserAudioTarget(
            codec_id="aac",
            codec_label="AAC",
            encoder="aac",
            media_type="audio/mp4",
            format_name="mp4",
            extension="m4a",
            bitrate="256k",
        )

    def delete(self, media_id: str | None) -> None:
        if media_id:
            self.store.delete(str(media_id))

    def asset_exists(self, media_id: str | None) -> bool:
        if not media_id:
            return False
        try:
            return self.store.manifest_path(str(media_id)).is_file()
        except (LargeFileError, OSError):
            return False

    def read_manifest(self, master_key: bytes, media_id: str) -> dict[str, Any]:
        return self.store.read_manifest(master_key, media_id)

    def probe_prefix(self, content: bytes) -> AudioProbe | None:
        tools = self.refresh_tools()
        if not tools.ffprobe or not content:
            return None
        command = [
            str(tools.ffprobe),
            "-v", "error",
            "-probesize", str(AUDIO_PROBE_BYTES),
            "-analyzeduration", "5000000",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name,codec_long_name,channels,channel_layout,sample_rate",
            "-of", "json",
            "-i", "pipe:0",
        ]
        try:
            completed = subprocess.run(
                command,
                input=content,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
            payload = json.loads((completed.stdout or b"{}").decode("utf-8", errors="replace"))
            streams = payload.get("streams") if isinstance(payload, dict) else None
            if not isinstance(streams, list) or not streams:
                return None
            stream = streams[0] if isinstance(streams[0], dict) else {}
            codec_id = normalize_codec_id(stream.get("codec_name"))
            channels = None
            sample_rate = None
            try:
                raw_channels = int(stream.get("channels"))
                if 1 <= raw_channels <= 64:
                    channels = raw_channels
            except (TypeError, ValueError):
                pass
            try:
                raw_rate = int(stream.get("sample_rate"))
                if 1000 <= raw_rate <= 768000:
                    sample_rate = raw_rate
            except (TypeError, ValueError):
                pass
            label = codec_label(codec_id) or str(stream.get("codec_long_name") or "").strip()
            return AudioProbe(
                codec_id=codec_id,
                codec_label=label,
                channels=channels,
                channel_layout=str(stream.get("channel_layout") or "").strip(),
                sample_rate=sample_rate,
            )
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None

    def transcode_browser_audio(
        self,
        *,
        master_key: bytes,
        media_id: str,
        source_iter: Iterable[bytes],
        source_size: int,
        cancel_event: threading.Event,
        progress: Callable[[int, int], None] | None = None,
        target: BrowserAudioTarget | None = None,
    ) -> dict[str, Any]:
        tools = self.refresh_tools()
        if not tools.ffmpeg:
            raise AudioCompatibilityError("未找到 FFmpeg，可设置 LIFEGRAPH_FFMPEG_PATH 或安装到 C:\\ffmpeg")
        target = target or self.preferred_target()
        command = [
            str(tools.ffmpeg),
            "-hide_banner",
            "-loglevel", "error",
            "-i", "pipe:0",
            "-map", "0:a:0",
            "-vn",
            "-c:a", target.encoder,
            # Compatibility derivative favors universal browser playback. The
            # original DTS/AC-3/TrueHD multichannel track remains untouched.
            "-ac", "2",
            "-b:a", target.bitrate,
        ]
        if target.codec_id == "aac":
            command.extend([
                "-profile:a", "aac_low",
                "-aac_coder", "fast",
                "-movflags", "+frag_keyframe+empty_moov+default_base_moof",
                "-frag_duration", "2000000",
            ])
        command.extend(["-f", target.format_name, "pipe:1"])
        try:
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,
            )
        except OSError as exc:
            raise AudioCompatibilityError(f"无法启动 FFmpeg：{exc}") from exc

        stderr_tail: deque[bytes] = deque(maxlen=32)
        feeder_error: list[BaseException] = []

        def read_stderr() -> None:
            if process.stderr is None:
                return
            try:
                while True:
                    block = process.stderr.read(2048)
                    if not block:
                        break
                    stderr_tail.append(block)
            except OSError:
                return

        def feed_source() -> None:
            sent = 0
            try:
                if process.stdin is None:
                    raise AudioCompatibilityError("FFmpeg 输入通道不可用")
                for block in source_iter:
                    if cancel_event.is_set():
                        raise AudioCompatibilityCancelled("兼容音轨生成已取消")
                    if not block:
                        continue
                    process.stdin.write(block)
                    sent += len(block)
                    if progress:
                        progress(sent, int(source_size))
                process.stdin.close()
            except BaseException as exc:  # background thread transports the exact failure
                feeder_error.append(exc)
                try:
                    if process.stdin:
                        process.stdin.close()
                except OSError:
                    pass
                try:
                    process.kill()
                except OSError:
                    pass

        stderr_thread = threading.Thread(target=read_stderr, name="lifegraph-ffmpeg-stderr", daemon=True)
        feeder_thread = threading.Thread(target=feed_source, name="lifegraph-ffmpeg-input", daemon=True)
        stderr_thread.start()
        feeder_thread.start()

        def output_iter():
            if process.stdout is None:
                raise AudioCompatibilityError("FFmpeg 输出通道不可用")
            while True:
                if cancel_event.is_set():
                    try:
                        process.kill()
                    except OSError:
                        pass
                    raise AudioCompatibilityCancelled("兼容音轨生成已取消")
                block = process.stdout.read(AUDIO_READ_SIZE)
                if not block:
                    break
                yield block

        try:
            manifest = self.store.write_stream(
                master_key,
                media_id,
                output_iter(),
                chunk_size=AUDIO_COMPAT_CHUNK_SIZE,
                manifest_extra=target.manifest_extra(),
                # The browser-audio derivative is a regenerable cache. Avoid forcing an
                # fsync for each small encrypted output chunk; the final manifest
                # is still atomically/durably committed when generation succeeds.
                durable_chunks=False,
            )
            feeder_thread.join(timeout=30)
            return_code = process.wait(timeout=30)
            stderr_thread.join(timeout=2)
            if feeder_error:
                raise feeder_error[0]
            if cancel_event.is_set():
                raise AudioCompatibilityCancelled("兼容音轨生成已取消")
            if return_code != 0:
                detail = b"".join(stderr_tail).decode("utf-8", errors="replace").strip()
                raise AudioCompatibilityError(detail[-800:] or f"FFmpeg 转码失败（退出码 {return_code}）")
            if progress:
                progress(int(source_size), int(source_size))
            return manifest
        except BaseException:
            self.store.delete(media_id)
            try:
                process.kill()
            except OSError:
                pass
            raise
        finally:
            feeder_thread.join(timeout=2)
            stderr_thread.join(timeout=2)
            for stream in (process.stdin, process.stdout, process.stderr):
                try:
                    if stream:
                        stream.close()
                except OSError:
                    pass
