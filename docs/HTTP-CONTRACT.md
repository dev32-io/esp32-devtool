## HTTP contract

Current companion behavior. Check board adapter/provider support before
relying on an endpoint.

### `GET /info` → 200 application/json

```json
{
  "device_id": "esp32-001",
  "board": "generic-s3-devkit",
  "chip": "esp32-s3",
  "ip": "192.168.0.121",
  "mac": "aa:bb:cc:dd:ee:ff",
  "firmware": "<your-app>-<git-sha>",
  "build_profile": "debug",
  "uptime_s": 3421,
  "wifi_ssid": "your-ssid",
  "wifi_rssi": -42,
  "capabilities": ["screenshot", "touch", "audio_record", "audio_inject", "log_relay"],
  "endpoints": {
    "screenshot": "/screenshot",
    "touch": "/touch",
    "audio_record": "/audio/record",
    "audio_inject": "/audio/inject"
  },
  "contract_version": "1.0"
}
```

### `GET /screenshot`

```
200 OK
Content-Type: application/octet-stream
X-Screenshot-Width: <int>
X-Screenshot-Height: <int>
X-Screenshot-Format: rgb565
<raw RGB565 LE bytes, chunked response>
```

Host `screenshot --format rgb565` saves raw bytes; default PNG conversion
runs on host. JPEG conversion requires Pillow. Missing snapshot provider
returns 503. Firmware does not encode PNG/JPEG or accept a format query.

### `POST /touch`

```
Body: {"x": int, "y": int, "hold_ms": int? = 60}
200 → {"ok": true}
```

Server enqueues synthetic press at (x,y), release after hold_ms via injected `lv_indev`.

### `GET /audio/record?duration_ms=<int>&sample_rate=<int>`

```
200 OK
Content-Type: audio/L16; rate=<sample_rate>; channels=1
X-Audio-Samples: <int>
<raw PCM16 LE>
```

Default 1000 ms, 16000 Hz. Duration must be 1–1000 ms; sample rate must
be 1000–48000 Hz (at least one sample required). Invalid query returns 400,
not a clamped capture. Capture is synchronous into a PSRAM buffer; HTTP
sends chunks **after** capture. Board provider may apply its own limit.

### `POST /audio/inject`

```
Content-Type: audio/L16; rate=16000; channels=1
<raw PCM16 LE>
200 → {"ok": true, "samples": <int>}
```

Body must be nonempty, even-length PCM16 at exactly 16000 Hz mono and at
most 2 MiB; it is buffered in PSRAM. Invalid length/format is rejected.
Provider feeds microphone injection ring, not speaker playback. `samples`
reports samples **actually queued**: full acceptance returns 200 with
`{"ok":true,"samples":N}`; partial acceptance returns 409 with
`{"ok":false,"samples":accepted}`. Missing or failed counted provider returns
503 with `{"ok":false,"samples":0}`. Host `--json audio inject` reports a
validated 409 as `{"error":"audio injection partially accepted","exit_code":5,
"samples":accepted,"requested_samples":N}` with exit status 5. It does not
retry automatically. Invalid response counts are not reported as accepted.

Board adapters using legacy `esp32_devtool_set_audio_inject_provider` must
register `esp32_devtool_set_audio_inject_counted_provider` for HTTP injection.
Counted callback returns 0 and writes actual queued count via `accepted`;
legacy callback alone no longer handles this endpoint (503). No automatic
fallback, since legacy callback cannot report partial ring acceptance.
Separate USB-CDC `audio play` uses `audio.play_pcm` when firmware exposes
that verb.

### Log relay (device → host)

UDP datagrams, NDJSON one line per packet:

```json
{"ts_ms": 12345, "level": "I", "tag": "your.app.tag", "msg": "status: ..."}
```

Devtool's `logs --source udp` binds the host-side port to receive.

### Version header (`/info`)

```
X-Devtool-Version: <semver>
```

Current host does not enforce or warn on version mismatch.

### Contract versioning

`contract_version` in `/info` reports firmware contract version. Host does
not currently validate it.

### Authentication

Out-of-scope v1 (LAN-only). OSS extraction guide will document reverse-proxy patterns.

### CORS

Off v1. Add when a web UI is built.
