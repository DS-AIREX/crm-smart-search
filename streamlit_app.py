# ======================================
# AIREX SMART CRM SEARCH (WITH LOGIN)
# ======================================

import streamlit as st
import xmlrpc.client
import re
import pandas as pd
from itertools import islice
from datetime import datetime, timedelta

# ======================================
# SIMPLE LOGIN SYSTEM
# ======================================

USERNAME = "airex"
PASSWORD = "airex111"
SESSION_HOURS = 24

def login_page():

    st.title("🔐 Airex Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        if u == USERNAME and p == PASSWORD:
            st.session_state["logged"] = True
            st.session_state["login_time"] = datetime.now()
            st.success("✅ Login Successful")
            st.rerun()
        else:
            st.error("❌ Wrong Username or Password")

def check_login():

    if "logged" not in st.session_state:
        return False

    if datetime.now() - st.session_state["login_time"] > timedelta(hours=SESSION_HOURS):
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

models, uid, db, password, base_url = connect_odoo()
st.success("✅ Connected to Odoo")

# ======================================
# VARIANT GENERATION (LIMITED)
# ======================================

def normalize(num):
    return re.sub(r"\D","",num)

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

st.title("📞 Airex Smart CRM Search (Fast)")
st.markdown("Searches in **20-combination chunks**")

number = st.text_input("Enter Mobile / Phone Number")
search_btn = st.button("🔍 Search")

# ======================================
# SEARCH
# ======================================

if search_btn and number:

    variants = generate_variants(number)
    st.info(f"Total combinations: {len(variants)}")

    results = []

    for batch in chunked(variants, 20):

        for v in batch:

            domain = [
                "|",
                ("mobile","ilike",v),
                ("phone","ilike",v)
            ]

            leads = models.execute_kw(
                db, uid, password,
                "crm.lead",
                "search_read",
                [domain],
                {"fields":["name","partner_name","user_id","mobile","phone"],"limit":20}
            )

            for l in leads:
                results.append({
                    "Matched With": v,
                    "Lead Name": l.get("name"),
                    "Company": l.get("partner_name"),
                    "Salesperson": l["user_id"][1] if l.get("user_id") else "",
                    "Stored Mobile": l.get("mobile"),
                    "Stored Phone": l.get("phone")
                })

        if results:
            break

    if results:
        df = pd.DataFrame(results).drop_duplicates()
        st.success(f"✅ {len(df)} Lead(s) Found")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("❌ No lead found")
