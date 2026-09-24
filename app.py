import streamlit as st
from pathlib import Path
import html
import base64
import mysql.connector
from mysql.connector import Error

# =========================================================
# DATABASE — TiDB CLOUD
# =========================================================

# Keep TiDB credentials outside the Python file.
# For local development create: .streamlit/secrets.toml
# and add the values shown in the setup message.

def _get_tidb_config():
    try:
        tidb = st.secrets["tidb"]
    except Exception:
        raise RuntimeError(
            "TiDB credentials are not configured. Create "
            ".streamlit/secrets.toml with the [tidb] settings."
        )

    config = {
        "host": str(tidb["host"]),
        "port": int(tidb.get("port", 4000)),
        "user": str(tidb["user"]),
        "password": str(tidb["password"]),
        "database": str(tidb.get("database", "data_personality")),
        "use_pure": True,
    }

    # TiDB Cloud Starter uses TLS. If a CA path is supplied, explicitly
    # verify both the certificate and the hostname.
    ca_path = str(tidb.get("ca_path", "")).strip()
    if ca_path:
        config["ssl_ca"] = ca_path
        config["ssl_verify_cert"] = True
        config["ssl_verify_identity"] = True

    return config


def _connect_to_personality_db():
    """Connect directly to the cloud TiDB database."""
    config = _get_tidb_config()
    connection = mysql.connector.connect(**config)
    if not connection.is_connected():
        raise Error("Could not connect to TiDB Cloud.")
    return connection


def save_personality_to_database(personality, personality_description, story):
    connection = None
    cursor = None
    try:
        connection = _connect_to_personality_db()
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS personality_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                song VARCHAR(255),
                memory TEXT,
                moment VARCHAR(255),
                favorite_app VARCHAR(255),
                screen_time VARCHAR(100),
                phone_time VARCHAR(100),
                favorite_movie VARCHAR(255),
                fictional_world VARCHAR(255),
                viewer_type VARCHAR(255),
                personality VARCHAR(255),
                personality_description TEXT,
                generated_story TEXT
            )
        """)

        query = """
            INSERT INTO personality_users (
                song, memory, moment, favorite_app, screen_time, phone_time,
                favorite_movie, fictional_world, viewer_type, personality,
                personality_description, generated_story
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """

        values = (
            st.session_state.get("song", ""),
            st.session_state.get("memory", ""),
            st.session_state.get("moment", ""),
            st.session_state.get("app", ""),
            st.session_state.get("screen_time", ""),
            st.session_state.get("phone_time", ""),
            st.session_state.get("comfort_watch", ""),
            st.session_state.get("fictional_world", ""),
            st.session_state.get("viewer_type", ""),
            personality,
            personality_description,
            story,
        )

        cursor.execute(query, values)
        connection.commit()
        return True, cursor.lastrowid

    except Error as e:
        return False, str(e)

    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                pass



# =========================================================
# ADMIN DASHBOARD
# =========================================================

def _get_admin_password():
    try:
        admin = st.secrets["admin"]
        return str(admin["password"])
    except Exception:
        return ""


def _load_admin_data():
    connection = None
    cursor = None
    try:
        connection = _connect_to_personality_db()
        cursor = connection.cursor(dictionary=True)
        query = (
            "SELECT id, created_at, song, memory, moment, favorite_app, "
            "screen_time, phone_time, favorite_movie, fictional_world, "
            "viewer_type, personality, personality_description, generated_story "
            "FROM personality_users ORDER BY created_at DESC, id DESC"
        )
        cursor.execute(query)
        return True, cursor.fetchall(), None
    except Error as e:
        return False, [], str(e)
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                if connection.is_connected():
                    connection.close()
            except Exception:
                pass


def render_admin_dashboard():
    st.markdown(
        '<style>'
        '.admin-title{font-size:42px;font-weight:800;letter-spacing:-1px;margin-bottom:4px;}'
        '.admin-subtitle{color:rgba(255,255,255,.62);margin-bottom:28px;}'
        '.admin-card{background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.10);'
        'border-radius:18px;padding:18px 20px;margin-bottom:14px;}'
        '.admin-label{color:rgba(255,255,255,.48);font-size:11px;letter-spacing:2px;'
        'text-transform:uppercase;margin-bottom:6px;}'
        '.admin-value{color:white;font-size:15px;line-height:1.55;white-space:pre-wrap;word-break:break-word;}'
        '</style>',
        unsafe_allow_html=True
    )

    if not st.session_state.get("admin_authenticated", False):
        st.markdown('<div class="admin-title">🔐 Admin Dashboard</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="admin-subtitle">Private access to all collected Data Personality responses.</div>',
            unsafe_allow_html=True
        )

        password = st.text_input(
            "Admin Password",
            type="password",
            key="admin_password_input",
            placeholder="Enter admin password"
        )

        if st.button("Login →", key="admin_login"):
            admin_password = _get_admin_password()
            if not admin_password:
                st.error("Admin password is not configured in .streamlit/secrets.toml.")
            elif password == admin_password:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")

        if st.button("← Back to App", key="admin_back_login"):
            st.query_params.clear()
            st.rerun()
        return

    st.markdown('<div class="admin-title">📊 Data Personality Admin</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="admin-subtitle">Every field collected and every generated result from your app.</div>',
        unsafe_allow_html=True
    )

    ok, rows, error = _load_admin_data()
    if not ok:
        st.error(f"Could not load data: {error}")
        if st.button("← Back to App", key="admin_back_error"):
            st.query_params.clear()
            st.rerun()
        return

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total submissions", len(rows))
    with c2:
        st.metric("Personalities generated", sum(1 for r in rows if r.get("personality")))

    st.markdown("### All collected data")

    if not rows:
        st.info("Abhi koi personality submission database mein nahi hai.")
    else:
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "ID",
                "created_at": "Submitted At",
                "song": "Song",
                "memory": "Song Memory",
                "moment": "Listening Moment",
                "favorite_app": "Favorite App",
                "screen_time": "Screen Time",
                "phone_time": "Phone Time",
                "favorite_movie": "Favorite Movie / Comfort Watch",
                "fictional_world": "Fictional World",
                "viewer_type": "Viewer Type",
                "personality": "Personality",
                "personality_description": "Personality Description",
                "generated_story": "Generated Story",
            },
        )

        st.markdown("### 🔎 Full details of a submission")
        ids = [r["id"] for r in rows]
        selected_id = st.selectbox(
            "Select submission",
            ids,
            format_func=lambda x: f"Submission #{x}",
            key="admin_selected_id"
        )
        selected = next((r for r in rows if r["id"] == selected_id), None)

        if selected:
            fields = [
                ("ID", selected.get("id")),
                ("Submitted At", selected.get("created_at")),
                ("Song", selected.get("song")),
                ("Song Memory", selected.get("memory")),
                ("Listening Moment", selected.get("moment")),
                ("Favorite App", selected.get("favorite_app")),
                ("Screen Time", selected.get("screen_time")),
                ("Phone Time", selected.get("phone_time")),
                ("Favorite Movie / Comfort Watch", selected.get("favorite_movie")),
                ("Fictional World", selected.get("fictional_world")),
                ("Viewer Type", selected.get("viewer_type")),
                ("Personality", selected.get("personality")),
                ("Personality Description", selected.get("personality_description")),
                ("Generated Story", selected.get("generated_story")),
            ]

            for label, value in fields:
                display_value = "" if value is None else str(value)
                st.markdown(
                    '<div class="admin-card">'
                    f'<div class="admin-label">{html.escape(label)}</div>'
                    f'<div class="admin-value">{html.escape(display_value)}</div>'
                    '</div>',
                    unsafe_allow_html=True
                )

    st.markdown("---")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🔄 Refresh Data", key="admin_refresh"):
            st.rerun()
    with b2:
        if st.button("← Back to App", key="admin_back"):
            st.session_state.admin_authenticated = False
            st.query_params.clear()
            st.rerun()


# =========================================================
# PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Your 2026 Data Personality",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# =========================================================
# SESSION STATE
# =========================================================

if "page" not in st.session_state:
    st.session_state.page = "landing"

if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

# MUSIC
if "song" not in st.session_state:
    st.session_state.song = ""

if "memory" not in st.session_state:
    st.session_state.memory = ""

if "moment" not in st.session_state:
    st.session_state.moment = ""

# ENTERTAINMENT
if "comfort_watch" not in st.session_state:
    st.session_state.comfort_watch = ""

if "fictional_world" not in st.session_state:
    st.session_state.fictional_world = ""

if "viewer_type" not in st.session_state:
    st.session_state.viewer_type = ""



# DIGITAL LIFE
if "app" not in st.session_state:
    st.session_state.app = ""

if "screen_time" not in st.session_state:
    st.session_state.screen_time = ""

if "phone_time" not in st.session_state:
    st.session_state.phone_time = ""


# =========================================================
# ENTERTAINMENT IMAGE ASSET
# =========================================================

CINEMA_IMAGE = Path(__file__).resolve().parent / "cinema_entertainment_asset.png"
MUSIC_IMAGE_URL = "https://images.unsplash.com/photo-1741745978060-9add161ba2c2?auto=format&fit=crop&fm=jpg&ixlib=rb-4.1.0&q=85&w=1600"

# User-provided panda images for the personality reveal.
# Embedded as data URIs so the app stays self-contained.
PANDA_IMAGE_1 = "data:image/png;base64,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"
PANDA_IMAGE_2 = "data:image/png;base64,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"
PANDA_IMAGE_3 = "data:image/png;base64,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"

# One panda is shown at a time, based on the generated personality title.
PERSONALITY_PANDA_IMAGES = {
    "THE DIGITAL NIGHT OWL": PANDA_IMAGE_3,
    "THE BINGE NIGHT OWL": PANDA_IMAGE_3,
    "THE NIGHT OWL": PANDA_IMAGE_3,
    "THE DIGITAL EXPLORER": PANDA_IMAGE_3,

    "THE STORY LOVER": PANDA_IMAGE_2,
    "THE COMFORT ESCAPIST": PANDA_IMAGE_2,
    "THE BINGE LOVER": PANDA_IMAGE_2,
    "THE PLOT HUNTER": PANDA_IMAGE_2,
    "THE COMFORT SEEKER": PANDA_IMAGE_2,
    "THE DREAMER": PANDA_IMAGE_2,

    "THE LITTLE MOMENT COLLECTOR": PANDA_IMAGE_1,
    "THE BALANCED EXPLORER": PANDA_IMAGE_1,
    "THE QUIETLY CURIOUS ONE": PANDA_IMAGE_1,
}



# =========================================================
# GLOBAL CSS
# =========================================================

st.markdown(
    """
    <style>

    /* =====================================================
       GLOBAL
    ===================================================== */

    html, body, [data-testid="stAppViewContainer"] {
        background: #050509 !important;
        color: #ffffff !important;
    }

    [data-testid="stAppViewContainer"] {
        background:
            radial-gradient(
                circle at 20% 25%,
                rgba(86, 54, 190, 0.20),
                transparent 30%
            ),
            radial-gradient(
                circle at 82% 60%,
                rgba(20, 130, 170, 0.14),
                transparent 30%
            ),
            #050509 !important;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stToolbar"] {
        display: none !important;
    }

    .block-container {
        max-width: 1400px !important;
        padding-top: 0rem !important;
        padding-bottom: 3rem !important;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }


    /* =====================================================
       TEXT
    ===================================================== */

    .eyebrow {
        color: #a9a7ba;
        font-size: 12px;
        letter-spacing: 6px;
        text-transform: uppercase;
        text-align: center;
        margin-bottom: 22px;
    }

    .hero-title {
        color: #ffffff;
        font-size: clamp(52px, 7vw, 100px);
        line-height: 0.95;
        font-weight: 900;
        letter-spacing: -4px;
        text-align: center;
        margin: 0 auto;
    }

    .hero-subtitle {
        color: #e1e0e8;
        font-size: 22px;
        line-height: 1.55;
        text-align: center;
        margin-top: 34px;
    }

    .hero-small {
        color: #aaa8b8;
        font-size: 16px;
        text-align: center;
        margin-top: 15px;
    }

    .page-label {
        color: #8d899f;
        font-size: 12px;
        letter-spacing: 6px;
        text-align: center;
        text-transform: uppercase;
        margin-top: 80px;
        margin-bottom: 22px;
    }

    .question {
        color: #ffffff;
        font-size: clamp(38px, 5vw, 68px);
        font-weight: 850;
        line-height: 1.05;
        letter-spacing: -2px;
        text-align: center;
        max-width: 900px;
        margin: 0 auto;
    }

    .question-sub {
        color: #bcb9c8;
        font-size: 17px;
        text-align: center;
        margin-top: 20px;
        margin-bottom: 35px;
    }


    /* =====================================================
       ORBIT CIRCLES
    ===================================================== */

    .orb-left {
        position: fixed;
        width: 520px;
        height: 520px;
        border: 1px solid rgba(150, 130, 255, 0.14);
        border-radius: 50%;
        left: -260px;
        top: 130px;
        pointer-events: none;
        z-index: 0;
    }

    .orb-right {
        position: fixed;
        width: 520px;
        height: 520px;
        border: 1px solid rgba(50, 190, 220, 0.12);
        border-radius: 50%;
        right: -260px;
        bottom: 20px;
        pointer-events: none;
        z-index: 0;
    }


    /* =====================================================
       MOVING BALLS
    ===================================================== */

    .dot {
        position: fixed;
        width: 8px;
        height: 8px;
        border-radius: 50%;

        background: rgba(255,255,255,0.95);

        box-shadow:
            0 0 8px rgba(255,255,255,0.9),
            0 0 20px rgba(150,130,255,0.75),
            0 0 35px rgba(100,80,255,0.35);

        pointer-events: none;
        z-index: 2;
    }

    .dot1 {
        left: 25%;
        top: 24%;
        animation: floatBall1 6s ease-in-out infinite;
    }

    .dot2 {
        right: 22%;
        top: 31%;
        animation: floatBall2 7s ease-in-out infinite;
    }

    .dot3 {
        left: 48%;
        top: 20%;
        animation: floatBall3 5s ease-in-out infinite;
    }


    @keyframes floatBall1 {

        0% {
            transform: translate(0px, 0px);
        }

        20% {
            transform: translate(35px, -25px);
        }

        40% {
            transform: translate(70px, 15px);
        }

        60% {
            transform: translate(45px, 50px);
        }

        80% {
            transform: translate(-10px, 30px);
        }

        100% {
            transform: translate(0px, 0px);
        }
    }


    @keyframes floatBall2 {

        0% {
            transform: translate(0px, 0px);
        }

        20% {
            transform: translate(-30px, 25px);
        }

        40% {
            transform: translate(-65px, -15px);
        }

        60% {
            transform: translate(-40px, -50px);
        }

        80% {
            transform: translate(15px, -25px);
        }

        100% {
            transform: translate(0px, 0px);
        }
    }


    @keyframes floatBall3 {

        0% {
            transform: translate(0px, 0px);
        }

        20% {
            transform: translate(-20px, -30px);
        }

        40% {
            transform: translate(25px, -45px);
        }

        60% {
            transform: translate(45px, 10px);
        }

        80% {
            transform: translate(15px, 35px);
        }

        100% {
            transform: translate(0px, 0px);
        }
    }


    /* =====================================================
       BUTTON
    ===================================================== */

    div.stButton > button {
        width: 280px !important;
        min-height: 62px !important;

        background: #ffffff !important;
        color: #09090d !important;

        border: none !important;
        border-radius: 50px !important;

        font-size: 17px !important;
        font-weight: 700 !important;

        box-shadow:
            0 0 0 1px rgba(255,255,255,0.15),
            0 15px 45px rgba(255,255,255,0.10) !important;

        transition:
            transform 0.25s ease,
            box-shadow 0.25s ease !important;
    }

    div.stButton > button:hover {
        transform: translateY(-3px) !important;

        box-shadow:
            0 0 0 1px rgba(255,255,255,0.25),
            0 20px 60px rgba(255,255,255,0.18) !important;

        color: #000000 !important;
        background: #ffffff !important;
    }

    div.stButton > button p {
        color: #09090d !important;
        font-weight: 700 !important;
    }


    /* CLICKABLE INVESTIGATION CARDS — dark original look */
    [data-testid="st-key-invest_card_music"] div.stButton > button,
    [data-testid="st-key-invest_card_digital"] div.stButton > button,
    [data-testid="st-key-invest_card_entertainment"] div.stButton > button,
    [class*="st-key-invest_card_music"] div.stButton > button,
    [class*="st-key-invest_card_digital"] div.stButton > button,
    [class*="st-key-invest_card_entertainment"] div.stButton > button {
        width: 100% !important;
        min-height: 205px !important;
        background: rgba(18, 15, 32, 0.72) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.13) !important;
        border-radius: 24px !important;
        box-shadow: 0 15px 45px rgba(0,0,0,0.28) !important;
        white-space: pre-line !important;
    }

    [data-testid="st-key-invest_card_music"] div.stButton > button:hover,
    [data-testid="st-key-invest_card_digital"] div.stButton > button:hover,
    [data-testid="st-key-invest_card_entertainment"] div.stButton > button:hover,
    [class*="st-key-invest_card_music"] div.stButton > button:hover,
    [class*="st-key-invest_card_digital"] div.stButton > button:hover,
    [class*="st-key-invest_card_entertainment"] div.stButton > button:hover {
        background: rgba(30, 25, 50, 0.88) !important;
        color: #ffffff !important;
        border-color: rgba(170,145,255,0.30) !important;
        box-shadow: 0 20px 60px rgba(30,20,70,0.38) !important;
        transform: translateY(-5px) !important;
    }

    [data-testid="st-key-invest_card_music"] div.stButton > button p,
    [data-testid="st-key-invest_card_digital"] div.stButton > button p,
    [data-testid="st-key-invest_card_entertainment"] div.stButton > button p,
    [class*="st-key-invest_card_music"] div.stButton > button p,
    [class*="st-key-invest_card_digital"] div.stButton > button p,
    [class*="st-key-invest_card_entertainment"] div.stButton > button p {
        color: #ffffff !important;
        white-space: pre-line !important;
        line-height: 2.0 !important;
    }

    /* =====================================================
       CATEGORY CARDS
    ===================================================== */

    .category-card {
        background: rgba(255,255,255,0.025);
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 24px;
        padding: 30px 20px;
        text-align: center;
        min-height: 170px;

        transition:
            transform 0.25s ease,
            border-color 0.25s ease,
            background 0.25s ease;
    }

    .category-card:hover {
        transform: translateY(-5px);
        border-color: rgba(255,255,255,0.28);
        background: rgba(255,255,255,0.045);
    }

    .category-icon {
        font-size: 38px;
        margin-bottom: 18px;
    }

    .category-title {
        color: #ffffff;
        font-size: 16px;
        letter-spacing: 3px;
        font-weight: 600;
    }

    .category-desc {
        color: #9d9aa9;
        font-size: 12px;
        margin-top: 10px;
    }


    /* =====================================================
       TEXT INPUT
    ===================================================== */

    div[data-testid="stTextInput"] label {
        display: none !important;
    }

    div[data-testid="stTextInput"] input {
        background: #15151d !important;
        color: #ffffff !important;

        border: 1px solid #3d3b4b !important;
        border-radius: 12px !important;

        height: 60px !important;

        font-size: 17px !important;
        padding-left: 20px !important;

        caret-color: #ffffff !important;
    }

    div[data-testid="stTextInput"] input::placeholder {
        color: #858294 !important;
        opacity: 1 !important;
    }

    div[data-testid="stTextInput"] input:focus {
        border-color: #9a8cff !important;
        box-shadow: 0 0 0 1px #9a8cff !important;
    }


    /* =====================================================
       RADIO BUTTONS
    ===================================================== */

    div[data-testid="stRadio"] label {
        color: #e8e6ee !important;
        font-size: 16px !important;
    }

    div[data-testid="stRadio"] p {
        color: #e8e6ee !important;
    }

    div[data-testid="stRadio"] [data-baseweb="radio"] {
        color: #ffffff !important;
    }

    div[data-testid="stRadio"] > div {
        gap: 12px !important;
    }


    /* =====================================================
       DIGITAL LIFE
    ===================================================== */

    .digital-wrapper {
        max-width: 1100px;
        margin: auto;
    }

    .digital-intro {
        text-align: center;
        color: #a7a4b5;
        font-size: 16px;
        line-height: 1.7;
        margin-top: 22px;
    }

    .clue-number {
        color: #8f86ff;
        font-size: 11px;
        letter-spacing: 5px;
        text-transform: uppercase;
        text-align: center;
        margin-bottom: 15px;
    }

    .clue-question {
        color: #ffffff;
        font-size: 30px;
        font-weight: 750;
        text-align: center;
        line-height: 1.2;
        margin-bottom: 10px;
    }

    .clue-description {
        color: #9693a4;
        text-align: center;
        font-size: 14px;
        margin-bottom: 25px;
    }

    .digital-card {
        background:
            linear-gradient(
                145deg,
                rgba(255,255,255,0.055),
                rgba(255,255,255,0.018)
            );

        border: 1px solid rgba(255,255,255,0.11);
        border-radius: 28px;

        padding: 30px;

        margin-bottom: 28px;

        box-shadow:
            0 20px 60px rgba(0,0,0,0.20);

        transition:
            transform 0.3s ease,
            border-color 0.3s ease;
    }

    .digital-card:hover {
        transform: translateY(-4px);
        border-color: rgba(154,140,255,0.35);
    }


    /* =====================================================
       PHONE ORBIT
    ===================================================== */

    .phone-orbit {
        width: 280px;
        height: 280px;

        border: 1px solid rgba(154,140,255,0.20);
        border-radius: 50%;

        margin: 20px auto;

        position: relative;

        animation: slowRotate 16s linear infinite;
    }

    .phone-orbit::before {
        content: "";

        position: absolute;

        width: 190px;
        height: 190px;

        border: 1px solid rgba(50,190,220,0.20);
        border-radius: 50%;

        top: 45px;
        left: 45px;
    }

    .phone-icon {
        position: absolute;

        top: 50%;
        left: 50%;

        transform: translate(-50%, -50%);

        font-size: 70px;

        animation: phoneFloat 3s ease-in-out infinite;
    }


    @keyframes slowRotate {

        from {
            transform: rotate(0deg);
        }

        to {
            transform: rotate(360deg);
        }
    }


    @keyframes phoneFloat {

        0%, 100% {
            transform: translate(-50%, -50%);
        }

        50% {
            transform: translate(-50%, -58%);
        }
    }


    /* =====================================================
       PROGRESS
    ===================================================== */

    .progress-text {
        text-align: center;
        color: #777487;
        font-size: 11px;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-top: 45px;
    }


    /* =====================================================
       BOTTOM NOTE
    ===================================================== */

    .bottom-note {
        color: #777487;
        font-size: 11px;
        letter-spacing: 5px;
        text-align: center;
        text-transform: uppercase;
        margin-top: 65px;
    }



    /* =====================================================
       MUSIC PAGE — CINEMATIC PLAYER STYLE
    ===================================================== */

    .music-wrapper {
        max-width: 1120px;
        margin: 0 auto;
        position: relative;
        z-index: 3;
    }

    .music-hero {
        text-align: center;
        margin-top: 10px;
        margin-bottom: 42px;
    }

    .music-kicker {
        display: inline-block;
        color: #aaa4c7;
        font-size: 11px;
        letter-spacing: 5px;
        text-transform: uppercase;
        padding: 9px 16px;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 999px;
        background: rgba(255,255,255,0.035);
        box-shadow: 0 10px 35px rgba(0,0,0,0.18);
    }

    .music-title {
        color: #ffffff;
        font-size: clamp(42px, 5.2vw, 72px);
        font-weight: 900;
        line-height: 1.02;
        letter-spacing: -3px;
        text-align: center;
        margin: 25px auto 0;
        max-width: 900px;
    }

    .music-title .soft {
        color: #a9a3ba;
        font-weight: 700;
    }

    .music-subtitle {
        color: #aaa7b7;
        font-size: 16px;
        line-height: 1.7;
        text-align: center;
        max-width: 620px;
        margin: 20px auto 0;
    }

    .music-stage {
        position: relative;
        max-width: 980px;
        margin: 0 auto;
        padding: 38px;
        border-radius: 34px;
        border: 1px solid rgba(255,255,255,0.12);
        background:
            radial-gradient(circle at 50% 5%, rgba(139,112,255,0.16), transparent 38%),
            linear-gradient(145deg, rgba(255,255,255,0.065), rgba(255,255,255,0.018));
        box-shadow:
            0 30px 90px rgba(0,0,0,0.38),
            inset 0 1px 0 rgba(255,255,255,0.05);
        overflow: hidden;
    }

    .music-stage::before {
        content: "";
        position: absolute;
        width: 330px;
        height: 330px;
        left: 50%;
        top: -190px;
        transform: translateX(-50%);
        border-radius: 50%;
        border: 1px solid rgba(154,140,255,0.16);
        box-shadow:
            0 0 80px rgba(125,105,255,0.12),
            0 0 150px rgba(50,190,220,0.05);
        pointer-events: none;
    }

    .music-disc {
        width: 210px;
        height: 210px;
        margin: 0 auto 28px;
        border-radius: 50%;
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        background:
            radial-gradient(circle at 50% 50%, #0a0a0f 0 9%, transparent 10%),
            repeating-radial-gradient(circle at 50% 50%,
                rgba(255,255,255,0.08) 0 1px,
                transparent 1px 8px),
            radial-gradient(circle at 35% 28%, #7c6cff, #25223d 42%, #0b0b10 72%);
        border: 1px solid rgba(255,255,255,0.16);
        box-shadow:
            0 0 0 10px rgba(154,140,255,0.035),
            0 0 0 22px rgba(154,140,255,0.02),
            0 25px 70px rgba(0,0,0,0.45);
        animation: musicSpin 14s linear infinite;
    }

    .music-disc::before {
        content: "";
        position: absolute;
        width: 62px;
        height: 62px;
        border-radius: 50%;
        background: rgba(255,255,255,0.055);
        border: 1px solid rgba(255,255,255,0.13);
        box-shadow: inset 0 0 25px rgba(0,0,0,0.35);
    }

    .music-disc::after {
        content: "♪";
        position: absolute;
        color: #ffffff;
        font-size: 28px;
        font-weight: 800;
        text-shadow: 0 0 18px rgba(255,255,255,0.5);
        animation: musicCounterSpin 14s linear infinite;
    }

    @keyframes musicSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    @keyframes musicCounterSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(-360deg); }
    }

    .music-equalizer {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 5px;
        height: 34px;
        margin: 4px auto 30px;
    }

    .music-equalizer span {
        width: 4px;
        border-radius: 10px;
        background: rgba(255,255,255,0.78);
        box-shadow: 0 0 12px rgba(154,140,255,0.45);
        animation: equalize 1.1s ease-in-out infinite;
    }

    .music-equalizer span:nth-child(1) { height: 12px; animation-delay: .05s; }
    .music-equalizer span:nth-child(2) { height: 24px; animation-delay: .18s; }
    .music-equalizer span:nth-child(3) { height: 17px; animation-delay: .30s; }
    .music-equalizer span:nth-child(4) { height: 29px; animation-delay: .12s; }
    .music-equalizer span:nth-child(5) { height: 20px; animation-delay: .36s; }
    .music-equalizer span:nth-child(6) { height: 13px; animation-delay: .22s; }
    .music-equalizer span:nth-child(7) { height: 25px; animation-delay: .42s; }

    @keyframes equalize {
        0%, 100% { transform: scaleY(.55); opacity: .45; }
        50% { transform: scaleY(1.15); opacity: 1; }
    }

    .music-input-label {
        color: #8f86ff;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        text-align: center;
        margin-bottom: 10px;
    }

    .music-input-help {
        color: #777487;
        font-size: 12px;
        text-align: center;
        margin-top: 10px;
    }

    .music-clue-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-top: 22px;
    }

    .music-clue-card {
        position: relative;
        padding: 27px 25px 25px;
        border-radius: 26px;
        border: 1px solid rgba(255,255,255,0.10);
        background:
            linear-gradient(145deg, rgba(255,255,255,0.052), rgba(255,255,255,0.015));
        box-shadow: 0 20px 60px rgba(0,0,0,0.22);
        transition: transform .3s ease, border-color .3s ease, background .3s ease;
    }

    .music-clue-card:hover {
        transform: translateY(-5px);
        border-color: rgba(154,140,255,0.30);
        background:
            linear-gradient(145deg, rgba(154,140,255,0.075), rgba(255,255,255,0.018));
    }

    .music-clue-number {
        color: #8f86ff;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-bottom: 12px;
    }

    .music-clue-title {
        color: #ffffff;
        font-size: 22px;
        font-weight: 760;
        line-height: 1.2;
        margin-bottom: 8px;
    }

    .music-clue-copy {
        color: #9996a6;
        font-size: 13px;
        line-height: 1.55;
        margin-bottom: 18px;
    }

    .music-card-icon {
        float: right;
        font-size: 27px;
        opacity: .88;
    }

    .music-progress-shell {
        max-width: 980px;
        margin: 30px auto 0;
        padding: 18px 22px;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        background: rgba(255,255,255,0.025);
    }

    .music-progress-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        color: #858194;
        font-size: 10px;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .music-progress-track {
        height: 4px;
        width: 100%;
        border-radius: 22px;
        background: rgba(255,255,255,0.07);
        overflow: hidden;
    }

    .music-progress-fill {
        width: 33%;
        height: 100%;
        border-radius: 20px;
        background: linear-gradient(90deg, #7468ff, #a89fff, #55cde0);
        box-shadow: 0 0 15px rgba(126,109,255,0.5);
    }

    /* Keep radio choices attractive and readable on Music page */
    .music-options div[data-testid="stRadio"] > div {
        gap: 9px !important;
    }

    .music-options div[data-testid="stRadio"] label {
        background: rgba(255,255,255,0.035) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 14px !important;
        padding: 11px 14px !important;
        transition: all .22s ease !important;
    }

    .music-options div[data-testid="stRadio"] label:hover {
        background: rgba(154,140,255,0.08) !important;
        border-color: rgba(154,140,255,0.28) !important;
        transform: translateY(-2px);
    }

    /* =====================================================
       MUSIC QUESTION + ANSWER LAYOUT
    ===================================================== */

    .music-question-grid {
        max-width: 980px;
        margin: 34px auto 0;
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
    }

    .music-question-panel { min-width: 0; }

    .music-answer-label {
        color: #8f86ff;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin: 13px 0 8px 4px;
    }

    .music-answer-help {
        color: #777487;
        font-size: 12px;
        line-height: 1.5;
        margin: 0 4px 10px;
    }

    .music-question-panel .music-clue-card {
        min-height: 185px;
        margin: 0;
    }

    .music-question-panel div[data-testid="stTextInput"] input {
        height: 56px !important;
    }

    .music-question-panel div[data-testid="stRadio"] > div {
        display: grid !important;
        grid-template-columns: 1fr 1fr;
        gap: 8px !important;
    }

    .music-question-panel div[data-testid="stRadio"] label {
        margin: 0 !important;
        min-height: 48px !important;
        display: flex !important;
        align-items: center !important;
        box-sizing: border-box !important;
    }

    .music-art-stage {
        position: relative;
        width: min(980px, calc(100vw - 48px));
        max-width: 980px;
        margin: 0 auto;
        padding: 16px;
        border-radius: 34px;
        border: 1px solid rgba(255,255,255,0.12);
        background: linear-gradient(145deg, rgba(255,255,255,0.06), rgba(255,255,255,0.015));
        box-shadow: 0 30px 90px rgba(0,0,0,0.38), inset 0 1px 0 rgba(255,255,255,0.05);
        overflow: hidden;
    }

    .music-art-stage::before {
        content: "";
        position: absolute;
        width: 360px;
        height: 360px;
        left: 50%;
        top: -230px;
        transform: translateX(-50%);
        border-radius: 50%;
        border: 1px solid rgba(154,140,255,0.15);
        box-shadow: 0 0 100px rgba(125,105,255,0.12);
        pointer-events: none;
    }

    .music-art-image {
        display: block !important;
        width: 100% !important;
        max-width: none !important;
        height: 360px !important;
        object-fit: cover;
        object-position: center;
        border-radius: 24px;
        border: 1px solid rgba(255,255,255,0.12);
        position: relative;
        z-index: 1;
        box-shadow: 0 20px 55px rgba(0,0,0,0.35);
    }

    .music-art-caption {
        position: relative;
        z-index: 2;
        text-align: center;
        color: #8f86ff;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-top: 18px;
    }

    .music-art-fallback {
        height: 310px;
        border-radius: 24px;
        border: 1px dashed rgba(154,140,255,0.28);
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        color: #9996a6;
        padding: 30px;
        box-sizing: border-box;
        background: radial-gradient(circle at center, rgba(124,108,255,0.14), rgba(255,255,255,0.02));
    }

    .music-art-fallback strong { color: #ffffff; }

    @media (max-width: 768px) {
        .music-stage {
            padding: 25px 16px;
            border-radius: 26px;
        }

        .music-disc {
            width: 165px;
            height: 165px;
        }

        .music-clue-grid {
            grid-template-columns: 1fr;
        }

        .music-title {
            letter-spacing: -2px;
        }
    }


    /* =====================================================
       ENTERTAINMENT PAGE — CINEMATIC STYLE
    ===================================================== */

    .ent-wrapper {
        max-width: 1120px;
        margin: 0 auto;
        position: relative;
        z-index: 2;
    }

    .ent-hero {
        text-align: center;
        padding-top: 58px;
        margin-bottom: 38px;
    }

    .ent-kicker {
        display: inline-block;
        color: #a7a0c8;
        font-size: 11px;
        letter-spacing: 5px;
        text-transform: uppercase;
        padding: 9px 16px;
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 999px;
        background: rgba(255,255,255,0.035);
    }

    .ent-title {
        color: #ffffff;
        font-size: clamp(42px, 5.8vw, 78px);
        font-weight: 900;
        line-height: .98;
        letter-spacing: -3px;
        margin: 24px auto 0;
        max-width: 920px;
    }

    .ent-title .soft {
        color: #aaa4bd;
    }

    .ent-subtitle {
        color: #a7a4b3;
        font-size: 16px;
        line-height: 1.7;
        max-width: 650px;
        margin: 20px auto 0;
    }

    .entertainment-feature {
        width: 100%;
        max-width: 1180px;
        margin: 35px auto 42px auto;
        padding: 18px;
        display: grid;
        grid-template-columns: 1.25fr 0.9fr;
        gap: 0;
        background:
            radial-gradient(circle at 20% 20%, rgba(120, 85, 255, 0.13), transparent 40%),
            linear-gradient(135deg, rgba(30, 24, 55, 0.72), rgba(8, 18, 27, 0.82));
        border: 1px solid rgba(180, 170, 255, 0.18);
        border-radius: 28px;
        box-shadow: 0 0 45px rgba(90, 70, 255, 0.08), inset 0 0 30px rgba(255,255,255,0.02);
        overflow: hidden;
    }

    .entertainment-image-wrap {
        min-height: 390px;
        display: flex;
        align-items: stretch;
        justify-content: center;
        overflow: hidden;
        border-radius: 21px 0 0 21px;
        background: #11111d;
        position: relative;
    }

    .entertainment-image {
        width: 100%;
        height: 100%;
        min-height: 390px;
        object-fit: cover;
        object-position: center;
        display: block;
        transition: transform .5s ease, filter .5s ease;
    }

    .entertainment-image-wrap:hover .entertainment-image {
        transform: scale(1.025);
        filter: brightness(1.04) saturate(1.03);
    }

    .entertainment-image-wrap::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, rgba(8,7,18,.02), rgba(8,7,18,.12));
        pointer-events: none;
    }

    .entertainment-question {
        padding: 38px 38px 30px 38px;
        display: flex;
        flex-direction: column;
        justify-content: center;
        background: linear-gradient(145deg, rgba(20, 20, 38, 0.72), rgba(8, 15, 24, 0.78));
        border-left: 1px solid rgba(180,170,255,0.12);
    }

    .entertainment-kicker {
        color: #9b8cff;
        font-size: 11px;
        letter-spacing: 4px;
        text-transform: uppercase;
        font-weight: 700;
        margin-bottom: 17px;
    }

    .entertainment-question h2 {
        margin: 0 0 10px 0;
        font-size: 28px;
        line-height: 1.15;
        color: #ffffff;
        font-weight: 800;
    }

    .entertainment-question p {
        margin: 0 0 25px 0;
        color: rgba(220,220,235,0.68);
        font-size: 14px;
        line-height: 1.6;
    }

    .ent-option {
        width: 100%;
        box-sizing: border-box;
        padding: 12px 16px;
        margin: 7px 0;
        border-radius: 13px;
        border: 1px solid rgba(150,150,190,0.16);
        background: linear-gradient(90deg, rgba(80,75,130,0.13), rgba(20,30,45,0.20));
        color: #f3f2fa;
        font-size: 14px;
        transition: border-color .25s ease, background .25s ease, transform .25s ease;
    }

    .ent-option:hover {
        border-color: rgba(150,130,255,0.55);
        background: linear-gradient(90deg, rgba(100,85,200,0.22), rgba(30,50,70,0.25));
        transform: translateX(4px);
    }

    .ent-question-count {
        text-align: right;
        margin-top: 16px;
        color: rgba(220,220,240,0.55);
        font-size: 12px;
        letter-spacing: 1px;
    }

    .ent-clue-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 20px;
        margin-top: 25px;
    }

    .ent-card {
        padding: 27px 25px;
        min-height: 205px;
        border-radius: 26px;
        border: 1px solid rgba(255,255,255,.10);
        background: linear-gradient(145deg, rgba(255,255,255,.052), rgba(255,255,255,.014));
        box-shadow: 0 20px 60px rgba(0,0,0,.22);
        transition: transform .3s ease, border-color .3s ease;
    }

    .ent-card:hover {
        transform: translateY(-5px);
        border-color: rgba(154,140,255,.30);
    }

    .ent-number {
        color: #8f86ff;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        margin-bottom: 13px;
    }

    .ent-card-title {
        color: #fff;
        font-size: 23px;
        font-weight: 780;
        line-height: 1.2;
        margin-bottom: 9px;
    }

    .ent-card-copy {
        color: #9996a6;
        font-size: 13px;
        line-height: 1.55;
        margin-bottom: 20px;
    }

    .ent-icon {
        float: right;
        font-size: 27px;
    }

    .ent-wide-card {
        margin-top: 20px;
        padding: 27px 25px;
        border-radius: 26px;
        border: 1px solid rgba(255,255,255,.10);
        background: linear-gradient(145deg, rgba(255,255,255,.052), rgba(255,255,255,.014));
        box-shadow: 0 20px 60px rgba(0,0,0,.22);
    }

    .ent-progress {
        max-width: 980px;
        margin: 30px auto 0;
        padding: 18px 22px;
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 18px;
        background: rgba(255,255,255,.025);
    }

    .ent-progress-top {
        display: flex;
        justify-content: space-between;
        color: #858194;
        font-size: 10px;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin-bottom: 10px;
    }

    .ent-track {
        height: 4px;
        border-radius: 20px;
        background: rgba(255,255,255,.07);
        overflow: hidden;
    }

    .ent-fill {
        width: 66%;
        height: 100%;
        border-radius: 20px;
        background: linear-gradient(90deg, #7468ff, #a89fff, #55cde0);
        box-shadow: 0 0 15px rgba(126,109,255,.5);
    }

    .ent-fill-full {
        width: 100%;
    }

    @media (max-width: 850px) {
        .entertainment-feature {
            grid-template-columns: 1fr;
        }

        .entertainment-image-wrap {
            min-height: 285px;
            border-radius: 21px 21px 0 0;
        }

        .entertainment-image {
            min-height: 285px;
        }

        .entertainment-question {
            border-left: none;
            border-top: 1px solid rgba(180,170,255,0.12);
            padding: 30px 25px;
        }
    }


    /* =====================================================
       ENTERTAINMENT ANSWER GUIDANCE
    ===================================================== */

    .answer-label {
        color: #8f86ff;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        font-weight: 700;
        margin: 18px 0 7px;
    }

    .answer-hint {
        color: #777487;
        font-size: 12px;
        line-height: 1.5;
        margin: 0 0 9px;
    }

    .answer-zone {
        max-width: 1120px;
        margin: 0 auto;
    }

    .answer-divider {
        height: 1px;
        background: rgba(255,255,255,0.06);
        margin: 18px 0 4px;
    }

    /* =====================================================
       MOBILE
    ===================================================== */

    @media (max-width: 768px) {

        /* FINAL REVEAL — MOBILE */
        .reveal-intro {
            padding: 70px 18px 25px !important;
        }

        .reveal-intro-title {
            font-size: 42px !important;
            letter-spacing: -2px !important;
            line-height: 1.02 !important;
        }

        .reveal-intro-copy {
            font-size: 13px !important;
            line-height: 1.6 !important;
        }

        .reveal-personality-wrap {
            padding: 0 12px !important;
        }

        .reveal-personality-card {
            padding: 36px 22px !important;
            border-radius: 24px !important;
        }

        .reveal-personality-name {
            font-size: 32px !important;
            line-height: 1.05 !important;
            letter-spacing: -1.5px !important;
        }

        .reveal-personality-tag {
            font-size: 13px !important;
            line-height: 1.6 !important;
        }

        .reveal-section {
            padding-left: 14px !important;
            padding-right: 14px !important;
        }

        .reveal-section-title {
            font-size: 32px !important;
            letter-spacing: -1.5px !important;
            line-height: 1.08 !important;
        }

        .reveal-storybook {
            padding: 0 12px !important;
        }


        .reveal-story-card {
            padding: 34px 22px 30px !important;
            border-radius: 24px !important;
        }

        .story-greeting {
            font-size: 9px !important;
            letter-spacing: 3px !important;
        }

        .story-paragraph {
            font-size: 15px !important;
            line-height: 1.8 !important;
            margin-bottom: 19px !important;
        }

        .story-ending {
            font-size: 14px !important;
            line-height: 1.75 !important;
            margin-top: 24px !important;
            padding-top: 22px !important;
        }

        .story-signoff {
            font-size: 8px !important;
            letter-spacing: 2.5px !important;
        }

        .reveal-final {
            margin: 80px 12px 25px !important;
            padding: 60px 20px !important;
            border-radius: 26px !important;
        }

        .reveal-final-title {
            font-size: 36px !important;
            letter-spacing: -2px !important;
        }

        .reveal-final-copy {
            font-size: 12px !important;
            line-height: 1.65 !important;
        }

        .reveal-orbit-one {
            width: 300px !important;
            height: 300px !important;
            right: -190px !important;
        }

        .reveal-orbit-two {
            width: 240px !important;
            height: 240px !important;
            left: -170px !important;
        }

        .reveal-star {
            font-size: 14px !important;
        }

        .hero-title {
            font-size: 48px;
            letter-spacing: -2px;
        }

        .hero-subtitle {
            font-size: 18px;
        }

        .question {
            font-size: 38px;
        }

        .orb-left,
        .orb-right {
            opacity: 0.5;
        }

        .dot {
            width: 6px;
            height: 6px;
        }

        .digital-card {
            padding: 22px 15px;
        }

        .clue-question {
            font-size: 25px;
        }

        .phone-orbit {
            width: 220px;
            height: 220px;
        }

        .phone-orbit::before {
            width: 150px;
            height: 150px;
            top: 35px;
            left: 35px;
        }
    }


    /* =====================================================
       FINAL PERSONALITY REVEAL
    ===================================================== */

    .reveal-orbit {
        position: fixed;
        border: 1px solid rgba(143,134,255,0.14);
        border-radius: 50%;
        pointer-events: none;
        z-index: 0;
        animation: revealSpin 18s linear infinite;
    }

    .reveal-orbit-one {
        width: 560px;
        height: 560px;
        right: -270px;
        top: 20%;
    }

    .reveal-orbit-two {
        width: 390px;
        height: 390px;
        left: -220px;
        bottom: 8%;
        animation-direction: reverse;
        animation-duration: 24s;
    }

    .reveal-star {
        position: fixed;
        color: #a99dff;
        opacity: .45;
        pointer-events: none;
        z-index: 0;
        animation: revealFloat 4s ease-in-out infinite;
    }

    .reveal-star-one { right: 12%; top: 24%; font-size: 22px; }
    .reveal-star-two { left: 10%; top: 58%; font-size: 14px; animation-delay: 1s; }
    .reveal-star-three { right: 20%; bottom: 18%; font-size: 34px; animation-delay: 2s; }

    .reveal-intro,
    .reveal-personality-wrap,
    .reveal-section,
    .reveal-pattern-grid,
    .reveal-story-card,
    .reveal-final,
    .reveal-explore-note {
        position: relative;
        z-index: 1;
    }

    .reveal-intro {
        text-align: center;
        padding: 72px 20px 20px;
    }

    .reveal-overline,
    .reveal-card-label,
    .reveal-section-kicker,
    .reveal-final-small {
        color: #9289ff;
        font-size: 10px;
        letter-spacing: 5px;
        font-weight: 800;
        text-transform: uppercase;
    }

    .reveal-intro-title {
        margin-top: 20px;
        color: #fff;
        font-size: clamp(48px, 7vw, 92px);
        line-height: .96;
        font-weight: 900;
        letter-spacing: -4px;
    }

    .reveal-intro-title span,
    .reveal-section-title span,
    .reveal-final-title span {
        color: #aaa1ff;
    }

    .reveal-intro-copy {
        color: #a9a5b9;
        font-size: 16px;
        line-height: 1.7;
        margin-top: 28px;
    }

    .reveal-personality-wrap {
        max-width: 1080px;
        margin: 0 auto;
        padding: 0 18px;
    }

    .reveal-personality-card {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(174,163,255,.28);
        border-radius: 34px;
        padding: 72px 55px 42px;
        text-align: center;
        background:
            radial-gradient(circle at 50% 20%, rgba(124,92,255,.25), transparent 38%),
            linear-gradient(145deg, rgba(30,24,57,.94), rgba(10,10,18,.96));
        box-shadow: 0 35px 100px rgba(70,40,160,.25), inset 0 1px rgba(255,255,255,.08);
    }

    .reveal-card-glow {
        position: absolute;
        width: 340px;
        height: 340px;
        border-radius: 50%;
        background: rgba(126,103,255,.18);
        filter: blur(70px);
        left: 50%;
        top: -180px;
        transform: translateX(-50%);
        pointer-events: none;
    }

    .reveal-personality-name {
        position: relative;
        margin-top: 22px;
        color: #fff;
        font-size: clamp(38px, 6vw, 72px);
        line-height: 1;
        font-weight: 950;
        letter-spacing: -3px;
        text-shadow: 0 0 45px rgba(153,137,255,.25);
    }

    .reveal-personality-tag {
        position: relative;
        color: #c7c2d7;
        font-size: 17px;
        line-height: 1.6;
        margin: 24px auto 0;
        max-width: 680px;
    }

    .reveal-divider {
        height: 1px;
        background: rgba(255,255,255,.10);
        margin: 42px 0 20px;
    }

    .reveal-card-foot {
        display: flex;
        justify-content: center;
        gap: 40px;
        color: #6f6a7f;
        font-size: 9px;
        letter-spacing: 4px;
        font-weight: 800;
    }

    .reveal-section {
        max-width: 1080px;
        margin: 105px auto 28px;
        padding: 0 18px;
    }

    .reveal-section-title {
        color: #fff;
        font-size: clamp(32px, 4vw, 54px);
        line-height: 1.03;
        font-weight: 850;
        letter-spacing: -2px;
        margin-top: 15px;
    }

    .reveal-pattern-grid {
        max-width: 1080px;
        margin: 0 auto;
        padding: 0 18px;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 16px;
    }

    .reveal-pattern-card {
        min-height: 245px;
        padding: 28px;
        border: 1px solid rgba(255,255,255,.08);
        border-radius: 24px;
        background: rgba(255,255,255,.025);
        box-shadow: inset 0 1px rgba(255,255,255,.04);
    }

    .reveal-pattern-icon { font-size: 25px; margin-bottom: 28px; }
    .reveal-pattern-label { color:#777187; font-size:9px; letter-spacing:4px; font-weight:800; }
    .reveal-pattern-value { color:#fff; font-size:21px; font-weight:800; line-height:1.2; margin-top:11px; }
    .reveal-pattern-copy { color:#858093; font-size:12px; line-height:1.65; margin-top:14px; }

    .reveal-story-heading { margin-top: 105px; }

    .reveal-storybook {
        max-width: 980px;
        margin: 0 auto;
        padding: 0 18px;
    }

    .reveal-personality-panda-wrap {
        position: relative;
        display: flex;
        justify-content: center;
        align-items: center;
        margin: -6px auto 12px;
        min-height: 150px;
        pointer-events: none;
    }

    .reveal-personality-panda {
        display: block;
        width: min(190px, 48vw);
        height: 165px;
        object-fit: contain;
        object-position: center;
        filter: drop-shadow(0 16px 28px rgba(0,0,0,.24));
        transform-origin: 50% 85%;
        animation: personalityPandaFloat 3.4s ease-in-out infinite;
    }

    .reveal-personality-panda-wrap::before {
        content: '✦';
        position: absolute;
        color: #b7afff;
        font-size: 14px;
        opacity: .45;
        transform: translate(-92px, -35px);
        animation: personalityPandaSparkleLeft 2.8s ease-in-out infinite;
    }

    .reveal-personality-panda-wrap::after {
        content: '✦';
        position: absolute;
        color: #a79cff;
        font-size: 18px;
        opacity: .65;
        transform: translate(82px, -62px);
        animation: personalityPandaSparkle 2.4s ease-in-out infinite;
    }

    @keyframes personalityPandaFloat {
        0%, 100% { transform: translateY(0) rotate(-1deg) scale(1); }
        50% { transform: translateY(-10px) rotate(1.2deg) scale(1.025); }
    }

    @keyframes personalityPandaSparkle {
        0%, 100% { opacity: .30; transform: translate(82px, -62px) scale(.82); }
        50% { opacity: 1; transform: translate(82px, -69px) scale(1.18); }
    }

    @keyframes personalityPandaSparkleLeft {
        0%, 100% { opacity: .20; transform: translate(-92px, -35px) scale(.75); }
        50% { opacity: .85; transform: translate(-92px, -42px) scale(1.10); }
    }

    .reveal-story-card {
        position: relative;
        overflow: hidden;
        padding: 58px 64px 54px;
        border: 1px solid rgba(174,163,255,.18);
        border-radius: 30px;
        background:
            radial-gradient(circle at 12% 10%, rgba(150,132,255,.14), transparent 30%),
            radial-gradient(circle at 90% 90%, rgba(54,176,190,.08), transparent 30%),
            rgba(18,16,29,.78);
        box-shadow: 0 30px 90px rgba(35,20,85,.18), inset 0 1px rgba(255,255,255,.055);
    }

    .reveal-story-card::before {
        content: '✦';
        position: absolute;
        right: 32px;
        top: 25px;
        color: #8e83ff;
        opacity: .65;
        font-size: 18px;
        animation: revealFloat 4s ease-in-out infinite;
    }

    .story-greeting {
        color: #9d94ff;
        font-size: 10px;
        letter-spacing: 4px;
        font-weight: 800;
        text-transform: uppercase;
        margin-bottom: 24px;
    }

    .story-paragraph {
        color: #d8d4e2;
        font-size: 17px;
        line-height: 1.82;
        margin: 0 0 20px;
    }

    .story-paragraph strong {
        color: #fff;
        font-weight: 800;
    }

    .story-highlight {
        color: #b2a9ff;
        font-weight: 800;
    }

    .story-divider {
        width: 76px;
        height: 1px;
        background: linear-gradient(90deg, rgba(157,148,255,.8), transparent);
        margin: 34px 0;
    }

    .story-ending {
        margin-top: 34px;
        padding-top: 28px;
        border-top: 1px solid rgba(255,255,255,.07);
        color: #aaa4ba;
        font-size: 16px;
        line-height: 1.85;
        font-style: italic;
    }

    .story-signoff {
        margin-top: 28px;
        color: #817a91;
        font-size: 10px;
        letter-spacing: 4px;
        text-transform: uppercase;
        font-weight: 800;
    }

    .reveal-final {
        max-width: 1000px;
        margin: 120px auto 30px;
        padding: 90px 30px;
        text-align: center;
        border-radius: 34px;
        background: radial-gradient(circle at 50% 40%, rgba(104,78,220,.18), transparent 55%);
    }

    .reveal-final-mark { color:#a79cff; font-size:32px; animation: revealPulse 2.4s ease-in-out infinite; }
    .reveal-final-small { margin-top: 20px; }
    .reveal-final-title { color:#fff; font-size:clamp(34px,5vw,64px); line-height:1.02; font-weight:900; letter-spacing:-3px; margin-top:18px; }
    .reveal-final-personality { color:#aaa1ff; font-size:13px; letter-spacing:4px; font-weight:900; margin-top:30px; }
    .reveal-final-copy { color:#858091; font-size:14px; margin-top:18px; }

    .reveal-explore-note {
        max-width: 700px;
        margin: 0 auto;
        padding: 18px 24px;
        text-align: center;
        border: 1px solid rgba(146,137,255,.15);
        border-radius: 18px;
        color: #807a8e;
        font-size: 12px;
        line-height: 1.6;
        background: rgba(255,255,255,.02);
    }

    .reveal-explore-note span { color:#a79cff; margin-right:7px; }

    @keyframes revealSpin { from { transform:rotate(0deg); } to { transform:rotate(360deg); } }
    @keyframes revealFloat { 0%,100% { transform:translateY(0); } 50% { transform:translateY(-12px); } }
    @keyframes revealPulse { 0%,100% { opacity:.55; transform:scale(1); } 50% { opacity:1; transform:scale(1.12); } }

    @media (max-width: 850px) {
        .reveal-pattern-grid { grid-template-columns: 1fr; }
        .reveal-personality-card { padding:55px 25px 34px; }
        .reveal-personality-name { letter-spacing:-2px; }
        .reveal-personality-panda { width: 165px; height: 145px; }
        .reveal-personality-panda-wrap::before { transform: translate(-70px, -48px); }
        .reveal-personality-panda-wrap::after { transform: translate(70px, -55px); }
        .reveal-story-card { padding: 8px 18px; }
        .reveal-section { margin-top:75px; }
    }


    /* =====================================================
       FINAL ALIGNMENT / SPACING PASS — V2
    ===================================================== */

    /* Investigation: keep the three chapter buttons visually close. */
    [class*="st-key-investigation_cards"] {
        width: min(1040px, calc(100vw - 48px)) !important;
        max-width: 1040px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    [class*="st-key-investigation_cards"] [data-testid="stHorizontalBlock"] {
        gap: 0px !important;
    }

    [class*="st-key-investigation_cards"] [data-testid="column"] {
        padding-left: 0px !important;
        padding-right: 0px !important;
    }

    [class*="st-key-invest_card_music"],
    [class*="st-key-invest_card_digital"],
    [class*="st-key-invest_card_entertainment"] {
        width: 100% !important;
    }

    [class*="st-key-invest_card_music"] div.stButton > button,
    [class*="st-key-invest_card_digital"] div.stButton > button,
    [class*="st-key-invest_card_entertainment"] div.stButton > button {
        width: 100% !important;
    }

    /* One vertical 980px alignment rail for every question + answer. */
    [class*="st-key-music_song_answer"],
    [class*="st-key-music_memory_answer"],
    [class*="st-key-music_moment_answer"],
    [class*="st-key-digital_app_answer"],
    [class*="st-key-digital_screen_answer"],
    [class*="st-key-digital_phone_answer"],
    [class*="st-key-ent_movie_answer"],
    [class*="st-key-ent_world_answer"],
    [class*="st-key-ent_viewer_answer"] {
        width: min(980px, calc(100vw - 48px)) !important;
        max-width: 980px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    [class*="st-key-music_song_answer"] div[data-testid="stRadio"],
    [class*="st-key-music_memory_answer"] div[data-testid="stRadio"],
    [class*="st-key-music_moment_answer"] div[data-testid="stRadio"],
    [class*="st-key-digital_app_answer"] div[data-testid="stRadio"],
    [class*="st-key-digital_screen_answer"] div[data-testid="stRadio"],
    [class*="st-key-digital_phone_answer"] div[data-testid="stRadio"],
    [class*="st-key-ent_movie_answer"] div[data-testid="stRadio"],
    [class*="st-key-ent_world_answer"] div[data-testid="stRadio"],
    [class*="st-key-ent_viewer_answer"] div[data-testid="stRadio"] {
        width: 100% !important;
        max-width: none !important;
        margin: 0 !important;
    }

    /* Compact radio rows: little horizontal padding, no huge row width feeling. */
    [class*="st-key-music_song_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-music_moment_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-digital_app_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-digital_screen_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-digital_phone_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-ent_movie_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-ent_world_answer"] div[data-testid="stRadio"] > div,
    [class*="st-key-ent_viewer_answer"] div[data-testid="stRadio"] > div {
        gap: 2px !important;
        width: 100% !important;
    }

    [class*="st-key-music_song_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-music_moment_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-digital_app_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-digital_screen_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-digital_phone_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-ent_movie_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-ent_world_answer"] div[data-testid="stRadio"] label,
    [class*="st-key-ent_viewer_answer"] div[data-testid="stRadio"] label {
        margin: 0 !important;
        padding: 4px 0 !important;
        min-height: 32px !important;
    }

    /* Keep every answer input exactly on the same left/right rail as its question. */
    [class*="st-key-music_song_answer"] div[data-testid="stTextInput"],
    [class*="st-key-music_memory_answer"] div[data-testid="stTextInput"],
    [class*="st-key-digital_app_answer"] div[data-testid="stTextInput"],
    [class*="st-key-digital_screen_answer"] div[data-testid="stTextInput"],
    [class*="st-key-digital_phone_answer"] div[data-testid="stTextInput"],
    [class*="st-key-ent_movie_answer"] div[data-testid="stTextInput"],
    [class*="st-key-ent_world_answer"] div[data-testid="stTextInput"],
    [class*="st-key-ent_viewer_answer"] div[data-testid="stTextInput"] {
        width: 100% !important;
        max-width: none !important;
        margin: 10px 0 0 !important;
    }

    /* The Back to Chapters control stays at the bottom of each chapter. */
    [data-testid="st-key-music_back"],
    [data-testid="st-key-digital_back"],
    [data-testid="st-key-entertainment_back"] {
        margin-top: 12px !important;
    }


    .chapter-content {
        width: min(980px, calc(100vw - 48px));
        margin: 0 auto;
    }

    .answer-wrap {
        width: min(980px, calc(100vw - 48px));
        margin: 0 auto;
    }

    /* Keep radio options compact and on the same left edge as inputs. */
    .answer-wrap div[data-testid="stRadio"],
    .chapter-content div[data-testid="stRadio"] {
        width: 100% !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    .answer-wrap div[data-testid="stRadio"] > div,
    .chapter-content div[data-testid="stRadio"] > div {
        gap: 3px !important;
        width: 100% !important;
    }

    .answer-wrap div[data-testid="stRadio"] label,
    .chapter-content div[data-testid="stRadio"] label {
        margin: 0 !important;
        padding: 5px 0 !important;
        min-height: 34px !important;
        line-height: 1.25 !important;
    }

    .answer-wrap div[data-testid="stRadio"] label > div:first-child,
    .chapter-content div[data-testid="stRadio"] label > div:first-child {
        margin-right: 8px !important;
    }

    /* Streamlit's element wrapper must not add a mysterious left/right offset. */
    .answer-wrap [data-testid="stVerticalBlock"],
    .chapter-content [data-testid="stVerticalBlock"] {
        width: 100%;
    }

    .question-answer-block {
        width: min(980px, calc(100vw - 48px));
        margin: 0 auto;
    }

    /* Every answer widget uses the exact same 980px alignment rail. */
    div[data-testid="stTextInput"],
    div[data-testid="stRadio"] {
        width: min(980px, calc(100vw - 48px)) !important;
        max-width: 980px !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }

    div[data-testid="stRadio"] > div {
        gap: 3px !important;
    }

    div[data-testid="stRadio"] label {
        margin: 0 !important;
        padding: 5px 0 !important;
        min-height: 34px !important;
    }

    .question-answer-block .music-answer-label,
    .question-answer-block .answer-label {
        margin-left: 0 !important;
    }

    .question-answer-block .music-answer-help,
    .question-answer-block .answer-hint {
        margin-left: 0 !important;
    }

    .question-answer-block div[data-testid="stTextInput"] {
        width: 100% !important;
    }

    .question-answer-block div[data-testid="stTextInput"] input {
        width: 100% !important;
        box-sizing: border-box !important;
    }

    /* Investigation chapter cards sit closer together horizontally. */
    [data-testid="stHorizontalBlock"]:has([data-testid="st-key-invest_card_music"]) {
        gap: 0px !important;
    }

    /* Entertainment: give the artwork the room; question lives BELOW it. */
    .entertainment-feature {
        grid-template-columns: 1fr !important;
        padding: 18px !important;
        max-width: 980px !important;
    }

    .entertainment-image-wrap {
        min-height: 500px !important;
        height: 500px !important;
        border-radius: 22px !important;
    }

    .entertainment-image {
        min-height: 500px !important;
        height: 500px !important;
        object-fit: cover !important;
    }

    .entertainment-question {
        border-left: none !important;
        border-top: 1px solid rgba(180,170,255,0.12) !important;
        padding: 28px 8px 8px !important;
        background: transparent !important;
    }

    .entertainment-question .ent-option,
    .entertainment-question .ent-question-count {
        display: none !important;
    }

    .entertainment-question h2 { margin-bottom: 8px !important; }
    .entertainment-question p { margin-bottom: 0 !important; }

    .ent-sequence-card {
        width: min(980px, calc(100vw - 48px));
        margin: 28px auto 0;
    }

    .ent-sequence-card .ent-card {
        min-height: 0 !important;
    }

    @media (max-width: 850px) {
        .chapter-content,
        .answer-wrap,
        .question-answer-block,
        .ent-sequence-card {
            width: min(100% - 28px, 980px) !important;
        }
        .entertainment-image-wrap,
        .entertainment-image {
            min-height: 300px !important;
            height: 300px !important;
        }
    }

    </style>
    """,
    unsafe_allow_html=True
)


# =========================================================
# LANDING PAGE
# =========================================================


# =========================================================
# PRIVATE ADMIN ROUTE
# =========================================================
# Open the app URL with: ?admin=1
if st.query_params.get("admin") == "1":
    render_admin_dashboard()
    st.stop()

if st.session_state.page == "landing":

    st.markdown(
        """
<div class="orb-left"></div>
<div class="orb-right"></div>

<div class="dot dot1"></div>
<div class="dot dot2"></div>
<div class="dot dot3"></div>
        """,
        unsafe_allow_html=True
    )

    st.markdown(
        """
<div style="height:90px;"></div>

<div class="eyebrow">
YOUR YEAR. YOUR PATTERNS. YOUR STORY.
</div>

<div class="hero-title">
YOUR 2026<br>
DATA PERSONALITY
</div>

<div class="hero-subtitle">
You think you know yourself.<br>
Your data knows you better.
</div>

<div class="hero-small">
Your everyday choices leave clues. Let's find them.
</div>

<div class="page-label">
START THE INVESTIGATION
</div>
        """,
        unsafe_allow_html=True
    )

    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:

        if st.button(
            "Discover My 2026 →",
            key="discover"
        ):

            st.session_state.page = "investigation"
            st.rerun()

    st.markdown(
        """
<div class="bottom-note">
MUSIC &nbsp; • &nbsp; DIGITAL LIFE &nbsp; • &nbsp; ENTERTAINMENT
</div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# INVESTIGATION INTRO
# =========================================================

elif st.session_state.page == "investigation":

    st.markdown(
        """
<div style="height:70px;"></div>
<div class="eyebrow">THE INVESTIGATION BEGINS</div>
<div class="question">LET'S FIND<br>YOUR CLUES.</div>
<div class="hero-subtitle">You don't need to tell us everything.<br>Just give us a few pieces of your 2026.</div>
        """, unsafe_allow_html=True
    )

    st.markdown("<div style='height:38px;'></div>", unsafe_allow_html=True)

    with st.container(key="investigation_cards"):
        c1, c2, c3 = st.columns(3, gap=None)
        with c1:
            with st.container(key="invest_card_music"):
                if st.button("🎧\nMUSIC\nsongs • artists • memories", key="invest_music_card"):
                    st.session_state.page = "music"
                    st.rerun()
        with c2:
            with st.container(key="invest_card_digital"):
                if st.button("📱\nDIGITAL LIFE\napps • phone • routines", key="invest_digital_card"):
                    st.session_state.page = "digital"
                    st.rerun()
        with c3:
            with st.container(key="invest_card_entertainment"):
                if st.button("🎬\nENTERTAINMENT\nmovies • shows • moods", key="invest_entertainment_card"):
                    st.session_state.page = "entertainment"
                    st.rerun()

    st.markdown(
        """
<div class="bottom-note" style="margin-top:45px;">CHOOSE ANY CHAPTER · YOU CAN COME BACK ANYTIME</div>
<div class="section-nav-note" style="text-align:center;margin-top:18px;">NO ORDER · NO REQUIRED ANSWERS · FOLLOW WHATEVER FEELS INTERESTING.</div>
        """,
        unsafe_allow_html=True
    )


# =========================================================
# MUSIC PAGE
# =========================================================

elif st.session_state.page == "music":

    st.markdown("""
<div class="orb-left"></div><div class="orb-right"></div>
<div class="dot dot1"></div><div class="dot dot2"></div><div class="dot dot3"></div>
    """, unsafe_allow_html=True)

    st.html("""
<div class="music-wrapper">
    <div class="music-hero">
        <div class="music-kicker">FIRST CHAPTER · MUSIC</div>
        <div class="music-title">If your 2026 had<br><span class="soft">one song playing...</span></div>
        <div class="music-subtitle">There's probably a song hiding inside your year that says more about you than you think.</div>
    </div>
</div>
    """)

    st.html(f"""
<div class="music-art-stage">
    <img src="{MUSIC_IMAGE_URL}" class="music-art-image" alt="Neon purple music studio with headphones">
    <div class="music-art-caption">CLUE 01 · THE SOUNDTRACK</div>
</div>
    """)

    # CLUE 01 — question, then answer, all on one clean vertical axis.
    st.markdown("""
<div class="question-answer-block">
<div class="music-clue-card">
    <div class="music-card-icon">🎧</div>
    <div class="music-clue-number">CLUE 01 · THE SOUNDTRACK</div>
    <div class="music-clue-title">If your 2026 had ONE song playing in the background… what would it be?</div>
    <div class="music-clue-copy">Pick a recommendation or write your own. · Optional · Skip if you want.</div>
</div>
<div class="music-answer-label">YOUR ANSWER ↓</div>
<div class="music-answer-help">Choose a recommendation if it feels right — or type the real song yourself.</div>
</div>
    """, unsafe_allow_html=True)

    with st.container(key="music_song_answer"):
        song_choice = st.radio(
            "recommended_song",
            [
                "🎧 Maine Khud Ko",
                "🌙 Chann Wargi",
                "💫 Tu Na Samjhe",
                "🫶 Maafi",
                "✨ Be Intehaan",
                "✍️ I'll write my own"
            ], index=None, key="music_song_choice", label_visibility="collapsed"
        )
        if song_choice and song_choice != "✍️ I'll write my own":
            st.session_state.song = song_choice
            st.session_state["music_song_input"] = song_choice
        elif song_choice == "✍️ I'll write my own" and "music_song_input" not in st.session_state:
            st.session_state["music_song_input"] = st.session_state.song

        song = st.text_input(
            "song",
            placeholder="e.g. Apna Bana Le — Arijit Singh",
            label_visibility="collapsed",
            key="music_song_input"
        )
        if song.strip():
            st.session_state.song = song.strip()

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

    # CLUE 02 — fully vertical.
    st.markdown("""
<div class="question-answer-block">
<div class="music-clue-card">
    <div class="music-card-icon">👀</div>
    <div class="music-clue-number">CLUE 02 · MEMORY</div>
    <div class="music-clue-title">Every song has a person.</div>
    <div class="music-clue-copy">Who or what appears in your head when this song starts? · Optional · Skip if you want.</div>
</div>
<div class="music-answer-label">YOUR ANSWER ↓</div>
<div class="music-answer-help">Person, memory, place or feeling — type your own.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="music_memory_answer"):
        memory = st.text_input("memory", value=st.session_state.memory, placeholder="e.g. My best friend, college days, a road trip...", label_visibility="collapsed", key="music_memory_input")
        st.session_state.memory = memory

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

    # CLUE 03 — fully vertical.
    st.markdown("""
<div class="question-answer-block">
<div class="music-clue-card">
    <div class="music-card-icon">🌙</div>
    <div class="music-clue-number">CLUE 03 · YOUR MOMENT</div>
    <div class="music-clue-title">When does this song feel the most like you?</div>
    <div class="music-clue-copy">Pick the moment that matches your soundtrack. · Optional · Skip if you want.</div>
</div>
<div class="music-answer-label">YOUR ANSWER ↓</div>
<div class="music-answer-help">Choose one if it fits — leaving it blank is completely okay.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="music_moment_answer"):
        moment = st.radio(
            "moment",
            ["🌙 Late at night", "🌞 During the day", "🚗 While travelling", "🫠 When I'm in my feelings", "⚡ Whenever I need energy"],
            index=None, key="music_moment", label_visibility="collapsed"
        )
        if moment:
            st.session_state.moment = moment

    st.markdown("""
<div class="music-progress-shell" style="max-width:980px;margin-left:auto;margin-right:auto;">
    <div class="music-progress-top"><span>Music clues</span><span>03 / 09</span></div>
    <div class="music-progress-track"><div class="music-progress-fill"></div></div>
</div>
<div style="height:24px;"></div>
    """, unsafe_allow_html=True)

    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("← Back to Chapters", key="music_back"):
            st.session_state.page = "investigation"
            st.rerun()
    with b2:
        if st.button("Continue to Digital Life →", key="music_continue"):
            st.session_state.page = "digital"
            st.rerun()


# =========================================================
# DIGITAL LIFE PAGE
# =========================================================

elif st.session_state.page == "digital":

    st.markdown("""
<div class="orb-left"></div><div class="orb-right"></div>
<div class="dot dot1"></div><div class="dot dot2"></div><div class="dot dot3"></div>
<div class="digital-wrapper">
    <div style="height:55px;"></div>
    <div class="eyebrow">SECOND CHAPTER · DIGITAL LIFE</div>
    <div class="question">YOUR PHONE KNOWS<br>MORE THAN YOU THINK. 👀</div>
    <div class="digital-intro">Your everyday scrolling leaves clues too.<br>Let's see what your digital life says about you.</div>
</div>
    """, unsafe_allow_html=True)

    # CLUE 04
    st.markdown("""
<div class="question-answer-block">
<div class="digital-card">
    <div class="clue-number">CLUE 04 · YOUR GO-TO APP</div>
    <div class="clue-question">There's one app you open without even thinking. 👀</div>
    <div class="clue-description">Which one has your attention the most? · Optional · Skip if you want.</div>
</div>
<div class="answer-label">YOUR ANSWER ↓</div>
<div class="answer-hint">Pick a recommendation or write your own.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="digital_app_answer"):
        app_choice = st.radio(
            "app_choice",
            ["📸 Instagram", "▶️ YouTube", "💬 WhatsApp", "🎧 Spotify", "🎬 Netflix", "✍️ I'll enter my own"],
            index=None,
            key="digital_app_choice",
            label_visibility="collapsed"
        )

        app_custom = st.text_input(
            "app_custom",
            value=st.session_state.get("app_custom_value", ""),
            placeholder="e.g. Pinterest, Telegram, LinkedIn...",
            label_visibility="collapsed",
            key="digital_app_custom"
        )

        # A selected recommendation OR custom text should be saved.
        # Custom text wins only when the user actually types something.
        if app_custom.strip():
            st.session_state.app = app_custom.strip()
        elif app_choice and app_choice != "✍️ I'll enter my own":
            st.session_state.app = app_choice

    st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)

    # CLUE 05
    st.markdown("""
<div class="question-answer-block">
<div class="digital-card">
    <div class="clue-number">CLUE 05 · THE HOURS</div>
    <div class="clue-question">Let's see where your hours disappear. ⏱️</div>
    <div class="clue-description">Be honest... how much time does your phone get from you? · Optional · Skip if you want.</div>
</div>
<div class="answer-label">YOUR ANSWER ↓</div>
<div class="answer-hint">Pick a range or enter your own screen time.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="digital_screen_answer"):
        screen_choice = st.radio("screen_time", ["🌱 Under 2 hours", "🌤️ 2–4 hours", "🌆 4–6 hours", "🌙 6+ hours", "✍️ I'll enter my own"], index=None, key="digital_screen_time", label_visibility="collapsed")
        if screen_choice and screen_choice != "✍️ I'll enter my own":
            st.session_state.screen_time = screen_choice
        screen_custom = st.text_input("screen_custom", value="", placeholder="e.g. 3.5 hours a day", label_visibility="collapsed", key="digital_screen_custom")
        if screen_custom.strip():
            st.session_state.screen_time = screen_custom.strip()

    st.markdown("<div style='height:30px;'></div>", unsafe_allow_html=True)

    # CLUE 06
    st.markdown("""
<div class="question-answer-block">
<div class="digital-card">
    <div class="clue-number">CLUE 06 · YOUR PHONE MOMENT</div>
    <div class="clue-question">When does your phone become your favourite company? 🌙</div>
    <div class="clue-description">There's probably a pattern you haven't noticed yet. · Optional · Skip if you want.</div>
</div>
<div class="answer-label">YOUR ANSWER ↓</div>
<div class="answer-hint">Pick a recommendation or leave it blank.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="digital_phone_answer"):
        phone_choice = st.radio("phone_time", ["🌅 Right after waking up", "☀️ During the day", "🌆 In the evening", "🌙 Late at night", "🫠 Whenever I'm bored", "✍️ I'll enter my own"], index=None, key="digital_phone_time", label_visibility="collapsed")
        if phone_choice and phone_choice != "✍️ I'll enter my own":
            st.session_state.phone_time = phone_choice
        phone_custom = st.text_input("phone_custom", value="", placeholder="e.g. late at night when I'm bored...", label_visibility="collapsed", key="digital_phone_custom")
        if phone_custom.strip():
            st.session_state.phone_time = phone_custom.strip()

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    if st.button("← Back to Chapters", key="digital_back"):
        st.session_state.page = "investigation"
        st.rerun()
    if st.button("Continue to Entertainment →", key="digital_continue"):
        st.session_state.page = "entertainment"
        st.rerun()


# =========================================================
# ENTERTAINMENT PAGE
# =========================================================

elif st.session_state.page == "entertainment":

    st.html("""
<div class="orb-left"></div><div class="orb-right"></div>
<div class="dot dot1"></div><div class="dot dot2"></div><div class="dot dot3"></div>
<div class="ent-wrapper">
    <div class="ent-hero">
        <div class="ent-kicker">THIRD CHAPTER · ENTERTAINMENT</div>
        <div class="ent-title">What you watched<br><span class="soft">wasn't random.</span></div>
        <div class="ent-subtitle">The stories you return to, the characters you remember, and the worlds you escape into all leave little clues.</div>
    </div>
</div>
    """)

    # Artwork gets the full width. No question text beside it.
    if CINEMA_IMAGE.exists():
        with open(CINEMA_IMAGE, "rb") as f:
            cinema_b64 = base64.b64encode(f.read()).decode("utf-8")
        cinema_src = f"data:image/png;base64,{cinema_b64}"
    else:
        cinema_src = ""

    st.html(f"""
<div class="entertainment-feature">
    <div class="entertainment-image-wrap">
        {f'<img src="{cinema_src}" class="entertainment-image" alt="Cinema artwork">' if cinema_src else '<div style="display:flex;align-items:center;justify-content:center;color:#aaa4bd;font-size:14px;padding:30px;text-align:center;">Add cinema_entertainment_asset.png beside this Python file</div>'}
    </div>
</div>
    """)

    # CLUE 07 — question is now BELOW the image, and recommendation labels are clean.
    st.markdown("""
<div class="question-answer-block">
<div class="digital-card">
    <div class="clue-number">CLUE 07 · YOUR FAVORITE MOVIE</div>
    <div class="clue-question">What is your favorite movie? The one you never get tired of. 🍿</div>
    <div class="clue-description">Pick a recommendation or write the real movie name yourself. · Optional · Skip if you want.</div>
</div>
<div class="answer-label">YOUR ANSWER ↓</div>
<div class="answer-hint">Choose a movie style below, or type the exact movie you mean.</div>
</div>
    """, unsafe_allow_html=True)

    with st.container(key="ent_movie_answer"):
        movie_choice = st.radio(
            "movie_choice",
            [
                "🎬 Ramaiya Vastavaiya",
                "💜 Shiddat",
                "✨ Pritam and Pedro",
                "🍿 Vishwanath and Sons",
                "🌟 Hanuman Ansh",
                "✍️ I'll write my own"
            ],
            index=None, key="ent_movie_choice", label_visibility="collapsed"
        )
        # Keep the recommended movie unless the user actually types a custom movie.
        if movie_choice and movie_choice != "✍️ I'll write my own":
            st.session_state.comfort_watch = movie_choice
            st.session_state["ent_movie_custom"] = movie_choice
        elif movie_choice == "✍️ I'll write my own" and "ent_movie_custom" not in st.session_state:
            st.session_state["ent_movie_custom"] = st.session_state.comfort_watch

        movie_custom = st.text_input(
            "movie_custom",
            placeholder="e.g. another movie name...",
            label_visibility="collapsed",
            key="ent_movie_custom"
        )
        if movie_custom.strip():
            st.session_state.comfort_watch = movie_custom.strip()

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

    # CLUE 08
    st.markdown("""
<div class="question-answer-block">
<div class="ent-card">
    <div class="ent-icon">🏰</div>
    <div class="ent-number">CLUE 08 · THE ONE YOU'D LIVE IN</div>
    <div class="ent-card-title">If you could move into ONE fictional world for a week… where are you going?</div>
    <div class="ent-card-copy">Pick a recommendation or write your own world. · Optional · Skip if you want.</div>
</div>
<div class="answer-label">YOUR ANSWER ↓</div>
<div class="answer-hint">Choose a universe or type your own.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="ent_world_answer"):
        world_choice = st.radio(
            "fictional_world",
            ["✨ Hogwarts", "⚡ Marvel universe", "🌸 A K-drama world", "🏰 A Disney / Pixar world", "✍️ I'll write my own"],
            index=None,
            key="ent_fictional_world",
            label_visibility="collapsed"
        )

        # Keep recommendation and custom text independent.
        # The text box is ALWAYS available, while an empty text box never
        # overwrites a selected recommendation.
        world_custom = st.text_input(
            "world_custom",
            value=st.session_state.get("world_custom_value", ""),
            placeholder="e.g. Middle-earth, a fantasy kingdom...",
            label_visibility="collapsed",
            key="ent_world_custom"
        )

        if world_custom.strip():
            st.session_state.fictional_world = world_custom.strip()
        elif world_choice and world_choice != "✍️ I'll write my own":
            st.session_state.fictional_world = world_choice

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

    # CLUE 09
    st.markdown("""
<div class="question-answer-block">
<div class="ent-card">
    <div class="ent-icon">👀</div>
    <div class="ent-number">CLUE 09 · YOUR WATCHING PERSONALITY</div>
    <div class="ent-card-title">Be honest… what kind of viewer are you?</div>
    <div class="ent-card-copy">Pick the one that sounds most like you, or type your own. · Optional · Skip if you want.</div>
</div>
<div class="answer-label">YOUR ANSWER ↓</div>
<div class="answer-hint">Choose a watching habit or write your own.</div>
</div>
    """, unsafe_allow_html=True)
    with st.container(key="ent_viewer_answer"):
        viewer_choice = st.radio("viewer_type", ["😭 One episode → finishes the whole season", "🎭 Watches 5 shows simultaneously", "🔁 Rewatches the same favourites", "💀 Reads spoilers first", "😌 Watches only when the mood hits", "✍️ I'll write my own"], index=None, key="ent_viewer_type", label_visibility="collapsed")
        if viewer_choice and viewer_choice != "✍️ I'll write my own":
            st.session_state.viewer_type = viewer_choice
        viewer_custom = st.text_input("viewer_custom", value=st.session_state.viewer_type, placeholder="e.g. I watch one episode before bed...", label_visibility="collapsed", key="ent_viewer_custom")
        st.session_state.viewer_type = viewer_custom

    st.markdown("<div style='height:22px;'></div>", unsafe_allow_html=True)
    st.html("""
<div class="ent-progress" style="max-width:980px;">
    <div class="ent-progress-top"><span>PERSONALITY CLUES</span><span>09 / 09</span></div>
    <div class="ent-track"><div class="ent-fill ent-fill-full"></div></div>
</div>
    """)

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
    if st.button("← Back to Chapters", key="entertainment_back"):
        st.session_state.page = "investigation"
        st.rerun()
    if st.button("Reveal My Personality →", key="entertainment_continue"):
        st.session_state.page = "done"
        st.rerun()


# =========================================================
# FINAL PERSONALITY REVEAL
# =========================================================

elif st.session_state.page == "done":

    # -----------------------------------------------------
    # PERSONALITY ENGINE
    # -----------------------------------------------------

    song = st.session_state.song.strip()
    memory = st.session_state.memory.strip()
    moment = st.session_state.moment.strip()
    app = st.session_state.app.strip()
    screen_time = st.session_state.screen_time.strip()
    phone_time = st.session_state.phone_time.strip()
    movie = st.session_state.comfort_watch.strip()
    world = st.session_state.fictional_world.strip()
    viewer = st.session_state.viewer_type.strip()

    # Small rule-based personality engine — no ML required.
    # The personality is intentionally driven by the clues the user gave.
    moment_l = moment.lower()
    phone_l = phone_time.lower()
    screen_l = screen_time.lower()
    viewer_l = viewer.lower()
    world_l = world.lower()

    late_night = "late at night" in moment_l or "late at night" in phone_l or "night" in moment_l
    comfort_viewer = any(x in viewer_l for x in ["rewatches", "mood hits"])
    binge_viewer = "whole season" in viewer_l or "5 shows" in viewer_l
    spoiler_reader = "spoilers" in viewer_l
    fantasy_world = any(x in world_l for x in ["hogwarts", "marvel", "k-drama", "disney", "pixar", "fictional"])
    heavy_screen = "6+ hours" in screen_l or "don't even want to know" in screen_l or any(x in screen_l for x in ["7 hours", "8 hours", "9 hours", "10 hours"])
    medium_screen = "4–6 hours" in screen_l
    light_screen = "under 2 hours" in screen_l

    # Simple, memorable personality names — driven by the user's actual behaviour.
    # Night behaviour gets the clearest identity: NIGHT OWL.
    if late_night and heavy_screen and binge_viewer:
        personality = "THE DIGITAL NIGHT OWL"
        personality_tag = "You come alive when the world goes quiet — one scroll, one episode, one more hour."
    elif late_night and binge_viewer:
        personality = "THE BINGE NIGHT OWL"
        personality_tag = "Your nights have a habit of turning into just one more episode."
    elif late_night and heavy_screen:
        personality = "THE DIGITAL NIGHT OWL"
        personality_tag = "When everyone else switches off, your little digital world stays awake."
    elif late_night:
        personality = "THE NIGHT OWL"
        personality_tag = "You seem to find your own little rhythm after everyone else has gone quiet."
    elif binge_viewer and fantasy_world:
        personality = "THE STORY LOVER"
        personality_tag = "Once a story pulls you in, you don't really want to leave."
    elif comfort_viewer and fantasy_world:
        personality = "THE COMFORT ESCAPIST"
        personality_tag = "You know exactly which stories can make the world feel softer."
    elif binge_viewer:
        personality = "THE BINGE LOVER"
        personality_tag = "One episode is rarely just one episode for you."
    elif spoiler_reader:
        personality = "THE PLOT HUNTER"
        personality_tag = "You want the mystery, but you also want to know where it is going."
    elif comfort_viewer:
        personality = "THE COMFORT SEEKER"
        personality_tag = "Familiar stories are your way of making ordinary days feel like home."
    elif fantasy_world:
        personality = "THE DREAMER"
        personality_tag = "Your imagination is somewhere you can always go."
    elif heavy_screen:
        personality = "THE DIGITAL EXPLORER"
        personality_tag = "Your screen is a doorway into different worlds, ideas and little escapes."
    elif light_screen:
        personality = "THE LITTLE MOMENT COLLECTOR"
        personality_tag = "You keep your screen close without letting it take over the whole story."
    elif medium_screen:
        personality = "THE BALANCED EXPLORER"
        personality_tag = "You make room for screens, stories and the little things happening around you."
    else:
        personality = "THE QUIETLY CURIOUS ONE"
        personality_tag = "You collect little moments, stories and habits — then make them your own."

    # Escape user-entered text before putting it inside HTML.
    song_h = html.escape(song)
    memory_h = html.escape(memory)
    moment_h = html.escape(moment)
    app_h = html.escape(app)
    screen_h = html.escape(screen_time)
    phone_h = html.escape(phone_time)
    movie_h = html.escape(movie)
    world_h = html.escape(world)
    viewer_h = html.escape(viewer)
    personality_h = html.escape(personality)
    personality_tag_h = html.escape(personality_tag)

    # One panda appears above the personality title and changes with the title.
    personality_panda = PERSONALITY_PANDA_IMAGES.get(personality, PANDA_IMAGE_1)

    # -----------------------------------------------------
    # MOVING REVEAL BACKGROUND
    # -----------------------------------------------------

    st.html(
        """
<div class="reveal-orbit reveal-orbit-one"></div>
<div class="reveal-orbit reveal-orbit-two"></div>
<div class="reveal-star reveal-star-one">✦</div>
<div class="reveal-star reveal-star-two">✦</div>
<div class="reveal-star reveal-star-three">·</div>
        """
    )

    # -----------------------------------------------------
    # CINEMATIC INTRO
    # -----------------------------------------------------

    st.html(
        """
<div class="reveal-intro">
    <div class="reveal-overline">THE INVESTIGATION IS COMPLETE</div>
    <div class="reveal-intro-title">Your clues have<br><span>something to say.</span></div>
    <div class="reveal-intro-copy">Music. Digital life. Entertainment.<br>Three chapters. One version of you.</div>
</div>
        """
    )

    st.markdown("<div style='height:42px;'></div>", unsafe_allow_html=True)

    # -----------------------------------------------------
    # MAIN PERSONALITY CARD
    # -----------------------------------------------------

    st.html(
        f"""
<div class="reveal-personality-wrap">
    <div class="reveal-personality-card">
        <div class="reveal-card-glow"></div>
        <div class="reveal-card-label">YOUR 2026 DATA PERSONALITY</div>
        <div class="reveal-personality-panda-wrap">
            <img class="reveal-personality-panda" src="{personality_panda}" alt="Your personality panda">
        </div>
        <div class="reveal-personality-name">{personality_h}</div>
        <div class="reveal-personality-tag">{personality_tag_h}</div>
        <div class="reveal-divider"></div>
        <div class="reveal-card-foot">
            <span>09 CLUES</span>
            <span>01 STORY</span>
        </div>
    </div>
</div>
        """
    )

    # -----------------------------------------------------
    # YOUR STORY — DYNAMIC + ONLY SHOW REVEALED CLUES
    # -----------------------------------------------------

    revealed = []
    if song:
        revealed.append(f"<strong>{song_h}</strong>")
    if memory:
        revealed.append(f"<span class='story-highlight'>{memory_h}</span>")
    if movie:
        revealed.append(f"<strong>{movie_h}</strong>")
    if world:
        revealed.append(f"<strong>{world_h}</strong>")

    if late_night and heavy_screen and binge_viewer:
        opening = "When everyone else started winding down, <strong>your world was still awake</strong>. 🌙"
        pattern_line = "Late nights, long screen hours and stories that are hard to leave seem to be part of your rhythm."
    elif late_night and heavy_screen:
        opening = "Your day may have ended, but <strong>your little world hadn't</strong>. 🌙"
        pattern_line = "You seem to find your quietest little moments when everyone else has gone offline."
    elif late_night and binge_viewer:
        opening = "The day goes quiet and somehow <strong>your story begins</strong>. 🌙"
        pattern_line = "You don't just watch a story — you <strong>stay with it</strong>."
    elif binge_viewer and fantasy_world:
        opening = "Give you a good story and you might quietly disappear into it. ✨"
        pattern_line = "You don't just want entertainment — <strong>you want a world to step into</strong>."
    elif comfort_viewer and fantasy_world:
        opening = "Some people look for something new. You know the magic of <strong>returning to what feels right</strong>. ♡"
        pattern_line = "You seem to collect stories that feel a little like home."
    elif late_night:
        opening = "Somewhere between the busy day and the quiet night, you found your little world. 🌙"
        pattern_line = "There is a softness to the way you spend those late hours."
    elif comfort_viewer:
        opening = "Your 2026 seems to have had a soft spot for things that feel familiar. ♡"
        pattern_line = "Sometimes the best escape is the one that already knows you."
    elif binge_viewer:
        opening = "You have a tiny problem with stories: <strong>once they have you, they have you</strong>. ✦"
        pattern_line = "One episode becomes another, and suddenly you have spent a little more time inside a story."
    elif heavy_screen:
        opening = "Your screen seems to have been more than a screen this year. ✨"
        pattern_line = "You seem to collect tiny escapes wherever you find them."
    else:
        opening = "Your 2026 was made of little things that felt very <strong>you</strong>. ♡"
        pattern_line = "A collection of small choices quietly became your own little pattern."

    # Add only the clues the user actually revealed.
    detail_lines = []
    if song:
        detail_lines.append(f"Somewhere in the background, <strong>{song_h}</strong> became part of your year.")
    if memory:
        detail_lines.append(f"It carries a little piece of <span class='story-highlight'>{memory_h}</span>.")
    if moment:
        detail_lines.append(f"You said this soundtrack feels most like you <strong>{moment_h}</strong>.")
    if app:
        detail_lines.append(f"Your go-to digital corner is <strong>{app_h}</strong>.")
    if screen_time:
        detail_lines.append(f"You give your screen <strong>{screen_h}</strong> of your day.")
    if phone_time:
        detail_lines.append(f"And your phone becomes favourite company <strong>{phone_h}</strong>.")
    if movie:
        detail_lines.append(f"On the entertainment side, <strong>{movie_h}</strong> is part of your story.")
    if world:
        detail_lines.append(f"If you could escape somewhere fictional, you'd choose <strong>{world_h}</strong>.")
    if viewer:
        detail_lines.append(f"Your watching style? <strong>{viewer_h}</strong>.")

    memory_line = " ".join(detail_lines)
    closing_story = (
        f"Maybe that's what your data was really trying to say: "
        f"you find little things that make ordinary days feel a little more like <strong>home</strong>. "
        f"<br><br><strong>And honestly… that's pretty cute. ♡</strong>"
    )

    # -----------------------------------------------------
    # SAVE THIS COMPLETED REVEAL TO MYSQL
    # -----------------------------------------------------
    personality_description = personality_tag
    database_story = f"{opening} {memory_line} {pattern_line} {closing_story}"

    # Streamlit reruns the script, so only insert once for this reveal.
    if not st.session_state.get("database_saved", False):
        saved, result = save_personality_to_database(
            personality,
            personality_description,
            database_story,
        )
        if saved:
            st.session_state.database_saved = True
            st.session_state.database_user_id = result
        else:
            st.session_state.database_error = result

    if st.session_state.get("database_saved", False):
        st.caption(f"✦ Saved privately · Personality #{st.session_state.get('database_user_id')}")
    elif st.session_state.get("database_error"):
        st.error(f"Your personality is ready, but the database save failed: {st.session_state.database_error}")

    story_details_html = f'<p class="story-paragraph">{memory_line}</p>' if detail_lines else ''

    st.html(
        f"""
<div class="reveal-section reveal-story-heading">
    <div class="reveal-section-kicker">YOUR 2026 STORY</div>
    <div class="reveal-section-title">A little piece<br><span>of your year.</span></div>
</div>

<div class="reveal-storybook">
    <div class="reveal-story-card">
        <div class="story-greeting">Once upon your 2026…</div>

        <p class="story-paragraph">{opening}</p>

        {story_details_html}

        <div class="story-divider"></div>

        <p class="story-paragraph">{pattern_line}</p>

        <p class="story-ending">{closing_story}</p>

        <div class="story-signoff">made of little moments · ♡</div>
    </div>
</div>
        """
    )

    # -----------------------------------------------------
    # FINAL CINEMATIC QUOTE
    # -----------------------------------------------------

    st.html(
        f"""
<div class="reveal-final">
    <div class="reveal-final-mark">✦</div>
    <div class="reveal-final-small">AND IF YOUR YEAR WERE A LITTLE FILM…</div>
    <div class="reveal-final-title">this would be<br><span>your ending scene.</span></div>
    <div class="reveal-final-personality">{personality_h}</div>
    <div class="reveal-final-copy">The screen fades. The music keeps playing. And somewhere in the credits, your 2026 quietly smiles back at you.</div>
</div>
        """
    )

    st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

    if st.button("Explore My Personality ↗", key="explore_personality"):
        st.session_state.reveal_explored = True
        st.rerun()

    if st.session_state.get("reveal_explored", False):
        st.html(
            """
<div class="reveal-explore-note">
    <span>✦</span> Your personality is built from the clues you chose to share — and it can become richer as you add more data.
</div>
            """
        )

    st.markdown("<div style='height:35px;'></div>", unsafe_allow_html=True)

    if st.button("Start Again ↺", key="start_again"):
        for key in [
            "song", "memory", "moment", "comfort_watch",
            "fictional_world", "viewer_type", "app", "digital_app_choice", "digital_app_custom", "ent_world_custom",
            "screen_time", "phone_time", "reveal_explored",
            "database_saved", "database_user_id", "database_error"
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.session_state.page = "landing"
        st.rerun()

