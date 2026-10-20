#!/usr/bin/env python3
"""Audit Markdown pages for Diátaxis cross-quadrant contamination.

Modes:
  audit (default)  report findings for each page against its declared quadrant
  --receipt        print a pre-filled Quadrant Classification Receipt as JSON
  --plan           propose keep/move/split/review for each page; writes nothing
  --list-rules     print the rule registry

Stdlib only, directly runnable. Exit codes: 0 clean, 1 findings, 2 usage or IO
error (2 wins over 1). The signals are heuristics over structure and wording;
they check structural and functional quality only and cannot certify the deep
quality that https://diataxis.fr/quality/ describes.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shlex
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROG = "audit_quadrant"
SCHEMA_VERSION = 1

# --------------------------------------------------------------------------------------
# Thresholds. Each is a deliberate, tested boundary; change one only with a fixture.
# --------------------------------------------------------------------------------------
MIN_WORDS_FOR_INFERENCE = 80  # visible prose words needed before inference, mismatch, mixed-undeclared run
PROCEDURE_MIN_ITEMS = 3  # ordered-list length that can count as a procedure
PROCEDURE_IMPERATIVE_RATIO = 0.5  # share of imperative items that turns an ordered list into a procedure
UNORDERED_PROCEDURE_RATIO = 1.0  # share of imperative items that turns a bulleted list into a procedure
EXP_IMPERATIVE_MINOR = 2  # imperative sentences in one explanation paragraph: minor
EXP_IMPERATIVE_MAJOR = 3  # imperative sentences in one explanation paragraph: major
OPTION_TABLE_MIN_ROWS = 6  # data rows before an option-style table reads as reference material
TUT_TABLE_MAX_ROWS = 8  # largest table a tutorial carries before it reads as a reference dump
DEFINITION_LIST_MIN = 3  # consecutive "term: definition" items that form a definition list
REF_PARAGRAPH_MAX_SENTENCES = 4  # longest reference paragraph before it reads as narrative
REF_WHY_MIN_SENTENCES = 2  # rationale sentences in one reference block before it digresses
HOWTO_EXPLANATION_MIN_SENTENCES = 3  # non-imperative sentences that make a how-to paragraph a lecture
FILE_ESCALATION_COUNT = 2  # an escalating minor rule firing this often in one file becomes major
LANDING_LIST_MAX = 7  # longest unordered landing list that may stay unsorted
LANDING_PROCEDURE_MAX_STEPS = 4  # longest procedure a landing page keeps as a quick start
INFER_MIN_SIGNAL_TYPES = 2  # distinct signal types a quadrant needs to be inferred
TUT_HOWTO_MIN_IMPERATIVES = 5  # imperatives in a voiceless tutorial before it reads as a how-to
MARKER_SCAN_LINES = 10  # non-blank lines after front matter searched for a diataxis marker

QUADRANTS = ("tutorial", "how-to", "reference", "explanation")
ALL_QUADRANTS = QUADRANTS + ("landing",)

QUADRANT_ALIASES = {
    "tutorial": "tutorial",
    "tutorials": "tutorial",
    "how-to": "how-to",
    "howto": "how-to",
    "how-tos": "how-to",
    "how-to-guide": "how-to",
    "how-to-guides": "how-to",
    "guide": "how-to",
    "guides": "how-to",
    "reference": "reference",
    "explanation": "explanation",
    "explanations": "explanation",
    "concepts": "explanation",
    "landing": "landing",
}

# Directory segments that declare a quadrant. File stems never declare one, and the
# plural `references` is deliberately absent so a skill's references/ is not misread.
PATH_SEGMENTS = {
    "tutorial": "tutorial",
    "tutorials": "tutorial",
    "how-to": "how-to",
    "how-tos": "how-to",
    "howto": "how-to",
    "how-to-guides": "how-to",
    "guides": "how-to",
    "reference": "reference",
    "api-reference": "reference",
    "explanation": "explanation",
    "explanations": "explanation",
    "concepts": "explanation",
    "topics": "explanation",
    "background": "explanation",
    "discussion": "explanation",
}

DEFAULT_DIRS = {
    "tutorial": "tutorials",
    "how-to": "how-to",
    "reference": "reference",
    "explanation": "explanation",
}

# Neighbours that share the action/cognition axis: the likeliest misclassification.
NEIGHBOUR = {
    "tutorial": "how-to",
    "how-to": "tutorial",
    "reference": "explanation",
    "explanation": "reference",
}

INDEX_NAMES = {"readme.md", "index.md", "index.mdx", "_index.md"}
MARKDOWN_SUFFIXES = {".md", ".mdx"}
SKIP_DIRS = {".git", "node_modules"}
OPERATIONS = ("create", "edit", "move", "split", "delete")

# Verbs that may open a primary execution directive (any list item `--check-directives` checks).
ACTIVE_VERBS = frozenset(
    """
    add answer apply ask assume audit avoid bound build check choose cite classify
    compare confirm connect copy create cut declare default define delete describe
    duplicate edit embed emit end expect file fill fix follow give group hand ignore
    include insert keep label lead let limit link list load mark match merge mirror
    move name narrate number offer omit open order pad paste pick place point prefer
    preserve print proceed promise put quote read reclassify record remove rename
    replace report restructure return route run scope set show split start state stop
    suppress survey teach test title treat trim use verify wrap write
    """.split()
)

# Verbs that make a documentation sentence read as an instruction. `consider`, `note`,
# `imagine`, and `see` are excluded on purpose: they are common in explanation prose.
IMPERATIVE_VERBS = frozenset(
    """
    run install create open set add configure enable disable click select type enter
    copy paste edit change delete remove restart deploy navigate download execute start
    stop build update upgrade save push pull commit clone export import launch log sign
    press choose replace rename move check verify test apply define write insert
    """.split()
)

# Verbs that are also common nouns or adjectives; they count as imperative only when an
# object-like token follows ("Set the flag", not "Set theory").
AMBIGUOUS_VERBS = frozenset(
    """
    type set check test log update change export import build commit start move copy
    open save push pull select enter sign
    """.split()
)

OBJECT_LEADS = frozenset(
    "the a an your this that these those it them all each every code up out in on to into".split()
)

SHELL_FENCES = frozenset(
    "bash sh shell console zsh fish powershell ps1 pwsh cmd terminal".split()
)

OS_MARKERS_RE = re.compile(
    r"\b(macOS|Windows|Linux|WSL|Ubuntu|Debian|Fedora|zsh|bash|fish|PowerShell)\b"
)
# Prompt lines mark a shell session only in unlabeled or plain-text code; `#` is left
# out because it opens comments in YAML, Python, and most other fence languages.
PROMPT_LINE_RE = re.compile(r"^\s*(\$|>|PS>|PS [A-Z]:\\.*>)\s")
PROMPT_FENCES = frozenset({"", "text", "txt", "plain", "plaintext"})

# --------------------------------------------------------------------------------------
# Rule registry
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Rule:
    id: str
    quadrants: tuple[str, ...]
    severity: str
    message: str
    advice: str
    destination: str
    escalates: bool = False
    suppressible: bool = True


RULES: dict[str, Rule] = {}


def _rule(rule_id: str, quadrants: tuple[str, ...], severity: str, message: str,
          advice: str, destination: str, *, escalates: bool = False) -> None:
    suppressible = not rule_id.startswith(("dir-", "suppression-", "declaration-"))
    RULES[rule_id] = Rule(rule_id, quadrants, severity, message, advice, destination,
                          escalates, suppressible)


EXP = ("explanation",)
REF = ("reference",)
TUT = ("tutorial",)
HOW = ("how-to",)
LAND = ("landing",)
ANY = ALL_QUADRANTS + ("none",)

_rule("exp-procedure-list", EXP, "major",
      "list of instructions in an explanation page", "move the procedure to a how-to guide", "how-to")
_rule("exp-terminal-steps", EXP, "major",
      "shell session after an instruction in an explanation page", "move to a how-to guide", "how-to")
_rule("exp-procedure-heading", EXP, "major",
      "procedure heading in an explanation page", "move the section to a how-to guide", "how-to")
_rule("exp-imperative-prose", EXP, "minor",
      "imperative sentences in an explanation paragraph", "move the instructions to a how-to guide", "how-to")
_rule("exp-option-table", EXP, "minor",
      "option or parameter table in an explanation page", "link the reference entry instead", "reference")

_rule("ref-procedure", REF, "major",
      "task procedure inside a reference page", "link the how-to guide instead", "how-to")
_rule("ref-opinion", REF, "major",
      "opinion or recommendation in a reference page", "state facts; move judgement to explanation", "explanation")
_rule("ref-narrative-voice", REF, "minor",
      "first-person or story voice in a reference page", "write neutral declarative entries", "explanation or tutorial")
_rule("ref-why-digression", REF, "minor",
      "design rationale inside a reference entry", "move the why to an explanation page", "explanation")
_rule("ref-narrative-paragraph", REF, "minor",
      f"paragraph longer than {REF_PARAGRAPH_MAX_SENTENCES} sentences in a reference page",
      "split it into entries, lists, or tables", "split into entries")
_rule("ref-hedge", REF, "minor",
      "hedged statement in a reference page", "state the fact or the measured limit", "state the fact")
_rule("ref-marketing", REF, "major",
      "promotional superlative in a reference page", "state the fact or the measured limit", "state the fact")

_rule("tut-choice", TUT, "major",
      "alternative path offered inside a tutorial", "keep one path; link how-to guides for variants", "how-to")
_rule("tut-explanation-heading", TUT, "major",
      "background or theory section inside a tutorial", "link an explanation page instead", "explanation")
_rule("tut-why-digression", TUT, "minor",
      "explanatory digression inside a tutorial", "keep one line plus a link to explanation", "explanation",
      escalates=True)
_rule("tut-reference-dump", TUT, "minor",
      "reference table or definition list inside a tutorial", "link the reference page instead", "reference")
_rule("tut-learning-claim", TUT, "minor",
      "promise of what the learner will learn", "state what we will build instead", "state what we will build")
_rule("tut-reads-as-howto", TUT, "minor",
      "tutorial has instructions but no tutor voice", "add the tutor voice or reclassify as how-to", "how-to")

_rule("howto-teaching-tone", HOW, "major",
      "teaching or reassuring tone inside a how-to guide", "move the lesson to a tutorial", "tutorial")
_rule("howto-concept-heading", HOW, "minor",
      "concept section inside a how-to guide", "link an explanation page instead", "explanation")
_rule("howto-explanation-block", HOW, "minor",
      "explanatory paragraph with no action inside a how-to guide", "move it to an explanation page",
      "explanation", escalates=True)
_rule("howto-option-table", HOW, "minor",
      "option or parameter table inside a how-to guide", "link the reference entry instead", "reference")
_rule("howto-title", HOW, "minor",
      "how-to title does not name the goal", "retitle as 'How to <goal>'", "retitle")

_rule("landing-long-list", LAND, "minor",
      f"unordered landing list longer than {LANDING_LIST_MAX} items and not alphabetical",
      "group, order, or shorten the list", "landing")
_rule("landing-bare-list", LAND, "minor",
      "list directly under a heading with no introduction", "add one sentence that frames the list", "landing")
_rule("landing-quadrant-content", LAND, "minor",
      f"landing page holds an option table or a procedure longer than {LANDING_PROCEDURE_MAX_STEPS} steps",
      "move it to a reference or how-to page and link it", "reference or how-to")

_rule("declaration-invalid", ANY, "major",
      "invalid quadrant declaration", "use tutorial, how-to, reference, explanation, or landing", "declaration")
_rule("declaration-conflict", ANY, "major",
      "front matter and marker declare different quadrants", "keep one declaration", "declaration")
_rule("declared-inferred-mismatch", QUADRANTS + LAND, "minor",
      "content reads as a different quadrant than declared", "split the page or reclassify it", "split or move")
_rule("mixed-undeclared", ("none",), "minor",
      "undeclared page mixes quadrants", "declare a quadrant and split the page", "split")
_rule("layout-empty-quadrant", ANY, "major",
      "quadrant directory holds no page besides its index", "add content or remove the directory", "add content or remove")

_rule("suppression-unknown-rule", ANY, "major",
      "suppression names an unknown or non-suppressible rule", "name a suppressible rule id", "suppression")
_rule("suppression-unterminated", ANY, "major",
      "example region has no end marker; region stays audited", "close it with <!-- /diataxis-example -->", "suppression")
_rule("suppression-unused", ANY, "minor",
      "suppression matches no finding", "remove the suppression", "suppression")

_rule("dir-structure", ANY, "major",
      "directive sections are missing or hold non-directive content", "keep `Do` and `Do not` as bullet lists", "directives")
_rule("dir-word-count", ANY, "major",
      "directive is outside the 8-12 word range", "rewrite the directive in 8-12 words", "directives")
_rule("dir-verb", ANY, "major",
      "directive does not lead with an active verb", "start with a verb from ACTIVE_VERBS", "directives")
_rule("dir-redirect-missing", ANY, "major",
      "negative directive has no redirect", "add '; <what to do instead>'", "directives")
_rule("dir-legacy-prompt", ANY, "major",
      "legacy reasoning prompt", "govern with structure and output schemas instead", "directives")
_rule("dir-shouting", ANY, "major",
      "all-caps emphasis word", "use plain case; structure carries the weight", "directives")

UNSUPPRESSIBLE_PREFIXES = ("dir-", "suppression-", "declaration-")

# --------------------------------------------------------------------------------------
# Patterns
# --------------------------------------------------------------------------------------
FENCE_OPEN_RE = re.compile(r"^(\s*)(`{3,}|~{3,})(.*)$")
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})(?:[ \t]+(.*?))?[ \t]*$")
SETEXT_RE = re.compile(r"^\s{0,3}(=+|-+)\s*$")
LIST_RE = re.compile(r"^(\s*)([-*+]|\d{1,9}[.)])\s+(.*)$")
TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>")
LINK_DEF_RE = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*\S")
ADMON_COLON_OPEN_RE = re.compile(r"^\s*(:{3,})(?!:)\s*\S")
ADMON_BANG_RE = re.compile(r"^(\s*)(?:!!!|\?\?\?\+?)\s+\S")
DETAILS_OPEN_RE = re.compile(r"^\s{0,3}<details\b", re.I)
DETAILS_CLOSE_RE = re.compile(r"</details\s*>", re.I)
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1")
IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
REF_LINK_RE = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
AUTOLINK_RE = re.compile(r"<https?://[^>]+>")
BARE_URL_RE = re.compile(r"https?://\S+")
EMPHASIS_RE = re.compile(r"[*_]{1,3}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
WORD_RE = re.compile(r"[A-Za-z0-9]")

LINK_SECTION_RE = re.compile(
    r"^(See also|Related|Further reading|Next steps|Additional resources|Sources|References)\b", re.I
)

MARKER_RE = re.compile(r"^\s*diataxis\s*:\s*(.*?)\s*$", re.S)
IGNORE_RE = re.compile(r"^\s*diataxis-ignore\s*:(.*)$", re.S)
IGNORE_FILE_RE = re.compile(r"^\s*diataxis-ignore-file\s*:(.*)$", re.S)
EXAMPLE_OPEN_RE = re.compile(r"^\s*diataxis-example\s*$")
EXAMPLE_CLOSE_RE = re.compile(r"^\s*/diataxis-example\s*$")
FRONTMATTER_KEY_RE = re.compile(r"^(diataxis|diataxis_type)\s*[:=]\s*(.*?)\s*$")

LEADING_SEQ_RE = re.compile(r"^(?:Then|Next|Now|First|Second|Finally|Afterwards)\b,?\s*", re.I)
LEADING_CLAUSE_RE = re.compile(r"^(?:If|When|Before|After|To|Once)\b[^,]{0,80},\s*", re.I)
CONDITIONAL_RE = re.compile(r"^(?:If|When)\b[^,]{0,80},", re.I)

# Explanation
# `type` and `enter` are also nouns ("a name and a type"); they count only with an object.
EXP_LEADIN_RE = re.compile(
    r"\b(run|execute|install)\b|\b(type|enter)\s+(the|this|these|a|an|in|into|it|following|CODE)\b", re.I
)
EXP_PROCEDURE_HEADING_RE = re.compile(r"^(Steps?|Procedure|Prerequisites|Installation|Quick ?start|How to)\b", re.I)
OPTION_HEADER_RE = re.compile(r"\b(defaults?|types?|required|parameters?|flags?|options?)\b", re.I)
# Reference
REF_SEQUENCE_RE = re.compile(r"\b(first|next|then|finally),? (you|we) (should|need to|will)\b", re.I)
REF_OPINION_RE = re.compile(
    r"\bI (recommend|suggest|think|believe)\b|\bwe recommend\b|\bshould consider\b|\bbetter than\b|\bprefer(red)?\b",
    re.I,
)
REF_VOICE_RE = re.compile(
    r"\bI\b(?!/)|(?i:\b(we|we'll|let's|our|us)\b)|(?i:\b(once upon|imagine|journey)\b)"
)
REF_WHY_RE = re.compile(
    r"\b(because|the reason|historically|this means that|in other words|trade-?offs?|we chose|design decision)\b",
    re.I,
)
REF_HEDGE_RE = re.compile(r"\b(might|probably|perhaps|should work|in most cases)\b", re.I)
REF_MARKETING_RE = re.compile(
    r"\b(best|fastest|powerful|seamless|blazing|revolutionary|cutting-edge|world-class|amazing)\b(?!-)", re.I
)
# Tutorial
TUT_CHOICE_RE = re.compile(
    r"(?i:\b(alternatively|you could also|another (way|option|approach)|optionally|if you prefer|or you can)\b)"
    r"|\b[Oo]ption [A-Z1-9]\b"
)
TUT_EXPLANATION_HEADING_RE = re.compile(r"^(Understanding|About|Background|Theory|Why|How it works)\b", re.I)
TUT_WHY_RE = re.compile(
    r"\b(because|the reason|under the hood|how this works|in theory|historically|internally)\b", re.I
)
TUT_LEARNING_RE = re.compile(r"\byou(?: will|'ll|’ll) learn\b", re.I)
TUT_VOICE_RE = re.compile(
    r"\b(we|let's|let’s|notice|you should see|the output should look|you have built|in this tutorial)\b", re.I
)
TUT_REFDUMP_HEADER_RE = re.compile(r"\b(default|type|required)\b", re.I)
DEFINITION_ITEM_RE = re.compile(r"^([^\s:][^:]{0,40}):\s+\S")
# How-to
HOWTO_TEACHING_RE = re.compile(
    r"\b(let's learn|let’s learn|in this tutorial|don't worry|don’t worry|you will learn|before we begin)\b", re.I
)
HOWTO_CONCEPT_HEADING_RE = re.compile(r"^(What (is|are)|Understanding|About|Background|Theory)\b", re.I)
HOWTO_TITLE_OK_RE = re.compile(r"^(How to|Troubleshoot(ing)?)\b", re.I)
# Directives
LEGACY_PROMPT_RE = re.compile(
    r"think (step[- ]by[- ]step|carefully|hard)|step[- ]by[- ]step reasoning|chain[- ]of[- ]thought"
    r"|\b(think|thinking|reason|reasoning|work|go|walk)\b(\s+\S+){0,3}?\s+step[- ]by[- ]step"
    r"|(show|explain|walk through) (your|the) (reasoning|thought process|thinking)|<thinking>|take a deep breath",
    re.I,
)
SHOUTING_RE = re.compile(r"\b(MUST|NEVER|ALWAYS|CRITICAL|IMPORTANT|REQUIRED)\b")
DIRECTIVE_HEADING_RE = re.compile(r"^(do|do not)$", re.I)
# Sections whose list items quote, map, or cite instead of directing; every other list
# item in a checked file is a primary execution directive.
DIRECTIVE_EXEMPT_RE = re.compile(r"^(Signals|Neighbou?r bleed|Sources|Skeleton|Examples?)\b", re.I)
WHY_BULLET_RE = re.compile(r"^[*_]{0,2}Why:", re.I)

# Inference signals (distinct types per quadrant).
TEXT_SIGNALS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "tutorial": [
        ("voice", re.compile(r"\b(we|let's|let’s|let us|notice)\b", re.I)),
        ("you-should-see", re.compile(r"\b(you should see|output should look)\b", re.I)),
        ("you-have-built", re.compile(r"\byou have built\b", re.I)),
        ("in-this-tutorial", re.compile(r"\bin this tutorial,? we\b", re.I)),
    ],
    "how-to": [
        ("guide-shows-how", re.compile(r"\bthis guide shows you how to\b", re.I)),
    ],
    "reference": [
        ("subcommands-are", re.compile(r"\bsub-?commands are\b", re.I)),
        ("default-colon", re.compile(r"\bdefault:", re.I)),
    ],
    "explanation": [
        ("the-reason", re.compile(r"\bthe reason\b", re.I)),
        ("historically", re.compile(r"\bhistorically\b", re.I)),
        ("trade-off", re.compile(r"\btrade-?offs?\b", re.I)),
        ("design-decision", re.compile(r"\bdesign decision", re.I)),
        ("is-analogous-to", re.compile(r"\bis analogous to\b", re.I)),
        ("some-users-prefer", re.compile(r"\bsome users prefer\b", re.I)),
    ],
}
REFERENCE_HEADING_RE = re.compile(r"^(Parameters|Options|Returns|Arguments|Flags|Fields|Syntax)\b", re.I)

# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------


class UsageError(Exception):
    pass


@dataclass
class Fence:
    start: int  # 0-based line index of the opening fence
    end: int  # 0-based line index of the closing fence (or last line)
    indent: int
    info: str
    content: list[str]


@dataclass
class Block:
    kind: str  # heading | paragraph | list_item | table | fence | hidden
    start: int  # 1-based first line
    end: int  # 1-based last line
    lines: list[str] = field(default_factory=list)
    line_numbers: list[int] = field(default_factory=list)
    level: int = 0
    ordered: bool = False
    indent: int = 0
    list_id: int = -1
    raw: str = ""
    sub: str = ""
    info: str = ""
    content: list[str] = field(default_factory=list)
    header: list[str] = field(default_factory=list)
    rows: int = 0
    in_link_section: bool = False
    hidden_fence: bool = False
    heading_before: str = ""

    @property
    def text(self) -> str:
        return " ".join(part.strip() for part in self.lines if part.strip())

    def line_at(self, offset: int) -> int:
        position = 0
        for part, number in zip(self.lines, self.line_numbers):
            stripped = part.strip()
            if not stripped:
                continue
            position += len(stripped) + 1
            if offset < position:
                return number
        return self.line_numbers[-1] if self.line_numbers else self.start


@dataclass
class Suppression:
    line: int
    rules: list[str]
    scope: tuple[int, int] | None  # None means file-wide
    used: set[str] = field(default_factory=set)


@dataclass
class Finding:
    rule: str
    line: int
    match: str
    severity: str = ""

    def as_json(self) -> dict[str, object]:
        rule = RULES[self.rule]
        return {
            "rule": self.rule,
            "severity": self.severity or rule.severity,
            "line": self.line,
            "match": self.match,
            "message": rule.message,
            "destination": rule.destination,
        }


@dataclass
class Doc:
    lines: list[str]
    blocks: list[Block]
    fences: list[Fence]
    frontmatter: dict[str, tuple[str, int]]
    markers: list[tuple[str, int]]
    suppressions: list[Suppression]
    raw_findings: list[Finding]
    code_lines: set[int]  # 0-based indexes of front-matter and fence lines
    kinds: list[str] = field(default_factory=list)  # per-line kind: text, fm, fence, hidden-*
    visible: list[str] = field(default_factory=list)  # lines with HTML comments removed
    indented_code: set[int] = field(default_factory=set)  # 0-based indexes of indented code lines


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------


def normalize_quadrant(value: str) -> str | None:
    cleaned = value.strip().strip("\"'").strip().lower()
    return QUADRANT_ALIASES.get(cleaned)


def strip_inline_code(text: str, replacement: str = "CODE") -> str:
    return INLINE_CODE_RE.sub(replacement, text)


def mask_prose(text: str) -> str:
    text = strip_inline_code(text)
    text = IMAGE_RE.sub(r"\1", text)
    text = LINK_RE.sub(r"\1", text)
    text = REF_LINK_RE.sub(r"\1", text)
    text = AUTOLINK_RE.sub("LINK", text)
    text = BARE_URL_RE.sub("LINK", text)
    return text


def remove_comments(line: str, index: int, state: dict[str, object]) -> tuple[str, list[tuple[int, str]]]:
    """Strip HTML comments from one line, skipping inline code spans.

    `state` carries an open comment across lines: keys `open` (bool), `start` (0-based
    line index) and `buffer` (list of text). Returns the visible text and the comments
    completed on this line as (1-based start line, body) pairs.
    """
    out: list[str] = []
    done: list[tuple[int, str]] = []
    pos = 0
    length = len(line)
    buffer: list[str] = state["buffer"]  # type: ignore[assignment]
    while pos < length:
        if state["open"]:
            end = line.find("-->", pos)
            if end == -1:
                buffer.append(line[pos:])
                pos = length
            else:
                buffer.append(line[pos:end])
                done.append((int(state["start"]) + 1, "\n".join(buffer)))  # type: ignore[arg-type]
                buffer.clear()
                state["open"] = False
                pos = end + 3
            continue
        tick = line.find("`", pos)
        open_at = line.find("<!--", pos)
        if open_at == -1 and tick == -1:
            out.append(line[pos:])
            break
        if tick != -1 and (open_at == -1 or tick < open_at):
            run = re.match(r"`+", line[tick:]).group(0)  # type: ignore[union-attr]
            close = line.find(run, tick + len(run))
            stop = tick + len(run) if close == -1 else close + len(run)
            out.append(line[pos:stop])
            pos = stop
            continue
        out.append(line[pos:open_at])
        state["open"] = True
        state["start"] = index
        buffer.clear()
        pos = open_at + 4
    return "".join(out), done


def parse_rule_list(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def split_lines(text: str) -> list[str]:
    """Split on Markdown line endings only; str.splitlines also splits on U+2028 and FF."""
    lines = re.split(r"\r\n|\r|\n", text)
    if lines and lines[-1] == "":
        lines.pop()
    return lines


def mark_indented_code(lines: list[str], kinds: list[str], fences: list[Fence], body_start: int) -> set[int]:
    """Mark CommonMark indented code blocks as `hidden-indented-code`; return their lines.

    Runs before HTML comments are read, so a comment shown inside indented code never
    declares a quadrant or suppresses a rule. Only a paragraph line or an open list
    stops a 4-space-indented line from starting a code block.
    """
    code: set[int] = set()
    fence_indent = {fence.start: fence.indent for fence in fences}
    comment: dict[str, object] = {"open": False, "start": 0, "buffer": []}
    total = len(lines)
    previous = "blank"  # blank | para | other
    in_list = False
    index = body_start
    while index < total:
        if kinds[index] != "text":
            if index in fence_indent and fence_indent[index] == 0:
                in_list = False
            previous = "other"
            index += 1
            continue
        expanded = lines[index].expandtabs(4)
        if comment["open"]:
            remove_comments(lines[index], index, comment)
            previous = "other"
            index += 1
            continue
        if not expanded.strip():
            previous = "blank"
            index += 1
            continue
        indent = len(expanded) - len(expanded.lstrip())
        if indent >= 4 and previous != "para" and not in_list:
            end = index
            while end < total and kinds[end] == "text":
                candidate = lines[end].expandtabs(4)
                if candidate.strip() and len(candidate) - len(candidate.lstrip()) < 4:
                    break
                end += 1
            while end > index and not lines[end - 1].strip():
                end -= 1
            for hide in range(index, end):
                kinds[hide] = "hidden-indented-code"
                code.add(hide)
            previous = "other"
            index = end
            continue
        out, _ = remove_comments(lines[index], index, comment)
        if not out.strip():
            previous = "other"
        elif indent < 4 and HEADING_RE.match(expanded):
            previous = "other"
            in_list = False
        elif LIST_RE.match(expanded) and (indent < 4 or in_list):
            previous = "para"
            in_list = True
        else:
            if indent == 0 and previous != "para":
                in_list = False
            previous = "para"
        index += 1
    return code


def parse_document(text: str) -> Doc:
    lines = split_lines(text)
    total = len(lines)
    kinds = ["text"] * total
    raw_findings: list[Finding] = []

    # 1. Front matter: read for the declaration, then hide.
    frontmatter: dict[str, tuple[str, int]] = {}
    body_start = 0
    if lines and lines[0].strip() in ("---", "+++"):
        closers = ("---", "...") if lines[0].strip() == "---" else ("+++",)
        for index in range(1, total):
            if lines[index].strip() in closers:
                for fm_index in range(1, index):
                    match = FRONTMATTER_KEY_RE.match(lines[fm_index])
                    if match:
                        value = re.sub(r"\s+#.*$", "", match.group(2)).strip()
                        frontmatter.setdefault(match.group(1), (value, fm_index + 1))
                for fm_index in range(0, index + 1):
                    kinds[fm_index] = "fm"
                body_start = index + 1
                break

    # 2. Fenced code, length-matched; an unterminated fence runs to the end of the file.
    fences: list[Fence] = []
    fence_at: dict[int, Fence] = {}
    index = body_start
    while index < total:
        match = FENCE_OPEN_RE.match(lines[index])
        if match and not (match.group(2)[0] == "`" and "`" in match.group(3)):
            char = match.group(2)[0]
            size = len(match.group(2))
            close_re = re.compile(r"^\s*" + re.escape(char) + "{" + str(size) + r",}\s*$")
            end = index + 1
            while end < total and not close_re.match(lines[end]):
                end += 1
            content = lines[index + 1:end]  # an unterminated fence keeps every line to the end
            end = min(end, total - 1)
            info_words = match.group(3).strip().strip("{}").split()
            info = info_words[0].lstrip(".").lower() if info_words else ""
            fence = Fence(index, end, len(match.group(1).expandtabs(4)), info, content)
            fences.append(fence)
            fence_at[index] = fence
            for fence_index in range(index, end + 1):
                kinds[fence_index] = "fence"
            index = end + 1
        else:
            index += 1

    # 2b. Indented code, before comments, so code samples never act as directives.
    indented_code = mark_indented_code(lines, kinds, fences, body_start)

    # 3. HTML comments (directives parsed first), then <details>.
    visible = list(lines)
    comments: list[tuple[int, str]] = []
    state: dict[str, object] = {"open": False, "start": 0, "buffer": []}
    for index in range(body_start, total):
        if kinds[index] != "text":
            continue
        was_open = bool(state["open"])
        out, done = remove_comments(lines[index], index, state)
        comments.extend(done)
        if lines[index].strip() and not out.strip() and (was_open or done or state["open"]):
            kinds[index] = "hidden-comment"
        visible[index] = out

    markers: list[tuple[str, int]] = []
    suppressions: list[Suppression] = []
    example_opens: list[int] = []
    example_regions: list[tuple[int, int]] = []
    nonblank_after_fm = [i for i in range(body_start, total) if lines[i].strip()]
    marker_limit = nonblank_after_fm[MARKER_SCAN_LINES - 1] + 1 if len(nonblank_after_fm) >= MARKER_SCAN_LINES else total
    for line_number, body in comments:
        if (match := MARKER_RE.match(body)):
            if line_number <= marker_limit:
                markers.append((match.group(1), line_number))
        elif (match := IGNORE_FILE_RE.match(body)):
            suppressions.append(Suppression(line_number, parse_rule_list(match.group(1)), None))
        elif (match := IGNORE_RE.match(body)):
            suppressions.append(Suppression(line_number, parse_rule_list(match.group(1)), (0, 0)))
        elif EXAMPLE_OPEN_RE.match(body):
            example_opens.append(line_number)
        elif EXAMPLE_CLOSE_RE.match(body):
            if example_opens:
                example_regions.append((example_opens.pop(), line_number))
    for line_number in example_opens:
        raw_findings.append(Finding("suppression-unterminated", line_number, "<!-- diataxis-example -->"))

    for start, end in example_regions:
        for index in range(start - 1, end):
            if kinds[index] in ("text", "hidden-comment", "hidden-indented-code"):
                kinds[index] = "hidden-example"

    # <details> hides only an HTML block that starts the line and has a closer; an
    # unterminated one stays audited (fail closed).
    index = body_start
    while index < total:
        if kinds[index] == "text" and DETAILS_OPEN_RE.match(strip_inline_code(visible[index], " ")):
            end = index
            while end < total and not (kinds[end] == "text"
                                       and DETAILS_CLOSE_RE.search(strip_inline_code(visible[end], " "))):
                end += 1
            if end >= total:
                index += 1
                continue
            for hide in range(index, end + 1):
                if kinds[hide] == "text":
                    kinds[hide] = "hidden-details"
            index = end + 1
            continue
        index += 1

    # 4. Blockquotes, admonitions, link reference definitions.
    index = body_start
    while index < total:
        if kinds[index] != "text":
            index += 1
            continue
        line = visible[index]
        if BLOCKQUOTE_RE.match(line):
            # A quote runs on through lazy continuation lines until a blank or a new block.
            kinds[index] = "hidden-quote"
            end = index + 1
            while end < total and kinds[end] == "text" and visible[end].strip():
                following = visible[end]
                if not BLOCKQUOTE_RE.match(following) and (HEADING_RE.match(following) or LIST_RE.match(following)):
                    break
                kinds[end] = "hidden-quote"
                end += 1
            index = end
            continue
        elif LINK_DEF_RE.match(line):
            kinds[index] = "hidden-linkref"
        elif (match := ADMON_COLON_OPEN_RE.match(line)):
            # The closer needs at least as many colons as the opener, so nested
            # containers close in order; an unterminated container stays audited.
            close_re = re.compile(r"^\s*:{" + str(len(match.group(1))) + r",}\s*$")
            end = index + 1
            while end < total and not (kinds[end] == "text" and close_re.match(visible[end])):
                end += 1
            if end >= total:
                kinds[index] = "hidden-admonition"
                index += 1
                continue
            for hide in range(index, end + 1):
                if kinds[hide] == "text":
                    kinds[hide] = "hidden-admonition"
            index = end + 1
            continue
        elif (match := ADMON_BANG_RE.match(line)):
            base = len(match.group(1).expandtabs(4))
            kinds[index] = "hidden-admonition"
            end = index + 1
            while end < total:
                candidate = visible[end].expandtabs(4)
                if candidate.strip() and len(candidate) - len(candidate.lstrip()) < base + 4:
                    break
                if candidate.strip() and kinds[end] == "text":
                    kinds[end] = "hidden-admonition"
                end += 1
            index = end
            continue
        index += 1

    masked = [mask_prose(visible[i]).expandtabs(4) if kinds[i] == "text" else "" for i in range(total)]
    blocks = build_blocks(lines, kinds, masked, fence_at, example_regions)
    mark_link_sections(blocks)
    resolve_suppression_scopes(suppressions, blocks)
    code_lines = {i for i in range(total) if kinds[i] in ("fm", "fence")}
    return Doc(lines, blocks, fences, frontmatter, markers, suppressions, raw_findings, code_lines,
               kinds, visible, indented_code)


def build_blocks(lines: list[str], kinds: list[str], masked: list[str], fence_at: dict[int, Fence],
                 example_regions: list[tuple[int, int]]) -> list[Block]:
    total = len(lines)
    blocks: list[Block] = []
    list_stack: list[tuple[int, bool, int]] = []  # (indent, ordered, list_id)
    next_list_id = 0
    prev_blank = True
    current_heading = ""

    def starts_block(index: int) -> bool:
        text = masked[index]
        return bool(HEADING_RE.match(text) or LIST_RE.match(text) or is_table_start(index))

    def is_table_start(index: int) -> bool:
        return ("|" in masked[index] and index + 1 < total and kinds[index + 1] == "text"
                and "|" in masked[index + 1] and bool(TABLE_SEP_RE.match(masked[index + 1])))

    index = 0
    while index < total:
        kind = kinds[index]
        if kind == "fm":
            index += 1
            continue
        if kind == "fence":
            fence = fence_at.get(index)
            if fence is None:  # inside a fence already consumed
                index += 1
                continue
            hidden = any(start - 1 <= fence.start <= end - 1 for start, end in example_regions)
            blocks.append(Block("fence", fence.start + 1, fence.end + 1, info=fence.info, content=fence.content,
                                indent=fence.indent, hidden_fence=hidden, heading_before=current_heading))
            if fence.indent == 0:
                list_stack.clear()
            prev_blank = False
            index = fence.end + 1
            continue
        if kind.startswith("hidden"):
            end = index
            while end + 1 < total and kinds[end + 1] == kind:
                end += 1
            content = lines[index:end + 1] if kind == "hidden-indented-code" else []
            blocks.append(Block("hidden", index + 1, end + 1, sub=kind, content=content,
                                heading_before=current_heading))
            if kind == "hidden-indented-code":
                prev_blank = False
            index = end + 1
            continue
        text = masked[index]
        if not text.strip():
            prev_blank = True
            index += 1
            continue
        indent = len(text) - len(text.lstrip())
        heading = HEADING_RE.match(text) if indent < 4 else None
        if heading:
            title = re.sub(r"\s+#+$", "", (heading.group(2) or "")).strip()
            blocks.append(Block("heading", index + 1, index + 1, [title], [index + 1], level=len(heading.group(1)),
                                raw=lines[index]))
            current_heading = title
            list_stack.clear()
            prev_blank = False
            index += 1
            continue
        if indent < 4 and is_table_start(index):
            end = index + 2
            while end < total and kinds[end] == "text" and "|" in masked[end] and masked[end].strip():
                end += 1
            header = [cell.strip() for cell in masked[index].strip().strip("|").split("|")]
            blocks.append(Block("table", index + 1, end, [], list(range(index + 1, end + 1)), header=header,
                                rows=end - (index + 2), heading_before=current_heading))
            list_stack.clear()
            prev_blank = False
            index = end
            continue
        item = LIST_RE.match(text)
        in_list = bool(list_stack)
        if item and not (indent >= 4 and prev_blank and not in_list):
            item_indent = len(item.group(1))
            ordered = item.group(2)[0].isdigit()
            while list_stack and list_stack[-1][0] > item_indent:
                list_stack.pop()
            if list_stack and list_stack[-1][0] == item_indent and list_stack[-1][1] == ordered:
                list_id = list_stack[-1][2]
            else:
                if list_stack and list_stack[-1][0] == item_indent:
                    list_stack.pop()
                list_id = next_list_id
                next_list_id += 1
                list_stack.append((item_indent, ordered, list_id))
            body = [item.group(3)]
            numbers = [index + 1]
            end = index + 1
            while (end < total and kinds[end] == "text" and masked[end].strip()
                   and not LIST_RE.match(masked[end]) and not HEADING_RE.match(masked[end])):
                body.append(masked[end].strip())
                numbers.append(end + 1)
                end += 1
            raw_item = LIST_RE.match(lines[index])
            blocks.append(Block("list_item", index + 1, end, body, numbers, ordered=ordered, indent=item_indent,
                                list_id=list_id, raw=raw_item.group(3) if raw_item else item.group(3),
                                heading_before=current_heading))
            prev_blank = False
            index = end
            continue
        if indent == 0 or not in_list:
            list_stack.clear()
        body = [text]
        numbers = [index + 1]
        end = index + 1
        setext = 0
        while end < total and kinds[end] == "text" and masked[end].strip() and not starts_block(end):
            if indent < 4 and (underline := SETEXT_RE.match(masked[end])):
                setext = 1 if underline.group(1)[0] == "=" else 2
                break
            body.append(masked[end])
            numbers.append(end + 1)
            end += 1
        if setext:
            title = " ".join(part.strip() for part in body)
            blocks.append(Block("heading", index + 1, end + 1, [title], numbers, level=setext, raw=title))
            current_heading = title
            list_stack.clear()
            prev_blank = False
            index = end + 1
            continue
        blocks.append(Block("paragraph", index + 1, end, body, numbers, indent=indent,
                            heading_before=current_heading))
        prev_blank = False
        index = end
    return blocks


def mark_link_sections(blocks: list[Block]) -> None:
    section_level = 0
    for block in blocks:
        if block.kind == "heading":
            if section_level and block.level <= section_level:
                section_level = 0
            if LINK_SECTION_RE.match(block.text):
                section_level = block.level
            continue
        if section_level and block.kind in ("paragraph", "list_item", "table"):
            block.in_link_section = True


def resolve_suppression_scopes(suppressions: list[Suppression], blocks: list[Block]) -> None:
    for suppression in suppressions:
        if suppression.scope is None:
            continue
        following = [b for b in blocks if b.start > suppression.line and b.kind != "hidden"]
        if not following:
            suppression.scope = (suppression.line, suppression.line)
            continue
        target = following[0]
        start, end = target.start, target.end
        if target.kind == "list_item":
            members = [b for b in blocks if b.kind == "list_item" and b.list_id == target.list_id]
            start = min(b.start for b in members)
            end = max(b.end for b in members)
            nested = [b for b in blocks if b.kind == "list_item" and start <= b.start and b.end > end
                      and b.indent > target.indent]
            if nested:
                end = max(b.end for b in nested)
        elif target.kind == "paragraph" and len(following) > 1 and following[1].kind == "fence":
            end = following[1].end
        suppression.scope = (start, end)


# --------------------------------------------------------------------------------------
# Sentence helpers
# --------------------------------------------------------------------------------------


def sentences(text: str) -> list[str]:
    return [part for part in SENTENCE_SPLIT_RE.split(text.strip()) if part.strip()]


def is_imperative(sentence: str) -> bool:
    text = EMPHASIS_RE.sub("", sentence).strip().lstrip("\"'(“‘")
    text = LEADING_SEQ_RE.sub("", text, count=1)
    text = LEADING_CLAUSE_RE.sub("", text, count=1)
    tokens = text.split()
    if not tokens:
        return False
    first = re.sub(r"[^a-z]", "", tokens[0].lower())
    if first not in IMPERATIVE_VERBS:
        return False
    if first not in AMBIGUOUS_VERBS:
        return True
    if len(tokens) < 2:
        return False
    following = tokens[1]
    if following.startswith("CODE") or following[0] in "\"'“‘`":
        return True
    bare = following.strip(".,;:!?()").lower()
    if bare in OBJECT_LEADS:
        return True
    core = following.rstrip(".,;:!?)")
    return "/" in core or "." in core


def word_count(text: str) -> int:
    return sum(1 for token in text.split() if WORD_RE.search(token))


# --------------------------------------------------------------------------------------
# Declaration
# --------------------------------------------------------------------------------------


def declaration(path: Path, doc: Doc | None, flag: str | None) -> tuple[dict[str, str], list[Finding]]:
    findings: list[Finding] = []
    fm_quadrant = None
    fm_line = 1
    if doc is not None:
        for key in ("diataxis", "diataxis_type"):
            if key in doc.frontmatter:
                value, fm_line = doc.frontmatter[key]
                fm_quadrant = normalize_quadrant(value)
                if fm_quadrant is None:
                    findings.append(Finding("declaration-invalid", fm_line, f"{key}: {value}"))
                break
    marker_quadrant = None
    if doc is not None:
        for value, line in doc.markers:
            normalized = normalize_quadrant(value)
            if normalized is None:
                findings.append(Finding("declaration-invalid", line, f"<!-- diataxis: {value} -->"))
                continue
            if marker_quadrant is None:
                marker_quadrant = normalized
                if fm_quadrant and fm_quadrant != normalized:
                    findings.append(Finding("declaration-conflict", line,
                                            f"front matter {fm_quadrant} vs marker {normalized}"))
    if flag:
        return {"quadrant": flag, "source": "flag"}, findings
    if fm_quadrant:
        return {"quadrant": fm_quadrant, "source": "frontmatter"}, findings
    if marker_quadrant:
        return {"quadrant": marker_quadrant, "source": "marker"}, findings
    if path.name.lower() in INDEX_NAMES:
        return {"quadrant": "landing", "source": "filename"}, findings
    for segment in reversed(path_segments(path)):
        quadrant = PATH_SEGMENTS.get(segment.lower())
        if quadrant:
            return {"quadrant": quadrant, "source": "path"}, findings
    return {"quadrant": "none", "source": "none"}, findings


def path_segments(path: Path) -> list[str]:
    """Directory names above `path`, up to the nearest repository root.

    The result does not depend on the working directory: segments come from the
    absolute path, cut at the nearest ancestor holding `.git`, or the whole absolute
    path when there is no repository.
    """
    parent = Path(os.path.abspath(path)).parent
    root = next((candidate for candidate in (parent, *parent.parents) if (candidate / ".git").exists()), None)
    parts = parent.relative_to(root).parts if root is not None else parent.parts
    return [part for part in parts if part not in ("", os.sep, "/") and not part.endswith(":\\")]


# --------------------------------------------------------------------------------------
# Inference
# --------------------------------------------------------------------------------------


def prose_blocks(doc: Doc) -> list[Block]:
    return [b for b in doc.blocks if b.kind in ("paragraph", "list_item") and not b.in_link_section]


def headings(doc: Doc) -> list[Block]:
    return [b for b in doc.blocks if b.kind == "heading"]


def ordered_lists(doc: Doc) -> dict[int, list[Block]]:
    groups: dict[int, list[Block]] = {}
    for block in prose_blocks(doc):
        if block.kind == "list_item" and block.ordered:
            groups.setdefault(block.list_id, []).append(block)
    return groups


def unordered_lists(doc: Doc) -> dict[int, list[Block]]:
    groups: dict[int, list[Block]] = {}
    for block in prose_blocks(doc):
        if block.kind == "list_item" and not block.ordered:
            groups.setdefault(block.list_id, []).append(block)
    return groups


def is_procedure_list(items: list[Block], ratio: float = PROCEDURE_IMPERATIVE_RATIO) -> bool:
    if len(items) < PROCEDURE_MIN_ITEMS:
        return False
    imperative = sum(1 for item in items if (parts := sentences(item.text)) and is_imperative(parts[0]))
    return imperative / len(items) >= ratio


def definition_runs(doc: Doc) -> list[list[Block]]:
    runs: list[list[Block]] = []
    current: list[Block] = []
    last_id = None
    for block in prose_blocks(doc):
        is_definition = (block.kind == "list_item" and bool(DEFINITION_ITEM_RE.match(block.text))
                         and len(DEFINITION_ITEM_RE.match(block.text).group(1).split()) <= 4)  # type: ignore[union-attr]
        if is_definition and (not current or block.list_id == last_id):
            current.append(block)
            last_id = block.list_id
            continue
        if len(current) >= DEFINITION_LIST_MIN:
            runs.append(current)
        current = [block] if is_definition else []
        last_id = block.list_id if is_definition else None
    if len(current) >= DEFINITION_LIST_MIN:
        runs.append(current)
    return runs


def visible_words(doc: Doc) -> int:
    return sum(word_count(b.text) for b in doc.blocks
               if b.kind in ("paragraph", "list_item", "heading") and not b.in_link_section)


def infer_signals(doc: Doc) -> dict[str, list[str]]:
    signals: dict[str, set[str]] = {q: set() for q in QUADRANTS}
    prose = prose_blocks(doc)
    texts = [b.text for b in prose] + [b.text for b in headings(doc)]
    for quadrant, patterns in TEXT_SIGNALS.items():
        for name, pattern in patterns:
            if any(pattern.search(text) for text in texts):
                signals[quadrant].add(name)
    for block in prose:
        for sentence in sentences(block.text):
            if CONDITIONAL_RE.match(sentence) and is_imperative(sentence):
                signals["how-to"].add("conditional-imperative")
    if any(is_procedure_list(items) for items in ordered_lists(doc).values()):
        signals["how-to"].add("ordered-imperative-list")
    for block in headings(doc):
        if block.level == 1 and re.match(r"^How to\b", block.text, re.I):
            signals["how-to"].add("how-to-h1")
        if block.level == 1 and re.match(r"^About\b", block.text, re.I):
            signals["explanation"].add("about-h1")
        if re.match(r"^Why\b", block.text, re.I):
            signals["explanation"].add("why-heading")
        if REFERENCE_HEADING_RE.match(block.text):
            signals["reference"].add("reference-heading")
    for block in doc.blocks:
        if block.kind == "table" and not block.in_link_section and any(OPTION_HEADER_RE.search(c) for c in block.header):
            signals["reference"].add("options-table")
    if definition_runs(doc):
        signals["reference"].add("definition-list")
    return {q: sorted(names) for q, names in signals.items()}


def infer_quadrant(signals: dict[str, list[str]], words: int) -> str:
    if words < MIN_WORDS_FOR_INFERENCE:
        return "insufficient-signal"
    scores = {q: len(names) for q, names in signals.items()}
    best = max(scores.values())
    if best < INFER_MIN_SIGNAL_TYPES:
        return "unclear"
    leaders = [q for q, score in scores.items() if score == best]
    return leaders[0] if len(leaders) == 1 else "mixed"


def challenger(declared: str, signals: dict[str, list[str]]) -> str | None:
    candidates = {q: len(names) for q, names in signals.items() if q != declared and names}
    if candidates:
        best = max(candidates.values())
        leaders = [q for q, score in candidates.items() if score == best]
        neighbour = NEIGHBOUR.get(declared)
        return neighbour if neighbour in leaders else leaders[0]
    return NEIGHBOUR.get(declared)


# --------------------------------------------------------------------------------------
# Content rules
# --------------------------------------------------------------------------------------


def search_blocks(blocks: list[Block], pattern: re.Pattern[str], rule: str) -> list[Finding]:
    found: list[Finding] = []
    for block in blocks:
        match = pattern.search(block.text)
        if match:
            found.append(Finding(rule, block.line_at(match.start()), match.group(0)))
    return found


def option_table_findings(doc: Doc, rule: str) -> list[Finding]:
    found = []
    for block in doc.blocks:
        if block.kind == "table" and not block.in_link_section and block.rows >= OPTION_TABLE_MIN_ROWS:
            cell = next((c for c in block.header if OPTION_HEADER_RE.search(c)), None)
            if cell is not None:
                found.append(Finding(rule, block.start, f"| {' | '.join(block.header)} | ({block.rows} rows)"))
    return found


def first_paragraph(doc: Doc) -> Block | None:
    return next((b for b in prose_blocks(doc) if b.kind == "paragraph"), None)


def explanation_rules(doc: Doc) -> list[Finding]:
    found: list[Finding] = []
    for items in ordered_lists(doc).values():
        if is_procedure_list(items):
            found.append(Finding("exp-procedure-list", items[0].start, items[0].text[:80]))
    for items in unordered_lists(doc).values():
        if is_procedure_list(items, UNORDERED_PROCEDURE_RATIO):
            found.append(Finding("exp-procedure-list", items[0].start, items[0].text[:80]))
    previous: Block | None = None
    for block in doc.blocks:
        code: tuple[str, list[str]] | None = None
        if block.kind == "fence" and not block.hidden_fence:
            code = (block.info, block.content)
        elif block.kind == "hidden" and block.sub == "hidden-indented-code":
            code = ("", block.content)
        if code is not None:
            info, content = code
            shell = info in SHELL_FENCES or (info in PROMPT_FENCES
                                             and any(PROMPT_LINE_RE.match(line) for line in content))
            if shell and previous is not None and previous.kind in ("paragraph", "list_item") \
                    and not previous.in_link_section:
                parts = sentences(previous.text)
                if parts and EXP_LEADIN_RE.search(parts[-1]):
                    first_line = next((line.strip() for line in content if line.strip()), "")
                    found.append(Finding("exp-terminal-steps", block.start, first_line[:80]))
        if block.kind == "hidden" and block.sub == "hidden-comment":
            continue
        previous = block
    for block in headings(doc):
        if EXP_PROCEDURE_HEADING_RE.match(block.text):
            found.append(Finding("exp-procedure-heading", block.start, block.raw.strip()))
    for block in prose_blocks(doc):
        if block.kind != "paragraph":
            continue
        imperative = [s for s in sentences(block.text) if is_imperative(s)]
        if len(imperative) >= EXP_IMPERATIVE_MAJOR:
            found.append(Finding("exp-imperative-prose", block.start, imperative[0][:80], "major"))
        elif len(imperative) >= EXP_IMPERATIVE_MINOR:
            found.append(Finding("exp-imperative-prose", block.start, imperative[0][:80], "minor"))
    found += option_table_findings(doc, "exp-option-table")
    return found


def reference_rules(doc: Doc) -> list[Finding]:
    found: list[Finding] = []
    prose = prose_blocks(doc)
    for items in ordered_lists(doc).values():
        if is_procedure_list(items):
            found.append(Finding("ref-procedure", items[0].start, items[0].text[:80]))
    found += search_blocks(prose, REF_SEQUENCE_RE, "ref-procedure")
    found += search_blocks(prose, REF_OPINION_RE, "ref-opinion")
    found += search_blocks(prose, REF_VOICE_RE, "ref-narrative-voice")
    found += search_blocks(prose, REF_HEDGE_RE, "ref-hedge")
    found += search_blocks(prose, REF_MARKETING_RE, "ref-marketing")
    for block in prose:
        why = [s for s in sentences(block.text) if REF_WHY_RE.search(s)]
        if len(why) >= REF_WHY_MIN_SENTENCES:
            found.append(Finding("ref-why-digression", block.start, why[0][:80]))
        if block.kind == "paragraph" and len(sentences(block.text)) > REF_PARAGRAPH_MAX_SENTENCES:
            found.append(Finding("ref-narrative-paragraph", block.start, block.text[:80]))
    return found


def tutorial_rules(doc: Doc) -> list[Finding]:
    found: list[Finding] = []
    prose = prose_blocks(doc)
    for block in prose:
        for match in TUT_CHOICE_RE.finditer(block.text):
            line = block.line_at(match.start())
            line_text = doc.lines[line - 1] if 0 < line <= len(doc.lines) else ""
            if OS_MARKERS_RE.search(line_text) or OS_MARKERS_RE.search(block.heading_before):
                continue
            found.append(Finding("tut-choice", line, match.group(0)))
            break
    for block in headings(doc):
        if TUT_EXPLANATION_HEADING_RE.match(block.text):
            found.append(Finding("tut-explanation-heading", block.start, block.raw.strip()))
    first = first_paragraph(doc)
    for block in prose:
        if block.kind != "paragraph" or block is first:
            continue
        parts = sentences(block.text)
        if len(parts) >= 2 and not any(is_imperative(s) for s in parts):
            match = TUT_WHY_RE.search(block.text)
            if match:
                found.append(Finding("tut-why-digression", block.line_at(match.start()), match.group(0)))
    for block in doc.blocks:
        if block.kind == "table" and not block.in_link_section:
            if any(TUT_REFDUMP_HEADER_RE.search(c) for c in block.header) or block.rows > TUT_TABLE_MAX_ROWS:
                found.append(Finding("tut-reference-dump", block.start, f"table with {block.rows} rows"))
    for run in definition_runs(doc):
        found.append(Finding("tut-reference-dump", run[0].start, f"{len(run)} term: definition items"))
    found += search_blocks(prose, TUT_LEARNING_RE, "tut-learning-claim")
    texts = [b.text for b in prose] + [b.text for b in headings(doc)]
    if not any(TUT_VOICE_RE.search(t) for t in texts):
        imperative = sum(1 for b in prose for s in sentences(b.text) if is_imperative(s))
        if imperative >= TUT_HOWTO_MIN_IMPERATIVES:
            h1 = next((b for b in headings(doc) if b.level == 1), None)
            found.append(Finding("tut-reads-as-howto", h1.start if h1 else 1, f"{imperative} imperatives, no tutor voice"))
    return found


def howto_rules(doc: Doc) -> list[Finding]:
    found: list[Finding] = []
    prose = prose_blocks(doc)
    found += search_blocks(prose + headings(doc), HOWTO_TEACHING_RE, "howto-teaching-tone")
    for block in headings(doc):
        if HOWTO_CONCEPT_HEADING_RE.match(block.text):
            found.append(Finding("howto-concept-heading", block.start, block.raw.strip()))
        if block.level == 1:
            words = block.text.split()
            first = re.sub(r"[^a-z]", "", words[0].lower()) if words else ""
            if not (HOWTO_TITLE_OK_RE.match(block.text) or first in IMPERATIVE_VERBS or first in ACTIVE_VERBS):
                found.append(Finding("howto-title", block.start, block.raw.strip()))
    first = first_paragraph(doc)
    for block in prose:
        if block.kind != "paragraph" or block is first:
            continue
        parts = sentences(block.text)
        if len(parts) >= HOWTO_EXPLANATION_MIN_SENTENCES and not any(is_imperative(s) for s in parts):
            found.append(Finding("howto-explanation-block", block.start, block.text[:80]))
    found += option_table_findings(doc, "howto-option-table")
    return found


def landing_rules(doc: Doc) -> list[Finding]:
    found: list[Finding] = []
    unordered: dict[int, list[Block]] = {}
    for block in prose_blocks(doc):
        if block.kind == "list_item" and not block.ordered:
            unordered.setdefault(block.list_id, []).append(block)
    for items in unordered.values():
        if len(items) > LANDING_LIST_MAX:
            keys = [first_word(item.raw) for item in items]
            if keys != sorted(keys):
                found.append(Finding("landing-long-list", items[0].start, f"{len(items)} items, unsorted"))
    for items in ordered_lists(doc).values():
        if len(items) > LANDING_PROCEDURE_MAX_STEPS and is_procedure_list(items):
            found.append(Finding("landing-quadrant-content", items[0].start, f"{len(items)}-step procedure"))
    found += option_table_findings(doc, "landing-quadrant-content")
    previous: Block | None = None
    for block in doc.blocks:
        if block.kind == "hidden":
            continue
        if block.kind == "list_item" and previous is not None and previous.kind == "heading" \
                and not block.in_link_section:
            found.append(Finding("landing-bare-list", block.start, previous.raw.strip()))
        previous = block
    return found


def first_word(raw: str) -> str:
    cleaned = re.sub(r"[`*_\[\]]", "", raw).strip()
    return cleaned.split()[0].lower() if cleaned.split() else ""


QUADRANT_RULES = {
    "explanation": explanation_rules,
    "reference": reference_rules,
    "tutorial": tutorial_rules,
    "how-to": howto_rules,
    "landing": landing_rules,
}

# --------------------------------------------------------------------------------------
# Directive rules
# --------------------------------------------------------------------------------------


def directive_rules(doc: Doc) -> list[Finding]:
    """Check directive authoring in agent instruction files (`--check-directives`).

    Every list item is a primary execution directive except `Why:` sub-bullets and
    items under Signals, Neighbour bleed, Sources, Skeleton, Example, or link
    sections. `## Do` and `## Do not` must hold only directive bullets.
    """
    found: list[Finding] = []
    exempt_lines = {i for f in doc.fences for i in range(f.start, f.end + 1)} | doc.indented_code
    for index, line in enumerate(doc.lines):
        if index in exempt_lines:  # front matter stays checked; only code is exempt
            continue
        text = strip_inline_code(line, " ")
        match = LEGACY_PROMPT_RE.search(text)
        if match:
            found.append(Finding("dir-legacy-prompt", index + 1, match.group(0)))
        match = SHOUTING_RE.search(text)
        if match:
            found.append(Finding("dir-shouting", index + 1, match.group(0)))

    sections: set[str] = set()
    section: tuple[str, int] | None = None  # (name, heading level) of the open Do / Do not section
    exempt = False
    directives: list[tuple[int, list[str], bool]] = []  # (line, text parts, negative)
    for block in doc.blocks:
        if block.kind == "heading":
            if section is not None and block.level <= section[1]:
                section = None
            if section is not None:
                found.append(Finding("dir-structure", block.start, f"heading inside a directive section: {block.text[:40]}"))
                continue
            if 2 <= block.level <= 4 and DIRECTIVE_HEADING_RE.match(block.text):
                section = (block.text.lower(), block.level)
                sections.add(section[0])
            exempt = bool(DIRECTIVE_EXEMPT_RE.match(block.text) or LINK_SECTION_RE.match(block.text))
            continue
        if block.kind == "list_item":
            text = list_item_text(doc, block)
            if block.indent > 0 and WHY_BULLET_RE.match(text):
                continue
            if section is not None:
                if block.indent > 0:
                    found.append(Finding("dir-structure", block.start, f"nested bullet is not `Why:`: {text[:40]}"))
                    continue
                if block.ordered:
                    found.append(Finding("dir-structure", block.start, "ordered list inside a directive section"))
                directives.append((block.start, [text], section[0] == "do not"))
            elif not exempt and not block.in_link_section:
                directives.append((block.start, [text], False))
            continue
        if block.kind == "paragraph" and block.indent > 0 and directives and directives[-1][0] < block.start \
                and (section is not None or not exempt):
            # An indented paragraph continues the directive above it.
            directives[-1][1].append(" ".join(doc.visible[n - 1].strip() for n in block.line_numbers))
            continue
        if section is None or (block.kind == "hidden" and block.sub == "hidden-comment"):
            continue
        if block.kind == "fence":
            found.append(Finding("dir-structure", block.start, "code block inside a directive section"))
        elif block.kind == "paragraph":
            found.append(Finding("dir-structure", block.start, f"prose inside a directive section: {block.text[:40]}"))
        else:
            found.append(Finding("dir-structure", block.start, f"{block.sub or block.kind} inside a directive section"))
    for name in ("do", "do not"):
        if name not in sections:
            label = "Do" if name == "do" else "Do not"
            found.append(Finding("dir-structure", 1, f"missing `## {label}` section"))
    for line_number, parts, negative in directives:
        found += check_directive(line_number, " ".join(parts), negative)
    return found


def list_item_text(doc: Doc, block: Block) -> str:
    """Raw directive text of a list item: comments removed, lazy continuations joined."""
    first = LIST_RE.match(doc.visible[block.start - 1])
    parts = [first.group(3) if first else block.lines[0]]
    parts += [doc.visible[n - 1].strip() for n in block.line_numbers[1:]]
    return " ".join(part.strip() for part in parts if part.strip())


def mask_links(text: str) -> str:
    text = IMAGE_RE.sub(r"\1", text)
    text = LINK_RE.sub(r"\1", text)
    text = REF_LINK_RE.sub(r"\1", text)
    text = AUTOLINK_RE.sub("LINK", text)
    return BARE_URL_RE.sub("LINK", text)


def check_directive(line_number: int, text: str, negative: bool) -> list[Finding]:
    """Word count, leading verb, and (for `Do not`) redirect of one directive."""
    found: list[Finding] = []
    tokens = [t for t in EMPHASIS_RE.sub("", mask_links(text)).split() if WORD_RE.search(t)]
    if not (8 <= len(tokens) <= 12):
        found.append(Finding("dir-word-count", line_number, f"{len(tokens)} words: {text[:60]}"))
    first = re.sub(r"[^a-z]", "", tokens[0].lower()) if tokens else ""
    if first not in ACTIVE_VERBS:
        found.append(Finding("dir-verb", line_number, tokens[0] if tokens else ""))
    prose = strip_inline_code(text, " ")
    if negative and ";" not in prose and " — " not in prose:
        found.append(Finding("dir-redirect-missing", line_number, text[:60]))
    return found


# --------------------------------------------------------------------------------------
# Audit pipeline
# --------------------------------------------------------------------------------------


@dataclass
class FileResult:
    path: str
    declared: dict[str, str]
    inferred: str | None
    challenger: str | None
    words: int
    signals: dict[str, list[str]]
    findings: list[Finding]
    suppressed: list[tuple[Finding, int]]

    def as_json(self) -> dict[str, object]:
        return {
            "path": self.path,
            "declared": self.declared,
            "inferred": self.inferred,
            "challenger": self.challenger,
            "words": self.words,
            "signals": self.signals,
            "findings": [f.as_json() for f in self.findings],
            "suppressed": [dict(f.as_json(), suppressed_by=line) for f, line in self.suppressed],
        }


def audit_text(path: Path, display: str, text: str | None, flag: str | None,
               check_directives: bool) -> FileResult:
    doc = parse_document(text) if text is not None else parse_document("")
    declared, findings = declaration(path, doc if text is not None else None, flag)
    quadrant = declared["quadrant"]
    findings = list(doc.raw_findings) + findings
    signals = infer_signals(doc)
    words = visible_words(doc)
    inferred = infer_quadrant(signals, words)
    if quadrant in QUADRANT_RULES:
        findings += QUADRANT_RULES[quadrant](doc)
    if words >= MIN_WORDS_FOR_INFERENCE:
        if quadrant in ALL_QUADRANTS and inferred in QUADRANTS and inferred != quadrant:
            findings.append(Finding("declared-inferred-mismatch", 1, f"declared {quadrant}, inferred {inferred}"))
        if quadrant == "none":
            mixed = [q for q, names in signals.items() if len(names) >= INFER_MIN_SIGNAL_TYPES]
            if len(mixed) >= 2:
                findings.append(Finding("mixed-undeclared", 1, ", ".join(mixed)))
    if check_directives:
        findings += directive_rules(doc)

    kept, suppressed = apply_suppressions(doc, findings)
    kept = escalate(kept)
    kept.sort(key=lambda f: (f.line, f.rule))
    return FileResult(display, declared, inferred,
                      challenger(quadrant, signals), words, signals, kept, suppressed)


def apply_suppressions(doc: Doc, findings: list[Finding]) -> tuple[list[Finding], list[tuple[Finding, int]]]:
    extra: list[Finding] = []
    active: list[tuple[Suppression, set[str]]] = []
    for suppression in doc.suppressions:
        valid: set[str] = set()
        if not suppression.rules:
            extra.append(Finding("suppression-unknown-rule", suppression.line, "(no rule ids)"))
        for rule_id in suppression.rules:
            rule = RULES.get(rule_id)
            if rule is None or not rule.suppressible:
                extra.append(Finding("suppression-unknown-rule", suppression.line, rule_id))
            else:
                valid.add(rule_id)
        active.append((suppression, valid))
    kept: list[Finding] = []
    suppressed: list[tuple[Finding, int]] = []
    for finding in findings:
        hit = None
        for suppression, valid in active:
            if finding.rule not in valid:
                continue
            if suppression.scope is None or suppression.scope[0] <= finding.line <= suppression.scope[1]:
                hit = suppression
                break
        if hit is None:
            kept.append(finding)
        else:
            hit.used.add(finding.rule)
            suppressed.append((finding, hit.line))
    for suppression, valid in active:
        for rule_id in sorted(valid - suppression.used):
            extra.append(Finding("suppression-unused", suppression.line, rule_id))
    return kept + extra, suppressed


def escalate(findings: list[Finding]) -> list[Finding]:
    counts: dict[str, int] = {}
    for finding in findings:
        counts[finding.rule] = counts.get(finding.rule, 0) + 1
    for finding in findings:
        rule = RULES[finding.rule]
        if not finding.severity:
            finding.severity = rule.severity
        if rule.escalates and counts[finding.rule] >= FILE_ESCALATION_COUNT:
            finding.severity = "major"
    return findings


def layout_findings(directory: Path, display: str) -> list[dict[str, object]]:
    found = []
    candidates = [directory] + sorted(p for p in directory.rglob("*") if p.is_dir()
                                      and not SKIP_DIRS.intersection(p.relative_to(directory).parts))
    for candidate in candidates:
        quadrant = PATH_SEGMENTS.get(candidate.name.lower())
        if not quadrant:
            continue
        pages = [p for p in candidate.rglob("*") if p.is_file() and p.suffix.lower() in MARKDOWN_SUFFIXES
                 and p.name.lower() not in INDEX_NAMES]
        if not pages:
            rel = candidate.relative_to(directory)
            shown = (Path(display) / rel).as_posix() if str(rel) != "." else Path(display).as_posix()
            rule = RULES["layout-empty-quadrant"]
            found.append({"path": shown + "/", "rule": rule.id, "severity": rule.severity, "line": 0,
                          "match": quadrant, "message": rule.message, "destination": rule.destination})
    return found


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise UsageError(f"usage: {message}")


def build_parser() -> Parser:
    parser = Parser(prog="audit_quadrant.py", description=__doc__.splitlines()[0],
                    formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--receipt", action="store_true", help="print a pre-filled receipt for one PATH (JSON)")
    mode.add_argument("--plan", action="store_true", help="propose keep/move/split/review for DOCS_ROOT; writes nothing")
    mode.add_argument("--list-rules", action="store_true", help="print the rule registry")
    parser.add_argument("--operation", choices=OPERATIONS, help="receipt operation")
    parser.add_argument("--quadrant", help="declare the quadrant for every PATH")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--strict", action="store_true", help="fail on findings of any severity")
    parser.add_argument("--check-directives", action="store_true",
                        help="check directive authoring: Do / Do not sections and every other list item")
    parser.add_argument("paths", nargs="*", metavar="PATH")
    return parser


def expand_paths(args: list[str], errors: list[dict[str, str]]) -> tuple[list[tuple[Path, str]], list[tuple[Path, str]]]:
    files: list[tuple[Path, str]] = []
    directories: list[tuple[Path, str]] = []
    seen: set[str] = set()

    def add(path: Path, display: str) -> None:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            files.append((path, display))

    for arg in args:
        if any(ch in arg for ch in "*?[") and not Path(arg).exists():
            matches = sorted(glob.glob(arg, recursive=True))
            markdown = [m for m in matches if Path(m).is_file() and Path(m).suffix.lower() in MARKDOWN_SUFFIXES
                        and not SKIP_DIRS.intersection(Path(m).parts)]
            if not markdown:
                errors.append({"path": arg, "reason": "no markdown matched"})
            for match in markdown:
                add(Path(match), Path(match).as_posix())
            continue
        path = Path(arg)
        if path.is_dir():
            directories.append((path, path.as_posix().rstrip("/") or "."))
            found = sorted(p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in MARKDOWN_SUFFIXES
                           and not SKIP_DIRS.intersection(p.relative_to(path).parts))
            if not found:
                errors.append({"path": arg, "reason": "no markdown matched"})
            for item in found:
                add(item, item.as_posix())
        elif path.is_file():
            add(path, path.as_posix())
        else:
            errors.append({"path": arg, "reason": "no such file or directory"})
    return files, directories


def read_markdown(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as error:
        raise OSError(error.strerror or "unreadable") from error
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise OSError(f"not valid UTF-8 (byte {error.start})") from error


def print_error(path: str, reason: str) -> None:
    print(f"{PROG}: {path}: {reason}", file=sys.stderr)


def run_audit(options: argparse.Namespace, flag: str | None) -> int:
    errors: list[dict[str, str]] = []
    files, directories = expand_paths(options.paths, errors)
    results: list[FileResult] = []
    for path, display in files:
        try:
            text = read_markdown(path)
        except OSError as error:
            errors.append({"path": display, "reason": str(error)})
            continue
        results.append(audit_text(path, display, text, flag, options.check_directives))
    layout: list[dict[str, object]] = []
    for directory, display in directories:
        layout += layout_findings(directory, display)

    major = sum(1 for r in results for f in r.findings if f.severity == "major") + \
        sum(1 for f in layout if f["severity"] == "major")
    minor = sum(1 for r in results for f in r.findings if f.severity == "minor") + \
        sum(1 for f in layout if f["severity"] == "minor")
    suppressed = sum(len(r.suppressed) for r in results)
    if errors or not options.paths:
        exit_code = 2
    elif major or (options.strict and minor):
        exit_code = 1
    else:
        exit_code = 0

    for error in errors:
        print_error(error["path"], error["reason"])
    if options.format == "json":
        payload = {
            "schema_version": SCHEMA_VERSION,
            "strict": bool(options.strict),
            "files": [r.as_json() for r in results],
            "layout": layout,
            "errors": errors,
            "summary": {"files": len(results), "major": major, "minor": minor, "suppressed": suppressed},
            "exit_code": exit_code,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for result in results:
            for finding in result.findings:
                rule = RULES[finding.rule]
                print(f"{result.path}:{finding.line}: {finding.severity} {finding.rule}: "
                      f"{rule.message} -> {rule.advice} [{finding.match}]")
            if result.findings:
                print(f"{result.path}: declared {result.declared['quadrant']} ({result.declared['source']}); "
                      f"inferred {result.inferred}")
        for item in layout:
            rule = RULES[str(item["rule"])]
            print(f"{item['path']}: {item['severity']} {item['rule']}: {rule.message} -> {rule.advice}")
        print(f"audited {len(results)} files: {major} major, {minor} minor, {suppressed} suppressed; exit {exit_code}")
    return exit_code


def run_receipt(options: argparse.Namespace, flag: str | None) -> int:
    if len(options.paths) != 1:
        raise UsageError("usage: --receipt takes exactly one PATH")
    if not options.operation:
        raise UsageError("usage: --receipt requires --operation")
    arg = options.paths[0]
    path = Path(arg)
    text: str | None
    if path.is_file():
        try:
            text = read_markdown(path)
        except OSError as error:
            print_error(arg, str(error))
            return 2
    elif path.exists():
        print_error(arg, "receipt needs a file, not a directory")
        return 2
    elif options.operation == "create":
        text = None
    else:
        print_error(arg, "no such file (only --operation create accepts a missing path)")
        return 2
    result = audit_text(path, path.as_posix(), text, flag, False)
    risks: list[str] = []
    for finding in result.findings:
        if finding.rule not in risks:
            risks.append(finding.rule)
    script = Path(sys.argv[0]).as_posix() if sys.argv and sys.argv[0] else "audit_quadrant.py"
    command = ["python3", script, "--strict"]
    if flag:
        command += ["--quadrant", flag]
    command.append(path.as_posix())
    receipt = {
        "receipt": "diataxis/quadrant-classification",
        "schema_version": SCHEMA_VERSION,
        "asset": path.as_posix(),
        "operation": options.operation,
        "reader_need": None,
        "compass": {"informs": None, "serves": None},
        "quadrant": None,
        "declared": result.declared,
        "inferred": result.inferred,
        "strongest_alternative": {"quadrant": result.challenger, "rejected_because": None},
        "confidence": None,
        "contamination_risks": risks,
        "decision": None,
        "destination": None,
        "split_plan": [],
        "handoff": "readme-standard" if path.name.lower() == "readme.md" else None,
        "audit_command": " ".join(shlex.quote(part) for part in command),
    }
    print(json.dumps(receipt, indent=2, ensure_ascii=False))
    return 0


def run_plan(options: argparse.Namespace, flag: str | None) -> int:
    if len(options.paths) != 1:
        raise UsageError("usage: --plan takes exactly one DOCS_ROOT")
    root = Path(options.paths[0])
    if not root.is_dir():
        print_error(options.paths[0], "DOCS_ROOT must be a directory")
        return 2
    errors: list[dict[str, str]] = []
    files, _ = expand_paths([options.paths[0]], errors)
    existing: dict[str, str] = {}
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        quadrant = PATH_SEGMENTS.get(child.name.lower())
        if quadrant and quadrant not in existing:
            existing[quadrant] = child.name
    entries = []
    for path, display in files:
        try:
            text = read_markdown(path)
        except OSError as error:
            errors.append({"path": display, "reason": str(error)})
            continue
        result = audit_text(path, display, text, flag, False)
        quadrant = result.declared["quadrant"]
        has_major = any(f.severity == "major" for f in result.findings)
        proposed = None
        if quadrant == "landing":
            action = "keep"
        elif quadrant != "none":
            if result.inferred in QUADRANTS and result.inferred != quadrant and has_major:
                action = "split"
            elif not has_major and (result.inferred == quadrant
                                    or result.inferred in ("unclear", "insufficient-signal")):
                action = "keep"
            else:
                action = "review"
        elif result.inferred in QUADRANTS:
            action = "move"
            directory = existing.get(result.inferred, DEFAULT_DIRS[result.inferred])
            proposed = (root / directory / path.name).as_posix()
        else:
            action = "review"
        entries.append({"path": display, "declared": result.declared, "inferred": result.inferred,
                        "action": action, "proposed_path": proposed,
                        "findings": sorted({f.rule for f in result.findings})})
    layout = layout_findings(root, root.as_posix().rstrip("/") or ".")
    counts = {name: sum(1 for e in entries if e["action"] == name) for name in ("keep", "move", "split", "review")}
    exit_code = 2 if errors else 0
    for error in errors:
        print_error(error["path"], error["reason"])
    if options.format == "json":
        print(json.dumps({"schema_version": SCHEMA_VERSION, "mode": "plan", "root": root.as_posix(),
                          "files": entries, "layout": layout, "errors": errors,
                          "summary": dict(counts, files=len(entries)), "writes": 0, "exit_code": exit_code},
                         indent=2, ensure_ascii=False))
    else:
        for entry in entries:
            target = f" -> {entry['proposed_path']}" if entry["proposed_path"] else ""
            declared = entry["declared"]
            print(f"{entry['path']}: {entry['action']}{target} (declared {declared['quadrant']} via "  # type: ignore[index]
                  f"{declared['source']}; inferred {entry['inferred']})")  # type: ignore[index]
        for item in layout:
            print(f"{item['path']}: {item['severity']} {item['rule']}: {item['message']}")
        print(f"plan: {len(entries)} files: {counts['keep']} keep, {counts['move']} move, "
              f"{counts['split']} split, {counts['review']} review; wrote nothing")
    return exit_code


def run_list_rules(options: argparse.Namespace) -> int:
    if options.paths:
        raise UsageError("usage: --list-rules takes no PATH")
    if options.format == "json":
        print(json.dumps([{"id": r.id, "quadrants": list(r.quadrants), "severity": r.severity,
                           "message": r.message, "advice": r.advice, "destination": r.destination,
                           "escalates": r.escalates, "suppressible": r.suppressible} for r in RULES.values()],
                         indent=2, ensure_ascii=False))
    else:
        for rule in RULES.values():
            print(f"{rule.id}\t{rule.severity}\t{','.join(rule.quadrants)}\t{rule.message}")
    return 0


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        options = build_parser().parse_args(argv)
        flag = None
        if options.quadrant is not None:
            flag = normalize_quadrant(options.quadrant)
            if flag is None:
                raise UsageError(f"--quadrant: unknown quadrant {options.quadrant!r}")
        if options.operation and not options.receipt:
            raise UsageError("usage: --operation is only valid with --receipt")
        if options.list_rules:
            return run_list_rules(options)
        if options.receipt:
            return run_receipt(options, flag)
        if options.plan:
            return run_plan(options, flag)
        if not options.paths:
            raise UsageError("usage: give at least one PATH")
        return run_audit(options, flag)
    except UsageError as error:
        print(f"{PROG}: {error}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(f"{PROG}: interrupted", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
