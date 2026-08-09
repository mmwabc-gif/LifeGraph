(function initLifeGraphCalendarMeta(global) {
  "use strict";

  const LUNAR_DAY_NAMES = [
    "", "初一", "初二", "初三", "初四", "初五", "初六", "初七", "初八", "初九", "初十",
    "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
    "廿一", "廿二", "廿三", "廿四", "廿五", "廿六", "廿七", "廿八", "廿九", "三十",
  ];

  const SOLAR_TERM_NAMES = [
    "小寒", "大寒", "立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
    "立夏", "小满", "芒种", "夏至", "小暑", "大暑", "立秋", "处暑",
    "白露", "秋分", "寒露", "霜降", "立冬", "小雪", "大雪", "冬至",
  ];

  // Widely used minute offsets for the 24 solar terms, anchored at 1900-01-06 02:05 UTC.
  // We intentionally compare the resulting UTC calendar date. This keeps the traditional
  // day-level term table stable for the 1900-2100 range without any network dependency.
  const SOLAR_TERM_MINUTES = [
    0, 21208, 42467, 63836, 85337, 107014, 128867, 150921,
    173149, 195551, 218072, 240693, 263343, 285989, 308563, 331033,
    353350, 375494, 397447, 419210, 440795, 462224, 483532, 504758,
  ];
  const SOLAR_TERM_BASE_UTC = Date.UTC(1900, 0, 6, 2, 5);
  const TROPICAL_YEAR_MS = 31556925974.7;
  const WEEKDAY_NAMES = ["星期日", "星期一", "星期二", "星期三", "星期四", "星期五", "星期六"];

  const LUNAR_TRADITIONAL_FESTIVALS = new Map([
    ["正月-1", "春节"],
    ["正月-15", "元宵"],
    ["五月-5", "端午"],
    ["七月-7", "七夕"],
    ["八月-15", "中秋"],
    ["九月-9", "重阳"],
    ["腊月-8", "腊八"],
  ]);

  let chineseCalendarFormatter = null;

  function parseIsoDate(dateKey) {
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateKey || ""));
    if (!match) return null;
    const year = Number(match[1]);
    const month = Number(match[2]);
    const day = Number(match[3]);
    const date = new Date(Date.UTC(year, month - 1, day, 12));
    if (
      date.getUTCFullYear() !== year
      || date.getUTCMonth() !== month - 1
      || date.getUTCDate() !== day
    ) return null;
    return { year, month, day, date };
  }

  function getChineseCalendarFormatter() {
    if (chineseCalendarFormatter) return chineseCalendarFormatter;
    try {
      chineseCalendarFormatter = new Intl.DateTimeFormat("zh-CN-u-ca-chinese", {
        calendar: "chinese",
        year: "numeric",
        month: "long",
        day: "numeric",
        timeZone: "UTC",
      });
      return chineseCalendarFormatter;
    } catch (_error) {
      return null;
    }
  }

  function lunarPartsForDate(date) {
    const formatter = getChineseCalendarFormatter();
    if (!formatter) return null;
    try {
      const parts = formatter.formatToParts(date);
      const monthPart = parts.find((part) => part.type === "month")?.value || "";
      const dayNumber = Number(parts.find((part) => part.type === "day")?.value || 0);
      const yearName = parts.find((part) => part.type === "yearName")?.value || "";
      if (!monthPart || dayNumber < 1 || dayNumber > 30) return null;
      return {
        monthName: monthPart,
        dayNumber,
        dayName: LUNAR_DAY_NAMES[dayNumber],
        yearName,
      };
    } catch (_error) {
      return null;
    }
  }

  function solarTermDateKey(year, termIndex) {
    if (!Number.isInteger(year) || year < 1900 || year > 2100) return null;
    if (!Number.isInteger(termIndex) || termIndex < 0 || termIndex >= SOLAR_TERM_NAMES.length) return null;
    const instant = new Date(
      SOLAR_TERM_BASE_UTC
      + TROPICAL_YEAR_MS * (year - 1900)
      + SOLAR_TERM_MINUTES[termIndex] * 60000,
    );
    return `${instant.getUTCFullYear()}-${String(instant.getUTCMonth() + 1).padStart(2, "0")}-${String(instant.getUTCDate()).padStart(2, "0")}`;
  }

  function solarTermForDateKey(dateKey) {
    const parsed = parseIsoDate(dateKey);
    if (!parsed || parsed.year < 1900 || parsed.year > 2100) return "";
    const firstIndex = (parsed.month - 1) * 2;
    for (const termIndex of [firstIndex, firstIndex + 1]) {
      if (solarTermDateKey(parsed.year, termIndex) === dateKey) return SOLAR_TERM_NAMES[termIndex];
    }
    return "";
  }

  function traditionalFestivalForDate(parsed, lunar, solarTerm) {
    if (solarTerm === "清明") return "清明";
    if (!parsed || !lunar) return "";

    const fixedFestival = LUNAR_TRADITIONAL_FESTIVALS.get(`${lunar.monthName}-${lunar.dayNumber}`);
    if (fixedFestival) return fixedFestival;

    if (lunar.monthName === "腊月") {
      const nextDate = new Date(parsed.date.getTime() + 86400000);
      const nextLunar = lunarPartsForDate(nextDate);
      if (nextLunar?.monthName === "正月" && nextLunar.dayNumber === 1) return "除夕";
    }
    return "";
  }

  function getDateMeta(dateKey) {
    const parsed = parseIsoDate(dateKey);
    if (!parsed) return null;
    const lunar = lunarPartsForDate(parsed.date);
    const solarTerm = solarTermForDateKey(dateKey);
    const festival = traditionalFestivalForDate(parsed, lunar, solarTerm);
    const lunarDisplay = lunar
      ? festival || solarTerm || (lunar.dayNumber === 1 ? lunar.monthName : lunar.dayName)
      : festival || solarTerm;
    const lunarFull = lunar ? `${lunar.monthName}${lunar.dayName}` : "";
    const gregorianFull = `${parsed.year}年${parsed.month}月${parsed.day}日 ${WEEKDAY_NAMES[parsed.date.getUTCDay()]}`;
    const tooltipParts = [gregorianFull];
    if (lunarFull) tooltipParts.push(`农历${lunarFull}`);
    if (festival) tooltipParts.push(`传统节日：${festival}`);
    if (solarTerm && solarTerm !== festival) tooltipParts.push(`节气：${solarTerm}`);

    return {
      dateKey,
      lunarMonth: lunar?.monthName || "",
      lunarDay: lunar?.dayName || "",
      lunarFull,
      lunarDisplay: lunarDisplay || "",
      solarTerm,
      festival,
      gregorianFull,
      tooltip: tooltipParts.join(" · "),
    };
  }

  const api = {
    getDateMeta,
    solarTermForDateKey,
    traditionalFestivalForDate,
  };

  global.LifeGraphCalendarMeta = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
