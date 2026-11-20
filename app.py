# -*- coding: utf-8 -*-
"""
Dashboard báo cáo Facebook Ads — bản làm lại theo mẫu thammyha.
Chạy: streamlit run app.py
Kết nối Facebook Marketing API bằng access token + danh sách tài khoản quảng cáo.
"""
import time
from datetime import date, timedelta

import pandas as pd
import requests
import streamlit as st

# ----------------------------------------------------------------------------
# CẤU HÌNH
# ----------------------------------------------------------------------------
st.set_page_config(page_title="Báo cáo FB Ads — Á Âu", page_icon="📊", layout="centered")

GRAPH = "https://graph.facebook.com"
API_VERSION = st.secrets.get("api_version", "v21.0")

# Token + danh sách tài khoản lấy từ Settings (.streamlit/secrets.toml). Ví dụ:
#   access_token = "EAA..."
#   [accounts]
#   "01 TRUNG HM VK" = "act_1234567890"
#   "02 TRUNG HM VN" = "act_9876543210"
ACCESS_TOKEN = st.secrets.get("access_token", "")
ACCOUNTS = dict(st.secrets.get("accounts", {}))  # {label: act_id}

# Action type ứng với "tin nhắn" và "SĐT (lead form)" — có thể chỉnh trong tab Thêm
DEFAULT_MSG_ACTIONS = ["onsite_conversion.messaging_conversation_started_7d"]
DEFAULT_LEAD_ACTIONS = [
    "lead",
    "leadgen_grouped",
    "onsite_conversion.lead_grouped",
    "offsite_conversion.fb_pixel_lead",
]

# ----------------------------------------------------------------------------
# TIỆN ÍCH
# ----------------------------------------------------------------------------
def vnd(x):
    try:
        return f"{round(float(x)):,.0f} đ".replace(",", ".")
    except Exception:
        return "—"


def short_vnd(x):
    try:
        x = float(x)
    except Exception:
        return "—"
    if x >= 1_000_000:
        return f"{x/1_000_000:.2f}tr".replace(".", ",")
    if x >= 1_000:
        return f"{x/1_000:.0f}k"
    return f"{x:.0f}"


def compute_alerts(all_campaigns, per_account, ss):
    items = []
    for a in per_account:
        if a["running"] == 0 and a["spend"] == 0:
            items.append((a["label"], "TKQC: không có chiến dịch chạy / có thể bị vô hiệu hóa"))
    for c in all_campaigns:
        if c["effective"] != "ACTIVE":
            continue
        if c["spend"] >= ss.spend_zero_msg and c["messages"] == 0:
            items.append((f"{c['campaign']} · {c['account']}",
                          f"Tiêu {vnd(c['spend'])} nhưng 0 tin nhắn"))
        elif ss.msg_high and c["messages"] >= ss.min_msg and c["cost_per_msg"] > ss.msg_high:
            items.append((f"{c['campaign']} · {c['account']}",
                          f"Giá tin nhắn cao: {vnd(c['cost_per_msg'])}"))
    return items


def sum_actions(actions, wanted):
    """Cộng giá trị của các action_type nằm trong danh sách wanted."""
    if not actions:
        return 0
    total = 0
    for a in actions:
        if a.get("action_type") in wanted:
            try:
                total += float(a.get("value", 0))
            except Exception:
                pass
    return int(total)


@st.cache_data(ttl=300, show_spinner=False)
def fb_get(path, params):
    params = dict(params)
    params["access_token"] = ACCESS_TOKEN
    url = f"{GRAPH}/{API_VERSION}/{path}"
    out, pages = [], 0
    while url and pages < 25:
        r = requests.get(url, params=params if pages == 0 else None, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(r.json().get("error", {}).get("message", r.text))
        j = r.json()
        data = j.get("data", j)
        if isinstance(data, list):
            out.extend(data)
        else:
            return data
        url = j.get("paging", {}).get("next")
        pages += 1
    return out


def get_account_insights(act_id, since, until, msg_actions, lead_actions):
    rows = fb_get(
        f"{act_id}/insights",
        {
            "level": "account",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": "spend,clicks,ctr,impressions,actions",
        },
    )
    if not rows:
        return dict(spend=0, clicks=0, ctr=0, impressions=0, messages=0, leads=0)
    r = rows[0]
    return dict(
        spend=float(r.get("spend", 0) or 0),
        clicks=int(float(r.get("clicks", 0) or 0)),
        ctr=float(r.get("ctr", 0) or 0),
        impressions=int(float(r.get("impressions", 0) or 0)),
        messages=sum_actions(r.get("actions"), msg_actions),
        leads=sum_actions(r.get("actions"), lead_actions),
    )


def get_campaigns(act_id, since, until, msg_actions, lead_actions):
    camps = fb_get(
        f"{act_id}/campaigns",
        {"fields": "name,status,effective_status,daily_budget", "limit": 200},
    )
    cmap = {c["id"]: c for c in camps}
    ins = fb_get(
        f"{act_id}/insights",
        {
            "level": "campaign",
            "time_range": f'{{"since":"{since}","until":"{until}"}}',
            "fields": "campaign_id,campaign_name,spend,clicks,ctr,actions",
            "limit": 500,
        },
    )
    imap = {r["campaign_id"]: r for r in ins}
    out = []
    for cid, c in cmap.items():
        r = imap.get(cid, {})
        spend = float(r.get("spend", 0) or 0)
        msgs = sum_actions(r.get("actions"), msg_actions)
        leads = sum_actions(r.get("actions"), lead_actions)
        out.append(
            dict(
                campaign=c.get("name", ""),
                status="Đang chạy" if c.get("effective_status") == "ACTIVE" else "Không chạy",
                effective=c.get("effective_status", ""),
                daily_budget=float(c.get("daily_budget", 0) or 0) / 100.0,
                spend=spend,
                messages=msgs,
                leads=leads,
                cost_per_msg=(spend / msgs) if msgs else 0,
            )
        )
    return out


# ----------------------------------------------------------------------------
# STATE NGƯỠNG & RULE
# ----------------------------------------------------------------------------
ss = st.session_state
ss.setdefault("msg_high", 300000)
ss.setdefault("msg_good", 150000)
ss.setdefault("spend_zero_msg", 200000)
ss.setdefault("min_msg", 5)
ss.setdefault("budget_cap", 20000000)
ss.setdefault("msg_actions", list(DEFAULT_MSG_ACTIONS))
ss.setdefault("lead_actions", list(DEFAULT_LEAD_ACTIONS))

# ----------------------------------------------------------------------------
# PHẦN CHỌN TÀI KHOẢN + THỜI GIAN
# ----------------------------------------------------------------------------
st.markdown("### Tài khoản quảng cáo")

if not ACCESS_TOKEN or not ACCOUNTS:
    st.warning(
        "Chưa cấu hình token / tài khoản. Vào **Settings → Secrets** (hoặc file "
        "`.streamlit/secrets.toml`) điền `access_token` và mục `[accounts]`. "
        "Xem README để biết cách lấy token."
    )

labels = list(ACCOUNTS.keys())
pick = st.multiselect(
    "Chọn tài khoản (bỏ trống = ALL TKQC)",
    options=labels,
    default=[],
    placeholder="ALL TKQC",
)
chosen = pick if pick else labels

PRESETS = {
    "Hôm nay": 0,
    "Hôm qua": 1,
    "7 ngày qua": 7,
    "14 ngày qua": 14,
    "30 ngày qua": 30,
}
col1, col2 = st.columns([3, 1])
with col1:
    preset = st.selectbox("Khoảng thời gian", list(PRESETS.keys()), index=2)
with col2:
    st.write("")
    st.write("")
    refresh = st.button("🔄 Làm mới số liệu", use_container_width=True)

if refresh:
    st.cache_data.clear()

n = PRESETS[preset]
if preset == "Hôm nay":
    since = until = date.today().isoformat()
elif preset == "Hôm qua":
    since = until = (date.today() - timedelta(days=1)).isoformat()
else:
    until = (date.today() - timedelta(days=1)).isoformat()
    since = (date.today() - timedelta(days=n)).isoformat()

st.caption(f"{since} → {until} · Cập nhật {time.strftime('%H:%M')}")

# ----------------------------------------------------------------------------
# LẤY SỐ LIỆU
# ----------------------------------------------------------------------------
if not ACCESS_TOKEN or not ACCOUNTS:
    st.stop()

tot = dict(spend=0, clicks=0, impressions=0, messages=0, leads=0)
per_account, all_campaigns, errors = [], [], []
with st.spinner("Đang lấy số liệu..."):
    for label in chosen:
        act = ACCOUNTS[label]
        try:
            a = get_account_insights(act, since, until, ss.msg_actions, ss.lead_actions)
            for k in tot:
                tot[k] += a[k]
            camps = get_campaigns(act, since, until, ss.msg_actions, ss.lead_actions)
            running = sum(1 for c in camps if c["effective"] == "ACTIVE")
            per_account.append(dict(label=label, running=running, **a))
            for c in camps:
                c["account"] = label
            all_campaigns.extend(camps)
        except Exception as e:
            errors.append(f"{label}: {e}")

for e in errors:
    st.error(e)

ctr = (tot["clicks"] / tot["impressions"] * 100) if tot["impressions"] else 0
cpm_msg = (tot["spend"] / tot["messages"]) if tot["messages"] else 0
cpl = (tot["spend"] / tot["leads"]) if tot["leads"] else 0
daily_on = sum(c["daily_budget"] for c in all_campaigns if c["effective"] == "ACTIVE")
running_total = sum(1 for c in all_campaigns if c["effective"] == "ACTIVE")

# ----------------------------------------------------------------------------
# TABS
# ----------------------------------------------------------------------------
t_overview, t_camp, t_alert, t_more = st.tabs(
    ["Tổng quan", "Chiến dịch", "Cảnh báo", "Thêm"]
)

# ---- TỔNG QUAN ----
with t_overview:
    r1 = st.columns(2)
    r1[0].metric("TỔNG CHI TIÊU", vnd(tot["spend"]), help="Ngân sách đã sử dụng")
    r1[1].metric("TIN NHẮN", f"{tot['messages']}", help="Cuộc trò chuyện bắt đầu")
    r2 = st.columns(2)
    r2[0].metric("CHI PHÍ / TIN NHẮN", vnd(cpm_msg), help="Tổng chi tiêu ÷ tin nhắn")
    r2[1].metric("TỶ LỆ NHẤP · CTR", f"{ctr:.2f}%".replace(".", ","),
                 help=f"{tot['clicks']} lượt nhấp")
    r3 = st.columns(2)
    r3[0].metric("SĐT", f"{tot['leads']}", help="Từ form khách hàng tiềm năng")
    r3[1].metric("GIÁ SĐT", vnd(cpl), help="Tổng chi tiêu ÷ SĐT")

    # Cảnh báo tổng
    n_alert = len(compute_alerts(all_campaigns, per_account, ss))
    if n_alert:
        st.warning(f"⚠️ {n_alert} mục cần rà soát → xem tab **Cảnh báo**")

    cap = ss.budget_cap
    over = " ⚠️ vượt trần" if cap and daily_on > cap else ""
    st.info(
        f"**Tổng ngân sách/ngày đang bật**\n\n"
        f"{vnd(daily_on)} / trần {short_vnd(cap)} · {running_total} chiến dịch đang chạy{over}"
    )

    st.markdown(f"#### Tổng hợp tài khoản ({len(per_account)})")
    for a in sorted(per_account, key=lambda x: -x["spend"]):
        with st.container(border=True):
            top = st.columns([3, 1])
            top[0].markdown(f"**{a['label']}**")
            top[1].markdown(
                f"<div style='text-align:right;color:#888'>{a['running']} chiến dịch đang chạy</div>",
                unsafe_allow_html=True,
            )
            c = st.columns(4)
            c[0].caption("Chi tiêu"); c[0].markdown(f"**{short_vnd(a['spend'])}**")
            c[1].caption("Tin nhắn"); c[1].markdown(f"**{a['messages']}**")
            cpm = (a["spend"] / a["messages"]) if a["messages"] else 0
            c[2].caption("Giá/tin"); c[2].markdown(f"**:red[{short_vnd(cpm)}]**")
            c[3].caption("SĐT"); c[3].markdown(f"**{a['leads']}**")

# ---- CHIẾN DỊCH ----
with t_camp:
    only_on = st.toggle("Chỉ xem chiến dịch đang bật", value=False)
    rows = [c for c in all_campaigns if (c["effective"] == "ACTIVE" or not only_on)]
    df = pd.DataFrame(
        [
            {
                "Chiến dịch": c["campaign"],
                "TKQC": c["account"],
                "Trạng thái": c["status"],
                "Chi tiêu": round(c["spend"]),
                "Tin nhắn": c["messages"],
                "Giá/tin": round(c["cost_per_msg"]),
                "SĐT": c["leads"],
                "NS/ngày": round(c["daily_budget"]),
            }
            for c in sorted(rows, key=lambda x: -x["spend"])
        ]
    )
    st.caption(f"{len(df)} chiến dịch.")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        st.download_button(
            "⬇️ Tải CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            file_name=f"chien_dich_{since}_{until}.csv",
            mime="text/csv",
        )

# ---- CẢNH BÁO ----
with t_alert:
    items = compute_alerts(all_campaigns, per_account, ss)
    st.markdown(f"#### {len(items)} mục cần rà soát")
    for title, desc in items:
        with st.container(border=True):
            st.markdown(f"🔴 **{title}**")
            st.caption(desc)
    if not items:
        st.success("Không có cảnh báo nào trong khoảng thời gian này.")

# ---- THÊM (ngưỡng + rule) ----
with t_more:
    st.markdown("### Ngưỡng cảnh báo")
    ss.msg_high = st.number_input("Giá tin nhắn quá cao (đ) – đặt 0 để tắt", value=ss.msg_high, step=10000)
    ss.msg_good = st.number_input("Giá tin nhắn tốt (đ) – đủ điều kiện tăng ngân sách, 0 để tắt", value=ss.msg_good, step=10000)
    ss.spend_zero_msg = st.number_input("Chi tiêu tối thiểu để báo '0 tin nhắn' (đ)", value=ss.spend_zero_msg, step=10000)
    ss.min_msg = st.number_input("Số tin nhắn tối thiểu để xét 'đủ điều kiện tăng'", value=ss.min_msg, step=1)
    ss.budget_cap = st.number_input("Trần ngân sách/ngày toàn bộ (đ) – 0 để ẩn", value=ss.budget_cap, step=1000000)

    st.markdown("### Rule tăng / giảm ngân sách")
    st.caption("App chỉ có quyền xem nên **không tự đổi ngân sách**. Khi chiến dịch khớp rule, "
               "app hiện đề xuất ở tab Cảnh báo để bạn tự chỉnh trên Ads Manager.")
    st.toggle("Bật tất cả rule", value=True)
    with st.container(border=True):
        st.markdown("**Rule 1 — Nếu giá tin nhắn ≤ 150.000đ thì Tăng 20% ngân sách/ngày "
                    "(chỉ xét chiến dịch có ≥ 5 tin nhắn)**")

    st.markdown("### Loại action (nâng cao)")
    st.caption("Nếu số 'tin nhắn' hoặc 'SĐT' lệch, chỉnh lại action_type cho đúng tài khoản của bạn.")
    ss.msg_actions = [s.strip() for s in st.text_area(
        "Action cho TIN NHẮN (mỗi dòng 1 loại)",
        value="\n".join(ss.msg_actions)).splitlines() if s.strip()]
    ss.lead_actions = [s.strip() for s in st.text_area(
        "Action cho SĐT / LEAD (mỗi dòng 1 loại)",
        value="\n".join(ss.lead_actions)).splitlines() if s.strip()]
