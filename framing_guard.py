"""framing_guard.py -- the OUTPUT guard for tool-GENERATED text.

Mirrors the discipline proven in claim-check and tie-check: written and proven green BEFORE
any reconciliation logic exists.

This tool names real companies against real public government records. The single thing it
must never do is turn a checkable difference between two documents into an assertion about a
company's honesty, intent, or compliance. A filing that does not line up with an independent
public record has many innocent explanations -- different reporting thresholds, different
timing, an error in either source, duplicate records, or a genuine difference in what each
source is designed to capture. Stating the difference is the product; explaining it is not.

WHAT THIS SCANS: tool-generated prose only -- any Claude-authored narrative or summary. It is
NOT applied to:
  - the curated caveat/disclaimer constants in disclaimers.py. Those deliberately NAME
    "concealment"/"wrongdoing" in order to DISAVOW them ("this is not evidence of
    concealment"), so they would trip the lemma layer by design. They are human-reviewed and
    verified by exact-content tests in tests/test_disclaimers.py instead. Same boundary
    tie-check drew, and for the same reason.
  - the record data itself -- filing field values, complaint summaries quoted verbatim from
    the public record, entity names. Republishing a government record's own text is factual
    reporting attributed to its source, not a judgment this tool generates. A consumer
    complaint narrative may itself say "the manufacturer covered this up"; that is the
    complainant's statement, quoted and attributed, and the renderer never passes quoted
    source text through this guard.

TWO MATCH LAYERS:
  1. Attribution-construction patterns (F1-F11): affirmative attribution of concealment,
     intent, duty-breach, or a character judgment to a filer. Negated disclaimer forms are
     excluded via negative-lookbehind (and would be caught by Tier 1 anyway).
  2. Tier-1 hard-banned lemmas: words with no benign role in GENERATED prose about a
     document comparison. Deliberately blunt -- if generated text contains "concealed" or
     "underreported" at all, even negated, the safe move is to reject it and fall back to the
     deterministic template. Stating the careful negated framing is the curated caveats' job,
     not generated text's.

NOTE ON "omit": banned in generated prose even though it reads factual. "The filing omitted
X" presupposes that X belonged in it -- a duty claim this tool has no basis to make. The
neutral, equally informative phrasing is "X is not present in the filing", and the
deterministic templates use exactly that.
"""
from __future__ import annotations

import re

# --- Layer 1: attribution-construction patterns -------------------------------

# The document-subject discipline: these are the subjects a generated sentence may NOT take
# an accusatory predicate against.
_FILER = (r"(?:compan(?:y|ies)|filers?|operators?|manufacturers?|reporting\s+entit(?:y|ies)|"
          r"they|it|the\s+firm)")

_ATTRIBUTION_PATTERNS = [
    # F1 -- filer + concealed/hid/withheld/suppressed/buried + something
    (re.compile(
        _FILER + r"\s+(?:\w+\s+){0,2}"
        r"(?:conceal\w*|hid|hidden|hiding|withh?[eo]ld\w*|suppress\w*|buried|covered\s+up|"
        r"whitewash\w*|downplay\w*|glossed\s+over)\b", re.IGNORECASE),
     "F1: attributes concealing/withholding/suppressing to a filer"),

    # F2 -- failed to report / failed to disclose / did not disclose: asserts a duty breach
    (re.compile(
        r"\b(?:fail\w*|neglect\w*|refus\w*)\s+to\s+(?:report|disclose|file|submit|include)\b",
        re.IGNORECASE),
     "F2: asserts a failure/refusal to report or disclose (a duty-breach claim)"),

    # F3 -- underreported / misreported / underreporting
    (re.compile(r"\b(?:under[\s-]?report\w*|mis[\s-]?report\w*|under[\s-]?stat\w*|"
                r"under[\s-]?count\w*|under[\s-]?disclos\w*)\b", re.IGNORECASE),
     "F3: says a filing under-reported / mis-reported / under-stated"),

    # F4 -- affirmative "evidence of concealment/wrongdoing/...", not negated
    (re.compile(
        r"(?<!not )(?<!no )(?<!nor )evidence\s+of\s+"
        r"(?:conceal\w*|a\s+cover[\s-]?up|cover[\s-]?up|wrongdoing|misconduct|fraud\w*|"
        r"under[\s-]?report\w*|non[\s-]?compliance|a\s+violation)\b", re.IGNORECASE),
     "F4: asserts evidence of concealment/wrongdoing/non-compliance"),

    # F5 -- proves/shows/suggests ... concealment/wrongdoing/violation, not negated
    (re.compile(
        r"(?<!not )\b(?:proves?|proven|shows?|demonstrat\w*|confirms?|indicat\w*|suggests?|"
        r"means|reveals?|exposes?)\b(?:\s+\w+){0,6}\s+"
        r"(?:conceal\w*|cover[\s-]?up|wrongdoing|misconduct|fraud\w*|non[\s-]?compliance|"
        r"a\s+violation|deliberate\w*|intentional\w*)\b", re.IGNORECASE),
     "F5: claims the difference proves/shows concealment, wrongdoing, or intent"),

    # F6 -- violated/breached/broke + the order/requirement/obligation/law
    (re.compile(
        r"\b(?:violat\w*|breach\w*|broke|flout\w*|circumvent\w*|evad\w*)\s+(?:\w+\s+){0,3}"
        r"(?:standing\s+general\s+order|order|requirements?|obligations?|law|regulations?|"
        r"rules?|duty)\b", re.IGNORECASE),
     "F6: asserts the filer violated the order / its reporting obligations"),

    # F7 -- filer + is/was + dishonest/negligent/reckless/...
    (re.compile(
        r"\b(?:this|the)\s+(?:compan(?:y|ies)|filer|operator|manufacturer|reporting\s+entity)\s+"
        r"(?:is|was|are|were|has\s+been|have\s+been)\s+(?:\w+\s+){0,2}"
        r"(?:dishonest\w*|deceptive|fraudulent|negligen\w*|reckless\w*|careless|sloppy|"
        r"untrustworthy|unreliable|evasive|non[\s-]?compliant)\b", re.IGNORECASE),
     "F7: calls a filer dishonest/negligent/non-compliant/etc."),

    # F8 -- intent attribution: deliberately/intentionally/knowingly + left out/excluded/...
    (re.compile(
        r"\b(?:deliberate\w*|intentional\w*|knowing\w*|willful\w*|wilful\w*|purposeful\w*|"
        r"strategic\w*)\s+(?:\w+\s+){0,3}"
        r"(?:left\s+out|excluded?|omitt\w*|remov\w*|redact\w*|conceal\w*|withh?[eo]ld\w*|"
        r"under[\s-]?report\w*|misle\w*)\b", re.IGNORECASE),
     "F8: attributes intent (deliberately/knowingly) to what a filing does not contain"),

    # F9 -- compliance/transparency/honesty score attached to a company
    (re.compile(
        r"\b(?:compan(?:y|ies)|filers?|operators?|manufacturers?|their|its)(?:['’]s?)?\s+"
        r"(?:compliance|transparency|honesty|integrity|candour|candor|trustworthiness|"
        r"reporting)\s+(?:score|rating|rank|ranking|grade|index)\b", re.IGNORECASE),
     "F9: attaches a compliance/transparency/honesty score to a company"),

    # F10 -- reader cannot trust this company / these filings
    (re.compile(
        r"\b(?:can'?t|cannot|shouldn'?t|should\s+not)\s+(?:be\s+)?(?:trust\w*|believ\w*|rel(?:y|ied)\s+on)\b"
        r"(?:\s+\w+){0,4}\s*(?:compan\w*|filer\w*|operator\w*|manufacturer\w*|filings?|reports?|"
        r"submissions?|them|this|these)\b", re.IGNORECASE),
     "F10: says the company or its filings cannot be trusted"),

    # F11 -- calls for enforcement/punishment
    (re.compile(
        r"\b(?:should|ought\s+to|must)\s+be\s+(?:\w+\s+){0,2}"
        r"(?:fined|penali[sz]ed|sanctioned|investigated|prosecuted|punished|referred)\b",
        re.IGNORECASE),
     "F11: calls for the filer to be fined/investigated/sanctioned"),
]

# --- Layer 2: Tier-1 hard-banned lemmas in generated prose ---------------------
# falsif(?!iab) excludes "falsifiable"/"falsifiability". "liability" is deliberately NOT
# banned: it is ordinary vocabulary for the insurer audience and carries no accusation on its
# own. "discrepancy"/"difference"/"unmatched" are the tool's own neutral vocabulary and are
# likewise not banned.
_TIER1_LEMMAS = re.compile(
    r"\b(?:conceal\w*|cover[\s-]?up|coverup|whitewash\w*|suppress\w*|withh?[eo]ld\w*|"
    r"under[\s-]?report\w*|under[\s-]?stat\w*|mis[\s-]?report\w*|omit\w*|omission\w*|"
    r"fraud\w*|fraudulent|falsif(?!iab)\w*|fabricat\w*|misconduct|malfeasance|wrongdoing|"
    r"dishonest\w*|deceit\w*|deceptive\w*|deceiv\w*|mislead\w*|misleading|misled|"
    r"culpab\w*|guilty|guilt|negligen\w*|reckless\w*|"
    r"stonewall\w*|obfuscat\w*|evasive|sandbag\w*|"
    r"non[\s-]?compliance|non[\s-]?compliant|violation\w*|violat\w*)\b",
    re.IGNORECASE,
)


def check_framing_violations(text: str) -> list[str]:
    """Return a list of human-readable violation descriptions -- empty if clean.

    Never raises. Callers decide what to do with a non-empty result (this project: reject the
    generated narrative and fall back to the deterministic template, which is built only from
    curated constants plus factual interpolation and is clean by construction).
    """
    violations: list[str] = []
    for pattern, description in _ATTRIBUTION_PATTERNS:
        if pattern.search(text):
            violations.append(description)
    for term in sorted(set(m.group(0).lower() for m in _TIER1_LEMMAS.finditer(text))):
        violations.append(f"Tier-1 banned term in generated text: {term!r}")
    return violations


def assert_clean(text: str) -> None:
    """Raise ValueError if the text violates the framing discipline. The hard gate applied to
    any tool-generated narrative before it is returned to a caller."""
    violations = check_framing_violations(text)
    if violations:
        raise ValueError(
            "Generated text violates the mandatory framing discipline: "
            + "; ".join(sorted(violations))
        )
