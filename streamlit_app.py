import streamlit as st
import xmlrpc.client
import re
import pandas as pd

@st.cache_resource
def get_odoo_connection():
    url = st.secrets["ODOO_URL"]
    db = st.secrets["ODOO_DB"]
    username = st.secrets["ODOO_USER"]
    password = st.secrets["ODOO_PASS"]

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    uid = common.authenticate(db, username, password, {})

    if not uid:
        st.error("Login failed")
        st.stop()

    return models, uid, db, password, url

models, uid, db, password, base_url = get_odoo_connection()

def normalize(num):
    return re.sub(r"\D", "", num)

def generate_variants(num):
    base = normalize(num)
    variants = set([base])

    prefixes = ["", "0", "91", "+91"]
    for p in prefixes:
        variants.add(p + base)

    return list(variants)

def build_link(lead_id):
    return f"{base_url}/web#id={lead_id}&model=crm.lead&view_type=form"

st.title("📞 Airex CRM Smart Search")

number = st.text_input("Enter Mobile Number")
btn = st.button("Search")

if btn and number:
    variants = generate_variants(number)
    results = []

    for v in variants:
        domain = ["|", ("mobile","=",v), ("phone","=",v)]
        leads = models.execute_kw(
            db, uid, password,
            "crm.lead",
            "search_read",
            [domain],
            {"fields":["id","name","partner_name","mobile","phone"],"limit":10}
        )

        for l in leads:
            results.append({
                "Lead": l["name"],
                "Company": l["partner_name"],
                "Mobile": l["mobile"],
                "Phone": l["phone"],
                "Open": build_link(l["id"])
            })

    if results:
        df = pd.DataFrame(results)
        st.dataframe(df)
    else:
        st.warning("No lead found")
