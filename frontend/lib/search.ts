import type { Airport } from "./api";

/** Extra search terms per IATA code: Chinese names and common English variants. Display stays English. */
const ALIASES: Record<string, string[]> = {
  JFK: ["纽约", "美国", "nyc", "new york city"], LAX: ["洛杉矶", "美国"], ORD: ["芝加哥", "美国"], ATL: ["亚特兰大", "美国"],
  SFO: ["旧金山", "三藩市", "美国"], MIA: ["迈阿密", "美国"], SEA: ["西雅图", "美国"], DFW: ["达拉斯", "美国"], BOS: ["波士顿", "美国"],
  YYZ: ["多伦多", "加拿大"], YVR: ["温哥华", "加拿大"], MEX: ["墨西哥城", "墨西哥"],
  GRU: ["圣保罗", "巴西", "sao paulo"], GIG: ["里约热内卢", "里约", "巴西"], EZE: ["布宜诺斯艾利斯", "阿根廷"],
  SCL: ["圣地亚哥", "智利"], LIM: ["利马", "秘鲁"], BOG: ["波哥大", "哥伦比亚"], PTY: ["巴拿马城", "巴拿马"],
  LHR: ["伦敦", "英国", "heathrow"], CDG: ["巴黎", "法国", "paris"], FRA: ["法兰克福", "德国"], AMS: ["阿姆斯特丹", "荷兰"],
  MAD: ["马德里", "西班牙"], FCO: ["罗马", "意大利", "rome"], IST: ["伊斯坦布尔", "土耳其", "turkey", "turkiye"], ZRH: ["苏黎世", "瑞士", "zurich"],
  CPH: ["哥本哈根", "丹麦"], ATH: ["雅典", "希腊"], LIS: ["里斯本", "葡萄牙"], DUB: ["都柏林", "爱尔兰"], MUC: ["慕尼黑", "德国", "munchen"], VIE: ["维也纳", "奥地利", "wien"],
  DXB: ["迪拜", "阿联酋", "uae"], DOH: ["多哈", "卡塔尔"], AUH: ["阿布扎比", "阿联酋", "uae"], TLV: ["特拉维夫", "以色列"],
  JNB: ["约翰内斯堡", "南非"], CPT: ["开普敦", "南非"], CAI: ["开罗", "埃及"], ADD: ["亚的斯亚贝巴", "埃塞俄比亚"],
  NBO: ["内罗毕", "肯尼亚"], LOS: ["拉各斯", "尼日利亚"], CMN: ["卡萨布兰卡", "摩洛哥"],
  SIN: ["新加坡", "狮城"], HKG: ["香港", "中国香港"], NRT: ["东京", "成田", "日本", "tokyo"], HND: ["东京", "羽田", "日本", "tokyo"],
  KIX: ["大阪", "关西", "日本"], ICN: ["首尔", "仁川", "韩国", "korea", "seoul"], PEK: ["北京", "中国", "peking", "china"], PVG: ["上海", "浦东", "中国", "china"],
  TPE: ["台北", "桃园", "台湾", "中国台湾"], BKK: ["曼谷", "泰国"], KUL: ["吉隆坡", "马来西亚"], CGK: ["雅加达", "印度尼西亚", "印尼"],
  MNL: ["马尼拉", "菲律宾"], SGN: ["胡志明市", "西贡", "越南", "saigon"], DEL: ["德里", "新德里", "印度", "new delhi"], BOM: ["孟买", "印度", "bombay"],
  CMB: ["科伦坡", "斯里兰卡"], SYD: ["悉尼", "澳大利亚", "澳洲"], MEL: ["墨尔本", "澳大利亚", "澳洲"], BNE: ["布里斯班", "澳大利亚", "澳洲"],
  PER: ["珀斯", "澳大利亚", "澳洲"], AKL: ["奥克兰", "新西兰"],
};
const COUNTRY_ALIASES: Record<string, string[]> = {
  "United States": ["usa", "us", "america", "united states of america"], "United Kingdom": ["uk", "britain", "england", "great britain"],
  "United Arab Emirates": ["uae", "emirates"], "South Korea": ["korea"], "Hong Kong SAR": ["hong kong"], Türkiye: ["turkey"],
};

export const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

type Entry = { a: Airport; code: string; city: string; name: string; country: string; region: string; extra: string[] };
const cache = new WeakMap<Airport[], Entry[]>();

function index(airports: Airport[]): Entry[] {
  let e = cache.get(airports);
  if (!e) {
    e = airports.map((a) => ({
      a, code: norm(a.code), city: norm(a.city), name: norm(a.name), country: norm(a.country), region: norm(a.region),
      extra: [...(ALIASES[a.code] ?? []), ...(COUNTRY_ALIASES[a.country] ?? [])].map(norm),
    }));
    cache.set(airports, e);
  }
  return e;
}

/** Score of one token against one entry; 0 = no match. Prefix of a word beats a mid-word substring. */
function tokenScore(t: string, e: Entry): number {
  if (e.code === t) return 100;
  const prefix = (s: string) => s.startsWith(t) || s.split(/[\s\-/'’.]+/).some((w) => w.startsWith(t));
  if (e.city.startsWith(t)) return 90;
  if (e.extra.some((x) => x.startsWith(t))) return 85;
  if (e.country.startsWith(t)) return 70;
  if (prefix(e.city) || prefix(e.name)) return 65;
  if (prefix(e.country) || e.extra.some(prefix)) return 55;
  if (t.length >= 2 && (e.city.includes(t) || e.name.includes(t))) return 35;
  if (e.region.startsWith(t)) return 20;
  return 0;
}

export const POPULAR = ["JFK", "LHR", "DXB", "SIN", "HKG", "NRT", "SYD", "CDG", "LAX", "FRA"];

/** Airports matching a free-text query (city, country, airport name, IATA code, Chinese name). */
export function searchAirports(airports: Airport[], query: string, limit = 8): Airport[] {
  const q = norm(query);
  const all = index(airports);
  if (!q) return POPULAR.map((c) => airports.find((a) => a.code === c)).filter((a): a is Airport => !!a).slice(0, limit);
  const tokens = q.split(/\s+/);
  const scored: { e: Entry; s: number }[] = [];
  for (const e of all) {
    let total = 0;
    for (const t of tokens) {
      const s = tokenScore(t, e);
      if (!s) { total = 0; break; }
      total += s;
    }
    if (total) scored.push({ e, s: total + (e.a.hub ? 1 : 0) });
  }
  scored.sort((x, y) => y.s - x.s || x.e.city.localeCompare(y.e.city) || x.e.code.localeCompare(y.e.code));
  return scored.slice(0, limit).map((x) => x.e.a);
}

export const airportLabel = (a: Airport) => `${a.city} (${a.code})`;
