"""One bounded public-file download for offline MoneyPuck testing only.

No application imports, environment loading, credentials, database, paid provider,
retry, redirects, or scheduler integration. Run explicitly; cached files are reused.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zlib
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/nhl-low-cost-provider-research/moneypuck-offline-test"
URL = "https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv"
MAX_BYTES = 160 * 1024 * 1024
WALL_SECONDS = 90
MAX_COMPRESSED_BYTES = 40 * 1024 * 1024
TARGET_NAME = "all_teams.csv"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise HTTPError(req.full_url, code, "Redirects disabled for this test", headers, fp)


def worker(*, compressed=False):
    started = time.monotonic()
    temporary = OUTPUT / "all_teams.csv.part"
    report = {"url": URL, "attempts": 1, "maximum_bytes": MAX_BYTES,
              "hard_wall_seconds": WALL_SECONDS,
              "observed_at": datetime.now(timezone.utc).isoformat()}
    total = 0
    wire_total = 0
    wire_cap = MAX_COMPRESSED_BYTES if compressed else MAX_BYTES
    digest = hashlib.sha256()
    try:
        req = Request(URL, headers={"User-Agent": "G-Sports-offline-data-audit/1.0",
                                    "Accept-Encoding": "gzip" if compressed else "identity"})
        with build_opener(NoRedirect()).open(req, timeout=15) as response:
            report.update(status=response.status, last_modified=response.headers.get("Last-Modified"),
                          etag=response.headers.get("ETag"),
                          content_length=response.headers.get("Content-Length"))
            if response.status != 200:
                raise ValueError("Only a complete HTTP 200 download is admitted")
            encoding = response.headers.get("Content-Encoding", "identity")
            if encoding not in ({"gzip", "identity"} if compressed else {"identity"}):
                raise ValueError("Unexpected transport compression")
            report.update(content_encoding=encoding, maximum_wire_bytes=wire_cap)
            decoder = zlib.decompressobj(31) if encoding == "gzip" else None
            if report["content_length"] and int(report["content_length"]) > wire_cap:
                raise ValueError("Declared file size exceeds test cap")
            with temporary.open("wb") as target:
                while True:
                    if time.monotonic() - started > WALL_SECONDS:
                        raise TimeoutError("Test deadline exceeded")
                    chunk = response.read(min(65536, wire_cap - wire_total + 1))
                    if not chunk:
                        break
                    wire_total += len(chunk)
                    if wire_total > wire_cap:
                        raise ValueError("Transport byte budget exceeded")
                    if decoder is not None:
                        chunk = decoder.decompress(chunk, MAX_BYTES - total + 1)
                        if decoder.unconsumed_tail or decoder.unused_data:
                            raise ValueError("Compression expansion budget or trailing data rejected")
                    total += len(chunk)
                    if total > MAX_BYTES:
                        raise ValueError("Downloaded file exceeds test cap")
                    digest.update(chunk)
                    target.write(chunk)
            if decoder is not None and not decoder.eof:
                raise ValueError("Incomplete gzip stream")
            if report["content_length"] and wire_total != int(report["content_length"]):
                raise ValueError("Incomplete response body")
        if total == 0:
            raise ValueError("Empty file")
        temporary.replace(OUTPUT / TARGET_NAME)
        report.update(result="downloaded", bytes=total, wire_bytes=wire_total, sha256=digest.hexdigest(),
                      completed_at=datetime.now(timezone.utc).isoformat())
    except Exception as exc:
        report.update(result="failed", error=f"{type(exc).__name__}: {exc}", bytes=total)
    report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    (OUTPUT / "download.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report), flush=True)
    return 0 if report["result"] == "downloaded" else 1


def main():
    global OUTPUT, URL, MAX_BYTES, TARGET_NAME
    compressed = "--compressed" in sys.argv
    if compressed:
        OUTPUT = ROOT / "artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14"
    goalies = "--goalies" in sys.argv
    if goalies:
        if compressed:
            raise ValueError("Goalie ZIP transport does not require double compression")
        URL = "https://peter-tanner.com/moneypuck/downloads/seasonPlayersSummary/goalies/2026.zip"
        MAX_BYTES = 2_000_000
        TARGET_NAME = "goalies.zip"
        OUTPUT = ROOT / "artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14/goalies"
    nhl_reference = "--nhl-reference" in sys.argv
    if nhl_reference:
        if compressed or goalies:
            raise ValueError("Select one source per isolated test admission")
        URL = "https://api-web.nhle.com/v1/score/2026-10-13"
        MAX_BYTES = 2_000_000
        TARGET_NAME = "nhl-score-2026-10-13.json"
        OUTPUT = ROOT / "artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14/nhl"
    summary_reference = "--summary-reference" in sys.argv
    if summary_reference:
        if compressed or goalies or nhl_reference:
            raise ValueError("Select one source per isolated test admission")
        URL = "https://moneypuck.com/moneypuck/playerData/seasonSummary/2026/regular/teams.csv"
        MAX_BYTES = 2_000_000
        TARGET_NAME = "teams-summary.csv"
        OUTPUT = ROOT / "artifacts/nhl-low-cost-provider-research/moneypuck-offline-test/compressed-2026-10-14/summary"
    OUTPUT.mkdir(parents=True, exist_ok=True)
    if "--worker" in sys.argv:
        return worker(compressed=compressed)
    target = OUTPUT / TARGET_NAME
    ledger = OUTPUT / "attempt.json"
    if target.exists():
        try:
            metadata = json.loads((OUTPUT / "download.json").read_text(encoding="utf-8"))
            digest = hashlib.sha256()
            with target.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
            if (metadata.get("result") != "downloaded" or target.stat().st_size != metadata.get("bytes")
                    or digest.hexdigest() != metadata.get("sha256")):
                raise ValueError("Cached provenance mismatch")
        except (OSError, ValueError):
            print("Existing cache failed provenance checks; no replacement request sent", flush=True)
            return 1
        print("Verified local archive reused; no HTTP request sent", flush=True)
        return 0
    # Exclusive creation survives failures/restarts and prevents concurrent copies
    # from sending another request. A failed test requires deliberate reassessment.
    try:
        with ledger.open("x", encoding="utf-8") as handle:
            json.dump({"url": URL, "maximum_attempts": 1,
                       "admitted_at": datetime.now(timezone.utc).isoformat()}, handle)
    except FileExistsError:
        print("Prior admission exists; another request is blocked", flush=True)
        return 1
    kwargs = {"timeout": WALL_SECONDS, "check": False}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        command = [sys.executable, __file__, "--worker"] + (["--compressed"] if compressed else [])
        if goalies:
            command.append("--goalies")
        if nhl_reference:
            command.append("--nhl-reference")
        if summary_reference:
            command.append("--summary-reference")
        return subprocess.run(command, **kwargs).returncode
    except subprocess.TimeoutExpired:
        report = {"url": URL, "attempts": 1, "result": "failed",
                  "error": "Hard 90-second process deadline exceeded; no retry"}
        (OUTPUT / "download.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
