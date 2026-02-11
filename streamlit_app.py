import streamlit as st
import xmlrpc.client
import re
import pandas as pd

# =========================================
# ODOO CONNECTION (FROM SECRETS)
# =========================================

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
        st.error("❌ Odoo Login Failed")
        st.stop()

    return models, uid, db, password, url


models, uid, db, password, base_url = get_odoo_connection()
st.success("✅ Connected to Odoo")

# =========================================
# UTILITIES
# =========================================

def normalize(num):
    return re.sub(r"\D","",num)

def generate_variants(num):

    base = normalize(num)

    if base.startswith("91"):
        base = base[2:]

    last10 = base[-10:]

    return list(set([
        last10,
        base,
        "0" + last10,
        "91" + last10,
        "+91" + last10,
        num
    ]))

def build_link(lead_id):
    return f"{base_url}/web#id={lead_id}&model=crm.lead&view_type=form"

# =========================================
# UI
# =========================================

st.title("📞 Airex Smart CRM Search")
st.markdown("Search lead using mobile or phone number")

number = st.text_input("Enter Mobile Number")
search_btn = st.button("🔍 Search")

# =========================================
# SEARCH
# =========================================

if search_btn and number:

    variants = generate_variants(number)
    st.write("Trying Variants:", variants)

    found = []

    for v in variants:

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
            {"fields":["id","name","partner_name","user_id","mobile","phone"],"limit":20}
        )

        for l in leads:
            found.append({
                "Lead Name": l.get("name"),
                "Company": l.get("partner_name"),
                "Salesperson": l["user_id"][1] if l.get("user_id") else "",
                "Mobile": l.get("mobile"),
                "Phone": l.get("phone"),
                "Open": build_link(l["id"])
            })

    if found:
        df = pd.DataFrame(found)
        st.success(f"✅ {len(df)} Lead(s) Found")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("❌ No lead found")

