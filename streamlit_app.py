# ======================================
# AIREX SMART CRM SEARCH (SECURE VERSION)
# ======================================

import streamlit as st
import xmlrpc.client
import re
import pandas as pd
from itertools import islice
from datetime import datetime, timedelta
import socket
import time

# ======================================
# SECURITY SETTINGS
# ======================================

# Prevent hanging connections
socket.setdefaulttimeout(20)

# Load credentials from Streamlit secrets
USERNAME = st.secrets["APP_USERNAME"]
PASSWORD = st.secrets["APP_PASSWORD"]

SESSION_HOURS = 24
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_MINUTES = 15

# ======================================
# SECURITY INITIALIZATION
# ======================================

def initialize_security():

    if "failed_attempts" not in st.session_state:
        st.session_state["failed_attempts"] = 0

    if "lockout_until" not in st.session_state:
        st.session_state["lockout_until"] = None

# ======================================
# LOCKOUT CHECK
# ======================================

def is_locked():

    lockout_until = st.session_state.get("lockout_until")

    if lockout_until:

        if datetime.now() < lockout_until:

            remaining = lockout_until - datetime.now()
            mins = int(remaining.total_seconds() // 60) + 1

            st.error(f"🔒 Too many failed attempts. Try again in {mins} minute(s).")
            return True

        else:

            st.session_state["failed_attempts"] = 0
            st.session_state["lockout_until"] = None

    return False

# ======================================
# LOGIN PAGE
# ======================================

def login_page():

    initialize_security()

    st.title("🔐 Airex Login")

    if is_locked():
        st.stop()

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):

        if u == USERNAME and p == PASSWORD:

            st.session_state["logged"] = True
            st.session_state["login_time"] = datetime.now()
            st.session_state["failed_attempts"] = 0

            st.success("✅ Login Successful")

            time.sleep(1)
            st.rerun()

        else:

            st.session_state["failed_attempts"] += 1

            remaining = MAX_LOGIN_ATTEMPTS - st.session_state["failed_attempts"]

            if remaining <= 0:

                st.session_state["lockout_until"] = (
                    datetime.now() + timedelta(minutes=LOCKOUT_MINUTES)
                )

                st.error("🔒 Too many failed attempts. Locked for 15 minutes.")

            else:

                st.error(
                    f"❌ Wrong Username or Password. {remaining} attempt(s) remaining."
                )

# ======================================
# SESSION CHECK
# ======================================

def check_login():

    if "logged" not in st.session_state:
        return False

    login_time = st.session_state.get("login_time")

    if not login_time:
        return False

    if datetime.now() - login_time > timedelta(hours=SESSION_HOURS):

        st.session_state.clear()
        return False

    return True

# ======================================
# ODOO CONNECTION
# ======================================

@st.cache_resource
def connect_odoo():

    url = st.secrets["ODOO_URL"]
    db = st.secrets["ODOO_DB"]
    user = st.secrets["ODOO_USER"]
    password = st.secrets["ODOO_PASS"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    uid = common.authenticate(db, user, password, {})

    if not uid:
        st.error("❌ Odoo Login Failed")
        st.stop()

    return models, uid, db, password, url

# ======================================
# LOGIN CHECK FIRST
# ======================================

if not check_login():
    login_page()
    st.stop()

# ======================================
# CONNECT TO ODOO
# ======================================

models, uid, db, password, base_url = connect_odoo()

st.success("✅ Connected to Odoo")

# ======================================
# LOGOUT BUTTON
# ======================================

if st.button("🚪 Logout"):
    st.session_state.clear()
    st.rerun()

# ======================================
# NUMBER NORMALIZATION
# ======================================

def normalize(num):
    return re.sub(r"\D", "", str(num))

# ======================================
# PHONE NUMBER MASKING
# ======================================

def mask_number(num):

    if not num:
        return ""

    digits = normalize(num)

    if len(digits) >= 10:
        return digits[:5] + "XXXXX"

    return "XXXXX"

# ======================================
# VARIANT GENERATION
# ======================================

def generate_variants(number):

    digits = normalize(number)

    if digits.startswith("91"):
        digits = digits[2:]

    last10 = digits[-10:]

    base = set([
        number,
        last10,
        last10[:5] + " " + last10[5:],
        last10[:3] + " " + last10[3:],
        last10[:4] + " " + last10[4:]
    ])

    prefixes = ["", "0", "91", "+91", "91 ", "+91 "]

    final = []

    for p in prefixes:
        for b in base:
            final.append(p + b)

    return list(dict.fromkeys(final))

# ======================================
# CHUNK HELPER
# ======================================

def chunked(iterable, size):

    it = iter(iterable)

    while True:

        batch = list(islice(it, size))

        if not batch:
            break

        yield batch

# ======================================
# UI
# ======================================

st.title("📞 Airex Smart CRM Search")

st.markdown(
    "Searches in **20-combination chunks** (Includes Lost Leads)"
)

number = st.text_input(
    "Enter Mobile / Phone Number",
    max_chars=15
)

search_btn = st.button("🔍 Search")

# ======================================
# SEARCH
# ======================================

if search_btn and number:

    digits = normalize(number)

    # Input validation
    if len(digits) < 10 or len(digits) > 15:
        st.error("❌ Enter valid mobile number")
        st.stop()

    variants = generate_variants(number)

    st.info(f"Total combinations: {len(variants)}")

    results = []

    for batch in chunked(variants, 20):

        for v in batch:

            domain = [
                "&",
                ("active", "in", [True, False]),
                "|",
                ("mobile", "ilike", v),
                ("phone", "ilike", v)
            ]

            try:

                leads = models.execute_kw(
                    db,
                    uid,
                    password,
                    "crm.lead",
                    "search_read",
                    [domain],
                    {
                        "fields": [
                            "name",
                            "partner_name",
                            "user_id",
                            "mobile",
                            "phone",
                            "stage_id",
                            "active"
                        ],
                        "limit": 50
                    }
                )

                for l in leads:

                    results.append({
                        "Matched With": v,
                        "Lead Name": l.get("name"),
                        "Company": l.get("partner_name"),
                        "Salesperson": (
                            l["user_id"][1]
                            if l.get("user_id")
                            else ""
                        ),
                        "Stored Mobile": mask_number(
                            l.get("mobile")
                        ),
                        "Stored Phone": mask_number(
                            l.get("phone")
                        ),
                        "Stage": (
                            l["stage_id"][1]
                            if l.get("stage_id")
                            else ""
                        ),
                        "Status": (
                            "Lost / Archived"
                            if not l.get("active")
                            else "Active"
                        )
                    })

            except Exception:
                st.error("❌ Error while fetching data from Odoo")
                st.stop()

        if results:
            break

    if results:

        df = pd.DataFrame(results).drop_duplicates()

        st.success(
            f"✅ {len(df)} Lead(s) Found (Including Lost)"
        )

        st.dataframe(df, use_container_width=True)

    else:

        st.warning("❌ No lead found")
