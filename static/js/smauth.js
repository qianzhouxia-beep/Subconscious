/**
 * SMAuth — Subconscious Mirror 用户账户与支付闭环模块 v3
 * 蓝色主题 + 社交登录 + 虚拟币支付 (NOWPayments)
 */
const SMAuth = (function () {
  const API_BASE = "";
  const BLUE = "#4E85BF";
  const BLUE_GRADIENT = "linear-gradient(135deg,#3A7ABF,#5B9BD5)";
  const BLUE_LIGHT = "rgba(78,133,191,0.3)";
  const BLUE_TEXT = "#89AACC";

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
  async function fetchMe() { if (!token) return null; try { currentUser = await api("/api/user/me"); return currentUser; } catch (e) { logout(); return null; } }
  async function fetchPremiumStatus() { if (!token) return null; try { premiumStatus = await api("/api/user/premium-status"); return premiumStatus; } catch (e) { return null; } }

  function showModal(html) {
    const overlay = document.createElement("div");
    overlay.id = "sm-modal-overlay";
    overlay.style.cssText = "position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.7);display:flex;align-items:center;justify-content:center;z-index:99999;";
    overlay.innerHTML = '<div style="background:#1a1a2e;color:#e0e0e0;padding:32px 36px;border-radius:16px;max-width:440px;width:90%;position:relative;box-shadow:0 0 40px rgba(78,133,191,0.2);border:1px solid rgba(78,133,191,0.3);max-height:90vh;overflow-y:auto;">' + html + "</div>";
    document.body.appendChild(overlay);
    overlay.addEventListener("click", function (e) { if (e.target === overlay) overlay.remove(); });
    return overlay;
  }
  function closeModal() { var el = document.getElementById("sm-modal-overlay"); if (el) el.remove(); }
  function showError(msg) { var el = document.getElementById("sm-error"); if (el) { el.textContent = msg; el.style.display = "block"; } }
  function showSuccess(msg) { var el = document.getElementById("sm-success"); if (el) { el.textContent = msg; el.style.display = "block"; } }

  function btnP() { return "width:100%;padding:10px 20px;background:" + BLUE_GRADIENT + ";border:none;border-radius:999px;color:#fff;font-size:14px;cursor:pointer;font-weight:600;letter-spacing:0.5px;"; }
  function btnS() { return "width:100%;padding:10px 20px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.15);border-radius:999px;color:#ccc;font-size:14px;cursor:pointer;"; }

  // Social login buttons HTML
  function socialBtns() {
    return '<div style="margin-top:20px;margin-bottom:4px;"><div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;"><div style="flex:1;height:1px;background:rgba(255,255,255,0.08);"></div><span style="color:#666;font-size:12px;">or continue with</span><div style="flex:1;height:1px;background:rgba(255,255,255,0.08);"></div></div>' +
      '<button onclick="SMAuth.socialLogin(\'google\')" style="width:100%;padding:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#ccc;cursor:pointer;font-size:13px;display:flex;align-items:center;justify-content:center;gap:6px;">' + googleIcon() + ' Sign in with Google</button></div>';
  }
  function googleIcon() { return '<svg width="16" height="16" viewBox="0 0 24 24"><path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/><path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/><path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/><path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/></svg>'; }

  async function socialLogin(provider) {
    try {
      var resp = await fetch("/api/auth/social/" + provider);
      var data = await resp.json();
      if (data.auth_url) {
        // Full page redirect — most reliable for OAuth flow
        window.location.href = data.auth_url;
      } else {
        alert(data.detail || provider + " login is being configured. Please use email.");
      }
    } catch (e) { alert(provider + " login not available yet."); }
  }

  function showLoginModal() {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';font-weight:600;">Welcome Back</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">Log in to access your dream interpretations</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-login-email" placeholder="Email" style="width:100%;padding:11px 14px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<input type="password" id="sm-login-password" placeholder="Password" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._doLogin()" style="' + btnP() + '">Log In</button>' +
      '<div style="text-align:center;margin-top:12px;font-size:13px;color:#666;">' +
      '<a href="javascript:SMAuth.showForgotModal()" style="color:' + BLUE_TEXT + ';text-decoration:none;">Forgot password?</a>' +
      '<span style="margin:0 8px;">\u00b7</span>' +
      '<a href="javascript:SMAuth.showRegisterModal()" style="color:' + BLUE_TEXT + ';text-decoration:none;">Create account</a></div>' + socialBtns());
  }

  async function _doLogin() {
    var email = document.getElementById("sm-login-email").value.trim();
    var pwd = document.getElementById("sm-login-password").value;
    try { await login(email, pwd); closeModal(); updateNavbar(); } catch (e) { showError(e.message); }
  }

  function showRegisterModal() {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';font-weight:600;">Create Account</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">Secure your purchases across devices</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-reg-email" placeholder="Email" style="width:100%;padding:11px 14px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<input type="password" id="sm-reg-password" placeholder="Password (8+ chars)" style="width:100%;padding:11px 14px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<input type="password" id="sm-reg-confirm" placeholder="Confirm password" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._doRegister()" style="' + btnP() + '">Create Account</button>' +
      '<div style="text-align:center;margin-top:12px;font-size:13px;color:#666;">Already have an account? <a href="javascript:SMAuth.showLoginModal()" style="color:' + BLUE_TEXT + ';text-decoration:none;">Log in</a></div>' + socialBtns());
  }

  async function _doRegister() {
    var email = document.getElementById("sm-reg-email").value.trim();
    var pwd = document.getElementById("sm-reg-password").value;
    var confirm = document.getElementById("sm-reg-confirm").value;
    if (pwd !== confirm) { showError("Passwords do not match"); return; }
    try { await api("/api/auth/register", "POST", { email, password: pwd }); await login(email, pwd); closeModal(); updateNavbar(); } catch (e) { showError(e.message); }
  }

  function showForgotModal() {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';font-weight:600;">Reset Password</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">Enter your email for a reset link</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<div id="sm-success" style="display:none;color:#4ade80;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-forgot-email" placeholder="Email" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._doForgot()" style="' + btnP() + '">Send Reset Link</button>' +
      '<div style="text-align:center;margin-top:12px;font-size:13px;color:#666;"><a href="javascript:SMAuth.showLoginModal()" style="color:' + BLUE_TEXT + ';text-decoration:none;">Back to login</a></div>');
  }

  async function _doForgot() {
    var email = document.getElementById("sm-forgot-email").value.trim();
    try { await api("/api/auth/forgot-password", "POST", { email }); showSuccess("If the email exists, a reset link has been sent."); } catch (e) { showError(e.message); }
  }

  function showPaymentPrompt(planType, planLabel, price) {
    if (token) { showMethodChoice(planType, planLabel, price); return; }
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';font-weight:600;">Secure Your Purchase</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">Create an account to save your purchase</p>' +
      '<button onclick="SMAuth._continuePay(\'' + planType + '\',\'' + planLabel + '\',' + price + ')" style="' + btnP() + 'margin-bottom:8px;">Create Account / Log In</button>' +
      '<button onclick="SMAuth._guestPay(\'' + planType + '\',\'' + planLabel + '\',' + price + ')" style="' + btnS() + '">Continue as Guest</button>' +
      '<p style="text-align:center;margin-top:14px;font-size:12px;color:#555;">Guest purchases require an email</p>');
  }

  function _continuePay(pt, pl, pr) { sessionStorage.setItem("sm_pending", JSON.stringify({ pt, pl, pr })); showLoginModal(); }
  function _guestPay(pt, pl, pr) {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';font-weight:600;">Guest Checkout</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">Enter your email for access link</p>' +
      '<div id="sm-error" style="display:none;color:#ff6b6b;font-size:13px;margin-bottom:12px;"></div>' +
      '<input type="email" id="sm-guest-email" placeholder="Email" style="width:100%;padding:11px 14px;margin-bottom:16px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.1);border-radius:8px;color:#fff;font-size:14px;box-sizing:border-box;">' +
      '<button onclick="SMAuth._guestDo(\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="' + btnP() + '">Continue to Payment</button>');
  }

  async function _guestDo(pt, pl, pr) {
    var email = document.getElementById("sm-guest-email").value.trim();
    if (!email.includes("@")) { showError("Valid email required"); return; }
    try {
      var tp = Math.random().toString(36).slice(-12);
      await api("/api/auth/register", "POST", { email, password: tp });
      await login(email, tp); closeModal(); showMethodChoice(pt, pl, pr);
    } catch (e) { showError(e.message); }
  }

  function showMethodChoice(pt, pl, pr) {
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button>' +
      '<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';font-weight:600;">Choose Payment</h2>' +
      '<p style="margin:0 0 20px;color:#666;font-size:13px;">' + pl + ' — <strong style="color:#fff;">$' + pr.toFixed(2) + '</strong></p>' +
      '<div onclick="SMAuth.closeModal();SMAuth._startPP(\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="width:100%;padding:14px 20px;margin-bottom:10px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);border-radius:12px;color:#ccc;cursor:pointer;font-size:14px;display:flex;align-items:center;gap:12px;box-sizing:border-box;"><span style="background:#0070ba;color:#fff;font-size:16px;font-weight:700;padding:4px 8px;border-radius:4px;min-width:50px;text-align:center;">PayPal</span><span style="flex:1;">Credit Card / PayPal</span><span style="color:#666;">\u2192</span></div>' +
      '<div onclick="SMAuth.closeModal();SMAuth._startNP(\'' + pt + '\',\'' + pl + '\',' + pr + ')" style="width:100%;padding:14px 20px;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.12);border-radius:12px;color:#ccc;cursor:pointer;font-size:14px;display:flex;align-items:center;gap:12px;box-sizing:border-box;"><span style="background:linear-gradient(135deg,#F7931A,#8DC63F);color:#fff;font-size:14px;font-weight:700;padding:4px 8px;border-radius:4px;min-width:50px;text-align:center;">\u0243</span><span style="flex:1;">Crypto (BTC, ETH, USDT...)</span><span style="color:#666;">\u2192</span></div>');
  }

  async function _startPP(pt, pl, pr) {
    if (!token) { showPaymentPrompt(pt, pl, pr); return; }
    showModal('<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';">Processing</h2><p style="margin:0 0 24px;color:#888;font-size:14px;">Creating order...</p><div style="text-align:center;padding:20px;"><div class="sm-loader"></div></div>');
    try {
      var r = await fetch("/api/paypal/create-order", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ amount: pr.toFixed(2) }) });
      var d = await r.json();
      if (!r.ok) throw new Error(d.error);
      closeModal();
      if (window.paypal) {
        var c = document.createElement("div"); c.id = "sm-pp"; c.style.cssText = "position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:99999;background:#1a1a2e;padding:30px;border-radius:16px;border:1px solid " + BLUE_LIGHT + ";";
        document.body.appendChild(c);
        window.paypal.Buttons({
          createOrder: function () { return Promise.resolve(d.orderID); },
          onApprove: async function (ev) { c.remove(); await paySuccess(ev.orderID, pt, pl, pr); },
          onCancel: function () { c.remove(); },
          onError: function () { c.remove(); }
        }).render("#sm-pp");
      } else { await paySuccess(d.orderID, pt, pl, pr); }
    } catch (e) { showModal('<p style="color:#ff6b6b;">' + e.message + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">Close</button>'); }
  }

  async function _startNP(pt, pl, pr) {
    if (!token) { showPaymentPrompt(pt, pl, pr); return; }
    showModal('<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';">Crypto Payment</h2><p style="margin:0 0 24px;color:#888;font-size:14px;">Generating invoice...</p><div style="text-align:center;padding:20px;"><div class="sm-loader"></div></div>');
    try {
      var r = await fetch("/api/nowpayments/create-payment", { method: "POST", headers: { "Content-Type": "application/json", "Authorization": "Bearer " + token }, body: JSON.stringify({ plan_type: pt }) });
      var d = await r.json();
      if (!r.ok) throw new Error(d.detail);
      closeModal();
      showModal('<div style="text-align:center;"><div style="font-size:36px;margin-bottom:12px;">\u0243</div><h2 style="margin:0 0 6px;font-size:20px;color:' + BLUE_TEXT + ';">Crypto Payment</h2><p style="margin:0 0 8px;color:#ccc;font-size:14px;"><strong>' + pl + '</strong></p><p style="margin:0 0 20px;color:#888;font-size:13px;">Amount: <strong style="color:#fff;">$' + pr.toFixed(2) + '</strong></p><a href="' + d.invoice_url + '" target="_blank" style="display:inline-block;padding:12px 28px;background:' + BLUE_GRADIENT + ';border:none;border-radius:999px;color:#fff;font-size:15px;font-weight:600;text-decoration:none;">Pay with Crypto \u2192</a><p style="margin-top:16px;color:#666;font-size:12px;">BTC, ETH, USDT, LTC, BCH, XRP, DOGE +50 more</p><p style="margin-top:8px;color:#555;font-size:11px;">Powered by NOWPayments</p></div>');
    } catch (e) { showModal('<p style="color:#ff6b6b;">' + e.message + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">Close</button>'); }
  }

  async function paySuccess(orderId, pt, pl, pr) {
    showModal('<h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';">Confirming</h2><p style="margin:0 0 24px;color:#888;font-size:14px;">Activating your plan...</p><div style="text-align:center;padding:20px;"><div class="sm-loader"></div></div>');
    try {
      var r = await fetch("/api/paypal/capture-order", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ orderID: orderId }) });
      var d = await r.json();
      if (!r.ok) throw new Error(d.error);
      try { await api("/api/entitlements/activate", "POST", { plan_type: pt, order_id: orderId }); } catch (e) { }
      await fetchPremiumStatus(); closeModal();
      showModal('<div style="text-align:center;"><div style="font-size:48px;margin-bottom:12px;">\u2728</div><h2 style="margin:0 0 6px;color:#4ade80;">Payment Successful!</h2><p style="margin:0 0 20px;color:#ccc;font-size:14px;"><strong style="color:' + BLUE_TEXT + ';">' + pl + '</strong> activated</p><div style="background:rgba(255,255,255,0.03);border-radius:12px;padding:14px;margin-bottom:20px;font-size:13px;"><div style="display:flex;justify-content:space-between;padding:4px 0;"><span style="color:#666;">Plan</span><span style="color:#ccc;">' + pl + '</span></div><div style="display:flex;justify-content:space-between;padding:4px 0;"><span style="color:#666;">Amount</span><span style="color:#ccc;">$' + pr.toFixed(2) + '</span></div></div><button onclick="SMAuth._goStart()" style="' + btnP() + 'margin-bottom:8px;">Start Interpretation</button></div>');
      updateNavbar();
    } catch (e) { showModal('<p style="color:#ff6b6b;">Error: ' + e.message + '</p><button onclick="SMAuth.closeModal()" style="' + btnP() + '">Close</button>'); }
  }

  function _goStart() { closeModal(); document.querySelector("#interpret, #hero")?.scrollIntoView({ behavior: "smooth" }); }

  function updateNavbar() {
    var el = document.getElementById("sm-nav-user");
    if (!el) return;
    if (token && currentUser) {
      var badge = (premiumStatus && premiumStatus.premium) ? '<span style="background:rgba(78,133,191,0.2);color:' + BLUE_TEXT + ';padding:3px 10px;border-radius:12px;font-size:11px;margin-right:8px;">' + (premiumStatus.plan_label || "Premium") + '</span>' : "";
      var rem = (premiumStatus && premiumStatus.premium && premiumStatus.total > 0) ? '<span style="color:#666;font-size:11px;margin-right:8px;">' + premiumStatus.remaining + "/" + premiumStatus.total + "</span>" : "";
      el.innerHTML = badge + rem +
        '<div style="position:relative;display:inline-block;"><button onclick="SMAuth._toggleMenu()" style="background:rgba(78,133,191,0.3);border:1px solid rgba(78,133,191,0.5);border-radius:50%;width:32px;height:32px;color:' + BLUE_TEXT + ';cursor:pointer;font-size:13px;font-weight:600;">' + currentUser.email[0].toUpperCase() +
        '</button><div id="sm-menu" style="display:none;position:absolute;right:0;top:40px;background:#1a1a2e;border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:8px;min-width:180px;box-shadow:0 4px 20px rgba(0,0,0,0.5);z-index:1000;"><div style="padding:8px 12px;color:#666;font-size:12px;border-bottom:1px solid rgba(255,255,255,0.05);">' + currentUser.email + '</div><a href="javascript:SMAuth.showAccountModal()" style="display:block;padding:8px 12px;color:#ccc;text-decoration:none;font-size:14px;">My Account</a><a href="javascript:SMAuth.logout()" style="display:block;padding:8px 12px;color:#ff6b6b;text-decoration:none;font-size:14px;">Log Out</a></div></div>';
    } else {
      el.innerHTML = '<button onclick="SMAuth.showLoginModal()" style="background:' + BLUE_GRADIENT + ';border:none;border-radius:999px;padding:8px 20px;color:#fff;cursor:pointer;font-size:11px;font-weight:600;letter-spacing:0.5px;text-transform:uppercase;">Log In</button>';
    }
  }

  function _toggleMenu() { var m = document.getElementById("sm-menu"); if (m) m.style.display = m.style.display === "none" ? "block" : "none"; }

  async function showAccountModal() {
    _toggleMenu();
    showModal('<button onclick="SMAuth.closeModal()" style="position:absolute;top:12px;right:16px;background:none;border:none;color:#888;font-size:20px;cursor:pointer;">\u2715</button><h2 style="margin:0 0 6px;font-size:22px;color:' + BLUE_TEXT + ';">My Account</h2><div id="sm-acct"><div style="text-align:center;padding:40px;"><div class="sm-loader"></div></div></div>');
    try {
      var me = await api("/api/user/me"), ent = await api("/api/user/entitlements"), ord = await api("/api/user/orders");
      var ae = ent.entitlements.find(function (e) { return !e.is_expired && (e.total_count < 0 || e.remaining > 0); });
      var labels = { spark: "The Spark", seeker: "The Seeker", oracle: "The Oracle" };
      var ehtml = '<p style="color:#888;font-size:13px;">No active plan.</p>';
      if (ae) { var rt = ae.total_count < 0 ? "Unlimited" : ae.remaining + "/" + ae.total_count; ehtml = '<div style="background:rgba(78,133,191,0.1);border:1px solid rgba(78,133,191,0.25);border-radius:12px;padding:14px;"><div style="color:' + BLUE_TEXT + ';font-weight:600;margin-bottom:6px;">' + (labels[ae.plan_type] || ae.plan_type) + '</div><div style="color:#4ade80;">Remaining: ' + rt + "</div></div>"; }
      var ohtml = ord.orders.length ? ord.orders.map(function (o) { return '<div style="padding:6px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:12px;display:flex;justify-content:space-between;"><span style="color:#666;">' + (labels[o.plan_type] || o.plan_type) + '</span><span style="color:#999;">$' + o.amount.toFixed(2) + "</span></div>"; }).join("") : '<p style="color:#555;font-size:12px;">No orders</p>';
      document.getElementById("sm-acct").innerHTML = '<div><div style="margin-bottom:16px;"><div style="font-size:11px;color:#555;">EMAIL</div><div style="color:#ccc;">' + me.email + "</div></div><div style='margin-bottom:16px'><div style='font-size:11px;color:#555;margin-bottom:6px;'>PLAN</div>" + ehtml + "</div><div><div style='font-size:11px;color:#555;margin-bottom:6px;'>ORDERS</div>" + ohtml + "</div></div>";
    } catch (e) { document.getElementById("sm-acct").innerHTML = '<p style="color:#ff6b6b;">' + e.message + "</p>"; }
  }

  async function _checkPending() {
    var p = sessionStorage.getItem("sm_pending");
    if (p && token) { sessionStorage.removeItem("sm_pending"); var d = JSON.parse(p); showMethodChoice(d.pt, d.pl, d.pr); }
  }

  async function init() {
    // Handle OAuth redirect back with token
    var params = new URLSearchParams(window.location.search);
    var oauthToken = params.get("oauth_token");
    if (oauthToken) {
      token = oauthToken;
      localStorage.setItem("sm_token", token);
      // Clean URL — remove oauth_token param without reloading
      var url = new URL(window.location);
      url.searchParams.delete("oauth_token");
      url.searchParams.delete("email");
      url.searchParams.delete("oauth_error");
      window.history.replaceState({}, "", url);
      await fetchMe();
      if (currentUser) { await fetchPremiumStatus(); }
      updateNavbar();
      return;
    }
    // Check for OAuth error
    var oauthError = params.get("oauth_error");
    if (oauthError) {
      var url = new URL(window.location);
      url.searchParams.delete("oauth_error");
      window.history.replaceState({}, "", url);
      alert("Google login was cancelled or encountered an error. Please try again.");
    }

    if (token) { await fetchMe(); if (currentUser) { await fetchPremiumStatus(); await _checkPending(); } }
    updateNavbar();
    // Inject loader style
    if (!document.getElementById("sm-loader-style")) {
      var s = document.createElement("style"); s.id = "sm-loader-style"; s.textContent = ".sm-loader{display:inline-block;width:36px;height:36px;border:3px solid rgba(78,133,191,0.2);border-top-color:" + BLUE_TEXT + ";border-radius:50%;animation:sm-spin 1s linear infinite;}@keyframes sm-spin{to{transform:rotate(360deg)}}";
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
    _doLogin, _doRegister, _doForgot, _continuePay, _guestPay, _guestDo, _toggleMenu, _goStart
  };
})();

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { SMAuth.init(); });
else SMAuth.init();
