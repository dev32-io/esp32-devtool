## Board manifest

`boards/_schema.yaml`:

```yaml
name: string
display_name: string
chip: esp32-s3 | esp32-s2 | esp32-p4 | esp32-c3 | esp32-c6
firmware_path: string?               # for `flash`
build_artifact: string?              # ELF filename in <firmware_path>/build/
build_profiles: [string]

usb:
  vid: int?
  pid: int?
  port_glob: string?

http:
  enabled: bool
  port: int
  discover_via: usb-info | mdns | static
  static_host: string?

capabilities:
  flash:        { transport: usb-cdc, require: [usb] }
  logs:         { transport: auto, sources: [usb, udp] }
  cmd:          { transport: usb-cdc, require: [daemon] }
  screenshot:   { transport: http, require: [http], format: [png, jpeg, rgb565] }
  touch:        { transport: http, require: [http] }
  audio_record: { transport: http, require: [http] }
  audio_inject: { transport: http, require: [http] }
  audio_play:   { transport: usb-cdc }

log_relay:
  enabled: bool
  port: int
  format: text | json

verbs: [string]                       # USB-CDC JSON-RPC verbs

extensions:                           # board-specific commands
  - cmd: string
    exec: string                      # ${REPO_ROOT}-aware
    args_passthrough: bool
    transient: bool?                  # prints deprecation hint
    help: string
```

### `build_artifact` (optional)

ELF filename in `<firmware_path>/build/`. Used by `gdb` and `audit-prod-strip`
to locate the firmware ELF without globbing.

```yaml
build_artifact: my_app.elf
```

If omitted, devtool globs `<firmware_path>/build/*.elf` and uses the single
match. Zero or multiple matches produce a helpful error directing you to
set this field.

### `boards/my-s3-board.yaml` (example)

```yaml
name: my-s3-board
display_name: "My ESP32-S3 Board (Waveshare ESP32-S3 AMOLED 2.16)"
chip: esp32-s3
firmware_path: <your-firmware-dir>
build_profiles: [debug, prod]
build_artifact: my_app.elf

usb:
  port_glob: "/dev/cu.usbmodem*"

http:
  enabled: true
  port: 8081
  discover_via: usb-info               # /info verb returns ip

capabilities:
  flash:        { transport: usb-cdc }
  logs:         { transport: auto, sources: [usb, udp] }
  cmd:          { transport: usb-cdc }
  screenshot:   { transport: http }
  touch:        { transport: http }
  audio_record: { transport: http }
  audio_inject: { transport: http }
  audio_play:   { transport: usb-cdc }

log_relay:
  enabled: true
  port: 9000

verbs:
  - <your-project>.status
  - button.toggle
  - state
  - restart
  - log_level
  - mark
  - wifi.connect
  - wifi.disconnect
  - wifi.reconnect
  - audio.dump_state
  - audio.play_pcm
  - audio.test_tone

extensions:
  - cmd: bake-creds
    exec: ${REPO_ROOT}/<your-firmware-dir>/scripts/bake-creds.sh
    args_passthrough: true
    transient: true
    help: |
      [transient — pre-device-pairing dev hack]
      Bake WiFi credentials into firmware headers. Retires with proper
      device-pairing flow.
```

### Auto-detect flow

```
1. If --board <name>: load boards/<name>.yaml. Done.
2. Else scan /dev/cu.usbmodem* (or platform equivalent).
3. For each port: optionally read MAC via esptool, match against boards/*.yaml.
4. Exactly 1 match → use; cache to ~/.config/esp32-devtool/last-board.
5. Zero → exit 3 ("no board connected; --board explicitly?").
6. Two+ → exit 3 ("multiple boards — disambiguate with --board=<name> --port=...").
```

Cache key: `(port, manifest_mtime)`. Invalidate if either changes.
