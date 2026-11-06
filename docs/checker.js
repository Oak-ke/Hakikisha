/* Hakikisha — in-browser checker. Mirrors app/checks/landing.py, domain.py and scoring.py.
   Runs with no server. Set window.HAKIKISHA_API to a deployed backend URL for deeper checks. */
(function (root) {
  "use strict";

  const rule = (code, weight, patterns, en, sw) => ({
    code, weight, en, sw, res: patterns.map((p) => new RegExp(p, "i")),
  });

  const RULES = [
    rule("cure_claim", 25, [
      "\\b100\\s*%\\s*(cure|natural|guaranteed|effective|results)",
      "\\b(permanent(ly)?|complete(ly)?|total(ly)?)\\s+(cure|heal)",
      "\\bcures?\\s+(in|within)\\s+\\d+\\s*(days?|hours?|weeks?)",
      "\\bmiracle\\b", "\\bguaranteed\\s+(cure|results)",
      "\\btiba\\s+ya\\s+kudumu\\b", "\\bpona\\s+kabisa\\b", "\\bdawa\\s+ya\\s+asili\\b",
    ], "Promises a miracle or guaranteed cure", "Inaahidi tiba ya muujiza au ya uhakika"),
    rule("health_target", 10, [
      "\\bprostat", "\\btezi\\s+dume", "\\berectile", "\\bnguvu\\s+za\\s+kiume",
      "\\bdiabet", "\\bkisukari", "\\bjoint\\s+pain", "\\bmaumivu\\s+ya\\s+viungo",
      "\\bhypertension", "\\bpresha\\b", "\\bhigh\\s+blood\\s+pressure",
    ], "Targets a chronic health condition", "Inalenga ugonjwa sugu"),
    rule("doctor_secret", 20, [
      "doctors?\\s+(don'?t|do\\s+not|hate|hide|won'?t)",
      "pharma(ceutical)?\\s+compan(y|ies)\\s+(hide|don'?t\\s+want|hate)",
      "\\bsecret\\s+(remedy|cure|formula|method)",
    ], "Claims doctors are hiding this from you", "Inadai madaktari wanakuficha hili"),
    rule("urgency", 15, [
      "\\bonly\\s+\\d+\\s+(left|remaining|pieces|packs|bottles)",
      "\\boffer\\s+ends\\b", "\\blimited\\s+(stock|offer|time)\\b", "\\bhurry\\b",
      "\\bimebaki\\s+\\d+", "\\bleo\\s+tu\\b", "\\bpromo(tion)?\\s+ends\\b",
    ], "Pressures you to buy quickly", "Inakulazimisha kununua haraka"),
    rule("pay_first", 25, [
      "\\btill\\s*(no\\.?|number|#)?\\s*:?\\s*\\d{5,7}",
      "\\bpay\\s*bill\\s*(no\\.?|number|#)?\\s*:?\\s*\\d{5,7}",
      "\\blipa\\s+na\\s+m-?pesa\\b", "\\bpay\\s+(before|first|in\\s+advance)\\b",
      "\\bsend\\s+(money|payment|the\\s+money)\\s+to\\b", "\\btuma\\s+pesa\\b",
    ], "Asks for M-Pesa payment up front", "Inaomba malipo ya M-Pesa kwanza"),
    rule("whatsapp_order", 5, [
      "wa\\.me/", "api\\.whatsapp\\.com", "order\\s+(via|on|through)\\s+whatsapp",
    ], "Orders only through WhatsApp", "Maagizo kupitia WhatsApp tu"),
    rule("fake_news_frame", 15, [
      "\\bbreaking\\s+news\\b", "\\bexclusive\\s+interview\\b",
      "\\b(citizen\\s+tv|ntv\\s+kenya|ktn\\s+news|nation\\s+media)\\b",
      "\\bas\\s+seen\\s+on\\s+(tv|citizen|ntv|ktn)\\b",
    ], "Dressed up as a news story", "Imepambwa ionekane kama habari"),
    rule("endorsement", 15, [
      "\\b(dr|doctor|prof)\\.?\\s+\\w+\\s+(reveals|recommends|discovered|explains|confirms)",
      "\\bendorsed\\s+by\\b",
      "\\bapproved\\s+by\\s+(the\\s+)?(ministry|who|kebs|ppb|kemri)\\b",
    ], "Uses a doctor's or official's name to sell", "Inatumia jina la daktari au taasisi kuuza"),
    rule("big_numbers", 10, [
      "\\b\\d{1,3}[,.]\\d{3}\\s+(people|customers|kenyans|men|women)\\s+(have\\s+)?(bought|ordered|been\\s+cured|cured)",
      "\\bsold\\s+out\\s+\\d+\\s+times\\b",
    ], "Quotes huge, unverifiable sales or cure numbers", "Inataja takwimu kubwa zisizothibitishwa"),
  ];

  // Keep in sync with app/data/brands.json — verify official domains before relying on them.
  const BRANDS = {
    safaricom: ["safaricom.co.ke", "safaricom.com"], mpesa: ["safaricom.co.ke"],
    citizen: ["citizen.digital"], nation: ["nation.africa"],
    standardmedia: ["standardmedia.co.ke"], ecitizen: ["ecitizen.go.ke"],
    pharmacyboard: ["pharmacyboardkenya.org"], kmpdc: ["kmpdc.go.ke"],
    equitybank: ["equitybank.co.ke"], kcbgroup: ["kcbgroup.com"],
  };
  const GOV_KEYWORDS = ["ministry", "government", "gov-ke", "govke", "moh-kenya", "kenyagov"];
  const SUSPICIOUS_TLDS = new Set(["xyz", "top", "shop", "online", "site", "click", "buzz", "icu",
    "live", "store", "fun", "cyou", "sbs", "cfd", "rest", "monster", "life"]);
  const SHORTENERS = new Set(["bit.ly", "tinyurl.com", "cutt.ly", "rb.gy", "t.ly", "is.gd",
    "shorturl.at", "ow.ly", "tiny.cc", "s.id", "rebrand.ly", "t.co", "lnkd.in", "shorturl.asia"]);
  const TWO_LEVEL = new Set(["co.ke", "go.ke", "or.ke", "ac.ke", "ne.ke", "sc.ke", "me.ke",
    "mobi.ke", "info.ke", "co.uk", "org.uk", "com.ng", "co.za", "co.tz", "co.ug", "com.au"]);

  const SW_WORDS = new Set(["habari", "tafadhali", "hii", "ni", "je", "dawa", "nisaidie", "kweli",
    "sawa", "kiungo", "angalia", "hiki", "hapa", "naomba", "kagua", "hili", "huu", "mambo", "ya",
    "kwa", "wa", "za", "tu", "leo", "pesa", "tuma", "kabisa", "sana", "nini", "gani", "hapana",
    "ndio", "msaada", "sasa", "asante", "yangu", "wangu", "hiyo"]);

  const S = (code, weight, en, sw, strong = false) => ({ code, weight, en, sw, strong });

  function extractUrls(text, limit = 3) {
    const out = [];
    for (const m of (text || "").match(/(?:https?:\/\/|www\.)[^\s<>"']+/gi) || []) {
      let u = m.replace(/[.,;:!?)\]}'"]+$/, "");
      if (/^www\./i.test(u)) u = "https://" + u;
      if (!out.includes(u)) out.push(u);
    }
    return out.slice(0, limit);
  }

  function registeredDomain(host) {
    const parts = host.toLowerCase().split(".").filter(Boolean);
    if (parts.length <= 2) return parts.join(".");
    const last2 = parts.slice(-2).join(".");
    return TWO_LEVEL.has(last2) ? parts.slice(-3).join(".") : last2;
  }

  function levenshtein(a, b) {
    if (a === b) return 0;
    let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
    for (let i = 1; i <= a.length; i++) {
      const cur = [i];
      for (let j = 1; j <= b.length; j++) {
        cur.push(Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] !== b[j - 1] ? 1 : 0)));
      }
      prev = cur;
    }
    return prev[b.length];
  }

  function lookalikeBrand(host) {
    const reg = registeredDomain(host);
    for (const officials of Object.values(BRANDS)) if (officials.includes(reg)) return null;
    const compact = host.replace(/[.\-_]/g, "");
    const tokens = host.split(/[.\-_]/).filter(Boolean);
    for (const brand of Object.keys(BRANDS)) {
      if (brand.length >= 4 && compact.includes(brand)) return brand;
      if (brand.length >= 5 && tokens.some((t) => levenshtein(t, brand) === 1)) return brand;
      if (brand.length < 4 && tokens.includes(brand)) return brand;
    }
    return null;
  }

  function urlSignals(url) {
    let u;
    try { u = new URL(url); } catch (e) { return { host: url, signals: [] }; }
    const host = u.hostname.toLowerCase();
    const out = [];
    const brand = lookalikeBrand(host);
    if (brand) out.push(S("lookalike_domain", 45, `Website imitates '${brand}' but is not its official site`,
      `Tovuti inaiga '${brand}' lakini si tovuti rasmi`));
    if (!host.endsWith(".go.ke") && GOV_KEYWORDS.some((k) => host.includes(k)))
      out.push(S("gov_impersonation", 40, "Looks like a government site but is not a .go.ke address",
        "Inaonekana ya serikali lakini si anwani ya .go.ke"));
    if (/^\d{1,3}(\.\d{1,3}){3}$/.test(host))
      out.push(S("ip_host", 20, "Link uses a bare IP address instead of a name",
        "Kiungo kinatumia anwani ya IP badala ya jina"));
    const tld = host.split(".").pop();
    if (SUSPICIOUS_TLDS.has(tld))
      out.push(S("risky_tld", 10, `Uses a cheap domain ending (.${tld}) common in scams`,
        `Inatumia kiambishi (.${tld}) kinachotumika sana na matapeli`));
    if (u.protocol === "http:")
      out.push(S("no_https", 10, "Site is not secure (no https)", "Tovuti si salama (haina https)"));
    if (SHORTENERS.has(host))
      out.push(S("shortener", 5, "Real address is hidden behind a short link — open with care",
        "Anwani halisi imefichwa kwa kiungo kifupi — fungua kwa tahadhari"));
    return { host, signals: out };
  }

  function analyseText(text) {
    if (!text) return [];
    const hits = RULES.filter((r) => r.res.some((re) => re.test(text)));
    const out = hits.map((r) => S(r.code, r.weight, r.en, r.sw));
    const codes = new Set(hits.map((r) => r.code));
    if (codes.has("cure_claim") && codes.has("health_target"))
      out.push(S("health_scam_combo", 15, "Matches the pattern of fake medicine ads",
        "Inafanana na matangazo ya dawa feki"));
    return out;
  }

  function extractEntities(text) {
    const phones = [...new Set(((text || "").match(/(?<!\d)(?:\+?254|0)\s?(?:7|1)\d{2}\s?\d{3}\s?\d{3}(?!\d)/g) || [])
      .map((p) => { const d = p.replace(/\D/g, ""); return d.startsWith("0") ? "254" + d.slice(1) : d; }))];
    const tills = [...new Set([...(text || "").matchAll(/\b(?:till|pay\s*bill)\s*(?:no\.?|number|#)?\s*:?\s*(\d{5,7})\b/gi)]
      .map((m) => m[1]))];
    return { phone: phones, till: tills };
  }

  function score(signals) {
    const total = signals.reduce((a, s) => a + s.weight, 0);
    let level = "low";
    if (signals.some((s) => s.strong) || total >= 60) level = "high";
    else if (total >= 30) level = "caution";
    return { score: Math.min(total, 100), level };
  }

  function detectLang(text) {
    const tokens = (text || "").toLowerCase().match(/[a-z]+/g) || [];
    const hits = new Set(tokens.filter((t) => SW_WORDS.has(t))).size;
    return hits >= 2 || (hits === 1 && tokens.length <= 3) ? "sw" : "en";
  }

  /** Check a message (links and/or ad text) entirely in the browser. */
  function check(text) {
    const urls = extractUrls(text);
    const textSignals = analyseText(text);
    const entities = extractEntities(text);
    const results = [];
    if (urls.length) {
      urls.forEach((url, i) => {
        const { host, signals } = urlSignals(url);
        // Text around the link (the ad copy) counts once, on the first link.
        const all = i === 0 ? signals.concat(textSignals) : signals;
        results.push({ input: url, label: host, signals: all, entities, ...score(all), mode: "browser" });
      });
    } else {
      results.push({ input: text, label: text.length > 60 ? text.slice(0, 60) + "…" : text,
        signals: textSignals, entities, ...score(textSignals), mode: "browser" });
    }
    return results;
  }

  const api = { check, analyseText, urlSignals, extractUrls, extractEntities, score, detectLang, lookalikeBrand };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Hakikisha = api;
})(typeof window !== "undefined" ? window : globalThis);
