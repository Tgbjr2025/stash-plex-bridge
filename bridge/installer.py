"""CLI orchestrator — runs the 5 phases with skip-on-success semantics."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from bridge import paths
from bridge.configure import capture_inputs, render_configs, ConfigInputs
from bridge.detect import detect_paths, DetectionResult
from bridge.fetch import fetch_all
from bridge.install_plugins import install_all, InstallTargets
from bridge.state import State, PhaseStatus
from bridge.validate import run_all_checks, Check

PHASES = ("detect", "fetch", "configure", "install", "validate")


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="bridge.installer",
        description="Install and configure three Stash/Plex bridge plugins.",
    )
    p.add_argument("--force", action="store_true",
                   help="Rerun all phases even if previously OK.")
    p.add_argument("--phase", choices=PHASES, default=None,
                   help="Run just one phase.")
    p.add_argument("--update", action="store_true",
                   help="Re-pull vendor repos to their latest.")
    p.add_argument("--stash-port", type=int, default=9999)
    p.add_argument("--plex-port", type=int, default=32400)
    p.add_argument("--reset-tokens", action="store_true",
                   help="Wipe saved secrets and re-prompt.")
    p.add_argument("--dry-run", action="store_true",
                   help="Plan phases but do not execute side effects.")
    return p


def _setup_logging(logs_dir: Optional[Path] = None) -> None:
    if logs_dir is None:
        logs_dir = paths.logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    logfile = logs_dir / f"install-{stamp}.log"
    # basicConfig is a no-op if handlers are already set; reset first.
    root = logging.getLogger()
    if root.handlers:
        root.handlers.clear()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(logfile), logging.StreamHandler()],
    )


def _hash_inputs(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, default=str).encode()
    ).hexdigest()


def _run_phase(
    state: State,
    name: str,
    inputs_hash: str,
    force: bool,
    body,
) -> bool:
    if not state.should_run(name, inputs_hash=inputs_hash, force=force):
        logging.info("phase %s: skipped (already ok)", name)
        return True
    logging.info("phase %s: running", name)
    try:
        body()
    except Exception as e:
        state.set_phase(name, PhaseStatus.FAILED,
                        inputs_hash=inputs_hash, error=str(e))
        state.save()
        logging.error("phase %s failed: %s", name, e)
        return False
    state.set_phase(name, PhaseStatus.OK, inputs_hash=inputs_hash)
    state.save()
    return True


def main(argv: Optional[list[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)

    cwd = Path.cwd()
    state_path = cwd / "state.json"
    logs_dir = cwd / "bridge" / "logs"
    try:
        _setup_logging(logs_dir)
    except OSError:
        # If log dir can't be created (e.g. in tests without the dir), fall back
        # to stream-only logging.
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

    state = State.load(state_path)

    if args.reset_tokens:
        state.secrets.clear()
        state.save()
        logging.info("secrets cleared")

    stash_url = f"http://localhost:{args.stash_port}"
    plex_url = f"http://localhost:{args.plex_port}"

    results: dict[str, object] = {}

    def do_detect():
        results["detect"] = detect_paths(state)

    def do_fetch():
        commits = fetch_all(paths.vendor_dir())
        results["fetch_commits"] = commits

    def do_configure():
        inputs = capture_inputs(
            state, stash_url=stash_url, plex_url=plex_url,
        )
        render_configs(inputs, paths.vendor_dir())
        results["config_inputs"] = inputs

    def do_install():
        detect_result = results.get("detect")
        if detect_result is not None:
            stash_plugins = Path(detect_result.stash_plugins)
            plex_plugins = Path(detect_result.plex_plugins)
        else:
            stash_plugins = Path(state.get_path("stash_plugins") or "")
            plex_plugins = Path(state.get_path("plex_plugins") or "")
        targets = InstallTargets(
            stash_plugins=stash_plugins,
            plex_plugins=plex_plugins,
            project_root=paths.project_root(),
        )
        install_all(paths.vendor_dir(), targets)

    def do_validate():
        inputs: ConfigInputs = results.get("config_inputs") or ConfigInputs(
            stash_url=stash_url,
            stash_api_key=state.get_secret("stash_api_key") or "",
            plex_url=plex_url,
            plex_token=state.get_secret("plex_token") or "",
            plex_library=state.get_secret("plex_library") or "",
        )
        checks: list[Check] = run_all_checks(
            stash_url=inputs.stash_url,
            stash_api_key=inputs.stash_api_key,
            plex_url=inputs.plex_url,
            plex_token=inputs.plex_token,
        )
        for c in checks:
            logging.info("check %s: %s — %s",
                         c.name, "OK" if c.ok else "FAIL", c.detail)
        if not all(c.ok for c in checks):
            raise RuntimeError("one or more validation checks failed")

    phase_bodies = {
        "detect": (do_detect, {"env": ["LOCALAPPDATA", "USERPROFILE", "APPDATA"]}),
        "fetch": (do_fetch, {"update": args.update}),
        "configure": (do_configure, {"stash_url": stash_url, "plex_url": plex_url}),
        "install": (do_install, {}),
        "validate": (do_validate, {}),
    }

    selected = [args.phase] if args.phase else list(PHASES)

    for name in selected:
        body, inputs_obj = phase_bodies[name]
        inputs_hash = _hash_inputs(inputs_obj)
        if args.dry_run:
            logging.info("[dry-run] would run phase %s", name)
            continue
        ok = _run_phase(state, name, inputs_hash, args.force, body)
        if not ok:
            return 1

    logging.info("all selected phases complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
