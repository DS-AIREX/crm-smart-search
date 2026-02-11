# ==========================================
# AIREX SMART CRM SEARCH (SECURE LOGIN + CHUNK SEARCH)
# ==========================================

import streamlit as st
import xmlrpc.client
import re
import pandas as pd
from itertools import islice
from datetime import datetime, timedelta

# ----------------------------
# LOGIN SETTINGS
# ----------------------------

USERS = {
    "airex": "airex111"
}

SESSION_HOURS = 24

# ----------------------------
# LOGIN FUNCTION
# ----------------------------

def login_screen():

    st.title("🔐 Airex CRM Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    login_btn = st.button("Login")

    if login_btn:
        if username in USERS and USERS[username] == password:
            st.session_state["logged_in"] = True
            st.session_state["login_time"] = datetime.now()
            st.success("✅ Login successful")
            st.experimental_rerun()
        else:
            st.error("❌ Invalid credentials")

# ----------------------------
# SESSION CHECK
# ----------------------------

def check_session():
    if "logged_in" not in st.session_state:
        return False

    if datetime.now() - st.session_state["login_time"] > timedelta(hours=SESSION_HOURS):
        st.session_state.clear()
        return False

    return True

# ----------------------------
# ODOO CONNECTION
# ----------------------------

@st.cache_resource
def connect_odoo():
    url = "http://103.12.1.110:8991"
    db = "airexheaters"
    username = "prateek@airexheaters.com"
    password = "airex@12345"

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    uid = common.authenticate(db, username, password, {})

    if not uid:
        st.error("❌ Odoo Login Failed")
        st.stop()

    return models, uid, db, password

models, uid, db, password = connect_odoo()

# ----------------------------
# CLEAN NUMBER
# ----------------------------

def normalize(num):
    return re.sub(r"\D", "", num)

# ----------------------------
# GENERATE VARIANTS
# ----------------------------

def generate_variants(number):

    base = normalize(number)

    if base.startswith("91"):
        base = base[2:]

    variants = set()

    variants.add(base)

    for i in [3,4,5]:
        variants.add(base[:i] + " " + base[i:])

    prefixes = ["", "0", "91", "+91", "91 ", "+91 "]

    final = set()

    for p in prefixes:
        for v in variants:
            final.add(p + v)

    return list(final)

# ----------------------------
# CHUNK GENERATOR
# ----------------------------

def chunked(iterable, size):
    it = iter(iterable)
    while True:
        chunk = list(islice(it, size))
        if not chunk:
            break
        yield chunk

# ----------------------------
# SEARCH FUNCTION
# ----------------------------

def search_lead(number):

    variants = generate_variants(number)

    found = []

    for batch in chunked(variants, 20):

        domain = []

        for v in batch:
            domain += ["|", ("mobile","=",v), ("phone","=",v)]

        domain = domain[1:]

        leads = models.execute_kw(
            db, uid, password,
            "crm.lead",
            "search_read",
            [domain],
            {
                "fields":["name","partner_name","user_id","mobile","phone"],
                "limit":10
            }
        )

        if leads:
            for l in leads:
                found.append({
                    "Lead Name": l.get("name"),
                    "Company": l.get("partner_name"),
                    "Salesperson": l["user_id"][1] if l.get("user_id") else "",
                    "Mobile": l.get("mobile"),
                    "Phone": l.get("phone")
                })

    return found

# ----------------------------
# MAIN APP
# ----------------------------

if not check_session():
    login_screen()
    st.stop()

st.set_page_config(page_title="Airex Smart CRM Search", layout="wide")
st.title("📞 Airex Smart CRM Search")

number = st.text_input("Enter Mobile Number")

if st.button("🔍 Search"):

    if not number:
        st.warning("Enter a number")
    else:
        with st.spinner("Searching..."):
            result = search_lead(number)

        if result:
            df = pd.DataFrame(result)
            st.success(f"✅ {len(df)} lead(s) found")
            st.dataframe(df, use_container_width=True)
        else:
            st.error("❌ No lead found")

