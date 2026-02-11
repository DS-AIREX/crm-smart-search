import streamlit as st
import xmlrpc.client
import re
import pandas as pd

# ---------------------------
# CONNECT TO ODOO (SECRETS)
# ---------------------------
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
        st.error("❌ Odoo login failed")
        st.stop()

    return models, uid, db, password, url

models, uid, db, password, base_url = get_odoo_connection()
st.success("✅ Connected to Odoo successfully")

# ---------------------------
# PHONE NORMALIZATION
# ---------------------------
def generate_variants(num):
    base = re.sub(r"\D", "", num)

    if base.startswith("91"):
        base = base[2:]

    variants = set()

    variants.add(base)
    variants.add("0" + base)
    variants.add("91" + base)
    variants.add("+91" + base)
    variants.add("+91 " + base)

    variants.add(base[:5] + " " + base[5:])
    variants.add(base[:3] + " " + base[3:])

    return list(variants)

# ---------------------------
# BUILD ODOO LINK
# ---------------------------
def build_link(lead_id):
    return f"{base_url}/web#id={lead_id}&model=crm.lead&view_type=form"

# ---------------------------
# UI
# ---------------------------
st.title("📞 Airex Smart CRM Search")
st.markdown("Search lead using mobile or phone number")

number = st.text_input("Enter Mobile Number")
btn = st.button("🔍 Search")

# ---------------------------
# SEARCH LOGIC
# ---------------------------
if btn and number:

    variants = generate_variants(number)
    st.write("Searching Variants:", variants)

    results = []

    for v in variants:

        domain = ["|", ("mobile", "=", v), ("phone", "=", v)]

        leads = models.execute_kw(
            db, uid, password,
            "crm.lead",
            "search_read",
            [domain],
            {"fields": ["id","name","partner_name","mobile","phone"], "limit": 10}
        )

        for l in leads:
            results.append({
                "Lead Name": l.get("name"),
                "Company": l.get("partner_name"),
                "Mobile": l.get("mobile"),
                "Phone": l.get("phone"),
                "Open Link": build_link(l["id"])
            })

    if results:
        df = pd.DataFrame(results)
        st.success(f"✅ {len(df)} Lead(s) Found")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("❌ No lead found")

