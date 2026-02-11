import streamlit as st
import xmlrpc.client
import re
import pandas as pd

# ======================================
# ODOO CONNECTION (SECRETS)
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


models, uid, db, password, base_url = connect_odoo()
st.success("✅ Connected to Odoo")

# ======================================
# VARIANT GENERATION (MAX COMBINATIONS)
# ======================================

def normalize(num):
    return re.sub(r"\D", "", num)

def generate_variants(number):

    digits = normalize(number)

    if digits.startswith("91"):
        digits = digits[2:]

    last10 = digits[-10:]

    base_variants = set()

    # Raw
    base_variants.add(number)
    base_variants.add(last10)

    # All possible single-space splits
    for i in range(2,9):
        base_variants.add(last10[:i] + " " + last10[i:])

    # Double-space splits
    for i in range(2,8):
        for j in range(i+2,9):
            base_variants.add(
                last10[:i] + " " + last10[i:j] + " " + last10[j:]
            )

    prefixes = ["", "0", "91", "+91", "91 ", "+91 "]

    final = set()
    for p in prefixes:
        for v in base_variants:
            final.add(p + v)

    return list(final)

# ======================================
# BUILD LINK
# ======================================

def lead_link(lead_id):
    return f"{base_url}/web#id={lead_id}&model=crm.lead&view_type=form"

# ======================================
# UI
# ======================================

st.title("📞 Airex Ultra Smart CRM Search")
st.markdown("Matches **all number formats & spacing styles**")

number = st.text_input("Enter Mobile / Phone Number")
search_btn = st.button("🔍 Search")

# ======================================
# SEARCH
# ======================================

if search_btn and number:

    variants = generate_variants(number)
    st.info(f"Trying {len(variants)} combinations")

    results = []

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
            results.append({
                "Matched With": v,
                "Lead Name": l.get("name"),
                "Company": l.get("partner_name"),
                "Salesperson": l["user_id"][1] if l.get("user_id") else "",
                "Stored Mobile": l.get("mobile"),
                "Stored Phone": l.get("phone"),
                "Open": lead_link(l["id"])
            })

    if results:
        df = pd.DataFrame(results).drop_duplicates()
        st.success(f"✅ {len(df)} Lead(s) Found")
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("❌ No lead found")

