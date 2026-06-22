# Subconscious Mirror 前端功能测试用例

> 基于 `index.html`（约 2800 行单文件应用）完整分析生成  
> 覆盖维度：正常场景 / 边界场景 / 异常场景 / UI 状态 / 跨浏览器兼容性 / 无障碍

---

## 1. 梦境对话系统（Oracle）

### 1.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ORA-001 | 输入梦境描述并发送消息 | 1. 在 textarea 输入"我梦见在太空中漂浮" 2. 点击"Transmit"按钮 | 1. 用户消息气泡显示在对话区（右对齐，标签"YOU"）2. 输入框清空 3. AI 思考气泡出现（3个跳动圆点）4. API 返回后显示 AI 回复气泡（左对齐，标签"AETHERIS"）5. turnCount 变为 1，turn-indicator 更新为"Connection 1 / 5" | P0 |
| ORA-002 | 完成 5 轮对话后生成 report | 1. 依次发送 5 条梦境描述 2. 每次等待 AI 回复 | 1. 前 4 轮返回 mode=question，显示 AI 追问气泡 2. 第 5 轮返回 mode=report，显示"神谕正在编织您的命运报告..." 3. 3 秒后 full-screen report 弹窗出现 4. free_part 显示在"心理学解析"区域 5. paid_part 模糊显示在"东方命理路径"区域 | P0 |
| ORA-003 | Premium 用户查看完整报告 | 1. 以 premium 用户身份登录 2. 完成 5 轮对话 | 1. paid_part 区域无模糊（无 .blurred 类）2. 无支付覆盖层（pay-overlay 为 hidden）3. 塔罗牌区域正常显示（如有 [TAROT:N] 标记） | P0 |
| ORA-004 | 报告中的塔罗牌展示 | 1. 完成报告生成 2. 检查塔罗牌区域 | 1. paid_part 含 [TAROT: N] 时，塔罗牌区域可见 2. 显示对应编号的塔罗牌图片 3. 显示中/英文牌名（根据语言）4. 提取并显示牌面解读文字 | P1 |
| ORA-005 | Reset 重置对话 | 1. 进行若干轮对话后 2. 点击"Reset"按钮 | 1. chatHistory 清空，turnCount 归零 2. 对话区恢复欢迎文本 3. final-report 隐藏 4. 输入框清空 5. 环境图标选中状态清除 6. turn-indicator 重置 | P0 |
| ORA-006 | 回车发送消息（需手动按 Transmit） | 1. 输入梦境文本后按回车键 | textarea 允许回车换行，不触发 sendMessage（需用户点击 Transmit） | P2 |

### 1.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ORA-007 | 空输入点击发送 | 1. 不输入任何文字 2. 点击"Transmit" | 不发送请求，sendMessage 函数直接 return（content 为空） | P0 |
| ORA-008 | 仅输入空格 | 1. 输入" "（空格）2. 点击"Transmit" | trim() 后为空，不发送请求 | P1 |
| ORA-009 | 输入 5000 字边界 | 1. 输入恰好 5000 个字符 2. 点击"Transmit" | 正常发送，不触发超长提示 | P1 |
| ORA-010 | 输入超过 5000 字 | 1. 输入 5001 个字符 2. 点击"Transmit" | 弹出 alert："输入内容过长,请控制在5000字以内"（中文）/ "Input too long, max 5000 characters"（英文），不发送请求 | P0 |
| ORA-011 | 输入特殊字符（emoji/Unicode） | 1. 输入含 emoji 的梦境描述"我梦见🔮和👻" | 正常发送，内容不被截断或乱码 | P1 |
| ORA-012 | 输入 HTML/XSS 内容 | 1. 输入 `<script>alert(1)</script>` 2. 发送 | addBubble 使用 innerText 而非 innerHTML，XSS 被安全转义 | P0 |
| ORA-013 | 按钮防重复点击 | 1. 快速连续点击"Transmit"按钮 2 次 | 第一次点击后 sendBtn.disabled = true，第二次点击被 return 拦截 | P0 |
| ORA-014 | 第 5 轮后继续对话 | 1. 完成 5 轮对话生成 report 后 2. 再次输入文本发送 | report 已展示，resetOracle 后才能继续新一轮对话（用户需手动 reset） | P2 |

### 1.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ORA-015 | 网络断开时发送消息 | 1. 断开网络 2. 输入梦境文本 3. 点击发送 | 1. fetch 抛出异常 2. 思考气泡移除 3. 显示错误气泡"以太连接出现波动,请重试" 4. 网络状态栏显示"Connection lost" | P0 |
| ORA-016 | API 返回 429 限流 | 1. 快速连续发送消息 2. API 返回 429 | 1. apiFetch 检测到 429 2. 显示气泡"请求过于频繁,请稍后再试" 3. 返回 null，不崩溃 | P1 |
| ORA-017 | API 返回 401 | 1. session 过期 2. 发送消息 | 1. apiFetch 检测到 401 2. 自动调用 initSession() 重新初始化 3. 返回 null | P1 |
| ORA-018 | API 返回 error 字段 | 1. 模拟后端返回 `{error: "Server Error"}` | 1. addBubble 显示 error 内容 2. 不崩溃 | P0 |
| ORA-019 | API 响应超过 10 秒 | 1. 发送消息 2. API 10 秒内无响应 | 1. 10 秒后显示慢速提示"神谕正在穿越梦境领域..." 2. 动画脉冲提示 3. API 返回后提示移除 | P1 |
| ORA-020 | fetch 抛出异常 | 1. 模拟 fetch 失败 | 1. 思考气泡移除 2. 发送按钮恢复 3. 显示错误气泡 4. 网络状态栏触发 offline 逻辑 | P0 |

### 1.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ORA-021 | 发送按钮禁用状态 | 1. 输入文本 2. 点击发送 3. 观察按钮状态 | 发送期间 sendBtn.disabled = true，回复返回后 disabled = false | P0 |
| ORA-022 | 输入框状态指示器 | 1. 空输入框 2. 输入文字 | 空时显示"Awaiting Transmission"（灰），有内容时显示"Synchronizing Frequencies..."（accent 色），状态圆点脉冲 | P1 |
| ORA-023 | 思考气泡动画 | 1. 发送消息后观察 | 3 个圆点依次闪烁（blink 动画，延迟 0/0.33s/0.66s），气泡从下往上 GSAP 动画入场 | P1 |
| ORA-024 | 对话气泡滚动 | 1. 连续发送多条消息 2. 观察对话区滚动 | 每条新消息自动滚动到底部（scrollTop = scrollHeight） | P1 |
| ORA-025 | Report 弹窗入场动画 | 1. 等待 report 生成 | GSAP from opacity:0, y:60 持续 0.8s，ease: power3.out | P2 |

### 1.5 跨浏览器兼容性

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ORA-026 | 移动端发送消息 | 1. 在 iPhone Safari 中打开 2. 输入文本 3. 点击发送 | 键盘弹出不遮挡输入框，发送后键盘收起，对话正常显示 | P0 |
| ORA-027 | 小屏（<375px）布局 | 1. 在 320px 宽度视口打开 2. 输入文本 3. 发送 | 输入区按钮不重叠，文字大小可读，气泡宽度合理 | P1 |

### 1.6 无障碍

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ORA-028 | textarea 键盘导航 | 1. Tab 键聚焦到 textarea 2. 输入文本 3. Tab 到 Transmit 按钮 4. Enter 发送 | 焦点顺序正确，键盘可完成全部操作 | P1 |
| ORA-029 | textarea 无障碍属性 | 1. 检查 textarea 元素 | 有 aria-label="Dream description"，有 placeholder，有 maxlength="5000" | P1 |

---

## 2. 语音输入

### 2.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| VOI-001 | 按住语音按钮录音（鼠标） | 1. 鼠标按住 Voice 按钮 2. 对着麦克风说话 3. 松开鼠标 | 1. 按钮变红（voice-recording 类），标签变"录音中" 2. voice-bar 显示，红色圆点脉冲 3. 实时显示 Web Speech 转写文本 4. 松开后停止录音，转写结果填入输入框 5. voice-bar 隐藏 | P0 |
| VOI-002 | 按住语音按钮录音（触摸） | 1. 触摸按住 Voice 按钮 2. 说话 3. 手指离开 | 与鼠标操作一致，touchstart/touchend 事件正常触发 | P0 |
| VOI-003 | Web Speech 成功后文本润色 | 1. 语音输入完成（Web Speech 有结果） 2. 观察转写后处理 | 1. voice-bar 显示"整理中..."黄色状态 2. 调用 /api/clean-text 润色 3. 润色后填入输入框（追加到现有内容） 4. 显示绿色勾号"完成" 5. 600ms 后 voice-bar 隐藏 | P0 |
| VOI-004 | Web Speech 失败 → MediaRecorder 回退 | 1. 在不支持 Web Speech 的浏览器中录音 2. 松开按钮 | 1. Web Speech 无结果 2. MediaRecorder 停止录音 3. voice-bar 显示"识别中..." 4. 发送音频到 /api/transcribe（Whisper）5. 返回文本填入输入框 | P1 |
| VOI-005 | 语音追加到已有文本 | 1. 输入框已有文字"我梦见" 2. 语音输入"一条蛇" | 文本追加："我梦见 一条蛇"（自动添加空格分隔），不会覆盖原有内容 | P1 |

### 2.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| VOI-006 | 录音时麦克风权限拒绝 | 1. 点击 Voice 按钮 2. 在权限弹窗中选择"拒绝" | 1. getUserMedia 抛出异常 2. 弹出 alert"需要麦克风权限才能语音输入。" 3. 不进入录音状态 | P0 |
| VOI-007 | 极短录音（<1 秒） | 1. 快速点击 Voice 按钮（<200ms）2. 松开 | 1. voiceMouseDown 设置为 true 2. mouseup 触发 stopVoiceInput 3. 处理空音频或无转写结果 4. 不崩溃 | P1 |
| VOI-008 | 长时间录音（>1 分钟） | 1. 按住 Voice 按钮超过 60 秒 | 1. Web Speech continuous=true 持续工作 2. MediaRecorder 持续采集（200ms 分片）3. 松开后正常处理 | P1 |
| VOI-009 | 鼠标离开按钮时松开 | 1. 按住 Voice 按钮 2. 鼠标移出按钮范围 3. 松开鼠标 | mouseleave 事件触发 stopVoiceInput，录音正常停止 | P1 |
| VOI-010 | 触摸取消（touchcancel） | 1. 触摸按住 2. 触发系统级中断（如来电） | touchcancel 触发 stopVoiceInput，正常处理或取消 | P2 |
| VOI-011 | 处理中再次按下 | 1. 语音输入处理中（isProcessing=true）2. 再次点击 Voice 按钮 | startVoiceInput 检查 isProcessing，直接 return 不执行 | P1 |

### 2.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| VOI-012 | /api/clean-text 润色失败 | 1. 语音录入成功 2. 模拟 /api/clean-text 返回 500 | 1. catch 捕获异常 2. 降级使用原始 rawText 填入输入框 3. 不崩溃 | P0 |
| VOI-013 | /api/clean-text 返回劣化文本 | 1. 语音录入成功 2. /api/clean-text 返回极短结果（<原文 30%） | 检测 cleaned.length < rawText.length * 0.3，降级使用原始文本 | P1 |
| VOI-014 | /api/transcribe Whisper 失败 | 1. Web Speech 无结果 2. MediaRecorder 回退 3. /api/transcribe 返回错误 | 1. voice-bar 显示"识别失败，请重试" 2. 红色状态指示 3. 2 秒后 voice-bar 隐藏 | P1 |
| VOI-015 | Web Speech 错误处理 | 1. Web Speech 返回 error 事件（非 no-speech/aborted） | console.log 记录错误，静默回退到 MediaRecorder | P1 |
| VOI-016 | 空音频 chunks | 1. 录音但未采集到音频数据（audioChunks.length=0） | processVoiceAudio 检测到空 chunks，console.warn，调用 cancelVoiceInput | P2 |

### 2.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| VOI-017 | 录音状态 UI | 1. 按住 Voice 按钮 | 按钮红色脉冲（voice-recording 类 + mic-pulse 动画），SVG 红色阴影，标签变"录音中" | P0 |
| VOI-018 | voice-bar 各阶段显示 | 1. 录音→识别→润色→完成 | 录音：红色图标+脉冲圆点+"Recording"；识别中：黄色旋转图标+"Transcribing"；润色中：黄色旋转+"Polishing"；完成：绿色勾+"Done" | P0 |
| VOI-019 | 语音完成后 UI 恢复 | 1. 语音输入完成后 | voice-btn 恢复默认样式，input-status-dot 恢复蓝色脉冲，status text 恢复默认 | P1 |

### 2.5 跨浏览器兼容性

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| VOI-020 | Safari（WebKit）Web Speech | 1. 在 Safari 中使用语音输入 | 使用 window.webkitSpeechRecognition，功能正常 | P0 |
| VOI-021 | Firefox（无 Web Speech） | 1. 在 Firefox 中使用语音输入 | Web Speech 不可用，自动回退到 MediaRecorder + Whisper API | P1 |
| VOI-022 | 移动端浏览器录音 | 1. 在 Chrome Android / Safari iOS 中使用语音 | 1. getUserMedia 请求麦克风权限 2. 权限授予后正常录音 3. 触摸事件正常响应 | P0 |
| VOI-023 | MediaRecorder MIME 类型兼容 | 1. 在不同浏览器中录音 | 自动检测支持的 MIME 类型（webm/opus > webm > ogg/opus > 默认），使用第一个支持的 | P1 |

### 2.6 无障碍

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| VOI-024 | 语音按钮键盘可访问 | 1. Tab 聚焦到 Voice 按钮 2. 按空格/Enter | 按钮可聚焦（非 button 元素但为可点击 div），需要有键盘事件支持 | P2 |
| VOI-025 | 录音状态 aria 通知 | 1. 开始录音 2. 检查无障碍树 | voice-bar 应有适当的 aria-live 或状态描述 | P2 |

---

## 3. 付费墙

### 3.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| PAY-001 | PayPal SDK 动态加载 | 1. 页面加载 2. 等待 initPayPalSdk 执行 | 1. 调用 /api/paypal/config 获取 clientId 2. 动态创建 script 标签加载 PayPal SDK 3. 加载完成后渲染所有 .paypal-sdk-container 中的按钮 | P0 |
| PAY-002 | PayPal 支付按钮渲染 | 1. PayPal SDK 加载完成 2. 查看定价区域和解锁区域 | 1. 3 个定价卡片各渲染 PayPal 按钮 2. report 中解锁区域渲染 PayPal 按钮（label='checkout'）3. 按钮样式 vertical/blue/pill | P0 |
| PAY-003 | PayPal 支付成功流程 | 1. 点击 PayPal 按钮 2. 完成 PayPal 支付流程 3. 返回页面 | 1. onApprove 触发 2. 调用 /api/paypal/capture-order 3. 设置 sm_auth_token cookie 4. 页面 reload 5. premium 状态刷新 | P0 |
| PAY-004 | License Key 验证成功 | 1. 在 report 付费区点击"Use redemption code" 2. 输入有效 license key 3. 点击"Verify Key" | 1. 输入框显示 2. 按钮变"验证中..." 3. 验证成功后模糊移除，付费覆盖层隐藏 4. isPremiumUser 设为 true | P0 |
| PAY-005 | 推荐裂变：邀请 2 人解锁 | 1. 打开推荐弹窗 2. 复制链接分享 3. 2 位好友通过链接访问 | 1. 弹窗显示 ref-link 2. 复制按钮显示"Copied!" 3. 每 5 秒轮询 /referral/status 4. count >= 2 时自动解锁 5. 进度条 100% | P1 |
| PAY-006 | 支付取消 | 1. 点击 PayPal 按钮 2. 在 PayPal 页面取消支付 | onCancel 触发，console.log 记录，无页面变化 | P1 |

### 3.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| PAY-007 | 空 License Key 验证 | 1. 不输入 license key 2. 点击"Verify Key" | key.trim() 为空，直接 return 不发送请求 | P1 |
| PAY-008 | PayPal 弹窗被拦截 | 1. 点击 PayPal 按钮 2. 浏览器拦截弹窗 | 1. payWithPayPalFallback 检测 popup 为 null 2. 调用 /api/paypal/create-order 获取 approve URL 3. 当前窗口跳转到 PayPal 4. 3 分钟后按钮自动恢复 | P1 |
| PAY-009 | 推荐裂变：仅 1 人加入 | 1. 分享链接 2. 仅 1 人通过链接访问 | 进度条显示 50%，文本显示"已加入的旅人: 1 / 2"，不触发解锁 | P1 |
| PAY-010 | 推荐裂变：自己点击自己的链接 | 1. 获取自己的 ref-link 2. 在同一个浏览器打开 | refBy !== refId 检查应防止自推 | P2 |
| PAY-011 | 多次连续点击 license 验证 | 1. 快速连续点击"Verify Key" | 第一次点击后 btn.disabled = true，后续点击无效 | P1 |
| PAY-012 | PayPal 按钮容器内容变化检测 | 1. PayPal SDK 显示 fallback 信息时 | MutationObserver 检测到 browser/浏览器/fallback 文本，自动重新渲染按钮 | P2 |

### 3.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| PAY-013 | PayPal SDK 加载失败 | 1. 模拟 PayPal CDN 不可用 | 1. initPayPalSdk catch 异常 2. console.warn 记录 3. 页面不崩溃，PayPal 按钮不渲染 4. fallback 支付方式仍可用（license key/推荐） | P0 |
| PAY-014 | /api/paypal/config 无 clientId | 1. 后端未配置 PayPal clientId | 1. fetch 返回 config.clientId 为空 2. 函数直接 return，不加载 SDK | P0 |
| PAY-015 | /api/paypal/create-order 失败 | 1. 点击 PayPal 按钮 2. create-order API 返回错误 | 1. throw Error 2. onError 触发 3. console.error 记录 | P0 |
| PAY-016 | /api/paypal/capture-order 返回非预期结果 | 1. 支付完成 2. capture 返回 status !== 'captured' | 1. throw Error 2. alert "Payment verification failed..." 3. 不设置 cookie | P0 |
| PAY-017 | License 验证 API 错误 | 1. 输入 license key 2. /api/verify-license 返回 500 | 1. catch 捕获 2. alert "以太连接出现波动,请重试" 3. 按钮恢复 | P0 |
| PAY-018 | License 验证返回非解锁状态 | 1. 输入无效 license key | 1. res.ok && data.status !== 'unlocked' 2. alert 显示 data.message/data.error 3. 不解锁 | P1 |
| PAY-019 | 推荐裂变：API 错误 | 1. /referral/status 返回 500 | catch 静默处理，不影响用户体验 | P1 |

### 3.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| PAY-020 | 付费墙模糊效果 | 1. 免费用户查看 report | 1. res-paid-blur 有 .blurred 类（filter:blur(18px);opacity:0.2;pointer-events:none）2. pay-overlay 覆盖在模糊区域上方 | P0 |
| PAY-021 | 付费墙解锁动画 | 1. 支付成功或输入 license key 后 | .blurred 移除（transition:all 1.5s ease-in-out），内容逐渐清晰 | P1 |
| PAY-022 | License 输入框显示/隐藏 | 1. 点击"Use redemption code" | 1. t-have-key 隐藏 2. license-input-wrapper 显示 3. 输入框和验证按钮可见 | P1 |
| PAY-023 | 推荐弹窗打开/关闭 | 1. 点击推荐按钮打开弹窗 2. 点击 ✕ 或遮罩关闭 | 1. modal 显示为 flex 2. focus 锁定在弹窗内 3. 关闭后焦点恢复到触发元素 4. 清除轮询定时器 | P1 |
| PAY-024 | 复制链接按钮反馈 | 1. 在推荐弹窗中点击"Copy" | 1. 使用 navigator.clipboard 复制 2. 按钮文字变为"Copied!"/"已复制" 3. 2 秒后恢复 | P1 |
| PAY-025 | PayPal 支付中按钮状态 | 1. fallback 支付时点击按钮 | 按钮 disabled，显示旋转动画 + "Connecting..."，opacity 降低 | P1 |

### 3.5 跨浏览器兼容性

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| PAY-026 | PayPal 弹窗拦截环境 | 1. 在严格弹窗拦截的浏览器中支付 | popup 为 null，fallback 到当前窗口跳转 | P0 |
| PAY-027 | 无 JavaScript 环境 | 1. 禁用 JS 查看付费区 | <noscript> 显示 PayPal requires JavaScript 提示，按钮 disabled | P2 |

### 3.6 无障碍

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| PAY-028 | 推荐弹窗焦点陷阱 | 1. 打开推荐弹窗 2. 连续 Tab | 焦点在弹窗内循环（trapFocus），不会逃逸到背景元素 | P1 |
| PAY-029 | 弹窗 Escape 关闭 | 1. 打开推荐/条款弹窗 2. 按 Escape | 弹窗关闭，焦点恢复 | P1 |
| PAY-030 | License 输入框 label | 1. 检查 license key 输入框 | 有 aria-label="License key" | P1 |

---

## 4. 环境变量收集

### 4.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ENV-001 | 滑块调整并更新标签 | 1. 拖动 Intensity 滑块从 5 到 10 | 1. atmo-intensity-val 文字从"中等"变为"震撼" 2. 实时更新，input 事件触发 | P0 |
| ENV-002 | 环境图标弹窗选择（presleep） | 1. 点击"睡前状态"图标 2. 在弹窗中选择"焦虑" | 1. 弹窗定位在图标附近 2. t-env-presleep 文字变为"焦虑" 3. 对应 env-icon 添加 .selected 类 4. 弹窗关闭 | P0 |
| ENV-003 | 环境图标弹窗选择（dreamtype） | 1. 点击"梦境类型" 2. 选择"清醒梦" | 同 ENV-002，文字和选中状态正确更新 | P1 |
| ENV-004 | 符号标签输入 | 1. 在符号输入框输入"飞行" 2. 按回车 | 1. 生成 tag span（.symbol-tag-item）2. 显示"飞行 ✕" 3. 占位文字隐藏 4. 输入框清空 | P0 |
| ENV-005 | 符号标签删除 | 1. 添加符号标签后 2. 点击标签上的 ✕ | 1. 标签从 DOM 移除 2. 所有标签删除后占位文字恢复显示 | P0 |
| ENV-006 | 环境变量随消息一起发送 | 1. 设置滑块和环境图标 2. 输入梦境描述 3. 发送 | 请求 body 中 messages 包含 [Atmosphere: intensity=..., lucidity=..., vividness=...] 和 [Environment: Presleep=...] 等上下文信息 | P1 |

### 4.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ENV-007 | 符号标签空输入 | 1. 不输入文字直接按回车 | symInput.value.trim() === ''，不创建标签 | P1 |
| ENV-008 | 符号标签超长输入（>20 字符） | 1. 输入 25 个字符的符号名 | maxlength="20" 限制输入长度，超出部分无法输入 | P1 |
| ENV-009 | 添加大量符号标签（>20 个） | 1. 连续添加 25 个标签 | 容器使用 flex-wrap，标签换行显示，不溢出 | P2 |
| ENV-010 | 符号标签包含特殊字符 | 1. 输入含 `<`、`>` 的标签文字 | 使用 innerHTML 直接插入，需要验证无 XSS（使用 textContent 更安全） | P1 |
| ENV-011 | 滑块边界值 | 1. 将 Intensity 滑块拖到 1 2. 拖到 10 | 标签正确显示"微弱"和"震撼"，不会越界 | P1 |
| ENV-012 | 快速切换环境图标选择 | 1. 选择"睡前状态"为"焦虑" 2. 再选择"平静" | 文字更新为最后一次选择的值 | P1 |

### 4.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ENV-013 | 弹窗定位超出视口 | 1. 在页面底部点击环境图标 | 1. openEnvPopup 计算 top 和 left 2. 保持弹窗在视口内（left≥12, left+320≤innerWidth-12, top+300≤innerHeight） | P1 |
| ENV-014 | 弹窗在小屏幕定位 | 1. 在 320px 宽度设备上点击环境图标 | 弹窗宽度 320px 可能超出屏幕，left 计算需适配小屏 | P2 |

### 4.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ENV-015 | 环境图标未选中/已选中状态 | 1. 未选中图标 2. 选中图标 | 未选中：灰色 SVG + 灰色文字；选中：.selected 类，accent 色 SVG + accent 色文字 | P0 |
| ENV-016 | 弹窗打开/关闭动画 | 1. 点击图标打开弹窗 2. 关闭弹窗 | 打开：GSAP from opacity:0, y:-8, 0.25s；关闭：GSAP to opacity:0, y:-8, 0.15s → display:none | P1 |
| ENV-017 | 弹窗点击外部关闭 | 1. 打开弹窗 2. 点击弹窗外部区域 | document click 事件检测，弹窗关闭 | P1 |
| ENV-018 | 符号标签占位文字显示/隐藏 | 1. 无标签 2. 添加标签 3. 删除全部标签 | MutationObserver 监听子元素变化，动态切换占位文字 display | P1 |

### 4.5 跨浏览器兼容性

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ENV-019 | 滑块在移动端拖动 | 1. 在移动端拖动滑块 | touch 事件正常，滑块值实时更新，标签正确 | P1 |
| ENV-020 | 环境图标弹窗在移动端 | 1. 在 375px 宽度设备点击图标 | 弹窗定位在图标下方，不超出屏幕，可正常选择 | P1 |

### 4.6 无障碍

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| ENV-021 | 滑块键盘操作 | 1. Tab 聚焦到滑块 2. 使用左右箭头调整值 | 滑块值正常变化，标签更新 | P1 |
| ENV-022 | 符号输入框键盘导航 | 1. Tab 聚焦到符号输入 2. 输入文字 3. 按回车添加 | 流程正常 | P1 |
| ENV-023 | 环境图标键盘触发 | 1. Tab 聚焦到图标 2. 按 Enter | 图标 div 非 button 元素，onclick 可能需要键盘事件支持 | P2 |

---

## 5. 塔罗牌展示

### 5.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| TAR-001 | 报告含塔罗牌标记时展示 | 1. 完成 5 轮对话 2. paid_part 含 [TAROT: 0] | 1. tarot-section 显示 2. 显示 00-the-fool.png 图片 3. 牌名为"The Fool"/"愚者" 4. 显示牌面解读文字 | P0 |
| TAR-002 | 22 张牌全部映射正确 | 1. 测试 [TAROT: 0] 到 [TAROT: 21] | 每张牌对应正确的图片路径（00-xx.png 到 21-xx.png）和名称 | P1 |
| TAR-003 | 报告不含塔罗牌标记 | 1. paid_part 不含 [TAROT: N] | tarot-section 保持 hidden，不显示 | P1 |

### 5.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| TAR-004 | [TAROT: 超出范围] | 1. paid_part 含 [TAROT: 99] | tarotIndex > 21，条件不满足，tarot-section 保持 hidden | P1 |
| TAR-005 | [TAROT: 负数] | 1. paid_part 含 [TAROT: -1] | tarotIndex < 0，条件不满足 | P2 |
| TAR-006 | [TAROT: 非数字] | 1. paid_part 含 [TAROT: abc] | parseInt 返回 NaN，条件 tarotIndex >= 0 不满足 | P2 |
| TAR-007 | 多个 [TAROT: N] 标记 | 1. paid_part 含两个 [TAROT: 0] 和 [TAROT: 1] | 只匹配第一个 tarotIndex（match 返回第一个匹配），其他 [TAROT: N] 从文本中移除 | P2 |

### 5.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| TAR-008 | 塔罗牌图片加载失败 | 1. 图片 URL 返回 404 | img error 事件可能被全局错误处理捕获，不崩溃 | P1 |
| TAR-009 | paid_part 为 null/undefined | 1. API 返回 result.data.paid_part 为空 | 1. if (result.data.paid_part) 条件不满足 2. 跳过塔罗牌和付费内容渲染 | P1 |

### 5.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| TAR-010 | 塔罗牌区域布局 | 1. 查看塔罗牌展示区域 | 左侧：160x240 圆角卡片容器 + 图片；右侧：牌名 + 解读文字；flex-col md:flex-row | P1 |
| TAR-011 | 中英文牌名切换 | 1. 英文环境查看塔罗牌 2. 切换中文 | 英文显示 tarotCards[N].en，中文显示 tarotCards[N].zh | P1 |

---

## 6. 符号速查

### 6.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SYM-001 | 搜索梦境符号 | 1. 在符号搜索框输入"Water" 2. 点击"Look Up" | 1. 显示加载状态（旋转动画 + "Consulting the collective unconscious..."）2. 调用 /api/symbol-lookup 3. 显示解读结果 | P0 |
| SYM-002 | 按回车搜索 | 1. 在搜索框输入"Snake" 2. 按 Enter | 触发 lookupSymbol()，与点击按钮效果一致 | P0 |
| SYM-003 | 点击快速符号标签搜索 | 1. 点击"Fire"标签按钮 | 1. 搜索框自动填入"Fire" 2. 自动触发搜索 3. 显示解读结果 | P0 |
| SYM-004 | 中文符号搜索 | 1. 切换为中文 2. 搜索"水" | 1. 请求 body 包含 lang: 'zh' 2. 返回中文解读 | P1 |

### 6.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SYM-005 | 空搜索 | 1. 不输入任何内容 2. 点击"Look Up" | symbol.trim() 为空，直接 return | P1 |
| SYM-006 | 超长搜索词（>60 字符） | 1. 输入 70 个字符的搜索词 | maxlength="60" 限制输入 | P1 |
| SYM-007 | 搜索特殊字符 | 1. 搜索"🌊"（emoji） | 正常发送请求，后端返回解读或错误 | P1 |
| SYM-008 | 连续快速搜索 | 1. 快速连续搜索"Water"、"Fire"、"Snake" | 每次搜索独立执行，最新结果覆盖旧结果，不崩溃 | P1 |

### 6.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SYM-009 | 搜索 API 返回错误 | 1. 搜索不存在的符号 2. API 返回 error | 1. 加载状态隐藏 2. result-content 显示 error 信息 3. result 区域显示 | P0 |
| SYM-010 | 搜索 API 网络错误 | 1. 断开网络 2. 搜索符号 | 1. catch 捕获异常 2. 加载状态隐藏 3. 显示"Failed to connect. Please try again." 4. result 区域显示 | P0 |
| SYM-011 | 搜索结果为空 | 1. API 返回空 interpretation | result-content 为空，result 区域显示但内容为空 | P2 |

### 6.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SYM-012 | 初始空状态 | 1. 页面加载后查看符号搜索区域 | 显示空状态：🔍 图标 + "Type a symbol above to reveal its meaning" | P1 |
| SYM-013 | 加载状态 | 1. 搜索符号时 | 1. symbol-empty 隐藏 2. symbol-result 隐藏 3. symbol-loading 显示：旋转圆圈 + 文字 | P0 |
| SYM-014 | 结果状态 | 1. 搜索完成后 | 1. loading 隐藏 2. result 显示：accent 色圆点脉冲 + "Interpretation" + 结果内容 | P0 |
| SYM-015 | 错误状态 | 1. API 返回错误后 | 1. loading 隐藏 2. result 显示错误信息 | P1 |
| SYM-016 | 快速标签中英文切换 | 1. 英文环境查看标签 2. 切换为中文 | 标签文字从"Water"变为"水"，"Snake"变为"蛇"等 | P1 |

### 6.5 跨浏览器兼容性

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SYM-017 | 移动端符号搜索 | 1. 在移动端输入并搜索 | 键盘弹出不遮挡搜索框和按钮，结果正常显示 | P1 |

---

## 7. UI 特效

### 7.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| UI-001 | Canvas 粒子动画 | 1. 页面加载 2. 观察背景 | 1. 40 个粒子在画布中移动 2. 粒子之间距离 < 150px 时绘制连线 3. 粒子淡入淡出（opacity 0.1-0.5）4. requestAnimationFrame 持续运行 | P0 |
| UI-002 | 粒子鼠标交互（吸引） | 1. 移动鼠标到画布中 | 1. 距离鼠标 < 250px 的粒子被吸引（vx,vy 增加）2. 距离鼠标 < 80px 的粒子被排斥（vx,vy 减少 2.5x） | P1 |
| UI-003 | 粒子鼠标离开 | 1. 鼠标移出视口 | mouse.active = false，粒子不再受鼠标影响，自由漂移 | P1 |
| UI-004 | GSAP 滚动揭示 | 1. 滚动页面到 .reveal-on-scroll 元素 | 1. IntersectionObserver 检测到元素进入视口（threshold:0.15）2. 添加 .is-visible 类 3. 触发 opacity:0→1, translateY:30→0 动画（1s） | P0 |
| UI-005 | 光标光晕效果 | 1. 移动鼠标 | cursor-glow div 跟随鼠标移动（left/top 更新），600px 圆形渐变光晕 | P1 |
| UI-006 | 玻璃态卡片悬停效果 | 1. 鼠标悬停 .glass-card 元素 | 1. 背景变亮 2. 边框变 accent 色 3. 上移 8px（translateY(-8px)）4. 添加阴影 5. 顶部渐变线出现 6. 图标容器放大旋转 7. 数字移动 | P1 |

### 7.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| UI-007 | 页面不可见时暂停动画 | 1. 切换到其他浏览器标签页 | visibilitychange 事件触发 stopAnim()，取消 requestAnimationFrame | P1 |
| UI-008 | 页面恢复可见时继续动画 | 1. 从其他标签页切回 | visibilitychange 事件触发 startAnim()，重新开始粒子动画 | P1 |
| UI-009 | 窗口大小调整 | 1. 缩放浏览器窗口 | 1. Canvas resize 事件更新 width/height 2. 粒子不会丢失或错位 | P1 |
| UI-010 | prefers-reduced-motion 媒体查询 | 1. 系统设置"减少动画" | 所有动画 duration 降至 0.01ms，typing-dot 动画停止 | P2 |

### 7.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| UI-011 | Canvas 不支持 | 1. 在禁用 Canvas 的浏览器中打开 | canvas 标签存在但 2D context 可能为 null，需优雅降级 | P2 |
| UI-012 | GSAP 未加载 | 1. 模拟 CDN 加载 GSAP 失败 | 1. GSAP 动画不执行（opacity 可能保持 0）2. 需提供 fallback | P2 |

### 7.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| UI-013 | Navbar 滚动背景变化 | 1. 在 Hero 区域（scrollY < heroBottom-80）2. 滚动到 Hero 以下 | Hero 区域：透明背景（rgba(20,20,20,0.05)）；下方：实色背景（rgba(20,20,20,0.92)） | P1 |
| UI-014 | Nav 链接下划线动画 | 1. 鼠标悬停 .nav-link | ::after 伪元素宽度从 0 过渡到 100%（0.3s），accent 色 | P1 |
| UI-015 | 移动端导航菜单 | 1. 在 <768px 视口点击汉堡按钮 | 1. mobile-nav 显示（display:flex）2. 全屏覆盖，毛玻璃背景 3. 链接大字显示 4. 点击 ✕ 关闭 | P0 |
| UI-016 | 输入框聚焦发光 | 1. 聚焦 textarea（.input-glow-card:focus-within） | 边框变 accent 色，添加蓝色阴影 | P1 |

### 7.5 跨浏览器兼容性

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| UI-017 | Canvas 性能（低端设备） | 1. 在低性能手机上打开页面 | 40 粒子 + O(n²) 连线，不应导致明显卡顿 | P1 |
| UI-018 | backdrop-filter 兼容性 | 1. 在不支持 backdrop-filter 的浏览器中 | glass-card 仍可读，失去毛玻璃效果但不影响功能 | P2 |
| UI-019 | 移动端触摸滚动 | 1. 在移动端滚动页面 | reveal-on-scroll 正常触发，粒子动画继续运行 | P1 |

---

## 8. 国际化（i18n）

### 8.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| I18N-001 | 页面加载时语言检测 | 1. 首次访问（无 localStorage）2. 浏览器语言为中文 | 1. navigator.language.startsWith('zh') 为 true 2. currentLang 设为 'zh' 3. 页面渲染中文 | P0 |
| I18N-002 | 英文语言渲染 | 1. 浏览器语言为英文或 localStorage 为 'en' | currentLang 为 'en'，页面渲染英文 | P0 |
| I18N-003 | 语言切换 | 1. 点击语言切换按钮（ZH/EN） | 1. currentLang 切换 2. localStorage 更新 3. window.location.reload() 刷新页面 | P0 |
| I18N-004 | 语言偏好持久化 | 1. 切换为中文 2. 关闭页面 3. 重新打开 | localStorage 读取 sm_lang 为 'zh'，页面中文渲染 | P0 |
| I18N-005 | 所有 UI 文本动态渲染 | 1. 检查页面所有 id 以 "t-" 开头的元素 | 1. renderLanguage() 遍历所有 [id^="t-"] 元素 2. textarea/input 的 placeholder 更新 3. 其他元素的 innerHTML 更新 | P0 |
| I18N-006 | SEO 元素更新 | 1. 切换语言后检查 | 1. document.documentElement.lang 更新 2. document.title 更新 | P1 |

### 8.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| I18N-007 | localStorage 中语言值为无效值 | 1. 手动设置 sm_lang 为 'fr' | currentLang 为 'en'（非 'zh' 则默认 'en'） | P2 |
| I18N-008 | 缺失的 i18n key | 1. 某个 t-xxx 元素无对应翻译 | renderLanguage 中 t[key] 为 undefined，元素不更新，保留 HTML 默认文本 | P1 |
| I18N-009 | 滑块标签国际化 | 1. 切换语言后查看滑块标签 | atmo_labels_i/l/v 的 JSON 字符串被正确解析，显示对应语言标签 | P1 |
| I18N-010 | 环境弹窗选项国际化 | 1. 切换语言后打开环境弹窗 | 选项文字根据 currentLang 显示对应语言（中文：疲惫/平静/兴奋...；英文：Exhausted/Calm/Excited...） | P1 |

### 8.3 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| I18N-011 | 语言按钮状态 | 1. 当前英文 2. 当前中文 | 英文时按钮显示"ZH"，中文时按钮显示"EN" | P1 |
| I18N-012 | 语言切换后页面完整重载 | 1. 切换语言 | 页面 reload，所有状态重置，session 重新初始化 | P0 |

---

## 9. 会话管理

### 9.1 正常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SES-001 | 页面加载时初始化会话 | 1. 打开页面 | 1. init() 调用 initSession() 2. POST /api/session/init 3. 获取 sessionId 4. 获取 premium 状态 5. 后续请求携带 Authorization: Bearer {sessionId} | P0 |
| SES-002 | Premium 用户状态识别 | 1. 以已付费用户身份打开页面 | initSession 返回 premium: true，isPremiumUser 设为 true | P0 |
| SES-003 | 网络状态检测 - 离线 | 1. 断开网络 | 1. offline 事件触发 2. 网络状态栏显示"Connection lost. Please check your network." 3. 红色背景 | P0 |
| SES-004 | 网络状态检测 - 恢复 | 1. 恢复网络连接 | 1. online 事件触发 2. 显示"Connection restored!" 3. 绿色背景 4. 3 秒后自动隐藏 | P0 |
| SES-005 | API 请求携带 sessionId | 1. 初始化后发送任意 API 请求 | apiFetch 自动添加 Authorization header | P1 |
| SES-006 | 推荐链接参数处理 | 1. 通过 ?ref=xxx 参数访问页面 | 1. urlParams 解析 refBy 2. initReferral 调用 /referral/click 3. 记录推荐点击 | P1 |

### 9.2 边界场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SES-007 | Session 初始化失败 | 1. /api/session/init 返回 500 | 1. catch 捕获 2. console.error 记录 3. sessionId 为 null 4. 后续请求不带 Authorization header | P1 |
| SES-008 | 无 refBy 参数访问 | 1. 直接访问页面（无 ?ref=） | 1. refBy 为 null 2. initReferral 仍会调用 /referral/init 创建新 refId | P1 |
| SES-009 | 推荐 ID 已存在于 localStorage | 1. 之前已生成 refId 2. 再次打开页面 | 不重新调用 /referral/init，使用已有 refId | P1 |
| SES-010 | 支付成功 URL 参数处理 | 1. 从 PayPal 返回带 ?payment=success&email=xxx | 1. 调用 checkPayPalPremium 2. alert 显示成功消息 3. URL 清理（history.replaceState） | P1 |
| SES-011 | 支付取消 URL 参数处理 | 1. 从 PayPal 返回带 ?payment=cancel | alert 显示取消消息，URL 清理 | P1 |

### 9.3 异常场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SES-012 | API 返回 401 时自动重试 | 1. Session 过期 2. 发送 API 请求 | 1. apiFetch 检测 401 2. 重新调用 initSession() 3. 返回 null（调用方需处理） | P1 |
| SES-013 | fetch 异常时网络状态检测 | 1. 网络断开 2. 发送 API 请求 | 1. catch 中检查 navigator.onLine 2. 如果离线，调用 showNetworkStatus | P1 |

### 9.4 UI 状态

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| SES-014 | 网络状态栏动画 | 1. 触发离线 | 1. transform translateY(-100%) → translateY(0) 2. 0.3s 过渡 | P1 |
| SES-015 | 网络恢复状态栏自动隐藏 | 1. 网络恢复 | 绿色背景 3 秒后添加 class 移除动画，状态栏隐藏 | P1 |

---

## 10. 综合场景 / 端到端

### 10.1 完整用户流程

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| E2E-001 | 免费用户完整解梦流程 | 1. 打开页面 2. 调整环境变量（滑块+图标+标签）3. 输入梦境描述 4. 进行 5 轮对话 5. 查看报告 6. 查看付费墙 | 所有步骤顺利完成，报告 free_part 可读，paid_part 模糊 | P0 |
| E2E-002 | Premium 用户完整流程 | 1. 以 premium 身份打开 2. 完成解梦 3. 查看完整报告 4. 查看塔罗牌 | 完整报告可见，塔罗牌正确展示 | P0 |
| E2E-003 | 支付 + 解梦流程 | 1. 完成解梦 2. 在报告页支付 3. 页面重载 4. 再次解梦查看完整报告 | 支付成功后 premium 状态持久化，报告完整可见 | P0 |
| E2E-004 | 语言切换 + 解梦 | 1. 中文环境完成解梦 2. 切换英文 3. 重新解梦 | 语言切换后所有 UI 正确翻译，解梦流程正常 | P0 |
| E2E-005 | 语音输入 + 解梦 | 1. 使用语音输入梦境 2. 发送 3. 完成 5 轮对话 | 语音转写准确，后续流程正常 | P1 |
| E2E-006 | 移动端完整流程 | 1. 在 iPhone/Android 打开 2. 导航到解梦区 3. 输入梦境 4. 完成解梦 5. 查看报告 | 所有功能正常，无布局问题，触摸交互流畅 | P0 |

### 10.2 压力场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| E2E-007 | 多标签页同时操作 | 1. 打开两个标签页 2. 两个标签页同时解梦 | 每个标签页独立 session，不相互干扰 | P2 |
| E2E-008 | 长时间页面停留 | 1. 打开页面后放置 30 分钟 2. 再进行解梦 | Session 可能过期，401 自动重试机制正常 | P1 |
| E2E-009 | 快速页面刷新 | 1. 连续多次刷新页面（F5） | 每次刷新正常初始化，不出现错误 | P2 |

### 10.3 安全场景

| ID | 场景描述 | 操作步骤 | 期望结果 | 优先级 |
|----|----------|----------|----------|--------|
| E2E-010 | XSS 防护 - 输入框 | 1. 在梦境描述中输入 `<img src=x onerror=alert(1)>` | addBubble 使用 innerText，HTML 被转义 | P0 |
| E2E-011 | XSS 防护 - 符号标签 | 1. 在符号输入中输入 `<script>alert(1)</script>` 2. 按回车 | 标签使用 innerHTML 直接插入（潜在 XSS 风险），应验证是否转义 | P0 |
| E2E-012 | XSS 防护 - AI 返回内容 | 1. AI 返回含 HTML 的内容 | formatReportText 使用 innerHTML 渲染（信任后端），需后端确保输出安全 | P0 |

---

## 测试覆盖总结

| 模块 | 用例数 | P0 | P1 | P2 |
|------|--------|----|----|-----|
| 1. 梦境对话系统 | 29 | 14 | 10 | 5 |
| 2. 语音输入 | 25 | 9 | 13 | 3 |
| 3. 付费墙 | 30 | 14 | 11 | 5 |
| 4. 环境变量收集 | 23 | 5 | 13 | 5 |
| 5. 塔罗牌展示 | 11 | 2 | 6 | 3 |
| 6. 符号速查 | 17 | 4 | 9 | 4 |
| 7. UI 特效 | 19 | 4 | 12 | 3 |
| 8. 国际化 | 12 | 4 | 7 | 1 |
| 9. 会话管理 | 15 | 4 | 10 | 1 |
| 10. 综合场景 | 12 | 8 | 3 | 1 |
| **合计** | **193** | **68** | **94** | **31** |

---

> 文档版本：v1.0  
> 生成日期：2026-06-22  
> 基于代码版本：v33.3.0  
> 代码文件：`/workspace/Subconscious/index.html`（约 2782 行）
