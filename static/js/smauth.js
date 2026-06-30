/**
 * SMAuth — Subconscious Mirror 用户账户与支付闭环模块 v3
 * 紫色主题 + 社交登录 + 虚拟币支付 (NOWPayments)
 */
const SMAuth = (function () {
  const API_BASE = "";
  const ACCENT = "#7c5cff";
  const ACCENT_GRADIENT = "linear-gradient(135deg,#7c5cff,#9b7fff)";
  const ACCENT_LIGHT = "rgba(124,92,255,0.3)";
  const ACCENT_TEXT = "#9b7fff";

  // ── i18n helper ──
  function _t(zh, en) {
    return (document.documentElement.lang.startsWith('zh')) ? zh : en;
  }

  let token = localStorage.getItem("sm_token");
  let currentUser = null;
  let premiumStatus = null;

  async function api(path, method, body) {
    const headers = { "Content-Type": "application/json" };
    if (token) headers["Authorization"] = "Bearer " + token;
    const opts = { method: method || "GET", headers };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(API_BASE + path, opts);
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.detail || "Request failed");
    return data;
  }

  async function login(email, password) {
    const data = await api("/api/auth/login", "POST", { email, password });
    token = data.token; currentUser = data.user;
    localStorage.setItem("sm_token", token);
    await fetchPremiumStatus();
    return data;
  }
  function logout() {
    token = null; currentUser = null; premiumStatus = null;
    localStorage.removeItem("sm_token"); updateNavbar();
  }
  async function fetchMe() { if (!token) return null; try { currentUser = await api("/api/user/me"); console.log("[SMAuth] fetchMe OK: " + (currentUser ? currentUser.email : "null")); return currentUser; } catch (e) { console.error("[SMAuth] fetchMe FAILED:", e.message); logout(); return null; } }
  async function fetchPremiumStatus() { if (!token) return null; try { premiumStatus = await api("/api/user/premium-status"); console.log("[SMAuth] premiumStatus:", JSON.stringify(premiumStatus)); return premiumStatus; } catch (e) { console.error("[SMAuth] premiumStatus FAILED:", e.message); return null; } }

  function showModal(html) {
    const overlay = document.createElement("div");
    overlay.id = "sm-modal-overlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:99999;";
    overlay.innerHTML = '<div style="background:#1a1a2e;color:#e0e0e0;padding:32px 36px;border-radius:16px;max-width:440px;width:90%;position:relative;box-shadow:0 0 40px rgba(124,92,255,0.2);border:1px solid rgba(124,92,255,0.3);max-height:90vh;overflow-y:auto;">' + html + "</div>";
    document.body.appendChild(overlay);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) overlay.remove(); });
    return overlay;
  }
  function closeModal() { var el = document.getElementById("sm-modal-overlay"); if (el) el.remove(); }
  function showError(msg) { var el = document.getElementById("sm-error"); if (el) { el.textContent = msg; el.style.display = "block"; } }
  function showSuccess(msg) { var el = document.getElementById("sm-success"); if (el) { el.textContent = msg; el.style.display = "block"; } }

  function btnP() { return "width:100%;padding:10px 20px;background:" + ACCENT_GRADIENT + ";border:none;border-radius:999px;color:#fff;font-size:14px;cursor:pointer;font-weight:600;letter-spacing:0.5px;"; }
  function btnS() { return "width:100%;padding:10px 20px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.15);border-radius:999px;color:#ccc;font-size:14px;cursor:pointer;"; }

  // Social login buttons HTML
  function socialBtns() {
    return '<div style="margin-top:20px;margin-bottom:4px;"><div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;"><div style="flex:1;height:1px;background:rgba(255,255,255,0.08);"></div><span style="color:#666;font-size:12px;">' + _t('或使用以下方式登录', 'or continue with') + '</span><div style="flex:1;height:1px;background:rgba(255,255,255,0.08);"></div></div>' +
      '<button onclick="SMAuth.socialLogin(\'google\')" style="width:100%;padding:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#ccc;cursor:pointer;font-size:13px;display:flex;align-items:center;justify-content:center;gap:6px;">' + googleIcon() + ' ' + _t('使用 Google 登录', 'Sign in with Google') + '</button></div>';
  }
  function googleIcon() { return '<svg width="16" height="16" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>'; }

  async function socialLogin(provider) {
    try {
      var resp = await fetch("/api/auth/social/" + provider);
      var data = await resp.json();
      if (data.auth_url) {
        window.location.href = data.auth_url;
      } else {
        alert(data.detail || _t(provider + ' 登录正在配置中，请使用邮箱登录。', provider + " login is being configured. Please use email."));
      }
    } catch (e) { alert(_t(provider + ' 登录暂时不可用。', provider + " login not available yet.")); }
  }

  function showLoginModal() {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;cursor:pointer;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2"><path d="M6 6l12 12M18 6l-12 12"/></svg></button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';font-weight:600;">' + _t('欢迎回来', 'Welcome Back') + '</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + _t('登录以查看你的梦境解读', 'Log in to access your dream interpretations') + '</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-login-email" placeholder="' + _t('邮箱地址', 'Email') + '" style="width:100%;padding:11px 14px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<input type="password" id="sm-login-password" placeholder="' + _t('密码', 'Password') + '" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._doLogin()" style="' + btnP() + '">' + _t('登录', 'Log In') + '</button>' +
      '<div style="text-align:center;margin-top:12px;font-size:13px;color:#666;">' +
      '<a href="javascript:SMAuth.showForgotModal()" style="color:' + ACCENT_TEXT + ';text-decoration:none;">' + _t('忘记密码？', 'Forgot password?') + '</a>' +
      '<span style="margin:0 8px;">\u00b7</span>' +
      '<a href="javascript:SMAuth.showRegisterModal()" style="color:' + ACCENT_TEXT + ';text-decoration:none;">' + _t('创建账户', 'Create account') + '</a></div>' + socialBtns());
  }

  async function _doLogin() {
    var email = document.getElementById("sm-login-email").value.trim();
    var pwd = document.getElementById("sm-login-password").value;
    try { await login(email, pwd); closeModal(); updateNavbar(); } catch (e) { showError(e.message); }
  }

  function showRegisterModal() {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;cursor:pointer;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2"><path d="M6 6l12 12M18 6l-12 12"/></svg></button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';font-weight:600;">' + _t('创建账户', 'Create Account') + '</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + _t('跨设备安全保存你的购买', 'Secure your purchases across devices') + '</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-reg-email" placeholder="' + _t('邮箱地址', 'Email') + '" style="width:100%;padding:11px 14px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<input type="password" id="sm-reg-password" placeholder="' + _t('密码（8位以上）', 'Password (8+ chars)') + '" style="width:100%;padding:11px 14px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<input type="password" id="sm-reg-confirm" placeholder="' + _t('确认密码', 'Confirm password') + '" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._doRegister()" style="' + btnP() + '">' + _t('创建账户', 'Create Account') + '</button>' +
      '<div style="text-align:center;margin-top:12px;font-size:13px;color:#666;">' + _t('已有账户？', 'Already have an account?') + ' <a href="javascript:SMAuth.showLoginModal()" style="color:' + ACCENT_TEXT + ';text-decoration:none;">' + _t('登录', 'Log in') + '</a></div>' + socialBtns());
  }

  async function _doRegister() {
    var email = document.getElementById("sm-reg-email").value.trim();
    var pwd = document.getElementById("sm-reg-password").value;
    var confirm = document.getElementById("sm-reg-confirm").value;
    if (pwd !== confirm) { showError(_t('两次密码不一致', 'Passwords do not match')); return; }
    try { await api("/api/auth/register", "POST", { email, password: pwd }); await login(email, pwd); closeModal(); updateNavbar(); } catch (e) { showError(e.message); }
  }

  function showForgotModal() {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;cursor:pointer;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2"><path d="M6 6l12 12M18 6l-12 12"/></svg></button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';font-weight:600;">' + _t('重置密码', 'Reset Password') + '</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + _t('输入邮箱地址获取重置链接', 'Enter your email for a reset link') + '</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<div id="sm-success" style="display:none;color:#4ade80;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-forgot-email" placeholder="' + _t('邮箱地址', 'Email') + '" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._doForgot()" style="' + btnP() + '">' + _t('发送重置链接', 'Send Reset Link') + '</button>' +
      '<div style="text-align:center;margin-top:12px;font-size:13px;color:#666;"><a href="javascript:SMAuth.showLoginModal()" style="color:' + ACCENT_TEXT + ';text-decoration:none;">' + _t('返回登录', 'Back to login') + '</a></div>');
  }

  async function _doForgot() {
    var email = document.getElementById("sm-forgot-email").value.trim();
    try { await api("/api/auth/forgot-password", "POST", { email }); showSuccess(_t('如果该邮箱已注册，重置链接已发送。', "If the email exists, a reset link has been sent.")); } catch (e) { showError(e.message); }
  }

  function showPaymentPrompt(planType, planLabel, price) {
    if (token) { showMethodChoice(planType, planLabel, price); return; }
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;cursor:pointer;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2"><path d="M6 6l12 12M18 6l-12 12"/></svg></button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';font-weight:600;">' + _t('安全支付', 'Secure Your Purchase') + '</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + _t('创建账户以保存你的购买记录', 'Create an account to save your purchase') + '</p>' +
      '<button onclick="SMAuth._continuePay(\'' + planType + '\',\'' + planLabel + '\',' + price + ')" style="' + btnP() + 'margin-bottom:8px;">' + _t('创建账户 / 登录', 'Create Account / Log In') + '</button>' +
      '<button onclick="SMAuth._guestPay(\'' + planType + '\',\'' + planLabel + '\',' + price + ')" style="' + btnS() + '">' + _t('访客继续购买', 'Continue as Guest') + '</button>' +
      '<p style="text-align:center;margin-top:14px;font-size:12px;color:#555;">' + _t('访客购买需要提供邮箱地址', 'Guest purchases require an email') + '</p>');
  }

  function _continuePay(pt, pl, pr) { sessionStorage.setItem("sm_pending", JSON.stringify({ pt, pl, pr })); showLoginModal(); }
  function _guestPay(pt, pl, pr) {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;cursor:pointer;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2"><path d="M6 6l12 12M18 6l-12 12"/></svg></button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';font-weight:600;">' + _t('访客结账', 'Guest Checkout') + '</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + _t('输入邮箱地址以获取访问链接', 'Enter your email for access link') + '</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-guest-email" placeholder="' + _t('邮箱地址', 'Email') + '" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._guestDo(\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="' + btnP() + '">' + _t('继续支付', 'Continue to Payment') + '</button>');
  }

  async function _guestDo(pt, pl, pr) {
    var email = document.getElementById("sm-guest-email").value.trim();
    if (!email.includes("@")) { showError(_t('请输入有效的邮箱地址', 'Valid email required')); return; }
    try {
      var tp = Math.random().toString(36).slice(-12);
      await api("/api/auth/register", "POST", { email, password: tp });
      await login(email, tp); closeModal(); showMethodChoice(pt, pl, pr);
    } catch (e) { showError(e.message); }
  }

  // Safe JSON parser — handles HTML error pages gracefully
  async function _safeJson(r) {
    try { return await r.json(); }
    catch(e) {
      if (r.status >= 500) throw new Error(_t('支付服务暂时不可用，请稍后重试。', "Payment service is temporarily unavailable. Please try again."));
      throw new Error(_t('服务器响应异常。', "Unexpected response from server."));
    }
  }

  function showMethodChoice(pt, pl, pr) {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;cursor:pointer;"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#888" stroke-width="2"><path d="M6 6l12 12M18 6l-12 12"/></svg></button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';font-weight:600;">' + _t('选择支付方式', 'Choose Payment') + '</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + pl + ' — <strong style="color:#fff;">$' + pr.toFixed(2) + '</strong></p>' +
      '<div onclick="SMAuth.closeModal();SMAuth._startPP(\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="width:100%;padding:14px 20px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);border-radius:12px;color:#ccc;cursor:pointer;font-size:14px;display:flex;align-items:center;gap:12px;box-sizing:border-box;"><span style="background:#0070ba;color:#fff;font-size:12px;font-weight:700;padding:5px 0;border-radius:4px;width:56px;text-align:center;display:inline-block;line-height:16px;">PayPal</span><span style="flex:1;">' + _t('信用卡 / PayPal', 'Credit Card / PayPal') + '</span><span style="color:#666;">\u2192</span></div>' +
      '<div onclick="SMAuth.closeModal();SMAuth._startNP(\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="width:100%;padding:14px 20px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);border-radius:12px;color:#ccc;cursor:pointer;font-size:14px;display:flex;align-items:center;gap:12px;box-sizing:border-box;"><span style="background:linear-gradient(135deg,#F7931A,#8DC63F);border-radius:4px;width:56px;text-align:center;display:inline-flex;align-items:center;justify-content:center;padding:5px 0;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M10 8.5v7M10 12h3.5a2 2 0 1 0 0-4H10z"/><path d="M10 12h4a2 2 0 1 1 0 4h-4"/></svg></span><span style="flex:1;">' + _t('加密货币（USDT）', 'Crypto (USDT)') + '</span><span style="color:#666;">\u2192</span></div>');
  }

  async function _startPP(pt, pl, pr) {
    if (!token) { showPaymentPrompt(pt, pl, pr); return; }
    showModal('<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';">' + _t('处理中', 'Processing') + '</h2><p style="margin:0 0 24px;color:#888;font-size:14px;">' + _t('正在准备 PayPal...', 'Preparing PayPal...') + '</p><div style="text-align:center;padding:20px;"><div class="sm-loader"></div></div>');
    try {
      var r = await fetch("/api/paypal/create-order", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ amount: pr.toFixed(2) }) });
      var d = await _safeJson(r);
      if (!r.ok) throw new Error(d.error || d.detail || _t('支付失败', 'Payment failed'));
      closeModal();

      // Wait for PayPal SDK to load (up to 8 seconds)
      var ppReady = !!window.paypal;
      if (!ppReady) {
        for (var w = 0; w < 40; w++) {
          await new Promise(r2 => setTimeout(r2, 200));
          if (window.paypal) { ppReady = true; break; }
        }
      }

      if (ppReady) {
        var c = document.createElement("div"); c.id = "sm-pp"; c.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:99999;background:#1a1a2e;padding:30px;border-radius:16px;border:1px solid " + ACCENT_LIGHT + ";";
        document.body.appendChild(c);
        window.paypal.Buttons({
          createOrder: function () { return Promise.resolve(d.id || d.orderID); },
          onApprove: async function (ev) { c.remove(); await paySuccess(ev.orderID, pt, pl, pr); },
          onCancel: function () { c.remove(); },
          onError: function () { c.remove(); showModal('<p style="color:#ff6b6b;">' + _t('PayPal 支付失败，请重试。', 'PayPal payment failed. Please try again.') + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">' + _t('关闭', 'Close') + '</button>'); }
        }).render("#sm-pp");
      } else {
        // Fallback: open PayPal checkout page in new tab
        var orderId = d.id || d.orderID;
        window.open("https://www.sandbox.paypal.com/checkoutnow?token=" + orderId, "_blank");
        showModal('<div style="text-align:center;"><div style="font-size:36px;margin-bottom:12px;">💳</div><h2 style="margin:0 0 6px;font-size:20px;color:' + ACCENT_TEXT + ';">' + _t('PayPal 结账', 'PayPal Checkout') + '</h2><p style="margin:0 0 8px;color:#ccc;font-size:14px;">' + _t('在新标签页中完成支付。', 'Complete payment in the new tab.') + '</p><p style="margin:0 0 20px;color:#888;font-size:13px;">' + _t('支付完成后，点击下方按钮激活你的套餐。', 'After payment, click the button below to activate your plan.') + '</p><button onclick="SMAuth._activateAfterPay(\'' + orderId + '\',\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="' + btnP() + '">' + _t('我已完成支付', "I've Completed Payment") + '</button></div>');
      }
    } catch (e) { showModal('<p style="color:#ff6b6b;">' + e.message + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">' + _t('关闭', 'Close') + '</button>'); }
  }

  async function _activateAfterPay(orderId, pt, pl, pr) {
    closeModal();
    await paySuccess(orderId, pt, pl, pr);
  }

  async function _startNP(pt, pl, pr) {
    if (!token) { showPaymentPrompt(pt, pl, pr); return; }
    showModal('<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';">' + _t('加密货币支付', 'Crypto Payment') + '</h2><p style="margin:0 0 24px;color:#888;font-size:14px;">' + _t('正在生成账单...', 'Generating invoice...') + '</p><div style="text-align:center;padding:20px;"><div class="sm-loader"></div></div>');
    try {
      var r = await fetch("/api/nowpayments/create-payment", { method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token }, body: JSON.stringify({ plan_type: pt }) });
      var d = await _safeJson(r);
      if (!r.ok) throw new Error(d.detail || _t('支付失败', 'Payment failed'));
      closeModal();
      showModal('<div style="text-align:center;"><span style="display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;margin-bottom:12px;"><svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#7c5cff" stroke-width="1.5"><circle cx="12" cy="12" r="9"/><path d="M10 8.5v7M10 12h3.5a2 2 0 1 0 0-4H10z"/><path d="M10 12h4a2 2 0 1 1 0 4h-4"/></svg></span><h2 style="margin:0 0 6px;font-size:20px;color:' + ACCENT_TEXT + ';">' + _t('USDT 支付', 'USDT Payment') + '</h2><p style="margin:0 0 8px;color:#ccc;font-size:14px;"><strong>' + pl + '</strong></p><p style="margin:0 0 20px;color:#888;font-size:13px;">' + _t('金额：', 'Amount: ') + '<strong style="color:#fff;">$' + pr.toFixed(2) + '</strong></p><a href="' + d.invoice_url + '" target="_blank" style="display:inline-block;padding:12px 28px;background:' + ACCENT_GRADIENT + ';border:none;border-radius:999px;color:#fff;font-size:15px;font-weight:600;text-decoration:none;">' + _t('使用 USDT 支付 →', 'Pay with USDT \u2192') + '</a><p style="margin-top:16px;color:#666;font-size:12px;">Powered by NOWPayments</p></div>');
    } catch (e) { showModal('<p style="color:#ff6b6b;">' + e.message + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">' + _t('关闭', 'Close') + '</button>'); }
  }

  async function paySuccess(orderId, pt, pl, pr) {
    showModal('<h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';">' + _t('确认中', 'Confirming') + '</h2><p style="margin:0 0 24px;color:#888;font-size:14px;">' + _t('正在激活你的套餐...', 'Activating your plan...') + '</p><div style="text-align:center;padding:20px;"><div class="sm-loader"></div></div>');
    try {
      var r = await fetch("/api/paypal/capture-order", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ orderID: orderId }) });
      var d = await r.json();
      if (!r.ok) throw new Error(d.error);
      try { await api("/api/entitlements/activate", "POST", { plan_type: pt, order_id: orderId }); } catch (e) { }
      await fetchPremiumStatus(); closeModal();
      // Auto-unlock report if user is currently on report page with locked content
      if (typeof unlockReport === 'function') {
        try { unlockReport(); } catch(e) { console.log('[SMAuth] unlockReport not applicable:', e.message); }
      }
      showModal('<div style="text-align:center;"><div style="font-size:48px;margin-bottom:12px;">\u2728</div><h2 style="margin:0 0 6px;color:#4ade80;">' + _t('支付成功！', 'Payment Successful!') + '</h2><p style="margin:0 0 20px;color:#ccc;font-size:14px;"><strong style="color:' + ACCENT_TEXT + ';">' + pl + '</strong> ' + _t('已激活', 'activated') + '</p><p style="margin:0 0 16px;color:#aaa;font-size:12px;">' + _t('你的完整命运报告已解锁。', 'Your full destiny report has been unlocked.') + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + 'margin-bottom:8px;">' + _t('继续阅读', 'Continue Reading') + '</button></div>');
      updateNavbar();
    } catch (e) { showModal('<p style="color:#ff6b6b;">' + _t('错误：', 'Error: ') + e.message + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">' + _t('关闭', 'Close') + '</button>'); }
  }

  function _goStart() { closeModal(); document.querySelector("#interpret, #hero")?.scrollIntoView({ behavior: "smooth" }); }

  function updateNavbar() {
    var el = document.getElementById("sm-nav-user");
    if (!el) return;
    if (token && currentUser) {
      var badge = (premiumStatus && premiumStatus.premium) ? '<span style="background:rgba(124,92,255,0.2);color:' + ACCENT_TEXT + ';padding:3px 10px;border-radius:12px;font-size:11px;margin-right:8px;">' + (premiumStatus.plan_label || _t('已订阅', 'Premium')) + '</span>' : "";
      var rem = (premiumStatus && premiumStatus.premium && premiumStatus.total > 0) ? '<span style="color:#666;font-size:11px;margin-right:8px;">' + premiumStatus.remaining + "/" + premiumStatus.total + "</span>" : "";
      el.innerHTML = badge + rem +
        '<div style="position:relative;display:inline-block;"><button onclick="SMAuth._toggleMenu()" style="background:rgba(124,92,255,0.3);border:1px solid rgba(124,92,255,0.5);border-radius:50%;width:32px;height:32px;color:' + ACCENT_TEXT + ';cursor:pointer;font-size:13px;font-weight:600;">' + currentUser.email[0].toUpperCase() +
        '</button><div id="sm-menu" style="display:none;position:absolute;right:0;top:40px;background:#1a1a2e;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px;min-width:180px;box-shadow:0 4px 20px rgba(0,0,0,0.5);z-index:1000;"><div style="padding:8px 12px;color:#666;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.05);">' + currentUser.email + '</div><a href="javascript:SMAuth.showAccountModal()" style="display:block;padding:8px 12px;color:#ccc;text-decoration:none;font-size:14px;">' + _t('我的账户', 'My Account') + '</a><a href="javascript:SMAuth.logout()" style="display:block;padding:8px 12px;color:#ff6b6b;text-decoration:none;font-size:14px;">' + _t('退出登录', 'Log Out') + '</a></div></div>';
    } else {
      el.innerHTML = '<button onclick="SMAuth.showLoginModal()" style="background:' + ACCENT_GRADIENT + ';border:none;border-radius:999px;padding:8px 20px;color:#fff;cursor:pointer;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;">' + _t('登录', 'Log In') + '</button>';
    }
  }

  function _toggleMenu() { var m = document.getElementById("sm-menu"); if (m) m.style.display = m.style.display === "none" ? "block" : "none"; }

  async function showAccountModal() {
    _toggleMenu();
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button><h2 style="margin:0 0 6px;font-size:22px;color:' + ACCENT_TEXT + ';">' + _t('我的账户', 'My Account') + '</h2><div id="sm-acct"><div style="text-align:center;padding:40px;"><div class="sm-loader"></div></div></div>');
    try {
      var me = await api("/api/user/me"), ent = await api("/api/user/entitlements"), ord = await api("/api/user/orders");
      // Find dream credits entitlement (credits_*)
      var dreamEnt = ent.entitlements.find(function (e) { return e.plan_type && e.plan_type.startsWith('credits_') && !e.is_expired && (e.total_count < 0 || e.remaining > 0); });
      // Find tarot credits entitlement (tarot_*)
      var tarotEnt = ent.entitlements.find(function (e) { return e.plan_type && e.plan_type.startsWith('tarot_') && !e.is_expired && (e.total_count < 0 || e.remaining > 0); });
      var labels = {
        spark: _t("火花计划", "The Spark"),
        seeker: _t("探索者", "The Seeker"),
        oracle: _t("先知计划", "The Oracle"),
        credits_3: _t("梦境分析 ×3", "Dream Analysis ×3"),
        credits_10: _t("梦境分析 ×10", "Dream Analysis ×10"),
        credits_30: _t("梦境分析 ×30", "Dream Analysis ×30"),
        tarot_3: _t("塔罗牌 ×3", "Tarot ×3"),
        tarot_10: _t("塔罗牌 ×10", "Tarot ×10"),
        tarot_30: _t("塔罗牌 ×30", "Tarot ×30")
      };
      // Fallback: strip prefix for unknown plan types
      function planLabel(pt) {
        return labels[pt] || pt;
      }
      var ehtml = '<p style="color:#888;font-size:13px;">' + _t('暂无活跃套餐', 'No active plan.') + '</p>';
      var parts = [];
      if (dreamEnt) {
        var rt = dreamEnt.total_count < 0 ? "\u221e" : dreamEnt.remaining + "/" + dreamEnt.total_count;
        parts.push('<div style="margin-bottom:8px;background:rgba(124,92,255,0.1);border:1px solid rgba(124,92,255,0.25);border-radius:12px;padding:14px;"><div style="color:' + ACCENT_TEXT + ';font-weight:600;margin-bottom:6px;">' + _t('梦境分析', 'Dream Analysis') + '</div><div style="color:#4ade80;">' + _t('剩余次数：', 'Remaining: ') + rt + "</div></div>");
      }
      if (tarotEnt) {
        var trt = tarotEnt.total_count < 0 ? "\u221e" : tarotEnt.remaining + "/" + tarotEnt.total_count;
        parts.push('<div style="background:rgba(255,213,79,0.1);border:1px solid rgba(255,213,79,0.25);border-radius:12px;padding:14px;"><div style="color:#fbbf24;font-weight:600;margin-bottom:6px;">' + _t('塔罗牌', 'Tarot') + '</div><div style="color:#4ade80;">' + _t('剩余次数：', 'Remaining: ') + trt + "</div></div>");
      }
      if (parts.length) ehtml = parts.join('');
      var ohtml = ord.orders.length ? ord.orders.map(function (o) { return '<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;display:flex;justify-content:space-between;"><span style="color:#666;">' + planLabel(o.plan_type) + '</span><span style="color:#999;">$' + o.amount.toFixed(2) + "</span></div>"; }).join("") : '<p style="color:#555;font-size:12px;">' + _t('暂无订单', 'No orders') + '</p>';
      document.getElementById("sm-acct").innerHTML = '<div><div style="margin-bottom:16px;"><div style="font-size:11px;color:#555;">' + _t('邮箱地址', 'EMAIL') + '</div><div style="color:#ccc;">' + me.email + "</div></div><div style='margin-bottom:16px'><div style='font-size:11px;color:#555;margin-bottom:6px;'>" + _t('积分余额', 'Credits Balance') + "</div>" + ehtml + "</div><div><div style='font-size:11px;color:#555;margin-bottom:6px;'>" + _t('购买记录', 'Purchase History') + "</div>" + ohtml + "</div></div>";
    } catch (e) { document.getElementById("sm-acct").innerHTML = '<p style="color:#ff6b6b;">' + e.message + "</p>"; }
  }

  // ═══ Report Email ═══════════════════════════════════════

  async function sendReportEmail() {
    // Get user email and payment info
    var userEmail = currentUser?.email || '';
    if (!userEmail) {
      // If not logged in, prompt for email
      userEmail = prompt(_t('请输入邮箱地址以接收报告：', "Enter your email to receive the report:"));
      if (!userEmail) return;
    }

    // Collect report content (from modal)
    var freeEl = document.getElementById('res-free-modal') || document.getElementById('res-free');
    var paidEl = document.getElementById('res-paid-modal') || document.getElementById('res-paid');
    var isUnlocked = document.getElementById('locked-preview-modal')?.classList.contains('hidden') || document.getElementById('locked-preview')?.classList.contains('hidden');
    var reportHTML = '<h2>' + _t('心理学分析', 'Psychology Analysis') + '</h2>' + (freeEl?.innerHTML || '');
    if (isUnlocked && paidEl?.innerHTML) {
      reportHTML += '<h2>' + _t('东方命运路径', 'Eastern Destiny Path') + '</h2>' + paidEl.innerHTML;
    }

    // Include tarot card info if available
    var tarotImg = document.getElementById('tarot-card-img-modal') || document.getElementById('tarot-card-img');
    var tarotName = document.getElementById('tarot-card-name-modal') || document.getElementById('tarot-card-name');
    var tarotMeaning = document.getElementById('tarot-card-meaning-modal') || document.getElementById('tarot-card-meaning');
    if (tarotImg && tarotName) {
      var meaningHTML = tarotMeaning ? tarotMeaning.innerHTML : '';
      var tarotSection = '<div class="tarot-section">' +
        '<img src="' + tarotImg.src + '" alt="' + tarotName.innerText + '"/>' +
        '<div class="card-name">' + tarotName.innerText + '</div>' +
        (meaningHTML ? '<div class="card-meaning" style="margin-top:12px;color:#c8bfe8;font-size:13px;line-height:1.7;">' + meaningHTML + '</div>' : '') +
        '</div>';
      reportHTML = tarotSection + reportHTML;
    }

    // Get order info
    var orderInfo = null;
    if (token) {
      try {
        var ord = await api("/api/user/orders");
        if (ord.orders && ord.orders.length > 0) {
          var last = ord.orders[ord.orders.length - 1];
          orderInfo = {
            plan_type: last.plan_type,
            amount: last.amount,
            currency: last.currency || 'USD',
            order_id: last.id,
            status: last.status
          };
        }
      } catch(e) {}
    }

    if (!reportHTML || reportHTML === '<h2>' + _t('心理学分析', 'Psychology Analysis') + '</h2>') {
      alert(_t('暂无报告内容。', 'No report content available.'));
      return;
    }

    // Show loading
    var overlay = showModal('<div style="text-align:center;padding:20px;"><div class="sm-loader"></div><p style="margin-top:16px;color:#888;font-size:13px;">' + _t('正在发送报告...', 'Sending report...') + '</p></div>');

    try {
      var r = await fetch("/api/send-report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: userEmail,
          html: reportHTML,
          dream_title: _t('你的梦境分析报告', "Your Dream Analysis Report"),
          lang: document.documentElement.lang || 'zh',
          customer_name: currentUser?.email?.split('@')[0] || _t('探索者', 'Seeker'),
          order_data: orderInfo
        })
      });
      var d = await r.json();
      closeModal();
      if (d.ok) {
        alert(_t('✅ 报告已发送至 ', '\u2705 Report sent to ') + userEmail);
      } else {
        alert(d.error || _t('邮件发送失败', 'Failed to send email'));
      }
    } catch (e) {
      closeModal();
      alert(_t('错误：', 'Error: ') + e.message);
    }
  }

  async function _checkPending() {
    var p = sessionStorage.getItem("sm_pending");
    if (p && token) { sessionStorage.removeItem("sm_pending"); var d = JSON.parse(p); showMethodChoice(d.pt, d.pl, d.pr); }
  }

  async function init() {
    console.log("[SMAuth] init() token=" + (token ? "EXISTS" : "null") + " url=" + window.location.href.substring(0,120));
    // Handle OAuth redirect back with token
    var params = new URLSearchParams(window.location.search);
    var oauthToken = params.get("oauth_token");
    if (oauthToken) {
      token = oauthToken;
      localStorage.setItem("sm_token", token);
      console.log("[SMAuth] OAuth token found, stored in localStorage");
      // Clean URL — remove oauth_token param without reloading
      var url = new URL(window.location);
      url.searchParams.delete("oauth_token");
      url.searchParams.delete("email");
      url.searchParams.delete("oauth_error");
      window.history.replaceState({}, "", url);
      await fetchMe();
      console.log("[SMAuth] OAuth fetchMe done, currentUser=" + (currentUser ? currentUser.email : "null"));
      if (currentUser) { await fetchPremiumStatus(); console.log("[SMAuth] OAuth premium=" + JSON.stringify(premiumStatus)); }
      updateNavbar();
      return;
    }
    // Check for OAuth error
    var oauthError = params.get("oauth_error");
    if (oauthError) {
      var url = new URL(window.location);
      url.searchParams.delete("oauth_error");
      window.history.replaceState({}, "", url);
      alert(_t('Google 登录已取消或遇到错误，请重试。', "Google login was cancelled or encountered an error. Please try again."));
    }

    if (token) { await fetchMe(); if (currentUser) { await fetchPremiumStatus(); await _checkPending(); } }
    updateNavbar();
    console.log("[SMAuth] init done loggedIn=" + !!token + " user=" + (currentUser ? currentUser.email : "null") + " premium=" + JSON.stringify(premiumStatus));
    // Inject loader style
    if (!document.getElementById("sm-loader-style")) {
      var s = document.createElement("style"); s.id = "sm-loader-style"; s.textContent = ".sm-loader{display:inline-block;width:36px;height:36px;border:3px solid rgba(124,92,255,0.2);border-top-color:" + ACCENT_TEXT + ";border-radius:50%;animation:sm-spin 1s linear infinite;}@keyframes sm-spin{to{transform:rotate(360deg)}}";
      document.head.appendChild(s);
    }
    document.addEventListener("click", function (e) { var m = document.getElementById("sm-menu"); if (m && m.style.display === "block" && !e.target.closest("#sm-nav-user")) m.style.display = "none"; });
  }

  return {
    init, login, logout, showLoginModal, showRegisterModal, showForgotModal,
    showPaymentPrompt, showAccountModal, closeModal, updateNavbar, fetchPremiumStatus,
    socialLogin,
    consumeEntitlement: function () { return api("/api/entitlements/consume", "POST"); },
    verifyLicense: function (k) { return api("/api/license/verify", "POST", { key: k }); },
    redeemLicense: function (k) { return api("/api/license/redeem", "POST", { key: k }); },
    get isLoggedIn() { return !!token; }, get user() { return currentUser; }, get premium() { return premiumStatus; },
    _doLogin, _doRegister, _doForgot, _continuePay, _guestPay, _guestDo, _toggleMenu, _goStart,
    _startPP, _startNP,
    sendReportEmail
  };
})();

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { SMAuth.init(); });
else SMAuth.init();

