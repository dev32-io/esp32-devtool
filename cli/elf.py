"""Resolve the firmware ELF path for a given board manifest.

Used by gdb + audit-prod-strip. Generalizes away from per-project ELF name
hardcodes by either using manifest.build_artifact when declared, or by
globbing build/*.elf and accepting a single result.
"""
from __future__ import annotations

from pathlib import Path

from cli.board import BoardManifest
from cli.errors import TransportUnavailable


def resolve_elf(manifest: BoardManifest, firmware_dir: Path) -> Path:
    """Return the path to the firmware ELF, or raise DevtoolError.

    Resolution order:
      1. If manifest.build_artifact is set, use <firmware_dir>/build/<artifact>.
         Raise if that file doesn't exist (user error, not a fallback case).
      2. Otherwise glob <firmware_dir>/build/*.elf. Exactly one match wins.
      3. Zero matches: error suggesting build-first.
      4. Multiple matches: error asking the user to set build_artifact.
    """
    build_dir = firmware_dir / "build"

    if manifest.build_artifact:
        explicit = build_dir / manifest.build_artifact
        if not explicit.exists():
            raise TransportUnavailable(
                f"ELF not found: {explicit} ({manifest.build_artifact} missing)",
                next_step=(
                    f"build first with `idf.py build` from {firmware_dir}, "
                    f"or verify manifest.build_artifact ({manifest.build_artifact}) "
                    f"matches the actual artifact name"
                ),
            )
        return explicit

    elfs = sorted(build_dir.glob("*.elf"))
    if len(elfs) == 1:
        return elfs[0]
    if not elfs:
        raise TransportUnavailable(
            f"no ELF in {build_dir}",
            next_step=f"run `idf.py build` from {firmware_dir} first",
        )
    raise TransportUnavailable(
        f"ambiguous ELF in {build_dir}: {[e.name for e in elfs]}",
        next_step=(
            f"set `build_artifact: <name>.elf` in the {manifest.name} board manifest"
        ),
    )
