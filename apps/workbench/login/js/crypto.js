/* =========================================================
   智枢智能工作台 · 口令派生
   PBKDF2-SHA256。优先使用 Web Crypto（crypto.subtle），
   当页面不在安全上下文（例如通过局域网 IP 以 http 打开，
   此时 crypto.subtle 为 undefined）时自动降级为内置的
   纯 JS 实现，两条路径产出完全一致的结果。

   ZhiCrypto.raw.* 以十六进制输出中间结果，便于与将来的
   服务端实现做逐字节对齐校验。
   ========================================================= */
(function (global) {
    'use strict';

    /* ---------- SHA-256 ---------- */
    var K = new Uint32Array([
        0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
    ]);

    function sha256(bytes) {
        var l = bytes.length;
        var total = (((l + 8) >> 6) + 1) << 6;
        var m = new Uint8Array(total);
        m.set(bytes);
        m[l] = 0x80;

        var bits = l * 8;
        var hi = Math.floor(bits / 4294967296);
        var lo = bits >>> 0;
        m[total - 8] = (hi >>> 24) & 255;
        m[total - 7] = (hi >>> 16) & 255;
        m[total - 6] = (hi >>> 8) & 255;
        m[total - 5] = hi & 255;
        m[total - 4] = (lo >>> 24) & 255;
        m[total - 3] = (lo >>> 16) & 255;
        m[total - 2] = (lo >>> 8) & 255;
        m[total - 1] = lo & 255;

        var h0 = 0x6a09e667, h1 = 0xbb67ae85, h2 = 0x3c6ef372, h3 = 0xa54ff53a,
            h4 = 0x510e527f, h5 = 0x9b05688c, h6 = 0x1f83d9ab, h7 = 0x5be0cd19;
        var w = new Uint32Array(64);
        var i, t;

        for (i = 0; i < total; i += 64) {
            for (t = 0; t < 16; t++) {
                var o = i + t * 4;
                w[t] = (m[o] << 24) | (m[o + 1] << 16) | (m[o + 2] << 8) | m[o + 3];
            }
            for (t = 16; t < 64; t++) {
                var x = w[t - 15], y = w[t - 2];
                var s0 = ((x >>> 7) | (x << 25)) ^ ((x >>> 18) | (x << 14)) ^ (x >>> 3);
                var s1 = ((y >>> 17) | (y << 15)) ^ ((y >>> 19) | (y << 13)) ^ (y >>> 10);
                w[t] = (w[t - 16] + s0 + w[t - 7] + s1) >>> 0;
            }

            var a = h0, b = h1, c = h2, d = h3, e = h4, f = h5, g = h6, h = h7;
            for (t = 0; t < 64; t++) {
                var S1 = ((e >>> 6) | (e << 26)) ^ ((e >>> 11) | (e << 21)) ^ ((e >>> 25) | (e << 7));
                var ch = (e & f) ^ (~e & g);
                var t1 = (h + S1 + ch + K[t] + w[t]) >>> 0;
                var S0 = ((a >>> 2) | (a << 30)) ^ ((a >>> 13) | (a << 19)) ^ ((a >>> 22) | (a << 10));
                var maj = (a & b) ^ (a & c) ^ (b & c);
                var t2 = (S0 + maj) >>> 0;
                h = g;
                g = f;
                f = e;
                e = (d + t1) >>> 0;
                d = c;
                c = b;
                b = a;
                a = (t1 + t2) >>> 0;
            }

            h0 = (h0 + a) >>> 0;
            h1 = (h1 + b) >>> 0;
            h2 = (h2 + c) >>> 0;
            h3 = (h3 + d) >>> 0;
            h4 = (h4 + e) >>> 0;
            h5 = (h5 + f) >>> 0;
            h6 = (h6 + g) >>> 0;
            h7 = (h7 + h) >>> 0;
        }

        var out = new Uint8Array(32);
        var hs = [h0, h1, h2, h3, h4, h5, h6, h7];
        for (i = 0; i < 8; i++) {
            out[i * 4] = (hs[i] >>> 24) & 255;
            out[i * 4 + 1] = (hs[i] >>> 16) & 255;
            out[i * 4 + 2] = (hs[i] >>> 8) & 255;
            out[i * 4 + 3] = hs[i] & 255;
        }
        return out;
    }

    /* ---------- HMAC-SHA256 ---------- */
    var BLOCK = 64;

    function hmacSha256(key, msg) {
        var k = key.length > BLOCK ? sha256(key) : key;
        var pad = new Uint8Array(BLOCK);
        pad.set(k);

        var ipad = new Uint8Array(BLOCK + msg.length);
        var opad = new Uint8Array(BLOCK + 32);
        for (var i = 0; i < BLOCK; i++) {
            ipad[i] = pad[i] ^ 0x36;
            opad[i] = pad[i] ^ 0x5c;
        }
        ipad.set(msg, BLOCK);
        opad.set(sha256(ipad), BLOCK);
        return sha256(opad);
    }

    /* ---------- PBKDF2-SHA256 ---------- */
    function pbkdf2(password, salt, iterations, dkLen) {
        var hLen = 32;
        var blocks = Math.ceil(dkLen / hLen);
        var out = new Uint8Array(blocks * hLen);
        var seed = new Uint8Array(salt.length + 4);
        seed.set(salt);

        for (var b = 1; b <= blocks; b++) {
            seed[salt.length] = (b >>> 24) & 255;
            seed[salt.length + 1] = (b >>> 16) & 255;
            seed[salt.length + 2] = (b >>> 8) & 255;
            seed[salt.length + 3] = b & 255;

            var u = hmacSha256(password, seed);
            var acc = u.slice();
            for (var i = 1; i < iterations; i++) {
                u = hmacSha256(password, u);
                for (var j = 0; j < hLen; j++) acc[j] ^= u[j];
            }
            out.set(acc, (b - 1) * hLen);
        }
        return out.slice(0, dkLen);
    }

    /* ---------- 编码 ---------- */
    function utf8(s) {
        if (typeof TextEncoder === 'function') return new TextEncoder().encode(String(s));
        var str = unescape(encodeURIComponent(String(s)));
        var bin = new Uint8Array(str.length);
        for (var i = 0; i < str.length; i++) bin[i] = str.charCodeAt(i);
        return bin;
    }

    function toB64(bytes) {
        var s = '';
        for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
        return global.btoa(s);
    }

    function fromB64(b64) {
        var s = global.atob(String(b64));
        var out = new Uint8Array(s.length);
        for (var i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
        return out;
    }

    function toHex(bytes) {
        var s = '';
        for (var i = 0; i < bytes.length; i++) s += ('0' + bytes[i].toString(16)).slice(-2);
        return s;
    }

    /* ---------- 安全随机 ---------- */
    function randomBytes(n) {
        var b = new Uint8Array(n);
        if (global.crypto && global.crypto.getRandomValues) {
            global.crypto.getRandomValues(b);
        } else {
            for (var i = 0; i < n; i++) b[i] = Math.floor(Math.random() * 256);
        }
        return b;
    }

    /* ---------- 统一入口 ---------- */
    var subtle = (global.crypto && global.crypto.subtle) ? global.crypto.subtle : null;
    var MODE = subtle ? 'webcrypto' : 'js';

    async function deriveRaw(password, saltBytes, iterations, dkLen) {
        var pw = utf8(password);
        if (subtle) {
            var key = await subtle.importKey('raw', pw, 'PBKDF2', false, ['deriveBits']);
            var bits = await subtle.deriveBits(
                {name: 'PBKDF2', salt: saltBytes, iterations: iterations, hash: 'SHA-256'},
                key, dkLen * 8
            );
            return new Uint8Array(bits);
        }
        return pbkdf2(pw, saltBytes, iterations, dkLen);
    }

    /* 派生口令摘要（返回 Base64） */
    async function derive(password, saltB64, iterations, dkLen) {
        return toB64(await deriveRaw(password, fromB64(saltB64), iterations, dkLen || 32));
    }

    /* 常数时间比较，避免通过响应时间判断前缀匹配长度 */
    function equals(a, b) {
        if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
        var diff = 0;
        for (var i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
        return diff === 0;
    }

    async function verify(password, saltB64, iterations, expectedB64) {
        var got = await derive(password, saltB64, iterations, 32);
        return equals(got, expectedB64);
    }

    function randomSalt(n) {
        return toB64(randomBytes(n || 16));
    }

    function randomHex(n) {
        return toHex(randomBytes(n || 16));
    }

    /* 账号不存在时也走一遍同代价的派生，抹平「邮箱是否已注册」的耗时差异 */
    var DUMMY_SALT = toB64(utf8('zhishu.dummy.salt'));

    async function equalize(password, iterations) {
        try {
            await derive(password || '', DUMMY_SALT, iterations, 32);
        } catch (e) {
        }
    }

    global.ZhiCrypto = {
        mode: MODE,
        iterations: 0,
        derive: derive,
        verify: verify,
        equals: equals,
        randomSalt: randomSalt,
        randomHex: randomHex,
        equalize: equalize,
        raw: {
            sha256Hex: function (s) {
                return toHex(sha256(utf8(s)));
            },
            hmacHex: function (k, m) {
                return toHex(hmacSha256(utf8(k), utf8(m)));
            },
            pbkdf2Hex: function (p, s, c, dkLen) {
                return toHex(pbkdf2(utf8(p), utf8(s), c, dkLen || 32));
            }
        }
    };
})(window);
