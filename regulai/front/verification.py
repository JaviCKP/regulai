"""Local response/citation checks; these cannot establish semantic truth."""
import json
import re


def normalize_finish_reason(finish_reason):
    if not isinstance(finish_reason, str):
        return "unknown"
    reason = finish_reason.strip().lower()
    if reason in {"stop", "end_turn", "stop_sequence", "complete", "completed"}:
        return "complete"
    if reason in {"length", "max_tokens", "max_output_tokens", "truncated", "incomplete"}:
        return "truncated"
    if reason in {"content_filter", "refusal", "refused", "safety", "blocked"}:
        return "refused"
    return "unknown"


def _normalize_quote(text):
    # Only whitespace is normalized: punctuation, case, and Unicode are literal.
    return " ".join(text.split())


def _unique_fields(pairs):
    fields = {}
    for key, value in pairs:
        if key in fields:
            raise ValueError("duplicate_json_field")
        fields[key] = value
    return fields


def _document_claims(content, fragments):
    """Resolve only request-supplied fragment IDs; no URL/path/HTML interpretation."""
    sources = {}
    for fragment in fragments:
        if (not isinstance(fragment, dict)
                or any(not isinstance(fragment.get(key), str) for key in ("id", "locator", "text"))
                or not fragment["id"] or fragment["id"] in sources):
            raise ValueError("invalid_sources")
        sources[fragment["id"]] = fragment
    try:
        fence = re.fullmatch(r"```json[ \t]*\r?\n([\s\S]*?)\r?\n```", content.strip())
        if fence:
            content = fence[1]
        document = json.loads(content, object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError):
        raise ValueError("invalid_document_json") from None
    if not isinstance(document, dict) or set(document) != {"claims"}:
        raise ValueError("invalid_document_structure")
    claims = document["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= 32:
        raise ValueError("invalid_claims")
    evidence, evidence_chars = [], 0
    for index, claim in enumerate(claims):
        if (not isinstance(claim, dict) or set(claim) != {"text", "citations"}
                or not isinstance(claim["text"], str) or not claim["text"].strip()
                or len(claim["text"]) > 4000):
            raise ValueError("invalid_claim")
        citations = claim["citations"]
        if not isinstance(citations, list) or not 1 <= len(citations) <= 8:
            raise ValueError("missing_citations")
        for citation in citations:
            if (not isinstance(citation, dict) or set(citation) != {"id", "quote"}
                    or not isinstance(citation["id"], str)
                    or not isinstance(citation["quote"], str)):
                raise ValueError("invalid_citation")
            source = sources.get(citation["id"])
            if source is None:
                raise ValueError("unknown_citation")
            quote = _normalize_quote(citation["quote"])
            if not quote or len(quote) > 1600:
                raise ValueError("invalid_quote")
            source_text = _normalize_quote(source["text"])
            position = source_text.find(quote)
            if position < 0:
                raise ValueError("quote_not_found")
            # Extract from the server source, never accept model locator/excerpt.
            excerpt = source_text[position:position + len(quote)]
            evidence_chars += len(excerpt)
            if evidence_chars > 16000:
                raise ValueError("evidence_limit")
            evidence.append({"claim_index": index, "id": source["id"],
                             "locator": source["locator"], "excerpt": excerpt})
    return claims, evidence


def verify_response(content, finish_reason, *, fragments=None, require_semantic=True):
    """Return serializable checks. A semantic judge is required by default.

    fragments=None checks prose; a list requires the exact document JSON contract.
    Document mode always needs semantic judgment. Returned strings are plain
    text and must be escaped/textContent in the UI.
    """
    checks, claims, evidence = [], [], []
    valid_content = isinstance(content, str) and bool(content.strip())
    checks.append({"code": "nonempty", "status": "passed" if valid_content else "failed"})
    completion = normalize_finish_reason(finish_reason)
    checks.append({"code": "completion", "status": "passed" if completion == "complete" else "failed",
                   "reason": completion})
    if valid_content:
        try:
            if len(content.encode("utf-8")) > 128000:
                checks.append({"code": "response_limit", "status": "failed"})
        except UnicodeEncodeError:
            checks.append({"code": "response_encoding", "status": "failed"})
    if fragments is not None and all(check["status"] == "passed" for check in checks):
        try:
            claims, evidence = _document_claims(content, fragments)
            checks.append({"code": "citations", "status": "passed"})
        except ValueError as error:
            checks.append({"code": "citations", "status": "failed", "reason": str(error)})
    local_status = "failed" if any(check["status"] == "failed" for check in checks) else "passed"
    require_semantic = require_semantic or fragments is not None
    if require_semantic:
        checks.append({"code": "semantic", "status": "not_verified"})
    status = "failed" if local_status == "failed" else ("not_verified" if require_semantic else "passed")
    return {"status": status, "local_status": local_status, "finish_reason": completion,
            "checks": checks, "claims": claims, "evidence": evidence}
