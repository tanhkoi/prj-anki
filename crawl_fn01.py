"""
[File Name]  crawl_fn01.py
[Description]  Fetching and scraping kanji data by JLPT level
[Refactored]   Fixes race conditions, unbounded threads, missing timeouts,
               adds retry logic, rate limiting, and structured concurrency.
"""

import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# Configuration — centralised so values are never scattered across the file
# ---------------------------------------------------------------------------
REQUEST_TIMEOUT = 10          # seconds before a request is abandoned
MAX_WORKERS = 5               # concurrent threads (one per JLPT level)
RATE_LIMIT_DELAY = 0.5        # seconds between requests per thread
MAX_RETRIES = 3               # retry attempts on transient failures
BACKOFF_FACTOR = 1.0          # exponential back-off multiplier
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB safety cap on response size

# ---------------------------------------------------------------------------
# Logging — replaces bare print() calls so output can be redirected/filtered
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Failure tracking — typed reasons make the missing log easy to filter/query
# ---------------------------------------------------------------------------
class FailReason(str, Enum):
    HTTP_ERROR    = "http_error"     # non-200 after all retries
    SIZE_EXCEEDED = "size_exceeded"  # response body too large, skipped
    NOT_FOUND     = "not_found"      # 200 OK but target <div> was absent


@dataclass
class MissedKanji:
    kanji:     str
    level:     int
    reason:    FailReason
    detail:    str        # human-readable context (status code, url, …)
    timestamp: str        # ISO-8601 UTC


# ---------------------------------------------------------------------------
# A per-thread write lock prevents interleaved output across threads
# (FIX: race condition — multiple threads writing to the same file)
# ---------------------------------------------------------------------------
_file_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Session factory
# Centralises timeout, SSL verification, and retry configuration so every
# requests.get() call inherits them automatically.
# (FIX: missing timeout; FIX: no retry logic; SEC: explicit SSL verification)
# ---------------------------------------------------------------------------
def _build_session() -> requests.Session:
    """Return a requests.Session pre-configured with retries and timeouts."""
    session = requests.Session()

    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        # Retry on these status codes (server-side transient errors)
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Attach a default timeout via an event hook so callers cannot forget it
    session.request = lambda method, url, **kwargs: requests.Session.request(
        session, method, url,
        timeout=kwargs.pop("timeout", REQUEST_TIMEOUT),
        verify=True,          # SEC: enforce SSL certificate verification
        **kwargs,
    )
    return session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _write_missing_log(level: int, missed: list[MissedKanji]) -> None:
    """
    Persist all missed kanji for a level to a JSON file.
    Each entry carries the kanji, failure reason, detail, and timestamp so
    the file can be used as a re-run manifest later.
    """
    if not missed:
        return

    path = f"jlpt_level_{level}_missing.json"
    payload = {
        "level":        level,
        "generated_at": _now(),
        "total_missed": len(missed),
        "kanji":        [asdict(m) for m in missed],
    }
    with _file_lock:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    log.info(
        "JLPT-%d — %d missed kanji written to %s", level, len(missed), path
    )


# ---------------------------------------------------------------------------
# Kanji list fetching
# ---------------------------------------------------------------------------
def fetch_kanji_data(session: requests.Session, level: int) -> list[str]:
    """
    Fetch the list of kanji for a JLPT level from kanjiapi.dev.
    Returns an empty list on failure rather than propagating exceptions.
    """
    url = f"https://kanjiapi.dev/v1/kanji/jlpt-{level}"
    try:
        response = session.get(url)
        response.raise_for_status()  # raises HTTPError for 4xx/5xx

        # SEC: cap memory usage before parsing
        if len(response.content) > MAX_RESPONSE_BYTES:
            log.warning("Response for level %d exceeds size limit; skipping.", level)
            return []

        data = response.json()
        if not isinstance(data, list):
            log.warning("Unexpected API response shape for level %d.", level)
            return []
        return data

    except requests.RequestException as exc:
        log.error("Failed to fetch kanji list for JLPT-%d: %s", level, exc)
        return []


# ---------------------------------------------------------------------------
# Structured kanji entry type
# ---------------------------------------------------------------------------
@dataclass
class KanjiEntry:
    Kanji:       str
    Vietsino:    str = ""
    Meaning:     str = ""
    Level:       str = ""
    StrokeCount: str = ""
    Kunyomi:     str = ""
    Onyomi:      str = ""
    Radicals:    str = ""   # optional — left blank when absent on the page
    Explanation: str = ""


# ---------------------------------------------------------------------------
# HTML → structured parser
# ---------------------------------------------------------------------------

# Maps Vietnamese section-header text found in the div to KanjiEntry fields.
# Order matters only for readability; matching is done by dict lookup.
_HEADER_MAP: dict[str, str] = {
    "Ý nghĩa:"              : "Meaning",
    "Trình độ JLPT:"        : "Level",
    "Số nét:"               : "StrokeCount",
    "Âm Kun:"               : "Kunyomi",
    "Âm On:"                : "Onyomi",
    "Bộ thủ:"               : "Radicals",         # traditional header
    "Cấu tạo từ các bộ thủ:": "Radicals",         # alternative header for radicals
    "Gợi ý cách nhớ:"       : "Explanation",
}

# Lines we want to discard entirely (kanji repeat, separator, pronunciation link)
_SKIP_LINES = {" - ", "→ Quy tắc chuyển âm"}


def _parse_div(kanji: str, div_text: str) -> KanjiEntry:
    """
    Convert the raw multi-line text of the target <div> into a KanjiEntry.

    Algorithm — single-pass state machine:
      1. The very first non-skipped, non-header line after the kanji character
         is Vietsino (e.g. "NHẤT").
      2. Every Vietnamese header in _HEADER_MAP switches the active field.
      3. All non-header, non-skip lines that follow are accumulated into the
         active field and later joined.
      4. Kunyomi / Onyomi / Explanation tokens that land on their own lines
         (including bare "," separators) are joined with ",  " or " ".
    """
    entry = KanjiEntry(Kanji=kanji)
    lines = [ln.strip() for ln in div_text.splitlines() if ln.strip()]

    current_field: str | None = None
    accumulator:   list[str]  = []
    vietsino_found = False
    first_kanji_skipped = False  # Only skip the initial kanji character at the start

    def _flush(field: str, tokens: list[str]) -> None:
        """Write accumulated tokens into the correct entry field."""
        if not tokens or not field:
            return
        joined = _join_tokens(field, tokens)
        if getattr(entry, field):                  # already has a value — append
            setattr(entry, field, getattr(entry, field) + ",  " + joined)
        else:
            setattr(entry, field, joined)

    for line in lines:
        # Always skip fixed decorative lines
        if line in _SKIP_LINES:
            continue

        # Skip the initial kanji character only once (at the very beginning)
        if line == kanji and not first_kanji_skipped:
            first_kanji_skipped = True
            continue

        # Check if this line is a section header
        if line in _HEADER_MAP:
            _flush(current_field, accumulator)
            accumulator    = []
            current_field  = _HEADER_MAP[line]
            continue

        # First real content line (before any header) → Vietsino
        if not vietsino_found and current_field is None:
            entry.Vietsino = line
            vietsino_found = True
            continue

        # Everything else accumulates into the active field
        if current_field:
            accumulator.append(line)

    # Flush whatever was being built when the text ended
    _flush(current_field, accumulator)
    return entry


def _join_tokens(field: str, tokens: list[str]) -> str:
    """
    Join a list of raw tokens into a clean string for a given field.

    - Kunyomi / Onyomi: bare "," lines are separators → join meaningful tokens
      with ",  " so the result looks like "ひと-,  ひと.つ".
    - Radicals: multiple radical characters/groups → join with space to preserve order
    - Explanation: tokens are fragments of a mnemonic sentence → join with " ".
    - All other fields: single-value, just strip and return.
    """
    if field in ("Kunyomi", "Onyomi"):
        meaningful = [t for t in tokens if t != ","]
        return ",  ".join(meaningful)

    if field == "Radicals":
        # Join multiple radicals with space (e.g. "一 勹")
        return " ".join(t for t in tokens if t != ",")

    if field == "Explanation":
        # Collapse whitespace-only separators and re-join as a readable sentence
        return " ".join(t for t in tokens if t != ",")

    # Single-value fields (Meaning, Level, StrokeCount)
    return tokens[0] if tokens else ""


# ---------------------------------------------------------------------------
# Single-kanji scraping
# ---------------------------------------------------------------------------
def scrape_kanji_data(
    session: requests.Session,
    kanji: str,
    level: int,
) -> tuple[KanjiEntry | None, MissedKanji | None]:
    """
    Scrape the detail page for one kanji from nhaikanji.com.

    Returns a (entry, missed) tuple:
      - entry  — structured KanjiEntry on success, or None on hard failure
      - missed — a MissedKanji record when something went wrong, else None

    Three failure modes are distinguished:
      NOT_FOUND     — page loaded but the target <div> was absent
      HTTP_ERROR    — non-200 status after all retries
      SIZE_EXCEEDED — response body exceeded the safety cap
    """
    safe_kanji = quote(kanji, safe="")
    url = f"https://nhaikanji.com/{safe_kanji}"

    try:
        response = session.get(url)
        response.raise_for_status()

        # SEC: cap response size before handing to the HTML parser
        if len(response.content) > MAX_RESPONSE_BYTES:
            log.warning("Response for kanji '%s' exceeds size limit; skipping.", kanji)
            return None, MissedKanji(
                kanji=kanji, level=level,
                reason=FailReason.SIZE_EXCEEDED,
                detail=f"Response size {len(response.content)} B > {MAX_RESPONSE_BYTES} B",
                timestamp=_now(),
            )

        soup = BeautifulSoup(response.text, "html.parser")
        target_class = (
            "flex flex-col items-center space-y-2 p-4 "
            "min-[1366px]:items-start min-[1366px]:text-left"
        )
        div = soup.find("div", class_=target_class)

        if div:
            div_text = div.get_text(separator="\n", strip=True)
            entry    = _parse_div(kanji, div_text)
            return entry, None

        # Target div missing — record as NOT_FOUND
        log.debug("Target div not found for '%s'.", kanji)
        return None, MissedKanji(
            kanji=kanji, level=level,
            reason=FailReason.NOT_FOUND,
            detail="Target div absent on page",
            timestamp=_now(),
        )

    except requests.RequestException as exc:
        log.error("Failed to scrape kanji '%s': %s", kanji, exc)
        return None, MissedKanji(
            kanji=kanji, level=level,
            reason=FailReason.HTTP_ERROR,
            detail=str(exc),
            timestamp=_now(),
        )


# ---------------------------------------------------------------------------
# Per-level worker
# Processes every kanji for one JLPT level and writes results to its file.
# (FIX: file opened once per level, not once per kanji)
# (FIX: _file_lock prevents concurrent writes corrupting the file)
# (PERF: RATE_LIMIT_DELAY avoids hammering the remote server)
# ---------------------------------------------------------------------------
def process_level(level: int) -> None:
    """Fetch, scrape, and write all kanji data for a single JLPT level."""
    session     = _build_session()          # each thread owns its session
    output_file = f"jlpt_level_{level}.json"

    log.info("Starting JLPT-%d", level)
    kanji_list = fetch_kanji_data(session, level)

    if not kanji_list:
        log.warning("No kanji returned for JLPT-%d; skipping.", level)
        return

    results: list[dict] = []
    missed:  list[MissedKanji] = []

    for kanji in kanji_list:
        log.info("Processing kanji: %s (JLPT-%d)", kanji, level)
        entry, miss = scrape_kanji_data(session, kanji, level)

        if miss:
            missed.append(miss)
            # For NOT_FOUND we have no structured entry — skip from output.
            # The missing log is the source of truth for re-runs.
        if entry:
            results.append(asdict(entry))

        time.sleep(RATE_LIMIT_DELAY)

    # Write structured JSON output in one locked block
    with _file_lock:
        with open(output_file, "w", encoding="utf-8") as fh:
            json.dump(results, fh, ensure_ascii=False, indent=4)

    # Write missing-kanji manifest (uses its own internal lock)
    _write_missing_log(level, missed)

    log.info(
        "Finished JLPT-%d — %d/%d written, %d missed.",
        level, len(results), len(kanji_list), len(missed),
    )


# ---------------------------------------------------------------------------
# Main entry point
# Uses ThreadPoolExecutor instead of raw threading.Thread so the pool size
# is bounded, exceptions surface properly, and cleanup is automatic.
# (FIX: unbounded thread creation replaced with a fixed-size pool)
# ---------------------------------------------------------------------------
def main() -> None:
    levels = range(5, 3, -1)  # 5 → 1

    # MAX_WORKERS == 5 means one thread per level — levels run in parallel
    # but each thread processes its kanji list serially (rate-limit friendly).
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_level, level): level for level in levels}

        for future in as_completed(futures):
            level = futures[future]
            exc = future.exception()
            if exc:
                log.error("Unhandled error processing JLPT-%d: %s", level, exc)
            else:
                log.info("JLPT-%d task completed successfully.", level)


if __name__ == "__main__":
    main()