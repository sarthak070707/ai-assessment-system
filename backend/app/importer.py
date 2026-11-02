"""Turns an uploaded question paper into draft questions for review.

Design constraint that shapes everything here: **nothing this module produces is
saved automatically.** Extraction from a human-formatted document is guesswork,
and a mis-read answer key is the worst defect an exam system can have — it marks
correct work wrong, silently, at scale. So the parser's job is to produce a
best-effort draft plus an honest list of what it was unsure about, and an
examiner confirms every question before it reaches the bank.

Two extractors sit behind one entry point, `extract_questions`:

  LLM (preferred)  - Groq, when GROQ_API_KEY is set. Reads intent rather than
      pattern, so it copes with tables, split answer keys and unusual numbering.
  Rules (fallback) - the regex parser below. No dependencies, no network, and it
      handles the conventions most papers follow.

The fallback is automatic and silent to the point of failure: a missing key, a
dead network or a rejected request all degrade to rules rather than erroring.
An examiner must never be unable to import a paper because an API is down.

Recognised shapes::

    Q1. What is the time complexity of binary search?      [2 marks]
    a) O(1)
    b) O(log n)
    Answer: b

    2) Explain database normalisation.
    Answer: Normalisation organises tables to reduce redundancy...
    Keywords: redundancy, dependency, 3NF
"""
from __future__ import annotations

import io
import logging
import re

logger = logging.getLogger(__name__)

# A question begins with a number, optionally prefixed by Q, followed by . or )
_QUESTION = re.compile(r"^\s*(?:Q(?:uestion)?\.?\s*)?(\d{1,3})\s*[.)\]]\s*(.+)$", re.I)
# An option begins with a letter a-h, optionally bracketed
_OPTION = re.compile(r"^\s*\(?([a-hA-H])\s*[.)\]]\s*(.+)$")
# \b after the alternation stops 'Key' matching the start of 'Keywords', which
# would otherwise swallow the rubric line into the reference answer.
_ANSWER = re.compile(
    r"^\s*(?:Ans|Answer|Correct(?:\s+answer)?|Key)\b\s*[:.\-]?\s*(.*)$", re.I
)
_KEYWORDS = re.compile(r"^\s*(?:Keywords?|Rubric|Must\s+mention)\s*[:.\-]?\s*(.*)$", re.I)
_MARKS = re.compile(r"[\[(]\s*(\d{1,3})\s*(?:marks?|m)\s*[\])]", re.I)
_DIFFICULTY = re.compile(r"\b(easy|medium|hard)\b", re.I)
# Signals that a question expects code rather than prose
_CODE_HINT = re.compile(
    r"\b(write a (?:function|program|method)|implement|def\s+\w+\s*\(|"
    r"return(?:s)? the|time complexity of your)\b",
    re.I,
)


def extract_text(filename: str, data: bytes) -> str:
    """Pull plain text out of a PDF, DOCX or text file."""
    name = (filename or "").lower()

    if name.endswith(".pdf"):
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
        except Exception as exc:
            raise ValueError(f"That PDF could not be opened ({exc}).") from exc
        if reader.is_encrypted:
            raise ValueError("That PDF is password protected. Remove the password and try again.")

        pages = [(page.extract_text() or "") for page in reader.pages]
        text = "\n".join(pages)
        if not text.strip():
            raise ValueError(
                "No text found in that PDF. It is probably a scan of a printed page — "
                "the file holds images, not characters. Paste the questions as text instead."
            )
        return text

    if name.endswith(".docx"):
        import docx

        try:
            document = docx.Document(io.BytesIO(data))
        except Exception as exc:
            raise ValueError(f"That Word file could not be opened ({exc}).") from exc
        return "\n".join(p.text for p in document.paragraphs)

    # An extensionless filename is treated as plain text, but the empty string
    # must not be in the endswith tuple: every string ends with it, so that
    # branch matched anything and the refusal below was unreachable.
    if name.endswith((".txt", ".md")) or "." not in name.rsplit("/", 1)[-1]:
        for encoding in ("utf-8", "utf-16", "latin-1"):
            try:
                return data.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise ValueError("That text file uses an encoding we could not read.")

    raise ValueError("Upload a PDF, Word document or text file, or paste the questions directly.")


def _blank(number: int) -> dict:
    return {
        "source_number": number,
        "kind": "descriptive",
        "prompt": "",
        "options": [],
        "correct_option": None,
        "reference_answer": "",
        "rubric_keywords": [],
        "max_score": None,
        "difficulty": None,
        "warnings": [],
    }


def _letter_to_index(token: str) -> int | None:
    match = re.search(r"[a-hA-H]", token or "")
    return ord(match.group().lower()) - ord("a") if match else None


def _finalise(draft: dict, default_marks: float) -> dict:
    """Decide the question type and record everything the parser is unsure about."""
    prompt = draft["prompt"].strip()

    # A long question wraps, so its "[15 marks]" tag can land on any line of it.
    # Scanning the assembled prompt catches those; scanning only the first line
    # silently fell back to the default and mis-weighted the paper.
    marks = _MARKS.search(prompt)
    if marks:
        draft["max_score"] = float(marks.group(1))
        prompt = _MARKS.sub("", prompt)

    trailing = _DIFFICULTY.search(prompt[-24:]) if len(prompt) > 24 else None
    if trailing and draft["difficulty"] is None:
        draft["difficulty"] = trailing.group(1).lower()
        prompt = prompt[:-24] + _DIFFICULTY.sub("", prompt[-24:])

    prompt = re.sub(r"\s{2,}", " ", prompt).strip(" -–—")
    draft["prompt"] = prompt

    if draft["options"]:
        draft["kind"] = "mcq"
        if draft["correct_option"] is None:
            draft["warnings"].append("No answer key found — mark the correct option yourself.")
        elif draft["correct_option"] >= len(draft["options"]):
            draft["warnings"].append(
                f"The answer key points at option {chr(97 + draft['correct_option']).upper()}, "
                f"but only {len(draft['options'])} options were read."
            )
            draft["correct_option"] = None
        if len(draft["options"]) < 2:
            draft["warnings"].append("Only one option was read — check the original formatting.")
    elif _CODE_HINT.search(prompt):
        draft["kind"] = "coding"
        draft["warnings"].append(
            "Looks like a coding question. Test cases cannot be read from a document — add them before saving."
        )
    else:
        draft["kind"] = "descriptive"
        if not draft["reference_answer"].strip():
            draft["warnings"].append(
                "No reference answer found. Descriptive questions are graded against one, so write it in."
            )

    if not prompt:
        draft["warnings"].append("The question text came out empty.")
    elif len(prompt) < 12:
        draft["warnings"].append("The question text looks truncated.")

    if draft["max_score"] is None:
        draft["max_score"] = default_marks
    draft["difficulty"] = draft["difficulty"] or "medium"
    draft["reference_answer"] = draft["reference_answer"].strip()
    return draft


def extract_questions(text: str, default_marks: float = 5.0) -> tuple[list[dict], str, str]:
    """Extract questions, preferring the LLM and falling back to rules.

    Returns (questions, backend_used, note). The backend is reported rather than
    hidden so an examiner knows which read their paper - the two behave
    differently enough that it changes how carefully they should check the result.
    """
    from . import llm

    if llm.is_configured():
        try:
            drafts = llm.extract(text)
            return (
                [_finalise_llm(d, default_marks) for d in drafts],
                "groq",
                f"Read by {llm.model_name()}.",
            )
        except llm.LLMUnavailable as exc:
            # Logged as well as returned: when the fallback also finds nothing the
            # caller sees an empty result, and without this the reason the LLM
            # declined would be invisible in both the response and the server log.
            logger.warning("LLM extraction unavailable, falling back to rules: %s", exc)
            return (
                parse(text, default_marks),
                "rules",
                f"Fell back to pattern matching because the AI reader was unavailable: {exc}",
            )

    return (
        parse(text, default_marks),
        "rules",
        "Read by pattern matching. Set GROQ_API_KEY for more reliable extraction.",
    )


# Enumerated option markers, in the orders papers actually use them.
_EMBEDDED_OPTIONS = re.compile(
    r"(?:^|\s)(?:"
    r"\(?(?:i{1,3}|iv|v|vi{1,3})\)?[.)]|"      # roman: i. ii. iii. iv)
    r"\(?[a-hA-H]\)?[.)]|"                     # letters: a) (b) C.
    r"\(?[1-9]\)?[.)]"                         # digits: 1. 2)
    r")\s+"
)


def _split_embedded_options(prompt: str) -> tuple[str, list[str]]:
    """Pull options back out of a question stem they were left inside.

    The model is told to keep options out of `prompt`, and usually does — but it
    varies between runs on the same document, and one run in a handful returns
    the whole question as a single block. Rather than trust the instruction, the
    output is repaired deterministically: the same input then produces the same
    questions whichever way the model happened to answer.
    """
    pieces = _EMBEDDED_OPTIONS.split(prompt)
    if len(pieces) < 3:
        return prompt, []

    stem, *candidates = pieces
    stem = stem.strip()
    options = [c.strip(" .;,") for c in candidates if c.strip()]

    # Guard against splitting on an abbreviation or a numbered clause inside the
    # stem: real options are short, similar in length, and there are 2 to 8.
    if not stem or len(options) < 2 or len(options) > 8:
        return prompt, []
    if any(len(o) > 160 for o in options):
        return prompt, []
    if len(stem) < 10:
        return prompt, []

    return stem, options


def _finalise_llm(draft: dict, default_marks: float) -> dict:
    """Apply the same completeness checks to LLM output as to parsed output.

    The model is told not to invent an answer key, so a missing one is honest
    rather than a failure - but it still needs flagging for the examiner.
    """
    # Repair before judging: an MCQ whose options were left in the stem is a
    # formatting slip by the model, not a question missing its options.
    if draft["kind"] == "mcq" and len(draft["options"]) < 2:
        stem, recovered = _split_embedded_options(draft["prompt"])
        if recovered:
            draft["prompt"] = stem
            draft["options"] = recovered
            draft["correct_option"] = None   # positions changed; do not guess
            draft["warnings"].append(
                "The options were embedded in the question text and have been separated. "
                "Check they are right, and mark the correct one."
            )

    if draft["kind"] == "mcq":
        if len(draft["options"]) < 2:
            # Saving it as an MCQ would fail validation; descriptive is the
            # honest fallback and the examiner can switch it back.
            draft["kind"] = "descriptive"
            draft["warnings"].append(
                "This looked like a multiple-choice question but no options could be read. "
                "Treated as descriptive — switch the type back and add the options if that is wrong."
            )
        elif draft["correct_option"] is None:
            draft["warnings"].append("No answer key in the document — mark the correct option yourself.")
    elif draft["kind"] == "coding":
        draft["warnings"].append(
            "Looks like a coding question. Test cases cannot be read from a document — add them before saving."
        )
    elif not draft["reference_answer"]:
        draft["warnings"].append(
            "No reference answer found. Descriptive questions are graded against one, so write it in."
        )

    if draft["max_score"] is None:
        draft["max_score"] = default_marks
    draft["difficulty"] = draft["difficulty"] or "medium"
    return draft


def parse(text: str, default_marks: float = 5.0) -> list[dict]:
    """Split raw text into draft questions.

    Line-oriented rather than regex-over-the-whole-document, because question
    papers are laid out by line and a stray blank line should not merge two
    questions together.
    """
    drafts: list[dict] = []
    current: dict | None = None
    mode: str | None = None   # what the previous marker means for continuation lines

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            mode = None
            continue

        question_match = _QUESTION.match(line)
        # A line like "1) O(log n)" inside an option block is an option, not a
        # new question — only start one when we are not mid-options.
        if question_match and not (current and mode == "options" and len(line) < 60):
            if current:
                drafts.append(_finalise(current, default_marks))
            current = _blank(int(question_match.group(1)))
            body = question_match.group(2)

            current["prompt"] = body.strip()
            mode = "prompt"
            continue

        if current is None:
            continue   # preamble before the first question

        answer_match = _ANSWER.match(line)
        if answer_match:
            value = answer_match.group(1).strip()
            if current["options"] and (len(value) <= 3 or _letter_to_index(value) is not None):
                current["correct_option"] = _letter_to_index(value)
            else:
                current["reference_answer"] = value
            mode = "answer"
            continue

        keyword_match = _KEYWORDS.match(line)
        if keyword_match:
            current["rubric_keywords"] = [
                k.strip() for k in re.split(r"[,;]", keyword_match.group(1)) if k.strip()
            ]
            mode = "keywords"
            continue

        option_match = _OPTION.match(line)
        if option_match and len(option_match.group(2)) < 200:
            current["options"].append(option_match.group(2).strip())
            mode = "options"
            continue

        # Anything else continues whatever came before it.
        if mode == "answer":
            current["reference_answer"] += " " + line.strip()
        elif mode == "options" and current["options"]:
            current["options"][-1] += " " + line.strip()
        else:
            current["prompt"] += " " + line.strip()
            mode = "prompt"

    if current:
        drafts.append(_finalise(current, default_marks))

    return drafts
