import re
from typing import Dict, List, Tuple

# Deterministic PII detection and masking.
# Regex patterns are intentionally conservative to avoid false negatives on common formats.

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DOC_ID_RE = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}\b|\b\d{7,9}\b")
PHONE_RE = re.compile(r"\+?\d[\d\s\-\(\)]{6,}\d")
ADDRESS_RE = re.compile(r"\b(calle|av\.?|avenida|callejon|pasaje|ruta)\b[^\n]{0,80}", re.IGNORECASE)
IBAN_RE = re.compile(r"\b[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}\b")
CBU_ALIAS_RE = re.compile(r"\b[0-9]{22}\b|\b[a-zA-Z0-9\.]{6,20}\b")

DEFAULT_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (EMAIL_RE, "EMAIL"),
    (DOC_ID_RE, "DOCUMENTO"),
    (PHONE_RE, "TELEFONO"),
    (IBAN_RE, "CUENTA_BANCARIA"),
    (CBU_ALIAS_RE, "CUENTA_BANCARIA"),
    (ADDRESS_RE, "DOMICILIO"),
]

# Placeholders permitted in outputs (LLM or masking).
ALLOWED_PLACEHOLDERS = {
    "[NOMBRE APELLIDO]",
    "[DOMICILIO]",
    "[DOCUMENTO]",
    "[TELEFONO]",
    "[EMAIL]",
    "[CUENTA BANCARIA]",
}


def pre_mask_text(text: str) -> Tuple[str, List[Dict[str, str]]]:
    masks: List[Dict[str, str]] = []

    def apply(pattern: re.Pattern[str], label: str, input_text: str) -> str:
        def _repl(match: re.Match[str]) -> str:
            idx = len(masks)
            placeholder = f"[{label}_{idx}]"
            masks.append({"id": idx, "label": label, "value": match.group(0), "placeholder": placeholder})
            return placeholder

        return pattern.sub(_repl, input_text)

    masked = text
    for pattern, label in DEFAULT_PATTERNS:
        masked = apply(pattern, label, masked)

    return masked, masks


def post_scan_text(text: str) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []
    for pattern, label in DEFAULT_PATTERNS:
        for match in pattern.finditer(text):
            findings.append({"label": label, "value": match.group(0)})

    return findings
