from __future__ import annotations

from pathlib import Path

from app.services.audio_compat import AudioCompatibilityManager, codec_label, codec_needs_compat, normalize_codec_id


def test_browser_incompatible_audio_codec_classification() -> None:
    assert normalize_codec_id("A_DTS") == "dts"
    assert codec_label("A_DTS") == "DTS"
    assert codec_needs_compat("dts") is True
    assert codec_needs_compat("ac3") is True
    assert codec_needs_compat("eac3") is True
    assert codec_needs_compat("truehd") is True
    assert codec_needs_compat("aac") is False
    assert codec_needs_compat("opus") is False



def test_audio_compat_prefers_mp3_when_lame_is_available(tmp_path, monkeypatch) -> None:
    manager = AudioCompatibilityManager(tmp_path / "audio")
    monkeypatch.setattr(manager, "_encoder_available", lambda encoder: encoder == "libmp3lame")
    target = manager.preferred_target()
    assert target.codec_id == "mp3"
    assert target.codec_label == "MP3"
    assert target.encoder == "libmp3lame"
    assert target.media_type == "audio/mpeg"
    assert target.bitrate == "224k"


def test_audio_compat_falls_back_to_fast_aac(tmp_path, monkeypatch) -> None:
    manager = AudioCompatibilityManager(tmp_path / "audio")
    monkeypatch.setattr(manager, "_encoder_available", lambda _encoder: False)
    target = manager.preferred_target()
    assert target.codec_id == "aac"
    assert target.media_type == "audio/mp4"
    assert target.bitrate == "256k"
    source = Path(__file__).resolve().parents[1] / "backend" / "app" / "services" / "audio_compat.py"
    text = source.read_text(encoding="utf-8")
    assert '"-aac_coder", "fast"' in text
