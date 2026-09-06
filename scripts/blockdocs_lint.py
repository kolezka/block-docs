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
    r"|\[(?:historical|design):[ \t]*[^\]\n]+\]"
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


def _extract_citations(page: Page) -> List[Citation]:
    prose = _strip_fenced_code(page.body)
    citations: List[Citation] = []
    for offset, line in enumerate(prose.splitlines()):
        for inline_match in INLINE_CODE_RE.finditer(line):
            value = inline_match.group(1).strip()
            wrapped_enforcement = value.startswith("enforcement:")
            if wrapped_enforcement:
                value = value.partition(":")[2].strip()
                if value.startswith("planned:"):
                    value = value.partition(":")[2].strip()
            if "::" not in value:
                continue
            path, symbol = (part.strip() for part in value.split("::", 1))
            if wrapped_enforcement:
                symbol = re.sub(r"\s+\([^)]*\)$", "", symbol)
            if not path or not symbol or "/" not in path and "." not in path:
                continue
            if len(symbol) >= 2 and symbol[0] == symbol[-1] and symbol[0] in "\"'":
                symbol = symbol[1:-1]
            elif symbol.endswith("()"):
                symbol = symbol[:-2]
            if symbol:
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


def lint(docs_dir: Path, repo: Path, exemptions: Set[Tuple[str, ...]], no_git: bool) -> LintResult:
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
    findings.sort(key=lambda finding: (finding.path, finding.line, finding.code, finding.message))
    return LintResult(
        findings=findings,
        scanned_files=len(pages),
        skipped_spec_citations=skipped_spec_citations,
    )


def _plural(count: int, singular: str, plural: str) -> str:
    return singular if count == 1 else plural


def _print_result(result: LintResult) -> None:
    for finding in result.findings:
        print("{}:{}: {} {}".format(finding.path, finding.line, finding.code, finding.message))
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
    result = lint(docs_dir, repo, exemptions, args.no_git)
    _print_result(result)
    if result.errors or args.strict and result.warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
