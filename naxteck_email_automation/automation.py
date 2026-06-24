import requests
import smtplib
import os
import schedule
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

META_TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
AD_ACCOUNTS = [a.strip() for a in os.getenv("META_AD_ACCOUNT_ID", "").split(",") if a.strip()]
CLIENT_NAMES  = os.getenv("CLIENT_NAMES", "My Account").split(",")
EMAIL_FROM    = os.getenv("EMAIL_FROM")
EMAIL_PASSWORD= os.getenv("EMAIL_PASSWORD", "").replace(" ", "")
EMAIL_TO      = os.getenv("EMAIL_TO")
MAX_CPA       = float(os.getenv("MAX_CPA", 600))
MIN_CTR       = float(os.getenv("MIN_CTR", 1.0))
MIN_ROAS      = float(os.getenv("MIN_ROAS", 2.5))
REPORT_TIME   = os.getenv("DAILY_REPORT_TIME", "09:00")
API_VERSION   = "v19.0"

AD_ACCOUNTS = [
    a.strip() if a.strip().startswith("act_") else f"act_{a.strip()}"
    for a in AD_ACCOUNTS if a.strip()
]

print("─" * 50)
print(f"🚀 NAXTECK Email Automation")
print(f"📧 FROM     : {EMAIL_FROM}")
print(f"📧 TO       : {EMAIL_TO}")
print(f"🔑 TOKEN    : {'✅ Set' if META_TOKEN else '❌ Missing'}")
print(f"📊 ACCOUNTS : {', '.join(AD_ACCOUNTS)}")
print(f"⏰ REPORT   : Daily at {REPORT_TIME}")
print(f"🔍 ALERTS   : Hourly check — only if triggered")
print("─" * 50)

def send_email(subject, html_body):
    if not EMAIL_FROM or not EMAIL_PASSWORD or not EMAIL_TO:
        print("❌ Email credentials missing!")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = EMAIL_FROM
        msg["To"]      = EMAIL_TO
        msg.attach(MIMEText(html_body, "html"))
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(EMAIL_FROM, EMAIL_PASSWORD)
            server.sendmail(
                 EMAIL_FROM,
                  [e.strip() for e in EMAIL_TO.split(",")],
                  msg.as_string()
                  )
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        print(f"✅ Email sent: {subject}")
    except Exception as e:
        print(f"❌ Email error: {e}")

def get_insights(account_id, date_preset="yesterday"):
    url = f"https://graph.facebook.com/{API_VERSION}/{account_id}/insights"
    params = {
        "access_token": META_TOKEN,
        "level": "campaign",
        "date_preset": date_preset,
        "fields": "campaign_name,objective,spend,impressions,clicks,ctr,cpm,reach,actions,action_values,cost_per_action_type",
        "limit": 100,
    }

    try:
        r = requests.get(url, params=params, timeout=20)

        print("\n" + "=" * 70)
        print("ACCOUNT:", account_id)
        print("STATUS:", r.status_code)
        print("RESPONSE:", r.text[:1000])
        print("=" * 70 + "\n")

        data = r.json()
        if "error" in data:
            print(f"❌ Meta error: {data['error']['message']}")
            return []
        return data.get("data", [])

    except Exception as e:
        print(f"❌ Fetch error: {e}")
        return []

def sf(val):
    try:    return float(val)
    except: return 0.0

def get_action(actions, atype):
    for a in (actions or []):
        if a.get("action_type") == atype:
            return int(float(a.get("value", 0)))
    return 0

def get_action_val(vals, atype):
    for a in (vals or []):
        if a.get("action_type") == atype:
            return float(a.get("value", 0))
    return 0.0

def get_cpa(cpa_list, atype):
    for a in (cpa_list or []):
        if a.get("action_type") == atype:
            return float(a.get("value", 0))
    return 0.0

def get_kpis(c):
    obj         = c.get("objective", "UNKNOWN")
    spend       = sf(c.get("spend", 0))
    clicks      = sf(c.get("clicks", 0))
    ctr         = sf(c.get("ctr", 0))
    cpm         = sf(c.get("cpm", 0))
    reach       = sf(c.get("reach", 0))
    impressions = sf(c.get("impressions", 0))
    actions     = c.get("actions", [])
    av          = c.get("action_values", [])
    cpa_list    = c.get("cost_per_action_type", [])

    k = {
        "obj": obj, "spend": spend, "clicks": clicks, "ctr": ctr,
        "cpm": cpm, "reach": reach, "impressions": impressions,
        "purchases": 0, "revenue": 0.0, "cpa": 0.0, "roas": 0.0,
        "messages": 0, "leads": 0, "cpl": 0.0,
    }

    if obj in ["OUTCOME_SALES", "CONVERSIONS", "PRODUCT_CATALOG_SALES"]:
        purchases = get_action(actions, "purchase")
        revenue   = get_action_val(av, "purchase")
        cpa       = get_cpa(cpa_list, "purchase")
        roas      = round(revenue / spend, 2) if spend > 0 else 0
        k.update({"purchases": purchases, "revenue": revenue, "cpa": cpa, "roas": roas})

    elif obj in ["OUTCOME_ENGAGEMENT", "MESSAGES", "OUTCOME_LEADS"]:
        msgs  = get_action(actions, "onsite_conversion.messaging_conversation_started_7d")
        if not msgs:
            msgs = get_action(actions, "onsite_conversion.total_messaging_connection")
        leads = get_action(actions, "lead")
        cpl   = get_cpa(cpa_list, "lead") if leads > 0 else 0
        k.update({"messages": msgs, "leads": leads, "cpl": cpl})

    return k

def campaign_row(name, k):
    obj, spend = k["obj"], k["spend"]
    if spend == 0:
        sc, st = "#94A3B8", "No Spend"
    elif obj in ["OUTCOME_SALES", "CONVERSIONS", "PRODUCT_CATALOG_SALES"]:
        good = k["cpa"] <= MAX_CPA and k["purchases"] > 0
        sc   = "#16A34A" if good else "#DC2626"
        st   = "🟢 Good" if good else "🔴 Review"
    else:
        sc, st = "#0D9488", "🔵 Active"

    if obj in ["OUTCOME_SALES", "CONVERSIONS", "PRODUCT_CATALOG_SALES"]:
        cols = f"<td>{k['purchases']}</td><td>Rs.{k['cpa']:.0f}</td><td>{k['roas']}x</td><td>{k['ctr']:.1f}%</td>"
    elif obj in ["OUTCOME_ENGAGEMENT", "MESSAGES", "OUTCOME_LEADS"]:
        cols = f"<td>{k['messages']} msgs</td><td>{k['leads']} leads</td><td>Rs.{k['cpl']:.0f}</td><td>{k['ctr']:.1f}%</td>"
    else:
        cols = f"<td>{int(k['reach']):,}</td><td>Rs.{k['cpm']:.0f}</td><td>{int(k['impressions']):,}</td><td>{k['ctr']:.1f}%</td>"

    return f"""<tr style="border-bottom:1px solid #E2E8F0;">
        <td style="padding:8px;font-weight:bold;color:#1A2B5E;">{name[:40]}</td>
        <td style="padding:8px;text-align:center;">
            <span style="background:{sc};color:white;padding:2px 8px;border-radius:10px;font-size:11px;">{st}</span>
        </td>
        <td style="padding:8px;text-align:center;">Rs.{spend:.0f}</td>
        {cols}
    </tr>"""

def build_alerts_html(all_client_data):
    alerts = []
    for client in all_client_data:
        for name, k in client["campaigns"]:
            if k["spend"] > 0:
                if k.get("cpa", 0) > MAX_CPA and k.get("purchases", 0) > 0:
                    alerts.append(f"<p style='color:#DC2626;'>🚨 High CPA — {name}: Rs.{k['cpa']:.0f} (Limit Rs.{MAX_CPA:.0f})</p>")
                if k.get("ctr", 0) < MIN_CTR and k["spend"] > 200:
                    alerts.append(f"<p style='color:#B45309;'>⚠️ Low CTR — {name}: {k['ctr']:.1f}% (Min {MIN_CTR}%)</p>")
                if k.get("roas", 0) >= MIN_ROAS and k.get("purchases", 0) > 0:
                    alerts.append(f"<p style='color:#16A34A;'>🎉 Great ROAS — {name}: {k['roas']}x — Scale budget!</p>")
    return "".join(alerts) if alerts else "<p style='color:#16A34A;'>✅ No alerts — all campaigns performing well!</p>"

def build_daily_html(all_client_data, date_str):
    total_spend    = sum(d["total_spend"]    for d in all_client_data)
    total_orders   = sum(d["total_orders"]   for d in all_client_data)
    total_messages = sum(d["total_messages"] for d in all_client_data)
    total_leads    = sum(d["total_leads"]    for d in all_client_data)

    client_sections = ""
    for client in all_client_data:
        rows = "".join(campaign_row(n, k) for n, k in client["campaigns"])
        client_sections += f"""
        <div style="margin-bottom:25px;">
            <h3 style="color:#1A2B5E;border-left:4px solid #0D9488;padding-left:10px;margin-bottom:8px;">{client['name']}</h3>
            <p style="color:#64748B;font-size:13px;margin-bottom:10px;">
                💰 Spend: <b>Rs.{client['total_spend']:.0f}</b> &nbsp;|&nbsp;
                🛒 Orders: <b>{client['total_orders']}</b> &nbsp;|&nbsp;
                💬 Messages: <b>{client['total_messages']}</b> &nbsp;|&nbsp;
                📋 Leads: <b>{client['total_leads']}</b>
            </p>
            <table style="width:100%;border-collapse:collapse;font-size:13px;">
                <thead><tr style="background:#F8FAFC;color:#64748B;font-size:11px;">
                    <th style="padding:8px;text-align:left;">Campaign</th>
                    <th style="padding:8px;">Status</th>
                    <th style="padding:8px;">Spend</th>
                    <th style="padding:8px;">Orders/Msgs</th>
                    <th style="padding:8px;">CPA/CPL</th>
                    <th style="padding:8px;">ROAS/Leads</th>
                    <th style="padding:8px;">CTR</th>
                </tr></thead>
                <tbody>{rows if rows else "<tr><td colspan='7' style='padding:20px;text-align:center;color:#94A3B8;'>No active campaigns today</td></tr>"}</tbody>
            </table>
        </div>"""

    return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#F8FAFC;">
    <div style="background:#1A2B5E;padding:25px;border-radius:12px;margin-bottom:20px;">
        <h1 style="color:white;margin:0;font-size:22px;">📊 MIK SERVICES Daily Report</h1>
        <p style="color:#93C5FD;margin:5px 0 0;">{date_str}</p>
    </div>
    <div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
        <div style="flex:1;background:white;padding:16px;border-radius:10px;border-left:4px solid #0D9488;min-width:120px;">
            <p style="color:#64748B;margin:0;font-size:12px;">Total Spend</p>
            <h2 style="color:#1A2B5E;margin:4px 0 0;">Rs.{total_spend:.0f}</h2>
        </div>
        <div style="flex:1;background:white;padding:16px;border-radius:10px;border-left:4px solid #F97316;min-width:120px;">
            <p style="color:#64748B;margin:0;font-size:12px;">Orders</p>
            <h2 style="color:#1A2B5E;margin:4px 0 0;">{total_orders}</h2>
        </div>
        <div style="flex:1;background:white;padding:16px;border-radius:10px;border-left:4px solid #25D366;min-width:120px;">
            <p style="color:#64748B;margin:0;font-size:12px;">Messages</p>
            <h2 style="color:#1A2B5E;margin:4px 0 0;">{total_messages}</h2>
        </div>
        <div style="flex:1;background:white;padding:16px;border-radius:10px;border-left:4px solid #7C3AED;min-width:120px;">
            <p style="color:#64748B;margin:0;font-size:12px;">Leads</p>
            <h2 style="color:#1A2B5E;margin:4px 0 0;">{total_leads}</h2>
        </div>
    </div>
    <div style="background:white;padding:20px;border-radius:12px;margin-bottom:20px;">
        <h2 style="color:#1A2B5E;margin-top:0;font-size:15px;">📋 Campaign Performance</h2>
        {client_sections}
    </div>
    <div style="background:white;padding:20px;border-radius:12px;margin-bottom:20px;">
        <h2 style="color:#1A2B5E;margin-top:0;font-size:15px;">🚨 Alerts</h2>
        {build_alerts_html(all_client_data)}
    </div>
    <div style="background:#1A2B5E;padding:12px;border-radius:10px;text-align:center;">
        <p style="color:#93C5FD;margin:0;font-size:11px;"> Powered by NAXTECK MARKETTING SOLUTIONS — {date_str}</p>
    </div>
    </body></html>"""

def build_alert_email_html(alerts_list, date_str):
    alerts_body = "".join(f"<p style='margin:8px 0;font-size:13px;'>{a}</p>" for a in alerts_list)
    return f"""<!DOCTYPE html><html><body style="font-family:Arial,sans-serif;max-width:700px;margin:0 auto;padding:20px;background:#F8FAFC;">
    <div style="background:#DC2626;padding:20px;border-radius:12px;margin-bottom:20px;">
        <h1 style="color:white;margin:0;font-size:20px;">🚨 MIK Alert</h1>
        <p style="color:#FEE2E2;margin:5px 0 0;">{date_str}</p>
    </div>
    <div style="background:white;padding:20px;border-radius:12px;">
        <h2 style="color:#1A2B5E;margin-top:0;font-size:15px;">⚠️ Action Required</h2>
        {alerts_body}
    </div>
    <div style="background:#1A2B5E;padding:12px;border-radius:10px;text-align:center;margin-top:20px;">
        <p style="color:#93C5FD;margin:0;font-size:11px;"> Powered by NAXTECK MARKETTING SOLUTIONS — {date_str}</p>
    </div>
    </body></html>"""

def fetch_all_clients(date_preset="yesterday"):
    all_client_data = []
    for i, account_id in enumerate(AD_ACCOUNTS):
        client_name = CLIENT_NAMES[i].strip() if i < len(CLIENT_NAMES) else account_id
        campaigns   = get_insights(account_id, date_preset)
        client_data = {
            "name": client_name, "campaigns": [],
            "total_spend": 0, "total_orders": 0,
            "total_messages": 0, "total_leads": 0,
        }
        for c in campaigns:
            name = c.get("campaign_name", "Unknown")
            k    = get_kpis(c)
            client_data["campaigns"].append((name, k))
            client_data["total_spend"]    += k["spend"]
            client_data["total_orders"]   += k.get("purchases", 0)
            client_data["total_messages"] += k.get("messages", 0)
            client_data["total_leads"]    += k.get("leads", 0)
        all_client_data.append(client_data)
    return all_client_data

def send_daily_report():
    print(f"\n📊 [{datetime.now().strftime('%H:%M')}] Sending daily report...")
    date_str        = datetime.now().strftime("%d %B %Y — %I:%M %p")
    all_client_data = fetch_all_clients("yesterday")
    html            = build_daily_html(all_client_data, date_str)
    send_email(f"📊 MIK CLIENTS DAILY REPORTS — {datetime.now().strftime('%d %b %Y')}", html)
    print("✅ Daily report sent!\n")

def check_alerts_hourly():
    print(f"\n🔍 [{datetime.now().strftime('%H:%M')}] Checking alerts silently...")
    all_client_data = fetch_all_clients("yesterday")
    alerts          = []

    for client in all_client_data:
        for name, k in client["campaigns"]:
            if k["spend"] > 0:
                if k.get("cpa", 0) > MAX_CPA and k.get("purchases", 0) > 0:
                    alerts.append(f"🚨 High CPA — {name} ({client['name']}): Rs.{k['cpa']:.0f} — Limit Rs.{MAX_CPA:.0f}")
                if k.get("ctr", 0) < MIN_CTR and k["spend"] > 200:
                    alerts.append(f"⚠️ Low CTR — {name} ({client['name']}): {k['ctr']:.1f}% — Min {MIN_CTR}%")
                if k.get("roas", 0) >= MIN_ROAS and k.get("purchases", 0) > 0:
                    alerts.append(f"🎉 Great ROAS — {name} ({client['name']}): {k['roas']}x — Consider scaling!")

    if alerts:
        print(f"🚨 {len(alerts)} alerts found — sending email!")
        date_str = datetime.now().strftime("%d %B %Y — %I:%M %p")
        html     = build_alert_email_html(alerts, date_str)
        send_email(f"🚨 MIK Alert — {len(alerts)} Action(s) Needed — {datetime.now().strftime('%d %b %Y %I:%M %p')}", html)
    else:
        print("✅ All good — no alerts — no email sent!")

def run():
    print(f"\n🚀 NAXTECK Email Automation Started!")
    print(f"📊 Daily report  : every day at {REPORT_TIME}")
    print(f"🔍 Alert check   : every hour — email only if triggered")
    print(f"📧 Sending to    : {EMAIL_TO}")
    print("─" * 50)
    send_daily_report()
    check_alerts_hourly()
    schedule.every().day.at(REPORT_TIME).do(send_daily_report)
    schedule.every(1).hours.do(check_alerts_hourly)
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    run()
