"""Speaker playback uses the board verb's b64 PCM16 contract."""
import base64

from cli.commands import audio


def test_play_sends_board_pcm_contract(monkeypatch, tmp_path):
    pcm = b"\x00\x00\x01\x00"
    clip = tmp_path / "clip.pcm"
    clip.write_bytes(pcm)
    calls = []

    class Client:
        def invoke(self, verb, params):
            calls.append((verb, params))
            return {"ok": True, "samples": 2}

    monkeypatch.setattr(audio, "detect_board", lambda **kwargs: object())
    monkeypatch.setattr(audio.UsbCdcClient, "for_manifest", lambda *args, **kwargs: Client())
    assert audio.play({}, str(clip)) == 0
    assert calls == [("audio.play_pcm", {"b64": base64.b64encode(pcm).decode()})]
