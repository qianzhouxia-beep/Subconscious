"""
Email Templates for Subconscious Mirror
Production-grade HTML email templates with SaaS-level quality
Supports order confirmation, dream report, and pro activation emails
"""

import os
import re

# Email service configuration (using SMTP)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.larksuite.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")
FROM_EMAIL = "Subconscious Mirror <billing@api-tokenmaster.com>"

# Brand assets
BRAND_URL = "https://mirror.api-tokenmaster.com"
HEADER_IMAGE_URL = "https://cdn.subconsciousmirror.ai/email/subconscious-header.png"  # Replace with actual CDN URL


def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ""
    return (str(text)
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#39;'))


def get_order_confirmation_template(data, lang="en"):
    """
    Order confirmation email - Premium SaaS style
    data: dict with keys: customer_name, product_name, order_id, amount, date, status, cta_link
    """
    # Default values
    customer_name = escape_html(data.get('customer_name', 'Seeker'))
    product_name = escape_html(data.get('product_name', 'Subconscious Mirror PRO'))
    order_id = escape_html(data.get('order_id', 'N/A'))
    amount = escape_html(data.get('amount', '$9.90'))
    date = escape_html(data.get('date', 'N/A'))
    status = escape_html(data.get('status', 'PAID'))
    cta_link = data.get('cta_link', BRAND_URL)
    
    # Language-specific content
    content = {
        "en": {
            "title": "Subconscious Mirror",
            "tagline": "Reflect. Understand. Transform.",
            "heading": "ORDER CONFIRMED",
            "welcome": "Welcome to the Inner Sanctum, Seeker.",
            "item_label": "Item",
            "amount_label": "Amount",
            "order_id_label": "Order ID",
            "date_label": "Date",
            "status_label": "Status",
            "unlocked_heading": "Your Vision is Now Expanded. Unlocked Powers:",
            "powers": [
                "Infinite Symbolic Reasoning via DeepSeek-R1",
                "Neural Dream Visualization (Flux.1 Pro)",
                "Full Destiny Prophecy Archiving"
            ],
            "cta_button": "ENTER THE MIRROR",
            "footer": "Official Purchase Receipt • Subconscious Mirror AI Lab"
        },
        "zh": {
            "title": "潜意识之镜",
            "tagline": "映照 · 理解 · 蜕变",
            "heading": "订单已确认",
            "welcome": "欢迎来到内在圣所，寻求者。",
            "item_label": "商品",
            "amount_label": "金额",
            "order_id_label": "订单号",
            "date_label": "日期",
            "status_label": "状态",
            "unlocked_heading": "您的视野现已拓展。已解锁权限：",
            "powers": [
                "DeepSeek-R1 无限符号推理",
                "神经网络梦境可视化 (Flux.1 Pro)",
                "完整命运预言存档"
            ],
            "cta_button": "进入魔镜",
            "footer": "官方购买凭证 • 潜意识之镜 AI 实验室"
        }
    }
    
    c = content.get(lang, content["en"])
    
    # Build powers list HTML
    powers_html = "".join([f'<li style="margin:6px 0;">✓ {escape_html(p)}</li>' for p in c["powers"]])
    
    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{c['title']} - Order Confirmation</title>
<style>
 body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
 table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; }}
 img {{ -ms-interpolation-mode:bicubic; }}
 body {{ margin:0; padding:0; width:100% !important; height:100% !important; background-color:#050816; font-family:Arial, sans-serif; color:#ffffff; }}
 @media screen and (max-width:600px){{
 .container {{ width:100% !important; padding:20px !important; }}
 h1 {{ font-size:24px !important; }}
 h2 {{ font-size:20px !important; }}
 .cta-button a {{ font-size:16px !important; padding:12px 30px !important; }}
 }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#050816; font-family:Arial, sans-serif; color:#ffffff;">

<!-- Wrapper Table -->
<table border="0" cellpadding="0" cellspacing="0" width="100%">
 <tr>
 <td align="center" valign="top">

 <!-- Header Image -->
 <table border="0" cellpadding="0" cellspacing="0" width="600" class="container">
 <tr>
 <td align="center" valign="top">
 <img src="{HEADER_IMAGE_URL}" alt="{c['title']}" width="600" style="display:block; width:100%; max-width:600px; border-radius:12px 12px 0 0;">
 </td>
 </tr>
 </table>

 <!-- Content Container -->
 <table border="0" cellpadding="0" cellspacing="0" width="600" class="container" style="background:rgba(5,8,22,0.88); border-radius:0 0 24px 24px; margin-top:-8px;">
 <tr>
 <td style="padding:40px 30px; text-align:center;">

 <!-- Title -->
 <h1 style="margin:0; font-size:28px; color:#b9a6ff;">{c['title']}</h1>
 <p style="margin:5px 0 20px 0; font-size:16px; color:#ccc;">{c['tagline']}</p>

 <!-- Order Confirmation -->
 <h2 style="margin:0 0 20px 0; font-size:22px; color:#0ff;">{c['heading']}</h2>
 <p style="margin:0 0 20px 0; font-size:16px; color:#ccc;">{c['welcome']}</p>

 <!-- Order Details Table -->
 <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:rgba(20,20,50,0.6); border-radius:12px; padding:20px; margin-bottom:20px;">
 <tr>
 <td style="padding:8px 0; font-weight:bold; color:#0ff;">{c['item_label']}:</td>
 <td style="padding:8px 0; color:#ccc;">{product_name}</td>
 </tr>
 <tr>
 <td style="padding:8px 0; font-weight:bold; color:#0ff;">{c['amount_label']}:</td>
 <td style="padding:8px 0; color:#ccc;">{amount}</td>
 </tr>
 <tr>
 <td style="padding:8px 0; font-weight:bold; color:#0ff;">{c['order_id_label']}:</td>
 <td style="padding:8px 0; color:#ccc;">{order_id}</td>
 </tr>
 <tr>
 <td style="padding:8px 0; font-weight:bold; color:#0ff;">{c['date_label']}:</td>
 <td style="padding:8px 0; color:#ccc;">{date}</td>
 </tr>
 <tr>
 <td style="padding:8px 0; font-weight:bold; color:#0ff;">{c['status_label']}:</td>
 <td style="padding:8px 0; color:#0f0; font-weight:bold;">{status}</td>
 </tr>
 </table>

 <!-- Unlocked Powers -->
 <h2 style="margin:20px 0 10px 0; font-size:20px; color:#0ff;">{c['unlocked_heading']}</h2>
 <ul style="list-style:none; padding:0; margin:0 0 30px 0; color:#9ccfff; text-align:left;">
 {powers_html}
 </ul>

 <!-- CTA Button -->
 <div class="cta-button" style="margin:30px 0;">
 <a href="{cta_link}" style="background:linear-gradient(135deg, #00E5FF, #7B61FF); padding:15px 40px; color:#fff; font-size:18px; font-weight:bold; text-decoration:none; border-radius:8px; display:inline-block;">{c['cta_button']}</a>
 </div>

 <!-- Footer -->
 <p style="font-size:12px; color:#666; margin-top:30px;">{c['footer']}<br>
 Powered by TokenMaster Global</p>

 </td>
 </tr>
 </table>

 </td>
 </tr>
</table>

</body>
</html>"""
    
    return html


def get_dream_report_template(data, lang="en"):
    """
    Dream report ready email
    data: dict with keys: dream_title, session_url, report_preview
    """
    dream_title = escape_html(data.get('dream_title', 'Your Dream'))
    session_url = data.get('session_url', BRAND_URL)
    report_preview = escape_html(data.get('report_preview', ''))[:200] + "..." if data.get('report_preview') else ""
    
    content = {
        "en": {
            "title": "Subconscious Mirror",
            "heading": "🔮 YOUR DREAM REPORT IS READY",
            "welcome": "The veil has been lifted. Your subconscious speaks.",
            "cta_button": "VIEW FULL REPORT",
            "footer": "Subconscious Mirror AI Lab • Powered by TokenMaster Global"
        },
        "zh": {
            "title": "潜意识之镜",
            "heading": "🔮 您的解梦报告已就绪",
            "welcome": "帷幕已揭开。你的潜意识正在诉说。",
            "cta_button": "查看完整报告",
            "footer": "潜意识之镜 AI 实验室 • TokenMaster Global 技术支持"
        }
    }
    
    c = content.get(lang, content["en"])
    
    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{c['title']} - Dream Report Ready</title>
<style>
 body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
 table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; }}
 img {{ -ms-interpolation-mode:bicubic; }}
 body {{ margin:0; padding:0; width:100% !important; height:100% !important; background-color:#050816; font-family:Arial, sans-serif; color:#ffffff; }}
 @media screen and (max-width:600px){{
 .container {{ width:100% !important; padding:20px !important; }}
 h1 {{ font-size:24px !important; }}
 h2 {{ font-size:20px !important; }}
 .cta-button a {{ font-size:16px !important; padding:12px 30px !important; }}
 }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#050816; font-family:Arial, sans-serif; color:#ffffff;">

<table border="0" cellpadding="0" cellspacing="0" width="100%">
 <tr>
 <td align="center" valign="top">

 <!-- Header Image -->
 <table border="0" cellpadding="0" cellspacing="0" width="600" class="container">
 <tr>
 <td align="center" valign="top">
 <img src="{HEADER_IMAGE_URL}" alt="{c['title']}" width="600" style="display:block; width:100%; max-width:600px; border-radius:12px 12px 0 0;">
 </td>
 </tr>
 </table>

 <!-- Content Container -->
 <table border="0" cellpadding="0" cellspacing="0" width="600" class="container" style="background:rgba(5,8,22,0.88); border-radius:0 0 24px 24px; margin-top:-8px;">
 <tr>
 <td style="padding:40px 30px; text-align:center;">
 <h1 style="margin:0; font-size:28px; color:#b9a6ff;">{c['title']}</h1>
 <p style="margin:5px 0 20px 0; font-size:16px; color:#ccc;">Reflect • Understand • Transform</p>

 <h2 style="margin:0 0 20px 0; font-size:22px; color:#0ff;">{c['heading']}</h2>
 <p style="margin:0 0 20px 0; font-size:16px; color:#ccc;">{c['welcome']}</p>

 <!-- Dream Preview -->
 <table border="0" cellpadding="0" cellspacing="0" width="100%" style="background:rgba(20,20,50,0.6); border-radius:12px; padding:20px; margin-bottom:20px; text-align:left;">
 <tr>
 <td style="padding:8px 0; color:#ccc; font-size:14px;">
 <strong style="color:#b9a6ff;">{dream_title}</strong><br><br>
 {report_preview}
 </td>
 </tr>
 </table>

 <!-- CTA Button -->
 <div class="cta-button" style="margin:30px 0;">
 <a href="{session_url}" style="background:linear-gradient(135deg, #00E5FF, #7B61FF); padding:15px 40px; color:#fff; font-size:18px; font-weight:bold; text-decoration:none; border-radius:8px; display:inline-block;">{c['cta_button']}</a>
 </div>

 <p style="font-size:12px; color:#666; margin-top:30px;">{c['footer']}</p>
 </td>
 </tr>
 </table>

 </td>
 </tr>
</table>

</body>
</html>"""
    
    return html


def get_pro_activation_template(data, lang="en"):
    """
    PRO membership activation email
    data: dict with keys: customer_name, features, cta_link
    """
    customer_name = escape_html(data.get('customer_name', 'Seeker'))
    cta_link = data.get('cta_link', BRAND_URL)
    
    content = {
        "en": {
            "title": "Subconscious Mirror",
            "heading": "🚀 WELCOME TO PRO",
            "welcome": f"Welcome, {customer_name}. Your journey into the subconscious just got deeper.",
            "features_heading": "What You've Unlocked:",
            "features": [
                "Unlimited AI Dream Analysis",
                "Deep Symbolic Interpretation", 
                "Personalized Dream Insights",
                "Dream History Archive",
                "Priority AI Processing",
                "Lifetime Access"
            ],
            "cta_button": "EXPLORE PRO FEATURES",
            "footer": "Subconscious Mirror AI Lab • Powered by TokenMaster Global"
        },
        "zh": {
            "title": "潜意识之镜",
            "heading": "🚀 欢迎加入 PRO",
            "welcome": f"欢迎，{customer_name}。您对潜意识的探索即将进入更深层次。",
            "features_heading": "您已解锁的功能：",
            "features": [
                "无限 AI 解梦分析",
                "深度符号解读",
                "个性化梦境洞察",
                "梦境历史存档",
                "优先 AI 处理",
                "终身访问权限"
            ],
            "cta_button": "探索 PRO 功能",
            "footer": "潜意识之镜 AI 实验室 • TokenMaster Global 技术支持"
        }
    }
    
    c = content.get(lang, content["en"])
    features_html = "".join([f'<li style="margin:8px 0; color:#9ccfff;">✓ {escape_html(f)}</li>' for f in c["features"]])
    
    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{c['title']} - PRO Activated</title>
<style>
 body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
 table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; }}
 img {{ -ms-interpolation-mode:bicubic; }}
 body {{ margin:0; padding:0; width:100% !important; height:100% !important; background-color:#050816; font-family:Arial, sans-serif; color:#ffffff; }}
 @media screen and (max-width:600px){{
 .container {{ width:100% !important; padding:20px !important; }}
 h1 {{ font-size:24px !important; }}
 h2 {{ font-size:20px !important; }}
 .cta-button a {{ font-size:16px !important; padding:12px 30px !important; }}
 }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#050816; font-family:Arial, sans-serif; color:#ffffff;">

<table border="0" cellpadding="0" cellspacing="0" width="100%">
 <tr>
 <td align="center" valign="top">

 <!-- Header Image -->
 <table border="0" cellpadding="0" cellspacing="0" width="600" class="container">
 <tr>
 <td align="center" valign="top">
 <img src="{HEADER_IMAGE_URL}" alt="{c['title']}" width="600" style="display:block; width:100%; max-width:600px; border-radius:12px 12px 0 0;">
 </td>
 </tr>
 </table>

 <!-- Content Container -->
 <table border="0" cellpadding="0" cellspacing="0" width="600" class="container" style="background:rgba(5,8,22,0.88); border-radius:0 0 24px 24px; margin-top:-8px;">
 <tr>
 <td style="padding:40px 30px; text-align:center;">
 <h1 style="margin:0; font-size:28px; color:#b9a6ff;">{c['title']}</h1>
 <p style="margin:5px 0 20px 0; font-size:16px; color:#ccc;">Reflect • Understand • Transform</p>

 <h2 style="margin:0 0 20px 0; font-size:22px; color:#7B61FF;">{c['heading']}</h2>
 <p style="margin:0 0 30px 0; font-size:16px; color:#ccc;">{c['welcome']}</p>

 <!-- Features -->
 <h3 style="margin:0 0 15px 0; font-size:18px; color:#0ff;">{c['features_heading']}</h3>
 <ul style="list-style:none; padding:0; margin:0 0 30px 0; text-align:left; display:inline-block;">
 {features_html}
 </ul>

 <!-- CTA Button -->
 <div class="cta-button" style="margin:30px 0;">
 <a href="{cta_link}" style="background:linear-gradient(135deg, #00E5FF, #7B61FF); padding:15px 40px; color:#fff; font-size:18px; font-weight:bold; text-decoration:none; border-radius:8px; display:inline-block;">{c['cta_button']}</a>
 </div>

 <p style="font-size:12px; color:#666; margin-top:30px;">{c['footer']}</p>
 </td>
 </tr>
 </table>

 </td>
 </tr>
</table>

</body>
</html>"""
    
    return html


def send_email(to_email, subject, html_content):
    """
    Send email using SMTP
    Returns: (success: bool, error_message: str or None)
    """
    if not SMTP_USER or not SMTP_PASS:
        print(f"[Email] SMTP credentials not configured, skipping email to {to_email}")
        return False, "SMTP credentials not configured"
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.header import Header
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = Header(subject, 'utf-8')
        msg['From'] = FROM_EMAIL
        msg['To'] = to_email
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html', 'utf-8')
        msg.attach(html_part)
        
        # Connect to SMTP server (Feishu uses SSL on port 465)
        import ssl
        context = ssl.create_default_context()
        if SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=30, context=context)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30)
            server.starttls(context=context)
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [to_email], msg.as_string())
        server.quit()
        
        print(f"[Email] Sent to {to_email}: {subject}")
        return True, None
    
    except Exception as e:
        error_msg = str(e)
        print(f"[Email] SMTP Error: {error_msg}")
        return False, error_msg


def send_dream_report(email, report_data, lang="en"):
    """
    Send dream report ready email
    report_data: dict with keys: dream_title, session_url, report_preview
    """
    subjects = {
        "en": "🔮 Your Dream Report Is Ready",
        "zh": "🔮 您的解梦报告已就绪"
    }
    
    html = get_dream_report_template(report_data, lang)
    return send_email(email, subjects.get(lang, subjects["en"]), html)


def get_order_confirmed_block(order_data, lang="en"):
    """
    Generate the ORDER CONFIRMED content block matching ChatGPT design.
    Includes: billing details table + unlocked powers list.
    order_data: dict with keys:
        item_name, item_subtitle, amount, amount_currency, amount_symbol,
        order_id, order_date, order_status, status_label,
        unlocked_powers (list of dicts with 'name' and 'desc')
    """
    item_name = escape_html(order_data.get('item_name', 'Subconscious Mirror - PRO STABLE'))
    item_subtitle = escape_html(order_data.get('item_subtitle', 'Lifetime Access'))
    amount = escape_html(str(order_data.get('amount', '9.90')))
    amount_symbol = escape_html(order_data.get('amount_symbol', '$'))
    order_id = escape_html(order_data.get('order_id', 'REDEEM_SM-000'))
    order_date = escape_html(order_data.get('order_date', '2026-01-01 00:00:00 UTC'))
    order_status = escape_html(order_data.get('order_status', 'PAID'))
    status_label = escape_html(order_data.get('status_label', 'SUCCESS'))
    unlocked_powers = order_data.get('unlocked_powers', [
        {'name': 'Infinite Symbolic Reasoning', 'desc': 'via DeepSeek-R1'},
        {'name': 'Neural Dream Visualization', 'desc': 'Flux.1 Pro'},
        {'name': 'Full Destiny Prophecy Archiving', 'desc': ''},
    ])

    labels = {
        "en": {
            "title": "ORDER CONFIRMED",
            "awakening": "AWAKENING",
            "billing_details": "Billing Details",
            "item": "Item",
            "amount": "Amount",
            "order_id": "Order ID",
            "date": "Date",
            "status": "Status",
            "paid_status": "PAID / SUCCESS",
            "unlocked_powers": "UNLOCKED POWERS",
            "thank_you": "Thank you for your order. Your PRO membership is now active.",
        },
        "zh": {
            "title": "订单已确认",
            "awakening": "觉醒",
            "billing_details": "账单明细",
            "item": "项目",
            "amount": "金额",
            "order_id": "订单号",
            "date": "日期",
            "status": "状态",
            "paid_status": "已支付 / 成功",
            "unlocked_powers": "已解锁权益",
            "thank_you": "感谢您的订单。您的 PRO 会员已激活。",
        }
    }
    l = labels.get(lang, labels["en"])

    # Build unlocked powers list
    powers_html = ''
    for p in unlocked_powers:
        power_name = escape_html(p.get('name', ''))
        power_desc = escape_html(p.get('desc', ''))
        desc_html = f' <span style="color:#556677;">{power_desc}</span>' if power_desc else ''
        powers_html += f'''<tr><td style="padding:6px 0; color:#b0b8c8; font-size:14px;">
            <span style="color:#00E5FF; margin-right:8px;">\u2726</span>{power_name}{desc_html}
        </td></tr>'''

    # Billing rows
    billing_rows = f'''<tr>
        <td style="padding:10px 0; font-size:12px; color:#667788; letter-spacing:0.06em; text-transform:uppercase;">{l['item']}</td>
        <td style="padding:10px 0; font-size:14px; color:#b0b8c8; text-align:right;">
            {item_name}<br><span style="font-size:11px; color:#556677;">{item_subtitle}</span>
        </td>
    </tr>
    <tr>
        <td style="padding:10px 0; font-size:12px; color:#667788; letter-spacing:0.06em; text-transform:uppercase;">{l['amount']}</td>
        <td style="padding:10px 0; font-size:18px; color:#00E5FF; text-align:right; font-weight:600;">
            {amount_symbol}{amount}
        </td>
    </tr>
    <tr>
        <td style="padding:10px 0; font-size:12px; color:#667788; letter-spacing:0.06em; text-transform:uppercase;">{l['order_id']}</td>
        <td style="padding:10px 0; font-size:13px; color:#8a9ab0; text-align:right; font-family:monospace;">
            {order_id}
        </td>
    </tr>
    <tr>
        <td style="padding:10px 0; font-size:12px; color:#667788; letter-spacing:0.06em; text-transform:uppercase;">{l['date']}</td>
        <td style="padding:10px 0; font-size:13px; color:#8a9ab0; text-align:right; font-family:monospace;">
            {order_date}
        </td>
    </tr>
    <tr>
        <td style="padding:10px 0; font-size:12px; color:#667788; letter-spacing:0.06em; text-transform:uppercase;">{l['status']}</td>
        <td style="padding:10px 0; font-size:14px; color:#00E57A; text-align:right; font-weight:600;">
            \u2713 &nbsp; {order_status}<br><span style="font-size:10px; color:#00C060; text-transform:uppercase;">{status_label}</span>
        </td>
    </tr>'''

    html = f'''<!-- Order Confirmed Block -->
<div style="margin:24px 0; padding:32px 28px;
            background:linear-gradient(180deg, rgba(20,25,50,0.5) 0%, rgba(10,12,30,0.6) 100%);
            border-radius:16px;
            border:1px solid rgba(0,229,255,0.12);
            box-shadow: 0 0 40px rgba(0,229,255,0.04);">

<!-- ORDER CONFIRMED Header -->
<div style="text-align:center; margin-bottom:24px;">
    <div style="display:inline-block; margin-bottom:12px;
                width:14px; height:14px; border-radius:50%;
                background:radial-gradient(circle, rgba(0,229,255,0.4), transparent 70%);
                box-shadow: 0 0 20px rgba(0,229,255,0.3);">
    </div>
    <h3 style="margin:0 0 6px; font-family:'Georgia','Times New Roman',serif;
               font-size:22px; font-weight:400; color:#00E5FF;
               letter-spacing:0.10em; text-transform:uppercase;">
        {l['title']}
    </h3>
    <p style="margin:0; font-size:11px; color:#667788; letter-spacing:0.15em; text-transform:uppercase;">
        {l['awakening']}
    </p>
</div>

<!-- Divider -->
<table border="0" cellpadding="0" cellspacing="0" width="100%">
    <tr><td style="height:1px; background:linear-gradient(90deg,transparent,rgba(0,229,255,0.10),transparent); font-size:0;">&nbsp;</td></tr>
</table>

<!-- Billing Details -->
<div style="margin-top:20px;">
    <h4 style="margin:0 0 12px; font-size:11px; color:#445566; letter-spacing:0.10em; text-transform:uppercase;">
        {l['billing_details']}
    </h4>
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        {billing_rows}
    </table>
</div>

<!-- Divider -->
<table border="0" cellpadding="0" cellspacing="0" width="100%">
    <tr><td style="padding:16px 0;">
        <div style="height:1px; background:linear-gradient(90deg,transparent,rgba(0,229,255,0.08),transparent); font-size:0;">&nbsp;</div>
    </td></tr>
</table>

<!-- Unlocked Powers -->
<div>
    <h4 style="margin:0 0 14px; font-size:11px; color:#445566; letter-spacing:0.10em; text-transform:uppercase;">
        {l['unlocked_powers']}
    </h4>
    <table border="0" cellpadding="0" cellspacing="0" width="100%">
        {powers_html}
    </table>
</div>

<!-- Thank You -->
<p style="margin:20px 0 0; font-size:12px; color:#667788; font-style:italic; text-align:center;">
    {l['thank_you']}
</p>

</div><!-- /Order Confirmed Block -->'''

    return html


def get_report_content_email(data, report_html, lang="en"):
    """
    Mystical dark-themed email template matching ChatGPT design.
    Full cosmic background + centered dark card + serif brand header + gradient CTA.
    data: dict with keys: customer_name, dream_title, session_url, cta_link, header_logo_b64, order_data
    report_html: raw HTML content of the report
    """
    customer_name = escape_html(data.get('customer_name', 'Seeker'))
    dream_title = escape_html(data.get('dream_title', 'Your Dream Analysis'))
    session_url = data.get('session_url', BRAND_URL)
    cta_link = data.get('cta_link', session_url)
    order_data = data.get('order_data', None)

    content = {
        "en": {
            "title": "Subconscious Mirror",
            "tagline": "REFLECT \u2022 UNDERSTAND \u2022 TRANSFORM",
            "heading": "YOUR DREAM REPORT IS READY",
            "welcome": f"Welcome to the Inner Sanctum, {customer_name}.",
            "sub_tagline": "The veil has been lifted. Your subconscious speaks.",
            "cta_button": "Enter the Mirror",
            "footer_tagline": "Step through. The mirror awaits.",
            "features": [
                ("DREAM", "INSIGHTS"),
                ("AI", "INTERPRETATION"),
                ("SUBCONSCIOUS", "UNLOCKED"),
                ("PERSONAL", "GROWTH"),
            ],
            "footer_receipt": "Official Dream Report",
            "footer_brand": "Subconscious Mirror AI Lab",
        },
        "zh": {
            "title": "\u6f5c\u610f\u8bc6\u4e4b\u955c",
            "tagline": "\u6620\u7167 \u00b7 \u7406\u89e3 \u00b7 \u8715\u53d8",
            "heading": "\u60a8\u7684\u89e3\u68a6\u62a5\u544a\u5df2\u5c31\u7eea",
            "welcome": f"\u6b22\u8fce\u6765\u5230\u5185\u5728\u5723\u6240\uff0c\u5bfb\u6c42\u8005\u3002",
            "sub_tagline": "\u5e37\u5e55\u5df2\u63ed\u5f00\u3002\u4f60\u7684\u6f5c\u610f\u8bc6\u6b63\u5728\u8bc9\u8bf4\u3002",
            "cta_button": "\u8fdb\u5165\u9b54\u955c",
            "footer_tagline": "\u8de8\u8fc7\u8fb9\u754c\u3002\u9b54\u955c\u6b63\u5728\u7b49\u5f85\u3002",
            "features": [
                ("\u68a6\u5883", "\u6d1e\u5bdf"),
                ("AI", "\u89e3\u8bfb"),
                ("\u6f5c\u610f\u8bc6", "\u5524\u9192"),
                ("\u4e2a\u4eba", "\u6210\u957f"),
            ],
            "footer_receipt": "\u5b98\u65b9\u89e3\u68a6\u62a5\u544a",
            "footer_brand": "Subconscious Mirror AI Lab",
        }
    }

    c = content.get(lang, content["en"])
    header_logo_b64 = data.get('header_logo_b64', '')

    # Mystical decorative divider with star
    divider = '<table border="0" cellpadding="0" cellspacing="0" width="100%"><tr><td style="padding:16px 0; text-align:center; color:rgba(137,170,204,0.3); font-size:14px;">\u2726 &nbsp;&nbsp;&nbsp; \u2726 &nbsp;&nbsp;&nbsp; \u2726</td></tr></table>'

    # Feature icons row (4 items)
    features_html = ''
    for top, bottom in c['features']:
        features_html += f'''<td align="center" style="padding:0 8px; width:25%;">
            <div style="font-size:18px; color:#89AACC; margin-bottom:4px;">\u2726</div>
            <div style="font-size:9px; color:#556; letter-spacing:0.08em; line-height:1.4;">{top}<br>{bottom}</div>
        </td>'''

    # Brand header with logo
    if header_logo_b64:
        logo_html = f'''<img src="{header_logo_b64}" width="48" height="48"
             style="display:block; margin:0 auto 16px; border-radius:50%; object-fit:cover;
                    border:1px solid rgba(137,170,204,0.15);
                    filter:drop-shadow(0 0 12px rgba(137,170,204,0.2));">'''
    else:
        logo_html = f'''<div style="font-size:36px; color:#89AACC; text-align:center; margin-bottom:12px;\n                    filter:drop-shadow(0 0 8px rgba(137,170,204,0.3));">\u2726</div>'''

    html = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!--[if mso]><noscript><xml><o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch></o:OfficeDocumentSettings></xml></noscript><![endif]-->
<style>
    body, table, td, a {{ -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%; }}
    table, td {{ mso-table-lspace:0pt; mso-table-rspace:0pt; }}
    img {{ -ms-interpolation-mode:bicubic; border:0; height:auto; line-height:100%; outline:none; text-decoration:none; }}
    body {{ margin:0; padding:0; width:100% !important; background-color:#050510; font-family:'Georgia','Times New Roman',serif; }}
    a {{ color:#00E5FF; text-decoration:none; }}
    @media screen and (max-width:600px){{
        .wrapper {{ width:100% !important; }}
        .content-card {{ padding:32px 20px !important; }}
        h2 {{ font-size:20px !important; }}
        .report-body {{ padding:12px 8px !important; }}
        .cta-button a {{ font-size:15px !important; padding:14px 36px !important; }}
        .features-row td {{ padding:0 4px !important; }}
    }}
</style>
</head>
<body style="margin:0; padding:0; background-color:#050510;">

<!-- Full-width cosmic background wrapper -->
<table border="0" cellpadding="0" cellspacing="0" width="100%" role="presentation">
<tr><td align="center" valign="top" style="padding:40px 16px; background:#050510;">

<!-- Mystical outer glow frame -->
<table border="0" cellpadding="0" cellspacing="0" width="600" class="wrapper" role="presentation"
       style="max-width:600px; border-radius:24px; overflow:hidden;
              background:linear-gradient(180deg, rgba(26,20,60,0.25) 0%, rgba(10,8,30,0.4) 100%);
              border:1px solid rgba(137,170,204,0.10);
              box-shadow: 0 0 60px rgba(120,80,200,0.08), inset 0 1px 0 rgba(137,170,204,0.06);">

<!-- Brand Header -->
<tr><td style="padding:48px 32px 24px; text-align:center; border-bottom:1px solid rgba(137,170,204,0.08);">
    {logo_html}
    <h1 style="margin:0; font-family:'Georgia','Times New Roman',serif; font-size:32px; font-weight:400;
               color:#e8e0f0; letter-spacing:0.04em;
               text-shadow: 0 0 30px rgba(137,170,204,0.15);">
        {c['title']}
    </h1>
    <p style="margin:10px 0 0; font-size:11px; color:#667788; letter-spacing:0.15em; text-transform:uppercase;">
        \u2726 &nbsp; {c['tagline']} &nbsp; \u2726
    </p>
</td></tr>

<!-- Content Card -->
<tr><td class="content-card" style="padding:36px 40px;">

<!-- Heading -->
<div style="text-align:center; margin-bottom:28px;">
    <h2 style="margin:0; font-family:'Georgia','Times New Roman',serif; font-size:26px; font-weight:400;
               color:#00E5FF; letter-spacing:0.06em;">
        {c['heading']}
    </h2>
    <p style="margin:10px 0 0; font-size:15px; color:#a0b0c8;">{c['welcome']}</p>
    <p style="margin:6px 0 0; font-size:13px; color:#667788; font-style:italic;">{c['sub_tagline']}</p>
</div>

<!-- Order Confirmed Block (if order data provided) -->
{'<!-- No order data -->' if not order_data else get_order_confirmed_block(order_data, lang)}

{divider}

<!-- Report Content -->
<div class="report-body" style="color:#b8c0d0; font-size:15px; line-height:1.9;">
    {report_html}
</div>

{divider}

<!-- CTA Button -->
<div style="text-align:center; margin:32px 0 20px;">
    <a href="{cta_link}" target="_blank"
       style="display:inline-block; padding:16px 48px; font-size:16px; font-weight:600; color:#fff;
              text-decoration:none; border-radius:12px;
              background:linear-gradient(135deg, #00E5FF 0%, #7B61FF 50%, #6B2D8E 100%);
              letter-spacing:0.06em;
              box-shadow: 0 6px 32px rgba(0,229,255,0.18), 0 0 60px rgba(123,97,255,0.12);">
        {c['cta_button']}
    </a>
    <p style="margin:16px 0 0; font-size:12px; color:#445566; font-style:italic;">
        {c['footer_tagline']}
    </p>
</div>

</td></tr>

<!-- Features Icons Row -->
<tr><td style="padding:0 40px 24px;">
    <table border="0" cellpadding="0" cellspacing="0" width="100%" class="features-row">
        <tr>
            {features_html}
        </tr>
    </table>
</td></tr>

<!-- Footer -->
<tr><td style="padding:20px 40px 32px; text-align:center; border-top:1px solid rgba(137,170,204,0.06);">
    <p style="margin:0; font-size:11px; color:#445566; letter-spacing:0.04em;">
        {c['footer_receipt']} &bull; {c['footer_brand']}
    </p>
    <p style="margin:8px 0 0; font-size:10px; color:#334;">
        &copy; 2026 Subconscious Mirror AI Labs
    </p>
</td></tr>

</table><!-- /Mystical Card -->

</td></tr>
</table><!-- /Background -->

</body>
</html>'''

    return html


def send_report_content_email(email, report_data, report_html, lang="en"):
    """
    Send full dream report wrapped in professional email template.
    report_data: dict with keys: customer_name, dream_title, session_url, cta_link
    report_html: the actual report content HTML
    """
    subjects = {
        "en": "\U0001f52e Your Subconscious Mirror \u2014 Dream Report",
        "zh": "\U0001f52e \u60a8\u7684\u6f5c\u610f\u8bc6\u4e4b\u955c \u2014 \u68a6\u5883\u62a5\u544a"
    }

    html = get_report_content_email(report_data, report_html, lang)
    return send_email(email, subjects.get(lang, subjects["en"]), html)


def send_order_confirmation(email, order_data, lang="en", customer_name="Seeker", header_logo_b64=""):
    """
    Send standalone Order Confirmation email (no dream report).
    Uses the brand wrapper template with order_data block centered.
    order_data: dict with item_name, amount, order_id, order_date, order_status, unlocked_powers
    """
    subjects = {
        "en": "\u2728 Your Order is Confirmed \u2014 Subconscious Mirror",
        "zh": "\u2728 \u60a8\u7684\u8ba2\u5355\u5df2\u786e\u8ba4 \u2014 \u6f5c\u610f\u8bc6\u4e4b\u955c"
    }

    # Build a minimal report container that ONLY has the order confirmed block
    report_data = {
        'customer_name': customer_name,
        'dream_title': order_data.get('item_name', 'PRO Access'),
        'session_url': BRAND_URL,
        'cta_link': BRAND_URL,
        'header_logo_b64': header_logo_b64,
        'order_data': order_data,
    }

    # Use empty report_html since order block renders independently
    html = get_report_content_email(report_data, '', lang)
    return send_email(email, subjects.get(lang, subjects["en"]), html)


def send_pro_activation(email, user_data, lang="en"):
    """
    Send PRO membership activation email
    user_data: dict with keys: customer_name, features, cta_link
    """
    subjects = {
        "en": "🚀 Welcome To PRO",
        "zh": "🚀 欢迎加入 PRO"
    }
    
    html = get_pro_activation_template(user_data, lang)
    return send_email(email, subjects.get(lang, subjects["en"]), html)

def get_inactive_reengagement_email(data, lang="en"):
    """
    3-day inactive re-engagement email - mystical dark theme.
    data: dict with keys: customer_name, last_dream_date, session_url, cta_link
    """
    customer_name = escape_html(data.get('customer_name', 'Seeker'))
    last_dream_date = data.get('last_dream_date', 'a few days ago')
    session_url = data.get('session_url', BRAND_URL)
    cta_link = data.get('cta_link', session_url)

    content = {
        "en": {
            "title": "Subconscious Mirror",
            "tagline": "The veil grows thin again...",
            "heading": f"{customer_name}, the mirror awaits",
            "body1": f"It's been 3 days since you last gazed into the subconscious. On {last_dream_date}, your dreams revealed patterns waiting to be understood.",
            "body2": "The symbols linger. The insights fade. Return now, before the visions dissolve into the void.",
            "cta_button": "Return to the Mirror",
            "footer": "The mirror never forgets. It only waits.",
            "features": [
                ("3", "DAYS<br>SILENCE"),
                ("∞", "DREAMS<br>UNREAD"),
                ("1", "CLICK<br>RETURN"),
            ],
        },
        "zh": {
            "title": "潜意识之镜",
            "tagline": "面纱再次变薄……",
            "heading": f"{customer_name}，魔镜在等你",
            "body1": f"你已经 3 天没有凝视潜意识了。在 {last_dream_date}，你的梦境揭示了等待被理解的图案。",
            "body2": "符号 lingering。洞察 fading。现在返回，在幻象消散到虚空中之前。",
            "cta_button": "返回魔镜",
            "footer": "魔镜从未忘记。它只是等待。",
            "features": [
                ("3", "天<br>沉默"),
                ("∞", "个<br>未读梦境"),
                ("1", "次<br>点击返回"),
            ],
        }
    }

    c = content.get(lang, content["en"])

    html = f'''<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
    body {{ margin:0; padding:0; background-color:#050510; font-family:'Georgia','Times New Roman',serif; }}
    .background {{ background-color:#050510; padding:40px 0; }}
    .card {{ max-width:600px; margin:0 auto; background:linear-gradient(135deg, #0a0a1a 0%, #050510 100%); border:1px solid rgba(137,170,204,0.15); border-radius:16px; overflow:hidden; }}
    .header {{ padding:48px 40px 32px; text-align:center; }}
    .logo {{ font-size:36px; color:#89AACC; margin-bottom:16px; filter:drop-shadow(0 0 8px rgba(137,170,204,0.3)); }}
    .title {{ font-size:11px; color:rgba(137,170,204,0.5); letter-spacing:0.3em; margin-bottom:12px; }}
    .tagline {{ font-size:13px; color:rgba(137,170,204,0.4); font-style:italic; margin-bottom:24px; }}
    .heading {{ font-size:28px; color:#f5f5f5; line-height:1.3; margin-bottom:20px; }}
    .divider {{ padding:16px 0; text-align:center; color:rgba(137,170,204,0.3); font-size:14px; }}
    .body-text {{ padding:0 40px 24px; font-size:15px; color:rgba(200,200,210,0.8); line-height:1.7; text-align:center; }}
    .features {{ padding:24px 40px; display:table; width:100%; }}
    .features td {{ text-align:center; padding:0 12px; }}
    .feature-num {{ font-size:24px; color:#89AACC; margin-bottom:4px; }}
    .feature-label {{ font-size:9px; color:#556; letter-spacing:0.1em; line-height:1.4; }}
    .cta {{ padding:32px 40px; text-align:center; }}
    .cta a {{ display:inline-block; padding:16px 48px; background:linear-gradient(135deg, #00E5FF 0%, #7B61FF 50%, #6B2D8E 100%); color:#050510; text-decoration:none; border-radius:50px; font-size:16px; font-weight:600; }}
    .footer {{ padding:32px 40px; text-align:center; font-size:12px; color:rgba(137,170,204,0.3); font-style:italic; }}
</style>
</head>
<body>
<table class="background" width="100%" cellpadding="0" cellspacing="0" border="0">
<tr><td>
    <table class="card" cellpadding="0" cellspacing="0" border="0">
        <tr><td class="header">
            <div class="logo">✦</div>
            <div class="title">{c['title']}</div>
            <div class="tagline">{c['tagline']}</div>
            <h2 class="heading">{c['heading']}</h2>
        </td></tr>
        <tr><td class="divider">✦ &nbsp;&nbsp; ✦ &nbsp;&nbsp; ✦</td></tr>
        <tr><td class="body-text">{c['body1']}</td></tr>
        <tr><td class="body-text" style="padding-top:0;">{c['body2']}</td></tr>
        <tr><td>
            <table class="features" cellpadding="0" cellspacing="0" border="0">
                <tr>
                    <td><div class="feature-num">{c['features'][0][0]}</div><div class="feature-label">{c['features'][0][1]}</div></td>
                    <td><div class="feature-num">{c['features'][1][0]}</div><div class="feature-label">{c['features'][1][1]}</div></td>
                    <td><div class="feature-num">{c['features'][2][0]}</div><div class="feature-label">{c['features'][2][1]}</div></td>
                </tr>
            </table>
        </td></tr>
        <tr><td class="cta"><a href="{cta_link}">{c['cta_button']}</a></td></tr>
        <tr><td class="footer">{c['footer']}</td></tr>
    </table>
</td></tr>
</table>
</body>
</html>'''

    return html


def send_inactive_reengagement_email(email, data, lang="en"):
    """
    Send 3-day inactive re-engagement email.
    data: dict with keys: customer_name, last_dream_date, session_url, cta_link
    """
    subjects = {
        "en": "✦ The Mirror Awaits Your Return",
        "zh": "✦ 魔镜等你归来"
    }

    html = get_inactive_reengagement_email(data, lang)
    return send_email(email, subjects.get(lang, subjects["en"]), html)

