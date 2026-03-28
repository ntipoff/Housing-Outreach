"""
utils.py — Business logic layer for the Outreach Hub app.
Keeps app.py clean and makes it easy to swap in real API calls later.
"""

from __future__ import annotations
import io
import csv
import re
from datetime import date, datetime, timedelta
from typing import Optional

import streamlit as st

from data import COMPLEXES

# ── City keyword detection ────────────────────────────────────────────────────
CITY_ALIASES: dict[str, str] = {
    "lewisville": "Lewisville",
    "carrollton": "Carrollton",
    "flower mound": "Flower Mound",
    "flowermound": "Flower Mound",
    "denton": "Denton",
}

def _detect_cities_from_query(query: str) -> list[str]:
    """Extract city names from a free-text query."""
    q = query.lower()
    found = []
    for alias, canonical in CITY_ALIASES.items():
        if alias in q and canonical not in found:
            found.append(canonical)
    return found


# ── Story 1: Search ───────────────────────────────────────────────────────────
def search_complexes(query: str, cities: list[str], state: str | None = None) -> list[dict]:
    """
    Filter COMPLEXES by state/city selection and/or NLP query.
    In production: call HUD / TDHCA / 211 Texas API here.
    """
    active_cities = list(cities) if cities else []

    # Start with state filter if provided
    filtered = [c for c in COMPLEXES if c["state"] == state] if state else list(COMPLEXES)

    # Keep analytics consistent with query city extraction
    if query:
        detected = _detect_cities_from_query(query)
        for c in detected:
            if c not in active_cities:
                active_cities.append(c)

    if active_cities:
        filtered = [c for c in filtered if c["city"] in active_cities]

    return filtered


# ── Story 2: Detail ───────────────────────────────────────────────────────────
def get_complex_by_id(complex_id: str) -> Optional[dict]:
    for c in COMPLEXES:
        if c["id"] == complex_id:
            return c
    return None


def flag_complex(complex_id: str) -> None:
    if complex_id in st.session_state.flags:
        st.session_state.flags.discard(complex_id)
    else:
        st.session_state.flags.add(complex_id)


def add_note(complex_id: str, text: str) -> None:
    st.session_state.notes[complex_id] = text


# ── Story 5: Visit tracking ───────────────────────────────────────────────────
def log_visit(complex_id: str, status: str, visit_date: str, notes: str) -> None:
    if complex_id not in st.session_state.visits:
        st.session_state.visits[complex_id] = []
    st.session_state.visits[complex_id].append({
        "status": status,
        "date": visit_date,
        "notes": notes,
        "logged_at": datetime.now().isoformat(),
    })


def get_visit_history(complex_id: str) -> list[dict]:
    return st.session_state.visits.get(complex_id, [])


def get_overdue_followups(days_threshold: int = 7) -> list[dict]:
    """Return complexes whose last visit was 'Follow-Up Needed' and is overdue."""
    cutoff = date.today() - timedelta(days=days_threshold)
    overdue = []
    for cid, visits in st.session_state.visits.items():
        if not visits:
            continue
        last = max(visits, key=lambda v: v["date"])
        if last["status"] == "Follow-Up Needed":
            try:
                last_date = date.fromisoformat(last["date"])
                if last_date <= cutoff:
                    c = get_complex_by_id(cid)
                    overdue.append({
                        "id": cid,
                        "name": c["name"] if c else cid,
                        "last_visit": last["date"],
                        "status": last["status"],
                    })
            except ValueError:
                pass
    return overdue


# ── Story 6: Contacts ─────────────────────────────────────────────────────────
def add_contact(
    complex_id: str,
    first: str,
    last: str,
    age: Optional[int],
    phone: str,
    relationship: str,
    illness: str,
) -> None:
    if complex_id not in st.session_state.contacts:
        st.session_state.contacts[complex_id] = []
    st.session_state.contacts[complex_id].append({
        "first": first,
        "last": last,
        "age": age,
        "phone": phone or None,
        "relationship": relationship,
        "illness": illness or None,
        "added_at": datetime.now().isoformat(),
    })


def get_contacts_for_complex(complex_id: str) -> list[dict]:
    return st.session_state.contacts.get(complex_id, [])


def check_hospice_eligibility(contact: dict) -> Optional[str]:
    """
    Basic eligibility flag — Story 6 acceptance criterion.
    Returns a short string describing indicators, or None.
    """
    reasons = []
    if contact.get("age") and contact["age"] >= 65:
        reasons.append("age 65+")
    if contact.get("illness"):
        reasons.append(f'chronic illness: {contact["illness"]}')
    return ", ".join(reasons) if reasons else None


# ── Story 4: Export ───────────────────────────────────────────────────────────
def export_to_csv(complexes: list[dict]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Address", "City", "State", "ZIP", "Phone", "Manager",
                     "Units", "Designations", "Source", "Last Updated", "Notes"])
    for c in complexes:
        writer.writerow([
            c["name"],
            c["address"],
            c["city"],
            c["state"],
            c["zip"],
            c.get("phone") or "Not on file",
            c.get("manager") or "Not on file",
            c.get("unit_count") or "Not on file",
            ", ".join(c.get("designations", [])),
            c.get("source", ""),
            c.get("last_updated", ""),
            st.session_state.notes.get(c["id"], ""),
        ])
    return output.getvalue().encode("utf-8")


def export_to_pdf(complexes: list[dict]) -> bytes:
    """
    Minimal PDF using only the stdlib (no reportlab dependency).
    For richer output, swap in reportlab or weasyprint.
    """
    lines = []
    lines.append("OUTREACH HUB — HOUSING COMPLEX EXPORT")
    lines.append(f"Generated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
    lines.append("=" * 60)
    for c in complexes:
        lines.append("")
        lines.append(f"  {c['name']}")
        lines.append(f"  {c['address']}, {c['city']}, {c['state']} {c['zip']}")
        lines.append(f"  Phone:   {c.get('phone') or 'Not on file'}")
        lines.append(f"  Manager: {c.get('manager') or 'Not on file'}")
        lines.append(f"  Units:   {c.get('unit_count') or 'Not on file'}")
        lines.append(f"  Type:    {', '.join(c.get('designations', [])) or 'N/A'}")
        lines.append(f"  Source:  {c.get('source', '')} (updated {c.get('last_updated', '')})")
        note = st.session_state.notes.get(c["id"], "")
        if note:
            lines.append(f"  Notes:   {note}")
        lines.append("-" * 60)

    # Wrap as a basic text/PDF structure (plain-text PDF v1.4)
    text_body = "\n".join(lines)
    pdf = _make_plain_text_pdf(text_body)
    return pdf


def _make_plain_text_pdf(text: str) -> bytes:
    """Generate a minimal valid PDF containing plain text."""
    # Escape PDF special chars
    safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    lines = safe.split("\n")

    stream_lines = []
    y = 750
    for line in lines:
        stream_lines.append(f"BT /F1 10 Tf 40 {y} Td ({line}) Tj ET")
        y -= 13
        if y < 40:
            # crude page break
            y = 750

    stream = "\n".join(stream_lines)
    stream_bytes = stream.encode("latin-1", errors="replace")
    stream_len = len(stream_bytes)

    obj1 = b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    obj2 = b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
    obj3 = b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
    obj4 = (
        f"4 0 obj\n<< /Length {stream_len} >>\nstream\n".encode()
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    obj5 = b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>\nendobj\n"

    header = b"%PDF-1.4\n"
    body = obj1 + obj2 + obj3 + obj4 + obj5
    xref_pos = len(header) + len(body)

    trailer = (
        f"xref\n0 6\n0000000000 65535 f \n"
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode()

    return header + body + trailer
