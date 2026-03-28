import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime, date
from data import COMPLEXES, VISIT_STATUSES
from utils import (
    search_complexes,
    get_complex_by_id,
    log_visit,
    add_contact,
    add_note,
    export_to_csv,
    export_to_pdf,
    flag_complex,
    get_visit_history,
    get_contacts_for_complex,
    check_hospice_eligibility,
    get_overdue_followups,
)

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Outreach Hub",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ───────────────────────────────────────────────────
for key, default in {
    "selected_complex_id": None,
    "view": "search",          # search | detail | visits | contacts | export
    "visits": {},              # complex_id -> list of visit dicts
    "contacts": {},            # complex_id -> list of contact dicts
    "notes": {},               # complex_id -> str
    "flags": set(),            # set of flagged complex ids
    "search_results": [],
    "search_query": "",
    "selected_cities": [],
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

h1, h2, h3 { font-family: 'DM Serif Display', serif; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f1923;
    color: #e8e0d4;
}
section[data-testid="stSidebar"] * { color: #e8e0d4 !important; }
section[data-testid="stSidebar"] .stButton > button {
    background: transparent;
    border: 1px solid #2e3d4e;
    color: #e8e0d4 !important;
    width: 100%;
    text-align: left;
    border-radius: 6px;
    transition: all 0.2s;
    font-family: 'DM Sans', sans-serif;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: #1e2d3e;
    border-color: #c8a96e;
    color: #c8a96e !important;
}

/* Cards */
.complex-card {
    background: #fff;
    border: 1px solid #e8e2d9;
    border-radius: 10px;
    padding: 1.1rem 1.3rem;
    margin-bottom: 0.75rem;
    cursor: pointer;
    transition: box-shadow 0.2s, border-color 0.2s;
}
.complex-card:hover {
    box-shadow: 0 4px 18px rgba(0,0,0,0.09);
    border-color: #c8a96e;
}
.complex-card h4 { margin: 0 0 0.2rem; color: #1a2332; font-family: 'DM Serif Display', serif; font-size: 1.05rem; }
.complex-card p  { margin: 0; color: #6b7280; font-size: 0.85rem; }

.badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.03em;
    margin-right: 4px;
}
.badge-hud    { background: #dbeafe; color: #1d4ed8; }
.badge-s8     { background: #fef3c7; color: #92400e; }
.badge-tc     { background: #d1fae5; color: #065f46; }
.badge-flag   { background: #fee2e2; color: #991b1b; }

.detail-label { font-size: 0.78rem; font-weight: 600; color: #9ca3af; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 2px; }
.detail-value { font-size: 0.97rem; color: #1a2332; margin-bottom: 1rem; }

.visit-row {
    background: #f9fafb;
    border-left: 3px solid #c8a96e;
    border-radius: 0 6px 6px 0;
    padding: 0.6rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.88rem;
}
.eligibility-flag {
    background: #fef3c7;
    border: 1px solid #f59e0b;
    border-radius: 8px;
    padding: 0.5rem 0.9rem;
    font-size: 0.85rem;
    color: #92400e;
    margin-top: 0.4rem;
}
.section-header {
    font-family: 'DM Serif Display', serif;
    font-size: 1.4rem;
    color: #1a2332;
    margin-bottom: 0.2rem;
}
.overdue-card {
    background: #fff1f2;
    border: 1px solid #fecdd3;
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.5rem;
    font-size: 0.87rem;
}
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
CITIES = ["Lewisville", "Carrollton", "Flower Mound", "Denton"]

def nav(view, complex_id=None):
    st.session_state.view = view
    if complex_id:
        st.session_state.selected_complex_id = complex_id
    st.rerun()

def designation_badges(designations):
    html = ""
    for d in designations:
        cls = {"HUD": "badge-hud", "Section 8": "badge-s8", "Tax Credit": "badge-tc"}.get(d, "badge-hud")
        html += f'<span class="badge {cls}">{d}</span>'
    return html

# ── Sidebar nav ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏠 Outreach Hub")
    st.markdown("---")
    st.button("🔍  Search Complexes",   on_click=nav, args=("search",))
    st.button("📋  Visit Tracker",       on_click=nav, args=("visits",))
    st.button("⚠️  Overdue Follow-ups",  on_click=nav, args=("overdue",))
    st.button("📤  Export",              on_click=nav, args=("export",))
    st.markdown("---")
    st.caption("Data sources: HUD · TDHCA · 211 Texas")
    st.caption(f"Last refreshed: {date.today().strftime('%b %d, %Y')}")

# ══════════════════════════════════════════════════════════════════════════════
# VIEW: SEARCH
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.view == "search":
    st.markdown('<p class="section-header">Find Housing Complexes</p>', unsafe_allow_html=True)
    st.caption("Search by city or natural language — e.g. *"Show me complexes in Denton"*")

    col_q, col_btn = st.columns([5, 1])
    with col_q:
        query = st.text_input("", placeholder='e.g. "Low-income housing in Lewisville"',
                              label_visibility="collapsed", key="nlp_query")
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        search_clicked = st.button("Search", use_container_width=True)

    selected_cities = st.multiselect("Filter by city", CITIES, key="city_filter")

    if search_clicked or selected_cities:
        results = search_complexes(query, selected_cities)
        st.session_state.search_results = results
    else:
        results = st.session_state.search_results

    st.markdown(f"**{len(results)} result(s)**" if results else "")

    if not results and (search_clicked or selected_cities):
        st.warning("No results found for your search. Try selecting different cities or broadening your query.")
    else:
        for c in results:
            flagged = c["id"] in st.session_state.flags
            badges = designation_badges(c.get("designations", []))
            flag_html = '<span class="badge badge-flag">⚑ Flagged</span>' if flagged else ""
            with st.container():
                st.markdown(f"""
                <div class="complex-card">
                    <h4>{c['name']}</h4>
                    <p>{c['address']}, {c['city']}, {c['state']} {c['zip']}</p>
                    <div style="margin-top:6px">{badges}{flag_html}</div>
                </div>
                """, unsafe_allow_html=True)
                if st.button("View Details →", key=f"view_{c['id']}"):
                    nav("detail", c["id"])

# ══════════════════════════════════════════════════════════════════════════════
# VIEW: DETAIL
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.view == "detail":
    cid = st.session_state.selected_complex_id
    c   = get_complex_by_id(cid)

    if not c:
        st.error("Complex not found.")
        st.button("← Back", on_click=nav, args=("search",))
    else:
        col_back, col_flag = st.columns([8, 2])
        with col_back:
            st.button("← Back to Search", on_click=nav, args=("search",))
        with col_flag:
            label = "⚑ Unflag" if cid in st.session_state.flags else "⚑ Flag for Follow-up"
            if st.button(label, use_container_width=True):
                flag_complex(cid)
                st.rerun()

        st.markdown(f'<p class="section-header">{c["name"]}</p>', unsafe_allow_html=True)
        st.markdown(designation_badges(c.get("designations", [])), unsafe_allow_html=True)
        st.markdown("---")

        col1, col2 = st.columns(2)
        fields = [
            ("Full Address",     f'{c["address"]}, {c["city"]}, {c["state"]} {c["zip"]}'),
            ("Phone",            c.get("phone", "Not on file")),
            ("Property Manager", c.get("manager", "Not on file")),
            ("Unit Count",       c.get("unit_count", "Not on file")),
            ("Designations",     ", ".join(c.get("designations", [])) or "Not on file"),
            ("Data Source",      c.get("source", "Not on file")),
        ]
        for i, (label, value) in enumerate(fields):
            col = col1 if i % 2 == 0 else col2
            col.markdown(f'<p class="detail-label">{label}</p><p class="detail-value">{value}</p>', unsafe_allow_html=True)

        maps_url = f"https://www.google.com/maps/search/?api=1&query={c['address'].replace(' ', '+')}+{c['city']}+{c['state']}"
        st.link_button("🗺️ Open in Google Maps", maps_url)

        # Notes
        st.markdown("#### 📝 Internal Notes")
        note_val = st.text_area("Add or edit notes for this complex", value=st.session_state.notes.get(cid, ""), key="note_input")
        if st.button("Save Note"):
            add_note(cid, note_val)
            st.success("Note saved.")

        # Log Visit
        st.markdown("#### 📅 Log a Visit")
        with st.form("visit_form"):
            v_status = st.selectbox("Visit Status", VISIT_STATUSES)
            v_date   = st.date_input("Visit Date", value=date.today())
            v_notes  = st.text_input("Visit Notes (optional)")
            if st.form_submit_button("Log Visit"):
                log_visit(cid, v_status, str(v_date), v_notes)
                st.success("Visit logged.")

        # Visit history
        history = get_visit_history(cid)
        if history:
            st.markdown("#### 🕐 Visit History")
            for v in reversed(history):
                st.markdown(f'<div class="visit-row"><b>{v["date"]}</b> — {v["status"]}'
                            + (f' &nbsp;|&nbsp; {v["notes"]}' if v["notes"] else "") + '</div>',
                            unsafe_allow_html=True)

        # Contacts
        st.markdown("#### 👤 Referral Contacts")
        contacts = get_contacts_for_complex(cid)
        if contacts:
            for ct in contacts:
                elig = check_hospice_eligibility(ct)
                st.markdown(f"**{ct['first']} {ct['last']}** — {ct['relationship']} | {ct.get('phone', 'No phone')}")
                if elig:
                    st.markdown(f'<div class="eligibility-flag">⚠️ May meet hospice eligibility indicators: {elig}</div>', unsafe_allow_html=True)

        with st.expander("+ Add Referral Contact"):
            with st.form("contact_form"):
                cc1, cc2 = st.columns(2)
                first = cc1.text_input("First Name")
                last  = cc2.text_input("Last Name")
                age   = st.number_input("Age (optional)", min_value=0, max_value=120, value=0)
                phone = st.text_input("Contact Number (optional)")
                rel   = st.selectbox("Relationship", ["Resident", "Family", "Staff"])
                illness = st.text_input("Chronic Illness (optional, for eligibility check)")
                if st.form_submit_button("Add Contact"):
                    if first and last:
                        add_contact(cid, first, last, int(age) if age else None, phone, rel, illness)
                        st.success("Contact added.")
                        st.rerun()
                    else:
                        st.error("First and last name are required.")

# ══════════════════════════════════════════════════════════════════════════════
# VIEW: VISIT TRACKER
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.view == "visits":
    st.markdown('<p class="section-header">Visit Tracker</p>', unsafe_allow_html=True)
    st.caption("All logged visits across complexes")

    all_visits = []
    for cid, visits in st.session_state.visits.items():
        c = get_complex_by_id(cid)
        name = c["name"] if c else cid
        for v in visits:
            all_visits.append({"Complex": name, "Date": v["date"], "Status": v["status"], "Notes": v["notes"]})

    if all_visits:
        df = pd.DataFrame(all_visits).sort_values("Date", ascending=False)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No visits logged yet. Open a complex detail page to log a visit.")

# ══════════════════════════════════════════════════════════════════════════════
# VIEW: OVERDUE FOLLOW-UPS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.view == "overdue":
    st.markdown('<p class="section-header">⚠️ Overdue Follow-ups</p>', unsafe_allow_html=True)
    overdue = get_overdue_followups()
    if overdue:
        for item in overdue:
            st.markdown(f"""
            <div class="overdue-card">
                <b>{item['name']}</b> &nbsp;·&nbsp; Last visit: {item['last_visit']} &nbsp;·&nbsp; Status: {item['status']}
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Open {item['name']}", key=f"od_{item['id']}"):
                nav("detail", item["id"])
    else:
        st.success("No overdue follow-ups. You're all caught up! ✓")

# ══════════════════════════════════════════════════════════════════════════════
# VIEW: EXPORT
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.view == "export":
    st.markdown('<p class="section-header">Export List</p>', unsafe_allow_html=True)
    st.caption("Export your current search results with notes.")

    results = st.session_state.search_results
    if not results:
        st.warning("No search results to export. Run a search first.")
    else:
        st.write(f"**{len(results)} complexes** ready to export.")
        fmt = st.radio("Export format", ["CSV", "PDF"], horizontal=True)

        if st.button("Export Now"):
            if fmt == "CSV":
                csv_data = export_to_csv(results)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv_data,
                    file_name=f"housing_outreach_{ts}.csv",
                    mime="text/csv",
                )
                st.success(f"CSV ready — {datetime.now().strftime('%b %d, %Y %I:%M %p')}")
            else:
                pdf_data = export_to_pdf(results)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_data,
                    file_name=f"housing_outreach_{ts}.pdf",
                    mime="application/pdf",
                )
                st.success(f"PDF ready — {datetime.now().strftime('%b %d, %Y %I:%M %p')}")
