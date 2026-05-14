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
import base64  # ➕ ADD THIS
from github import Github  # ➕ ADD THIS
import importlib.util  # ➕ ADD THIS
import sys  # ➕ ADD THIS

# ======================================
# SECURITY SETTINGS
# ======================================

# Prevent hanging connections
socket.setdefaulttimeout(20)

# Load credentials from Streamlit secrets
USERNAME = st.secrets["APP_USERNAME"]
PASSWORD = st.secrets["APP_PASSWORD"]

# ➕ ADD: GitHub credentials for fetching code
GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]  # Your private repo token
GITHUB_REPO = st.secrets["GITHUB_REPO_NAME"]  # Your repo name: "username/odoo-daily-report"
GITHUB_CODE_PATH = st.secrets.get("GITHUB_CODE_PATH", "crm_search_app.py")  # Path to your search app code

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
# ➕ FETCH CODE FROM PRIVATE GITHUB REPO
# ======================================

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_code_from_github():
    """Fetch the CRM search app code from private GitHub repo"""
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(GITHUB_REPO)
        
        # Get the file content
        contents = repo.get_contents(GITHUB_CODE_PATH)
        
        # Decode the content
        code_content = base64.b64decode(contents.content).decode('utf-8')
        
        return code_content
        
    except Exception as e:
        st.error(f"❌ Failed to fetch code from GitHub: {str(e)}")
        st.error(f"Make sure file '{GITHUB_CODE_PATH}' exists in repo '{GITHUB_REPO}'")
        return None

@st.cache_resource
def load_crm_search_module():
    """Load the CRM search code as a module"""
    code = fetch_code_from_github()
    
    if not code:
        return None
    
    try:
        # Create a temporary module
        module_name = "crm_search_app"
        
        # Remove old module if exists
        if module_name in sys.modules:
            del sys.modules[module_name]
        
        # Create new module from code
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        module = importlib.util.module_from_spec(spec)
        
        # Execute the code in the module context
        exec(code, module.__dict__)
        
        # Store in sys.modules
        sys.modules[module_name] = module
        
        return module
        
    except Exception as e:
        st.error(f"❌ Error loading CRM search module: {str(e)}")
        return None

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
# ➕ FETCH AND EXECUTE CRM SEARCH FROM GITHUB
# ======================================

# Fetch the CRM search app code from your private repo
with st.spinner("📥 Loading CRM Search from GitHub repository..."):
    crm_module = load_crm_search_module()

if crm_module:
    st.success(f"✅ CRM Search loaded from: {GITHUB_REPO}/{GITHUB_CODE_PATH}")
    
    # The module should have all the functions and UI elements
    # It will automatically render its UI when we call its main functionality
    
    # Check if the module has the necessary functions
    if hasattr(crm_module, 'normalize'):
        # Use the functions from the fetched module
        normalize = crm_module.normalize
        mask_number = crm_module.mask_number
        generate_variants = crm_module.generate_variants
        chunked = crm_module.chunked
        
        # Now run the UI part (your original search UI code)
        # ======================================
        # UI (from your original code)
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
    
    else:
        st.error("❌ Fetched code doesn't contain required functions")
        st.code("Make sure your GitHub file contains: normalize(), mask_number(), generate_variants(), chunked()")

else:
    st.error("❌ Could not load CRM search from GitHub")

# ======================================
# ➕ OPTIONAL: SHOW CODE INFO IN SIDEBAR
# ======================================

with st.sidebar:
    st.divider()
    st.caption("📦 Code Source")
    st.caption(f"Repo: `{GITHUB_REPO}`")
    st.caption(f"File: `{GITHUB_CODE_PATH}`")
    
    if st.button("🔄 Reload Code from GitHub"):
        # Clear cache and reload
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()
