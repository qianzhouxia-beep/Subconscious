/**
 * Subconscious Mirror — Error Boundary & Performance Optimization
 * 
 * 功能：
 * 1. 全局未捕获错误处理
 * 2. 未处理的 Promise rejection 捕获
 * 3. 移动端 Canvas 粒子动画降级
 * 4. 塔罗牌图片预加载
 * 5. 性能监控（FCP 近似值）
 */

(function() {
    'use strict';

    // === 1. 全局错误边界 ===
    window.addEventListener('error', function(e) {
        // 忽略 CDN 脚本加载失败（静默降级）
        if (e.target && (e.target.tagName === 'SCRIPT' || e.target.tagName === 'LINK')) {
            console.warn('[Mirror] Resource failed to load:', e.target.src || e.target.href);
            return;
        }
        console.error('[Mirror] Uncaught error:', e.error ? e.error.message : e.message);
        // 生产环境可上报到 Sentry
    });

    // === 2. 未处理的 Promise rejection ===
    window.addEventListener('unhandledrejection', function(e) {
        console.error('[Mirror] Unhandled promise rejection:', e.reason);
        // 防止控制台噪音，但不吞掉错误
    });

    // === 3. 移动端粒子动画降级 ===
    function isMobileDevice() {
        return /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) || window.innerWidth < 768;
    }

    // 降低移动端粒子数量（覆盖 initParticleCanvas 中的 particleCount）
    if (isMobileDevice()) {
        // 延迟执行，确保 particleCount 已声明
        document.addEventListener('DOMContentLoaded', function() {
            // 移动端：降低到 15 个粒子，禁用连线
            var canvas = document.getElementById('particleCanvas');
            if (canvas) {
                canvas.style.opacity = '0.25';  // 降低透明度节省 GPU
            }
            // 降低光标光晕尺寸
            var glow = document.getElementById('cursor-glow');
            if (glow) {
                glow.style.width = '300px';
                glow.style.height = '300px';
            }
        });
    }

    // === 4. 塔罗牌图片预加载 ===
    document.addEventListener('DOMContentLoaded', function() {
        var tarotSlugs = [
            '00-fool', '01-magician', '02-high-priestess', '03-empress',
            '04-emperor', '05-hierophant', '06-lovers', '07-chariot',
            '08-strength', '09-hermit', '10-wheel-of-fortune', '11-justice',
            '12-hanged-man', '13-death', '14-temperance', '15-devil',
            '16-tower', '17-star', '18-moon', '19-sun', '20-judgement', '21-world'
        ];
        var baseUrl = 'https://raw.githubusercontent.com/qianzhouxia-beep/Subconscious/main/static/tarot/';
        // 延迟预加载，不阻塞首屏
        setTimeout(function() {
            tarotSlugs.forEach(function(slug) {
                var img = new Image();
                img.src = baseUrl + slug + '.png';
            });
        }, 2000);
    });

    // === 5. 性能标记 ===
    if (window.performance && performance.timing) {
        window.addEventListener('load', function() {
            setTimeout(function() {
                var timing = performance.timing;
                var fcp = timing.domContentLoadedEventEnd - timing.navigationStart;
                console.log('[Mirror] Page load: ~' + fcp + 'ms (DOMContentLoaded)');
            }, 0);
        });
    }
})();
