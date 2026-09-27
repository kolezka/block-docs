#!/usr/bin/env python3
"""Lint block-style documentation trees."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union


DEFAULT_EXEMPTIONS = ("reference", "superpowers", "comparisons", "plans", "specs")
MANDATORY_DOCS = ("README", "CONTRACTS", "INVARIANTS", "GAPS", "OPERATIONS")
REQUIRED_FIELDS = ("block", "doc", "verified_against", "verified_on")
LIST_FIELDS = ("owns", "depends_on")
PIN_RE = re.compile(r"^(?:spec@)?[0-9a-fA-F]{7,40}$")
DOC_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*$")
FIELD_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):(?:[ \t]*(.*))?$")
HEADING_RE = re.compile(r"^(#{1,6})[ \t]+.+$")
ENFORCEMENT_RE = re.compile(r"^[ \t]*enforcement:[ \t]*(\S.*)$")
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
EVIDENCE_RE = re.compile(
    r"\[(?:verified|inferred|assumption)\]"
    r"|\[(?:verified|inferred|assumption|historical|design):[ \t]*[^\]\n]+\]"
)
VERIFIED_TAG_RE = re.compile(r"\[verified(?::[ \t]*[^\]\n]+)?\]")
EVIDENCE_COLON_DETAIL_OPEN_RE = re.compile(r"\[(?:verified|inferred|assumption):[ \t]*")
SCOPE_LINE_RE = re.compile(r"^[ \t]*scope:[ \t]*(\S.*)$")
SCOPE_PLACEHOLDER_VALUES = ("none", "n/a")
REVERT_SUBJECT_RE = re.compile(r"revert\b", re.IGNORECASE)
LIST_ITEM_RE = re.compile(r"^(?:[-*+]|\d+[.)])[ \t]+\S")
ABSOLUTE_WORD_RE = re.compile(
    r"\b(?:every|only|never|always|all|none|cannot|read-only|no[ \t]+other)\b",
    re.IGNORECASE,
)


FrontMatterValue = Union[str, List[str]]


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    code: str
    message: str


@dataclass
class Page:
    path: Path
    display_path: str
    relative_docs_path: PurePosixPath
    text: Optional[str]
    body: str = ""
    body_start_line: int = 1
    metadata: Optional[Dict[str, FrontMatterValue]] = None
    field_lines: Dict[str, int] = field(default_factory=dict)
    pin_valid: bool = False

    @property
    def is_root(self) -> bool:
        return len(self.relative_docs_path.parts) == 1

    @property
    def doc(self) -> Optional[str]:
        value = self.metadata.get("doc") if self.metadata else None
        return value if isinstance(value, str) else None

    @property
    def block(self) -> Optional[str]:
        value = self.metadata.get("block") if self.metadata else None
        return value if isinstance(value, str) else None

    @property
    def pin(self) -> Optional[str]:
        value = self.metadata.get("verified_against") if self.metadata else None
        return value if isinstance(value, str) else None


@dataclass(frozen=True)
class Citation:
    path: str
    symbol: str
    line: int


@dataclass(frozen=True)
class OwnedPath:
    raw: str
    parts: Tuple[str, ...]
    is_prefix: bool


@dataclass(frozen=True)
class PinState:
    available: bool
    ancestor: bool
    oid: Optional[str] = None


@dataclass
class LintResult:
    findings: List[Finding]
    scanned_files: int
    skipped_spec_citations: int
    notes: List[str] = field(default_factory=list)

    @property
    def errors(self) -> int:
        return sum(finding.code.startswith("E") for finding in self.findings)

    @property
    def warnings(self) -> int:
        return sum(finding.code.startswith("W") for finding in self.findings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="blockdocs_lint.py")
    parser.add_argument("docs_dir", help="block documentation directory")
    parser.add_argument("--repo", help="repository root, defaults to the current directory")
    parser.add_argument(
        "--exempt",
        action="append",
        default=[],
        metavar="DIR",
        help="additional directory to skip, relative to docs-dir",
    )
    parser.add_argument("--strict", action="store_true", help="fail on warnings")
    parser.add_argument(
        "--no-git",
        action="store_true",
        help="skip ancestry checks and inspect files from --repo",
    )
    parser.add_argument(
        "--drift",
        metavar="REF",
        help="warn about citation and ownership drift between each page's pin and REF",
    )
    return parser


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _resolve_directory(parser: argparse.ArgumentParser, raw: str, label: str) -> Path:
    try:
        path = Path(raw).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        parser.error("{} is not an accessible directory: {}".format(label, exc))
    if not path.is_dir():
        parser.error("{} is not a directory: {}".format(label, raw))
    return path


def _parse_exemptions(
    parser: argparse.ArgumentParser,
    values: Iterable[str],
) -> Set[Tuple[str, ...]]:
    exemptions: Set[Tuple[str, ...]] = set()
    for raw in tuple(DEFAULT_EXEMPTIONS) + tuple(values):
        normalized = raw.replace("\\", "/").strip("/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts:
            parser.error("--exempt must be a directory relative to docs-dir: {!r}".format(raw))
        exemptions.add(path.parts)
    return exemptions


def _is_exempt(path: PurePosixPath, exemptions: Set[Tuple[str, ...]]) -> bool:
    for exempt in exemptions:
        if path.parts[: len(exempt)] == exempt:
            return True
    return False


def _display_path(path: Path, repo: Path) -> str:
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return path.as_posix()


def _safe_markdown_text(path: Path, repo: Path) -> Tuple[Optional[str], Optional[str]]:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        return None, "Markdown path is not readable: {}".format(exc)
    if not _is_within(resolved, repo):
        return None, "Markdown path escapes --repo"
    if not resolved.is_file():
        return None, "Markdown path is not a regular file"
    try:
        return resolved.read_text(encoding="utf-8"), None
    except (OSError, UnicodeError) as exc:
        return None, "Markdown file is not readable UTF-8: {}".format(exc)


def _parse_flow_list(raw: str) -> Tuple[Optional[List[str]], Optional[str]]:
    if not raw.startswith("[") or not raw.endswith("]"):
        return None, "must be a flow-style list"
    inner = raw[1:-1].strip()
    if not inner:
        return [], None
    values: List[str] = []
    for item in inner.split(","):
        value = item.strip()
        if not value or any(character in value for character in "[]{}"):
            return None, "contains unsupported list syntax"
        if value.startswith(("'", '"')) or value.endswith(("'", '"')):
            return None, "contains unsupported quoted list syntax"
        values.append(value)
    return values, None


def _parse_front_matter(
    text: str,
) -> Tuple[
    Optional[Dict[str, FrontMatterValue]],
    Dict[str, int],
    str,
    int,
    Optional[Tuple[int, str]],
]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return None, {}, text, 1, (1, "front matter is missing")

    closing_index: Optional[int] = None
    for index in range(1, len(lines)):
        if lines[index] == "---":
            closing_index = index
            break
    if closing_index is None:
        return None, {}, text, 1, (1, "front matter has no closing delimiter")

    metadata: Dict[str, FrontMatterValue] = {}
    field_lines: Dict[str, int] = {}
    for index in range(1, closing_index):
        line = lines[index]
        line_number = index + 1
        if not line:
            continue
        if line[0].isspace() or line.startswith(("-", "?", ":")):
            return None, {}, text, 1, (
                line_number,
                "unsupported front matter syntax; only scalar values and flow-style lists are supported",
            )
        match = FIELD_RE.fullmatch(line)
        if not match:
            return None, {}, text, 1, (
                line_number,
                "unsupported front matter syntax; expected key: value",
            )
        key, raw_value = match.group(1), (match.group(2) or "").strip()
        if key in metadata:
            return None, {}, text, 1, (line_number, "duplicate front matter field {!r}".format(key))
        if raw_value.startswith("["):
            value, error = _parse_flow_list(raw_value)
            if error:
                return None, {}, text, 1, (
                    line_number,
                    "field {!r} {}".format(key, error),
                )
            metadata[key] = value or []
        elif raw_value.startswith(("{", "|", ">", "&", "*", "!")):
            return None, {}, text, 1, (
                line_number,
                "unsupported front matter syntax for field {!r}".format(key),
            )
        else:
            metadata[key] = raw_value
        field_lines[key] = line_number

    body_start_line = closing_index + 2
    body = "\n".join(lines[closing_index + 1 :])
    if text.endswith("\n"):
        body += "\n"
    return metadata, field_lines, body, body_start_line, None


def _validate_front_matter(page: Page) -> List[Finding]:
    if page.metadata is None:
        return []

    findings: List[Finding] = []
    metadata = page.metadata
    for key in REQUIRED_FIELDS:
        if key not in metadata:
            findings.append(
                Finding(page.display_path, 1, "E001", "missing required field {!r}".format(key))
            )
            continue
        value = metadata[key]
        if not isinstance(value, str):
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines[key],
                    "E001",
                    "field {!r} must be a scalar value".format(key),
                )
            )
        elif not value:
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines[key],
                    "E001",
                    "field {!r} must not be empty".format(key),
                )
            )

    if not page.is_root and page.path.name == "README.md" and "owns" not in metadata:
        findings.append(Finding(page.display_path, 1, "E001", "block README must declare 'owns'"))

    for key in LIST_FIELDS:
        if key not in metadata:
            continue
        value = metadata[key]
        if not isinstance(value, list):
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines[key],
                    "E001",
                    "field {!r} must be a flow-style list".format(key),
                )
            )
            continue
        if key == "owns" and not value:
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines[key],
                    "E001",
                    "field 'owns' must not be empty",
                )
            )
        if any(not item.strip() for item in value):
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines[key],
                    "E001",
                    "field {!r} contains an empty item".format(key),
                )
            )

    if any(key in metadata for key in LIST_FIELDS):
        if page.is_root or page.path.name != "README.md":
            for key in LIST_FIELDS:
                if key in metadata:
                    findings.append(
                        Finding(
                            page.display_path,
                            page.field_lines[key],
                            "E001",
                            "field {!r} is only allowed on a block README".format(key),
                        )
                    )

    verified_on = metadata.get("verified_on")
    if isinstance(verified_on, str) and verified_on:
        try:
            parsed_date = dt.datetime.strptime(verified_on, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = None
        if parsed_date is None or parsed_date.isoformat() != verified_on:
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines["verified_on"],
                    "E001",
                    "field 'verified_on' must be a valid YYYY-MM-DD date",
                )
            )

    pin = metadata.get("verified_against")
    if isinstance(pin, str) and pin:
        if not PIN_RE.fullmatch(pin):
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines["verified_against"],
                    "E001",
                    "field 'verified_against' must be a short commit SHA or spec@SHA",
                )
            )
        else:
            page.pin_valid = True

    owns = metadata.get("owns")
    if isinstance(owns, list):
        for owned_path in owns:
            normalized = PurePosixPath(owned_path.replace("\\", "/").removesuffix("/**").rstrip("/"))
            if (
                not normalized.parts
                or normalized.is_absolute()
                or ".." in normalized.parts
                or owned_path.startswith("~")
            ):
                findings.append(
                    Finding(
                        page.display_path,
                        page.field_lines["owns"],
                        "E001",
                        "field 'owns' contains a path that escapes --repo: {!r}".format(owned_path),
                    )
                )

    return findings


def _strip_fenced_code(text: str) -> str:
    stripped: List[str] = []
    fence_character: Optional[str] = None
    fence_length = 0
    for line in text.splitlines(keepends=True):
        candidate = line.lstrip(" ")
        indent = len(line) - len(candidate)
        marker = re.match(r"(`{3,}|~{3,})", candidate) if indent <= 3 else None
        if fence_character is None:
            if marker:
                fence_character = marker.group(1)[0]
                fence_length = len(marker.group(1))
                stripped.append("\n" if line.endswith("\n") else "")
            else:
                stripped.append(line)
        else:
            closing = re.match(
                re.escape(fence_character) + "{" + str(fence_length) + r",}[ \t]*$",
                candidate.rstrip("\r\n"),
            )
            stripped.append("\n" if line.endswith("\n") else "")
            if closing:
                fence_character = None
                fence_length = 0
    return "".join(stripped)


def _check_identity(page: Page) -> List[Finding]:
    if page.metadata is None:
        return []
    findings: List[Finding] = []
    block = page.block
    doc = page.doc
    if block:
        if page.is_root and block != "_root":
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines.get("block", 1),
                    "E002",
                    "root page block must be '_root'",
                )
            )
        elif not page.is_root:
            expected = page.relative_docs_path.parent.name
            if block != expected:
                findings.append(
                    Finding(
                        page.display_path,
                        page.field_lines.get("block", 1),
                        "E002",
                        "block {!r} must equal containing directory {!r}".format(block, expected),
                    )
                )
    if doc:
        expected_doc = page.path.stem
        if doc != expected_doc:
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines.get("doc", 1),
                    "E003",
                    "doc {!r} must match filename {!r}".format(doc, page.path.name),
                )
            )
        elif doc != "README" and not DOC_RE.fullmatch(doc):
            findings.append(
                Finding(
                    page.display_path,
                    page.field_lines.get("doc", 1),
                    "E003",
                    "doc must be README or uppercase kebab-case",
                )
            )
    return findings


def _check_complete_blocks(pages: Sequence[Page], docs_dir: Path, repo: Path) -> List[Finding]:
    block_files: Dict[PurePosixPath, Set[str]] = {}
    for page in pages:
        if page.is_root:
            continue
        directory = page.relative_docs_path.parent
        block_files.setdefault(directory, set()).add(page.path.name)

    findings: List[Finding] = []
    for directory, names in sorted(block_files.items(), key=lambda item: item[0].as_posix()):
        display = _display_path(docs_dir.joinpath(*directory.parts), repo)
        for doc in MANDATORY_DOCS:
            filename = "{}.md".format(doc)
            if filename not in names:
                findings.append(
                    Finding(display, 1, "E004", "block is missing mandatory file: {}".format(filename))
                )
    return findings


def _owned_path(raw: str) -> Optional[OwnedPath]:
    normalized_raw = raw.replace("\\", "/")
    is_prefix = normalized_raw.endswith("/") or normalized_raw.endswith("/**")
    base = normalized_raw.removesuffix("/**").rstrip("/")
    path = PurePosixPath(base)
    if not path.parts or path.is_absolute() or ".." in path.parts:
        return None
    return OwnedPath(raw=raw, parts=path.parts, is_prefix=is_prefix)


def _ownership_overlaps(first: OwnedPath, second: OwnedPath) -> bool:
    if first.parts == second.parts:
        return True
    if first.is_prefix and second.parts[: len(first.parts)] == first.parts:
        return True
    if second.is_prefix and first.parts[: len(second.parts)] == second.parts:
        return True
    return False


def _check_ownership(pages: Sequence[Page]) -> List[Finding]:
    owners: List[Tuple[str, Page, List[OwnedPath]]] = []
    for page in pages:
        if page.is_root or page.path.name != "README.md" or page.metadata is None:
            continue
        values = page.metadata.get("owns")
        if not isinstance(values, list):
            continue
        unique: Dict[Tuple[Tuple[str, ...], bool], OwnedPath] = {}
        for raw in values:
            parsed = _owned_path(raw)
            if parsed is not None:
                unique[(parsed.parts, parsed.is_prefix)] = parsed
        directory_owner = page.relative_docs_path.parent.as_posix()
        owners.append((directory_owner, page, list(unique.values())))

    findings: List[Finding] = []
    for first_index, (first_owner, first_page, first_paths) in enumerate(owners):
        for second_owner, second_page, second_paths in owners[first_index + 1 :]:
            overlaps: Set[Tuple[str, str]] = set()
            for first_path in first_paths:
                for second_path in second_paths:
                    if _ownership_overlaps(first_path, second_path):
                        overlaps.add((first_path.raw, second_path.raw))
            for first_raw, second_raw in sorted(overlaps):
                findings.append(
                    Finding(
                        second_page.display_path,
                        second_page.field_lines.get("owns", 1),
                        "E005",
                        "paths {!r} and {!r} overlap and are owned by both {!r} and {!r}".format(
                            first_raw,
                            second_raw,
                            first_owner,
                            second_owner,
                        ),
                    )
                )
    return findings


def _parse_citation_value(raw_value: str) -> Optional[Tuple[str, str]]:
    value = raw_value.strip()
    wrapped_enforcement = value.startswith("enforcement:")
    if wrapped_enforcement:
        value = value.partition(":")[2].strip()
        if value.startswith("planned:"):
            value = value.partition(":")[2].strip()
    if "::" not in value:
        return None
    path, symbol = (part.strip() for part in value.split("::", 1))
    if wrapped_enforcement:
        symbol = re.sub(r"\s+\([^)]*\)$", "", symbol)
    if not path or not symbol or "/" not in path and "." not in path:
        return None
    if len(symbol) >= 2 and symbol[0] == symbol[-1] and symbol[0] in "\"'":
        symbol = symbol[1:-1]
    elif symbol.endswith("()"):
        symbol = symbol[:-2]
    if not symbol:
        return None
    return path, symbol


def _opens_quoted_symbol(text: str, index: int) -> bool:
    """True when the quote character at `index` immediately follows a `::`
    separator (spaces allowed in between), i.e. it opens a cited symbol's
    quoted form (`path::"symbol"`) rather than an apostrophe in
    surrounding prose (`the writer's note`).
    """
    cursor = index
    while cursor > 0 and text[cursor - 1] in " \t":
        cursor -= 1
    return text[cursor - 2 : cursor] == "::"


def _colon_detail_span_quoted(line: str, start: int) -> Optional[str]:
    quote: Optional[str] = None
    for index in range(start, len(line)):
        char = line[index]
        if quote is not None:
            if char == quote:
                quote = None
            continue
        if char in "\"'" and _opens_quoted_symbol(line, index):
            quote = char
            continue
        if char == "]":
            return line[start:index]
    return None


def _colon_detail_span(line: str, start: int) -> Optional[str]:
    """Return the text of a `[verified: ...]`-style detail starting at
    `start`, treating a `]` inside a quoted symbol as part of the detail
    rather than its terminator (a cited code snippet can itself contain
    `]`, e.g. `rows[0]`, or a `;`, e.g. `end();`). A quote is only honored
    right after a `::` separator, so an apostrophe in ordinary prose (`the
    writer's note`) cannot swallow the rest of the line. If that stricter
    scan still finds no terminator, fall back to the first `]` on the
    line so the detail is never silently dropped.
    """
    span = _colon_detail_span_quoted(line, start)
    if span is not None:
        return span
    end = line.find("]", start)
    if end == -1:
        return None
    return line[start:end]


def _split_unquoted(text: str, separator: str) -> List[str]:
    """Split `text` on `separator`, ignoring occurrences inside a quoted
    symbol that opens right after a `::` separator.
    """
    pieces: List[str] = []
    current: List[str] = []
    quote: Optional[str] = None
    for index, char in enumerate(text):
        if quote is not None:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "\"'" and _opens_quoted_symbol(text, index):
            quote = char
            current.append(char)
            continue
        if char == separator:
            pieces.append("".join(current))
            current = []
            continue
        current.append(char)
    pieces.append("".join(current))
    return pieces


def _has_backtick(piece: str) -> bool:
    return "`" in piece


def _colon_detail_citations(line: str) -> List[Tuple[str, str]]:
    """Parse every `[verified|inferred|assumption: ...]` colon-detail
    citation on `line`, skipping any piece that contains a backtick
    (its citation is already captured by the inline-code pass over the
    same line, and parsing it again here would both double-count it and
    corrupt its path with the leading backtick).
    """
    found: List[Tuple[str, str]] = []
    for open_match in EVIDENCE_COLON_DETAIL_OPEN_RE.finditer(line):
        detail = _colon_detail_span(line, open_match.end())
        if detail is None:
            continue
        for piece in _split_unquoted(detail, ";"):
            if _has_backtick(piece):
                continue
            parsed = _parse_citation_value(piece)
            if parsed is not None:
                found.append(parsed)
    return found


def _extract_citations(page: Page) -> List[Citation]:
    prose = _strip_fenced_code(page.body)
    citations: List[Citation] = []
    for offset, line in enumerate(prose.splitlines()):
        for inline_match in INLINE_CODE_RE.finditer(line):
            parsed = _parse_citation_value(inline_match.group(1))
            if parsed is not None:
                path, symbol = parsed
                citations.append(
                    Citation(path=path, symbol=symbol, line=page.body_start_line + offset)
                )
        for path, symbol in _colon_detail_citations(line):
            citations.append(
                Citation(path=path, symbol=symbol, line=page.body_start_line + offset)
            )
    return citations


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            ("git", "-C", str(repo), *args),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(args=("git", *args), returncode=127, stdout=b"", stderr=str(exc).encode())


def _pin_state(repo: Path, pin: str) -> PinState:
    sha = pin.split("@", 1)[-1].lower()
    resolved = _git(repo, "rev-parse", "--verify", "{}^{{commit}}".format(sha))
    if resolved.returncode != 0:
        return PinState(available=False, ancestor=False)
    oid = resolved.stdout.decode("ascii").strip()
    ancestor = _git(repo, "merge-base", "--is-ancestor", oid, "HEAD").returncode == 0
    return PinState(available=True, ancestor=ancestor, oid=oid)


def _check_pins(
    pages: Sequence[Page],
    repo: Path,
    no_git: bool,
) -> Tuple[List[Finding], Dict[str, PinState]]:
    if no_git:
        return [], {}
    states: Dict[str, PinState] = {}
    findings: List[Finding] = []
    for page in pages:
        pin = page.pin
        if not page.pin_valid or pin is None:
            continue
        if pin not in states:
            states[pin] = _pin_state(repo, pin)
        state = states[pin]
        line = page.field_lines.get("verified_against", 1)
        if not state.available:
            findings.append(
                Finding(page.display_path, line, "E007", "pin {!r} is not available in --repo".format(pin))
            )
        elif not state.ancestor:
            findings.append(
                Finding(page.display_path, line, "E007", "pin {!r} is not an ancestor of HEAD".format(pin))
            )
    return findings, states


def _safe_repo_path(repo: Path, raw: str) -> Tuple[Optional[Path], Optional[str]]:
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not path.parts
        or path.is_absolute()
        or ".." in path.parts
        or normalized.startswith("~")
    ):
        return None, "citation path {!r} escapes --repo".format(raw)
    candidate = repo.joinpath(*path.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError):
        return None, "citation path {!r} is absent in --repo".format(raw)
    if not _is_within(resolved, repo):
        return None, "citation path {!r} escapes --repo".format(raw)
    if not resolved.is_file():
        return None, "citation path {!r} is absent in --repo".format(raw)
    return resolved, None


def _read_worktree_source(repo: Path, raw: str) -> Tuple[Optional[bytes], Optional[str]]:
    path, error = _safe_repo_path(repo, raw)
    if error:
        return None, error
    try:
        return path.read_bytes(), None
    except OSError as exc:
        return None, "citation path {!r} is not readable: {}".format(raw, exc)


def _valid_git_relative_path(raw: str) -> bool:
    normalized = raw.replace("\\", "/")
    path = PurePosixPath(normalized)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts and not normalized.startswith("~")


def _read_pinned_source(repo: Path, pin: str, raw: str) -> Tuple[Optional[bytes], Optional[str]]:
    if not _valid_git_relative_path(raw):
        return None, "citation path {!r} escapes --repo".format(raw)
    sha = pin.split("@", 1)[-1]
    result = _git(repo, "show", "{}:{}".format(sha, raw.replace("\\", "/")))
    if result.returncode != 0:
        return None, "citation path {!r} is absent at pin {!r}".format(raw, pin)
    return result.stdout, None


def _check_citations(
    pages: Sequence[Page],
    repo: Path,
    no_git: bool,
    pin_states: Mapping[str, PinState],
) -> Tuple[List[Finding], int]:
    findings: List[Finding] = []
    skipped_spec_citations = 0
    source_cache: Dict[Tuple[str, str], Tuple[Optional[bytes], Optional[str]]] = {}
    for page in pages:
        pin = page.pin
        for citation in _extract_citations(page):
            if no_git and page.pin_valid and pin and pin.startswith("spec@"):
                skipped_spec_citations += 1
                continue
            if no_git:
                cache_key = ("worktree", citation.path)
                if cache_key not in source_cache:
                    source_cache[cache_key] = _read_worktree_source(repo, citation.path)
                source, error = source_cache[cache_key]
            else:
                if not page.pin_valid or pin is None:
                    continue
                state = pin_states.get(pin)
                if state is None or not state.available or not state.ancestor:
                    continue
                if pin.startswith("spec@"):
                    skipped_spec_citations += 1
                    continue
                cache_key = (pin, citation.path)
                if cache_key not in source_cache:
                    source_cache[cache_key] = _read_pinned_source(repo, pin, citation.path)
                source, error = source_cache[cache_key]
            if error:
                findings.append(Finding(page.display_path, citation.line, "E006", error))
            elif source is not None and citation.symbol.encode("utf-8") not in source:
                location = "in --repo file" if no_git else "at pin {!r}".format(pin)
                findings.append(
                    Finding(
                        page.display_path,
                        citation.line,
                        "E006",
                        "citation symbol {!r} was not found {}".format(citation.symbol, location),
                    )
                )
    return findings, skipped_spec_citations


def _contract_entries(prose: str) -> List[Tuple[int, int, int]]:
    lines = prose.splitlines()
    headings: List[Tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1))))

    entries: List[Tuple[int, int, int]] = []
    for heading_index, (line_index, level) in enumerate(headings):
        if level not in (2, 3):
            continue
        next_same_or_higher = len(lines)
        contains_level_three = False
        for next_line, next_level in headings[heading_index + 1 :]:
            if next_level <= level:
                next_same_or_higher = next_line
                break
            if level == 2 and next_level == 3:
                contains_level_three = True
        if level == 2 and contains_level_three:
            continue
        entries.append((line_index, next_same_or_higher, level))
    return entries


def _absolute_claim_regions(prose: str) -> List[Tuple[int, int]]:
    """Return every (start, end) line range W004 must scan: each leaf
    `_contract_entries` section, plus the regions that have no leaf
    heading of its own and so falls outside `_contract_entries`: the text
    before the first heading, intro text under a level-1 title, and a parent `##` group's intro text before
    its first `###` child.
    """
    lines = prose.splitlines()
    headings: List[Tuple[int, int]] = []
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match:
            headings.append((index, len(match.group(1))))

    regions: List[Tuple[int, int]] = [
        (heading_line + 1, end_line) for heading_line, end_line, _level in _contract_entries(prose)
    ]

    if headings and headings[0][0] > 0:
        regions.append((0, headings[0][0]))

    # Intro text under a page title, up to the next heading or page end.
    for heading_index, (line_index, level) in enumerate(headings):
        if level != 1:
            continue
        if heading_index + 1 < len(headings):
            end_line = headings[heading_index + 1][0]
        else:
            end_line = len(lines)
        if end_line > line_index + 1:
            regions.append((line_index + 1, end_line))

    for heading_index, (line_index, level) in enumerate(headings):
        if level != 2:
            continue
        first_child_line: Optional[int] = None
        for next_line, next_level in headings[heading_index + 1 :]:
            if next_level <= level:
                break
            if next_level == 3 and first_child_line is None:
                first_child_line = next_line
        if first_child_line is not None and first_child_line > line_index + 1:
            regions.append((line_index + 1, first_child_line))

    return regions


def _scope_value_is_meaningful(value: str) -> bool:
    """A `scope:` value counts only when it names a command or a path
    set (it contains a backtick or a `/`); a bare placeholder like `none`
    or `n/a` does not, even though `n/a` itself contains a `/`.
    """
    normalized = value.strip().lower()
    if normalized in SCOPE_PLACEHOLDER_VALUES:
        return False
    return "`" in value or "/" in value


def _section_has_scope_line(lines: Sequence[str]) -> bool:
    for line in lines:
        match = SCOPE_LINE_RE.match(line)
        if match and _scope_value_is_meaningful(match.group(1)):
            return True
    return False


def _check_contract_enforcement(page: Page) -> List[Finding]:
    if page.path.name != "CONTRACTS.md":
        return []
    prose = _strip_fenced_code(page.body)
    lines = prose.splitlines()
    findings: List[Finding] = []
    for heading_line, end_line, _level in _contract_entries(prose):
        if not any(
            ENFORCEMENT_RE.match(line.strip().strip("`").strip())
            for line in lines[heading_line + 1 : end_line]
        ):
            findings.append(
                Finding(
                    page.display_path,
                    page.body_start_line + heading_line,
                    "E008",
                    "contract entry has no nonempty enforcement: value",
                )
            )
    return findings


def _strip_inline_code(text: str) -> str:
    return INLINE_CODE_RE.sub(" ", text)


def _strip_claim_noise(line: str) -> str:
    """Remove a colon-tag citation detail (`[verified|inferred|assumption:
    ...]`) and blank out a whole `enforcement:` line, before scanning
    prose for absolute words. A citation's own path/symbol text, or an
    enforcement value such as `(every route)`, is not a claim and must
    not trigger W004.
    """
    if ENFORCEMENT_RE.match(line.strip().strip("`").strip()):
        return ""
    pieces: List[str] = []
    cursor = 0
    for open_match in EVIDENCE_COLON_DETAIL_OPEN_RE.finditer(line):
        if open_match.start() < cursor:
            continue
        detail = _colon_detail_span(line, open_match.end())
        pieces.append(line[cursor : open_match.start()])
        if detail is None:
            cursor = open_match.end()
            continue
        cursor = open_match.end() + len(detail) + 1  # past the closing ]
    pieces.append(line[cursor:])
    return "".join(pieces)


def _paragraph_blocks(lines: Sequence[str]) -> List[Tuple[int, int]]:
    """Split lines into blank-line-delimited paragraphs, with each markdown
    list item split out as its own block that also absorbs its indented
    continuation lines. A heading line is always a hard block boundary,
    even with no blank line before or after it.
    """
    blocks: List[Tuple[int, int]] = []
    start: Optional[int] = None
    in_list_item = False

    def close(end: int) -> None:
        nonlocal start, in_list_item
        if start is not None:
            blocks.append((start, end))
            start = None
        in_list_item = False

    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or HEADING_RE.match(line):
            close(index)
            continue
        if LIST_ITEM_RE.match(stripped):
            close(index)
            start = index
            in_list_item = True
            continue
        if in_list_item and line[:1] in (" ", "\t"):
            continue  # indented continuation line: absorb into the list block
        if in_list_item:
            close(index)
        if start is None:
            start = index
    close(len(lines))
    return blocks


def _is_spec_mode(page: Page) -> bool:
    pin = page.pin
    return isinstance(pin, str) and pin.startswith("spec@")


def _check_unscoped_absolute_claims(page: Page) -> List[Finding]:
    if page.path.name not in ("CONTRACTS.md", "INVARIANTS.md"):
        return []
    if _is_spec_mode(page):
        return []
    prose = _strip_fenced_code(page.body)
    lines = prose.splitlines()
    findings: List[Finding] = []
    for start_line, end_line in _absolute_claim_regions(prose):
        section_lines = lines[start_line:end_line]
        if _section_has_scope_line(section_lines):
            continue
        offending_line: Optional[int] = None
        for block_start, block_end in _paragraph_blocks(section_lines):
            block_lines = section_lines[block_start:block_end]
            if not VERIFIED_TAG_RE.search("\n".join(block_lines)):
                continue
            for offset, line in enumerate(block_lines):
                scanned = _strip_claim_noise(_strip_inline_code(line))
                if ABSOLUTE_WORD_RE.search(scanned):
                    offending_line = start_line + block_start + offset
                    break
            if offending_line is not None:
                break
        if offending_line is not None:
            findings.append(
                Finding(
                    page.display_path,
                    page.body_start_line + offending_line,
                    "W004",
                    "absolute claim has no scope line in this section",
                )
            )
    return findings


def _check_verified_citation(page: Page) -> List[Finding]:
    if page.is_root or page.path.name == "README.md":
        return []
    if _is_spec_mode(page):
        return []
    prose = _strip_fenced_code(page.body)
    lines = prose.splitlines()
    scoped_ranges = [
        (heading_line + 1, end_line)
        for heading_line, end_line, _level in _contract_entries(prose)
        if _section_has_scope_line(lines[heading_line + 1 : end_line])
    ]
    findings: List[Finding] = []
    for block_start, block_end in _paragraph_blocks(lines):
        if any(
            start <= block_start and block_end <= end for start, end in scoped_ranges
        ):
            continue
        block_lines = lines[block_start:block_end]
        block_text = "\n".join(block_lines)
        if not VERIFIED_TAG_RE.search(block_text):
            continue
        has_citation = any(
            _parse_citation_value(match.group(1)) is not None
            for line in block_lines
            for match in INLINE_CODE_RE.finditer(line)
        )
        if not has_citation:
            has_citation = any(_colon_detail_citations(line) for line in block_lines)
        if has_citation:
            continue
        offending_line = block_start
        for offset, line in enumerate(block_lines):
            if VERIFIED_TAG_RE.search(line):
                offending_line = block_start + offset
                break
        findings.append(
            Finding(
                page.display_path,
                page.body_start_line + offending_line,
                "W005",
                "verified claim has no recognized citation",
            )
        )
    return findings


def _check_pins_consistent(
    pages: Sequence[Page], pin_states: Mapping[str, PinState]
) -> List[Finding]:
    pins: Dict[str, Page] = {}
    for page in pages:
        if page.pin_valid and page.pin is not None:
            state = pin_states.get(page.pin)
            identity = page.pin
            if state is not None and state.oid is not None:
                identity = ("spec@" if page.pin.startswith("spec@") else "") + state.oid
            pins.setdefault(identity, page)
    if len(pins) <= 1:
        return []
    pin_list = sorted(pins)
    page = pins[pin_list[1]]
    return [
        Finding(
            page.display_path,
            page.field_lines.get("verified_against", 1),
            "W001",
            "tree contains more than one verified_against pin: {}".format(", ".join(pin_list)),
        )
    ]


def _check_prose(page: Page) -> List[Finding]:
    prose = _strip_fenced_code(page.body)
    findings: List[Finding] = []
    for offset, line in enumerate(prose.splitlines()):
        if "–" in line or "—" in line:
            findings.append(
                Finding(
                    page.display_path,
                    page.body_start_line + offset,
                    "W002",
                    "prose contains an en dash or em dash",
                )
            )
    if not page.is_root and page.path.name != "README.md" and not EVIDENCE_RE.search(prose):
        findings.append(
            Finding(
                page.display_path,
                page.body_start_line,
                "W003",
                "block page has no recognized evidence tag",
            )
        )
    return findings


def _resolvable_pin_state(page: Page, pin_states: Mapping[str, PinState]) -> Optional[PinState]:
    pin = page.pin
    if not page.pin_valid or pin is None or pin.startswith("spec@"):
        return None
    state = pin_states.get(pin)
    if state is None or not state.available or not state.ancestor or state.oid is None:
        return None
    return state


def _check_drift_citations(pages: Sequence[Page], repo: Path, drift: str, pin_states: Mapping[str, PinState]) -> List[Finding]:
    findings: List[Finding] = []
    for page in pages:
        state = _resolvable_pin_state(page, pin_states)
        if state is None:
            continue
        drifted_paths: List[str] = []
        seen_paths: Set[str] = set()
        for citation in _extract_citations(page):
            if citation.path in seen_paths or not _valid_git_relative_path(citation.path):
                continue
            seen_paths.add(citation.path)
            diff = _git(repo, "diff", "--quiet", state.oid, drift, "--", citation.path)
            if diff.returncode == 1:
                drifted_paths.append(citation.path)
        for path in sorted(drifted_paths):
            findings.append(
                Finding(
                    page.display_path,
                    page.body_start_line,
                    "W006",
                    "cited file {!r} differs between pin {!r} and {!r}".format(path, page.pin, drift),
                )
            )
    return findings


def _check_drift_reverts(pages: Sequence[Page], repo: Path, drift: str, pin_states: Mapping[str, PinState]) -> List[Finding]:
    findings: List[Finding] = []
    for page in pages:
        if page.is_root or page.path.name != "README.md" or page.metadata is None:
            continue
        state = _resolvable_pin_state(page, pin_states)
        if state is None:
            continue
        owns = page.metadata.get("owns")
        if not isinstance(owns, list):
            continue
        owned_paths = [parsed for parsed in (_owned_path(raw) for raw in owns) if parsed is not None]
        if not owned_paths:
            continue
        log = _git(repo, "log", "--format=%H%x09%s", "{}..{}".format(state.oid, drift))
        if log.returncode != 0:
            continue
        for line in log.stdout.decode("utf-8", "replace").splitlines():
            sha, _, subject = line.partition("\t")
            if not sha or not REVERT_SUBJECT_RE.match(subject):
                continue
            # -m --first-parent so a merge revert's touched paths are enumerated
            # too (plain `show --name-only` reports none for a merge commit);
            # quotePath=false so a non-ASCII path isn't C-style escaped and can
            # still match against `owns:`.
            show = _git(
                repo,
                "-c",
                "core.quotePath=false",
                "diff-tree",
                "--no-commit-id",
                "--name-only",
                "-r",
                "-m",
                "--first-parent",
                sha,
            )
            if show.returncode != 0:
                continue
            touched_paths = [
                parsed
                for raw_path in show.stdout.decode("utf-8", "replace").splitlines()
                if raw_path.strip()
                for parsed in (_owned_path(raw_path),)
                if parsed is not None
            ]
            if any(
                _ownership_overlaps(touched_path, owned_path)
                for touched_path in touched_paths
                for owned_path in owned_paths
            ):
                findings.append(
                    Finding(
                        page.display_path,
                        page.field_lines.get("owns", 1),
                        "W007",
                        "revert commit {} ({!r}) touches an owned path between pin {!r} and {!r}".format(
                            sha[:12], subject, page.pin, drift
                        ),
                    )
                )
    return findings


def _pin_ancestor_of_drift(repo: Path, oid: str, drift: str) -> bool:
    return _git(repo, "merge-base", "--is-ancestor", oid, drift).returncode == 0


def _check_drift(
    pages: Sequence[Page],
    repo: Path,
    drift: str,
    pin_states: Mapping[str, PinState],
) -> Tuple[List[Finding], List[str]]:
    eligible_pages: List[Page] = []
    notes: List[str] = []
    for page in pages:
        state = _resolvable_pin_state(page, pin_states)
        if state is None:
            continue
        if _pin_ancestor_of_drift(repo, state.oid, drift):
            eligible_pages.append(page)
        else:
            notes.append(
                "{}: {!r} is not a descendant of pin {!r}; drift checks skipped".format(
                    page.display_path, drift, page.pin
                )
            )
    findings = _check_drift_citations(eligible_pages, repo, drift, pin_states)
    findings.extend(_check_drift_reverts(eligible_pages, repo, drift, pin_states))
    return findings, notes


def lint(
    docs_dir: Path,
    repo: Path,
    exemptions: Set[Tuple[str, ...]],
    no_git: bool,
    drift: Optional[str] = None,
) -> LintResult:
    pages: List[Page] = []
    findings: List[Finding] = []
    for path in sorted(docs_dir.rglob("*.md")):
        relative = PurePosixPath(path.relative_to(docs_dir).as_posix())
        if _is_exempt(relative, exemptions):
            continue
        display = _display_path(path, repo)
        text, read_error = _safe_markdown_text(path, repo)
        page = Page(path=path, display_path=display, relative_docs_path=relative, text=text)
        pages.append(page)
        if read_error:
            findings.append(Finding(display, 1, "E001", read_error))
            continue
        assert text is not None
        metadata, field_lines, body, body_start_line, parse_error = _parse_front_matter(text)
        page.metadata = metadata
        page.field_lines = field_lines
        page.body = body
        page.body_start_line = body_start_line
        if parse_error:
            line, message = parse_error
            findings.append(Finding(display, line, "E001", message))
            continue
        findings.extend(_validate_front_matter(page))
        findings.extend(_check_identity(page))
        findings.extend(_check_contract_enforcement(page))
        findings.extend(_check_prose(page))
        findings.extend(_check_unscoped_absolute_claims(page))
        findings.extend(_check_verified_citation(page))

    if not pages:
        findings.append(
            Finding(_display_path(docs_dir, repo), 1, "E999", "no non-exempt Markdown files were scanned")
        )
        return LintResult(findings=findings, scanned_files=0, skipped_spec_citations=0)

    findings.extend(_check_complete_blocks(pages, docs_dir, repo))
    findings.extend(_check_ownership(pages))
    pin_findings, pin_states = _check_pins(pages, repo, no_git)
    findings.extend(pin_findings)
    citation_findings, skipped_spec_citations = _check_citations(
        pages, repo, no_git, pin_states
    )
    findings.extend(citation_findings)
    findings.extend(_check_pins_consistent(pages, pin_states))
    notes: List[str] = []
    if drift:
        drift_findings, notes = _check_drift(pages, repo, drift, pin_states)
        findings.extend(drift_findings)
    findings.sort(key=lambda finding: (finding.path, finding.line, finding.code, finding.message))
    return LintResult(
        findings=findings,
        scanned_files=len(pages),
        skipped_spec_citations=skipped_spec_citations,
        notes=sorted(notes),
    )


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _print_result(result: LintResult) -> None:
    for finding in result.findings:
        print("{}:{}: {} {}".format(finding.path, finding.line, finding.code, finding.message))
    for note in result.notes:
        print("Note: {}".format(note))
    if result.skipped_spec_citations:
        print(
            "Limitations: {} {} skipped for spec pin; planned targets were not checked".format(
                result.skipped_spec_citations,
                _plural(result.skipped_spec_citations, "code citation", "code citations"),
            )
        )
    print(
        "Summary: {} {}, {} {}, {} {} scanned".format(
            result.errors,
            _plural(result.errors, "error", "errors"),
            result.warnings,
            _plural(result.warnings, "warning", "warnings"),
            result.scanned_files,
            _plural(result.scanned_files, "file", "files"),
        )
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    repo = _resolve_directory(parser, args.repo or str(Path.cwd()), "--repo")
    docs_dir = _resolve_directory(parser, args.docs_dir, "docs-dir")
    if not _is_within(docs_dir, repo):
        parser.error("docs-dir must resolve inside --repo")
    exemptions = _parse_exemptions(parser, args.exempt)
    if args.drift:
        if args.no_git:
            parser.error("--drift cannot be combined with --no-git")
        if _git(repo, "rev-parse", "--verify", "{}^{{commit}}".format(args.drift)).returncode != 0:
            parser.error("--drift ref {!r} does not resolve to a commit in --repo".format(args.drift))
    result = lint(docs_dir, repo, exemptions, args.no_git, args.drift)
    _print_result(result)
    if result.errors or args.strict and result.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
