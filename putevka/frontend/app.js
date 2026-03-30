import React, {
  startTransition,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "https://esm.sh/react@18.2.0";
import { createRoot } from "https://esm.sh/react-dom@18.2.0/client";
import htm from "https://esm.sh/htm@3.1.1";

const html = htm.bind(React.createElement);
const PAGE_SIZE = 12;
const NIGHT_OPTIONS = [3, 5, 7, 10, 14];
const PEOPLE_OPTIONS = [1, 2, 3, 4, 5, 6];
const SORT_OPTIONS = [
  { value: "price_asc" },
  { value: "price_desc" },
  { value: "days_asc" },
  { value: "days_desc" },
];
const CATEGORY_COPY = {
  with_hotel: {
    ru: { label: "С отелем", description: "Размещение в отеле включено" },
    eu: { label: "With hotel", description: "Hotel stay included" },
  },
  without_hotel: {
    ru: { label: "Без отеля", description: "Только программа отдыха без отеля" },
    eu: { label: "No hotel", description: "Travel plan without hotel stay" },
  },
  with_pool: {
    ru: { label: "С бассейном", description: "Есть бассейн на территории" },
    eu: { label: "With pool", description: "Pool available on site" },
  },
  without_pool: {
    ru: { label: "Без бассейна", description: "Без бассейна на территории" },
    eu: { label: "No pool", description: "No pool on site" },
  },
  mountains: {
    ru: { label: "Горы", description: "Горные маршруты и локации" },
    eu: { label: "Mountains", description: "Mountain routes and locations" },
  },
  forest: {
    ru: { label: "Лес", description: "Лесные направления и эко-туризм" },
    eu: { label: "Forest", description: "Forest routes and eco travel" },
  },
  recreation_base: {
    ru: { label: "Базы отдыха", description: "Отдых на базах и турбазах" },
    eu: { label: "Recreation bases", description: "Resort bases and lodges" },
  },
  waterfront: {
    ru: { label: "У воды", description: "Рядом море, озеро или река" },
    eu: { label: "By water", description: "Near sea, lake or river" },
  },
  family: {
    ru: { label: "Семейный", description: "Подходит для поездки с детьми" },
    eu: { label: "Family", description: "Good for trips with children" },
  },
  all_inclusive: {
    ru: { label: "Все включено", description: "Питание и часть активностей включены" },
    eu: { label: "All inclusive", description: "Meals and part of activities included" },
  },
};
const TRANSLIT_MAP = {
  А: "A", а: "a", Б: "B", б: "b", В: "V", в: "v", Г: "G", г: "g",
  Д: "D", д: "d", Е: "E", е: "e", Ё: "Yo", ё: "yo", Ж: "Zh", ж: "zh",
  З: "Z", з: "z", И: "I", и: "i", Й: "Y", й: "y", К: "K", к: "k",
  Л: "L", л: "l", М: "M", м: "m", Н: "N", н: "n", О: "O", о: "o",
  П: "P", п: "p", Р: "R", р: "r", С: "S", с: "s", Т: "T", т: "t",
  У: "U", у: "u", Ф: "F", ф: "f", Х: "Kh", х: "kh", Ц: "Ts", ц: "ts",
  Ч: "Ch", ч: "ch", Ш: "Sh", ш: "sh", Щ: "Sch", щ: "sch", Ъ: "", ъ: "",
  Ы: "Y", ы: "y", Ь: "", ь: "", Э: "E", э: "e", Ю: "Yu", ю: "yu",
  Я: "Ya", я: "ya",
};
const COPY = {
  ru: {
    title: "Путевки по России",
    eyebrow: "маршрут отдыха",
    calm: "спокойный режим",
    heroCopy:
      "Удобный каталог с живым поиском, быстрыми подсказками и спокойной навигацией по направлениям без визуальной каши.",
    variants: "вариантов",
    averagePrice: "средняя цена",
    trip: "поездка",
    flow: "поток выдачи",
    launchSearch: "запустить поиск",
    updating: "обновляем",
    source: "источник",
    updated: "обновлено",
    minimum: "минимум",
    maximum: "максимум",
    liveNote: (count) => `Каталог уже показывает ${count} реальных вариантов и продолжает догружаться в фоне.`,
    stableNote: "Выдача сейчас стабильна. Можно сузить поиск или запустить новый проход.",
    searchLabel: "что ищем",
    cityLabel: "город",
    priceLabel: "цена",
    nightsLabel: "ночей",
    peopleLabel: "людей",
    sortLabel: "сортировка",
    anyPrice: "любая",
    searchPlaceholder: "море, spa, горы",
    cityPlaceholder: "Сочи, Саки, Белокуриха",
    searchAction: "искать",
    resetAction: "сбросить",
    hints: "подсказки",
    hintsLoading: "подбираем запросы",
    cities: "города",
    citiesLoading: "собираем города",
    chosen: "вы выбрали",
    navigator: "Навигатор",
    allCategories: "все категории",
    activeCategories: (count) => `${count} активных`,
    plan: "План отдыха",
    concise: "без лишнего текста",
    duration: "длительность",
    party: "состав",
    start: "старт",
    averageBill: "средний чек",
    destinations: "Направления",
    destinationHint: "живые счётчики по текущим фильтрам",
    results: "вариантов",
    cityAll: "город: все",
    cityOne: (city) => `город: ${city}`,
    page: (current, total) => `страница ${current} из ${total}`,
    tripMeta: (nights, people) => `${nights} ночей · ${people} чел.`,
    tile: "плитка",
    list: "лента",
    noOptions: "Подходящих вариантов нет. Попробуйте убрать часть фильтров или выбрать другой город.",
    pulse: "Пульс",
    searching: "поиск идёт",
    done: "поиск завершён",
    inCatalog: "в каталоге",
    regions: "Регионы",
    regionsHint: "куда быстрее перейти",
    typeSlice: "Срез по типам",
    typeHint: "самое частое в выдаче",
    back: "назад",
    forward: "вперёд",
    open: "открыть",
    exactPrice: "точная цена с сайта",
    reviewButton: "отзывы",
    reviewsTitle: "Отзывы",
    reviewsLoading: "загружаем отзывы",
    reviewsEmpty: "Пока нет отзывов по этому объекту.",
    reviewsOpen: "перейти на объект",
    authOpen: "войти",
    authTitle: "Аккаунт",
    authSubtitle: "Регистрация и вход по логину и паролю.",
    authLoginTab: "вход",
    authRegisterTab: "регистрация",
    usernameLabel: "логин",
    usernamePlaceholder: "придумайте логин",
    passwordLabel: "пароль",
    passwordPlaceholder: "введите пароль",
    confirmPasswordLabel: "повтор пароля",
    confirmPasswordPlaceholder: "повторите пароль",
    authLoginAction: "войти",
    authRegisterAction: "зарегистрироваться",
    authLogout: "выйти",
    authLoggedIn: (username) => `вы вошли как ${username}`,
    authPasswordMismatch: "Пароли не совпадают.",
    authRequired: "Заполните логин и пароль.",
    close: "закрыть",
    guestLabel: "гость",
    reviewCount: (count) => `${count} отзывов`,
    sort: {
      price_asc: "Дешевле",
      price_desc: "Дороже",
      days_asc: "Короче",
      days_desc: "Дольше",
    },
    stage: {
      queued: "сбор",
      seed: "первая волна",
      regions: "по регионам",
      details: "детализация",
      idle: "готово",
      error: "ошибка",
    },
    themeDay: "День",
    themeNight: "Ночь",
  },
  eu: {
    title: "Putevki Across Russia",
    eyebrow: "travel route",
    calm: "steady mode",
    heroCopy:
      "A calmer catalog with live search, quick hints and a cleaner route through destinations instead of visual noise.",
    variants: "offers",
    averagePrice: "average price",
    trip: "trip plan",
    flow: "live stream",
    launchSearch: "run search",
    updating: "updating",
    source: "source",
    updated: "updated",
    minimum: "minimum",
    maximum: "maximum",
    liveNote: (count) => `The catalog already shows ${count} real offers and keeps loading more in the background.`,
    stableNote: "The feed is stable now. You can narrow the search or start a fresh pass.",
    searchLabel: "search",
    cityLabel: "city",
    priceLabel: "price",
    nightsLabel: "nights",
    peopleLabel: "people",
    sortLabel: "sorting",
    anyPrice: "any",
    searchPlaceholder: "sea, spa, mountains",
    cityPlaceholder: "Sochi, Saki, Belokurikha",
    searchAction: "search",
    resetAction: "reset",
    hints: "suggestions",
    hintsLoading: "finding ideas",
    cities: "cities",
    citiesLoading: "loading cities",
    chosen: "selected",
    navigator: "Navigator",
    allCategories: "all categories",
    activeCategories: (count) => `${count} active`,
    plan: "Trip plan",
    concise: "short view",
    duration: "duration",
    party: "party",
    start: "entry point",
    averageBill: "average bill",
    destinations: "Destinations",
    destinationHint: "live counts for the current filters",
    results: "offers",
    cityAll: "city: all",
    cityOne: (city) => `city: ${city}`,
    page: (current, total) => `page ${current} of ${total}`,
    tripMeta: (nights, people) => `${nights} nights · ${people} guests`,
    tile: "grid",
    list: "list",
    noOptions: "No matching offers. Try removing some filters or switch the city.",
    pulse: "Pulse",
    searching: "search in progress",
    done: "search complete",
    inCatalog: "in catalog",
    regions: "Regions",
    regionsHint: "quick jumps",
    typeSlice: "Type mix",
    typeHint: "most common in the feed",
    back: "back",
    forward: "next",
    open: "open",
    exactPrice: "exact price from site",
    reviewButton: "reviews",
    reviewsTitle: "Reviews",
    reviewsLoading: "loading reviews",
    reviewsEmpty: "No reviews found for this property yet.",
    reviewsOpen: "open property",
    authOpen: "sign in",
    authTitle: "Account",
    authSubtitle: "Registration and login with username and password.",
    authLoginTab: "login",
    authRegisterTab: "register",
    usernameLabel: "username",
    usernamePlaceholder: "choose username",
    passwordLabel: "password",
    passwordPlaceholder: "enter password",
    confirmPasswordLabel: "confirm password",
    confirmPasswordPlaceholder: "repeat password",
    authLoginAction: "sign in",
    authRegisterAction: "create account",
    authLogout: "log out",
    authLoggedIn: (username) => `signed in as ${username}`,
    authPasswordMismatch: "Passwords do not match.",
    authRequired: "Fill username and password.",
    close: "close",
    guestLabel: "guest",
    reviewCount: (count) => `${count} reviews`,
    sort: {
      price_asc: "Cheaper first",
      price_desc: "Pricier first",
      days_asc: "Shorter first",
      days_desc: "Longer first",
    },
    stage: {
      queued: "queued",
      seed: "first wave",
      regions: "regions",
      details: "details",
      idle: "ready",
      error: "error",
    },
    themeDay: "Day",
    themeNight: "Night",
  },
};
const normalizeText = (value) => String(value || "").trim().toLowerCase();
const progressRatio = (count, active) => (active ? Math.min(0.94, 0.14 + Math.log10((count || 0) + 1) * 0.22) : count ? 1 : 0);
const transliterateText = (value) => String(value || "").split("").map((char) => TRANSLIT_MAP[char] ?? char).join("");

function getCategoryContent(categoryId, localeMode, fallback = {}) {
  const localized = CATEGORY_COPY[categoryId]?.[localeMode];
  if (localized) return localized;
  return {
    label: localeMode === "eu" ? transliterateText(fallback.label || categoryId) : fallback.label || categoryId,
    description: localeMode === "eu" ? transliterateText(fallback.description || "") : fallback.description || "",
  };
}

function localizePlaceFragment(value, localeMode) {
  const safe = String(value || "").trim();
  if (!safe || localeMode !== "eu") return safe;
  if (safe === "Россия") return "Russia";
  if (/^Республика\s+.+$/i.test(safe)) {
    return safe.replace(/^Республика\s+(.+)$/i, (_, name) => `Republic of ${transliterateText(name)}`);
  }
  if (/^.+\s+область$/i.test(safe)) {
    return safe.replace(/^(.+)\s+область$/i, (_, name) => `${transliterateText(name)} Oblast`);
  }
  if (/^.+\s+край$/i.test(safe)) {
    return safe.replace(/^(.+)\s+край$/i, (_, name) => `${transliterateText(name)} Krai`);
  }
  if (/^.+\s+озеро$/i.test(safe)) {
    return safe.replace(/^(.+)\s+озеро$/i, (_, name) => `${transliterateText(name)} Lake`);
  }
  if (/^озеро\s+.+$/i.test(safe)) {
    return safe.replace(/^озеро\s+(.+)$/i, (_, name) => `${transliterateText(name)} Lake`);
  }
  return transliterateText(safe);
}

function localizePlaceText(value, localeMode) {
  const safe = String(value || "").trim();
  if (!safe || localeMode !== "eu") return safe;
  return safe
    .split(",")
    .map((part) => localizePlaceFragment(part, localeMode))
    .join(", ");
}

function buildPageTokens(currentPage, totalPages) {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, index) => index + 1);
  const tokens = [1];
  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);
  if (start > 2) tokens.push("...");
  for (let page = start; page <= end; page += 1) tokens.push(page);
  if (end < totalPages - 1) tokens.push("...");
  tokens.push(totalPages);
  return tokens;
}

function formatNightWord(value, localeMode) {
  const nights = Math.max(Number(value || 0), 1);
  if (localeMode !== "ru") return nights === 1 ? "night" : "nights";
  const mod10 = nights % 10;
  const mod100 = nights % 100;
  if (mod10 === 1 && mod100 !== 11) return "ночь";
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return "ночи";
  return "ночей";
}

function formatMinNights(value, localeMode) {
  const nights = Math.max(Number(value || 0), 1);
  return localeMode === "ru"
    ? `от ${nights} ${formatNightWord(nights, localeMode)}`
    : `from ${nights} ${formatNightWord(nights, localeMode)}`;
}

function formatReviewDate(value, localeCode) {
  const safe = String(value || "").trim();
  if (!safe) return "";
  const parsed = new Date(safe);
  if (Number.isNaN(parsed.getTime())) return safe;
  return parsed.toLocaleDateString(localeCode);
}

function placeLabelFromTour(tour) {
  const city = String(tour?.city || "").trim();
  const region = String(tour?.region || "").trim();
  if (city && region && city !== region) return `${city}, ${region}`;
  return city || region || "Россия";
}

function hashPhotoSeed(value) {
  const safe = String(value || "");
  let hash = 0;
  for (let index = 0; index < safe.length; index += 1) {
    hash = (hash << 5) - hash + safe.charCodeAt(index);
    hash |= 0;
  }
  return Math.abs(hash) || 1;
}

function buildPhotoTags(tour) {
  const tags = ["travel", "resort", "russia"];
  const place = normalizeText(`${tour?.city || ""} ${tour?.region || ""}`);
  const categories = new Set(tour?.categories || []);

  if (categories.has("waterfront")) tags.push("coast", "beach", "sea");
  if (categories.has("mountains")) tags.push("mountains");
  if (categories.has("forest")) tags.push("forest");
  if (categories.has("with_pool")) tags.push("pool");
  if (categories.has("with_hotel")) tags.push("hotel");
  if (categories.has("recreation_base")) tags.push("nature");

  if (place.includes("сочи") || place.includes("sochi")) tags.push("sochi", "black-sea");
  if (place.includes("крым") || place.includes("crimea")) tags.push("crimea");
  if (place.includes("алтай") || place.includes("altay")) tags.push("altai", "mountain-lake");
  if (place.includes("карел") || place.includes("karel")) tags.push("karelia", "lakes");
  if (place.includes("байкал") || place.includes("baikal")) tags.push("baikal");
  if (place.includes("калининград") || place.includes("kaliningrad")) tags.push("kaliningrad", "baltic");
  if (place.includes("дагестан") || place.includes("dagestan")) tags.push("dagestan", "caucasus");

  const translitCity = transliterateText(tour?.city || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  if (translitCity) tags.push(translitCity);

  return Array.from(new Set(tags)).slice(0, 6);
}

function getTourPhotoUrl(tour) {
  const explicit = String(tour?.image || "").trim();
  if (explicit) return explicit;
  const seed = hashPhotoSeed(`${tour?.id || ""}|${tour?.link || ""}|${tour?.title || ""}`);
  const tagPath = buildPhotoTags(tour).map((tag) => encodeURIComponent(tag)).join(",");
  return `https://loremflickr.com/960/640/${tagPath}?lock=${seed}`;
}

function getTourPhotoFallbackUrl(tour) {
  const seedSource = transliterateText(placeLabelFromTour(tour)).toLowerCase().replace(/\s+/g, "-");
  return `https://picsum.photos/seed/${encodeURIComponent(seedSource || "russia-trip")}/960/640`;
}

function App() {
  const shellRef = useRef(null);
  const liveSyncRef = useRef(false);
  const pollTickRef = useRef(0);
  const toursRequestRef = useRef(0);
  const [categories, setCategories] = useState([]);
  const [priceOptions, setPriceOptions] = useState([]);
  const [stats, setStats] = useState(null);
  const [quickCities, setQuickCities] = useState([]);
  const [citySuggestions, setCitySuggestions] = useState([]);
  const [searchSuggestions, setSearchSuggestions] = useState([]);
  const [filters, setFilters] = useState({ query: "", city: "", price: "", sort: "price_asc", categories: [] });
  const [searchInput, setSearchInput] = useState("");
  const [cityInput, setCityInput] = useState("");
  const [planner, setPlanner] = useState({ nights: 7, people: 2 });
  const [viewMode, setViewMode] = useState("grid");
  const [localeMode, setLocaleMode] = useState("ru");
  const [currentPage, setCurrentPage] = useState(1);
  const [tours, setTours] = useState([]);
  const [count, setCount] = useState(0);
  const [lastParsedAt, setLastParsedAt] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isStartingRefresh, setIsStartingRefresh] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCityLoading, setIsCityLoading] = useState(false);
  const [isSearchLoading, setIsSearchLoading] = useState(false);
  const [refreshStage, setRefreshStage] = useState("");
  const [error, setError] = useState("");
  const [reviewModalTour, setReviewModalTour] = useState(null);
  const [reviewItems, setReviewItems] = useState([]);
  const [isReviewsLoading, setIsReviewsLoading] = useState(false);
  const [reviewsError, setReviewsError] = useState("");
  const [detailModalTour, setDetailModalTour] = useState(null);
  const [detailData, setDetailData] = useState(null);
  const [detailError, setDetailError] = useState("");
  const [isDetailLoading, setIsDetailLoading] = useState(false);
  const [bookingForm, setBookingForm] = useState({ customerName: "", phone: "", email: "", comment: "" });
  const [bookingError, setBookingError] = useState("");
  const [bookingSuccess, setBookingSuccess] = useState("");
  const [isBookingPending, setIsBookingPending] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authMode, setAuthMode] = useState("login");
  const [authForm, setAuthForm] = useState({ username: "", password: "", confirmPassword: "" });
  const [authError, setAuthError] = useState("");
  const [isAuthPending, setIsAuthPending] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);

  const deferredCityInput = useDeferredValue(cityInput);
  const deferredSearchInput = useDeferredValue(searchInput);
  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const pageTokens = useMemo(() => buildPageTokens(currentPage, totalPages), [currentPage, totalPages]);
  const displayText = (value) => localizePlaceText(value, localeMode);
  const categoryMap = useMemo(
    () =>
      new Map(
        categories.map((item) => [item.id, getCategoryContent(item.id, localeMode, item).label])
      ),
    [categories, localeMode]
  );
  const topCategoryRows = useMemo(
    () =>
      Object.entries(stats?.categoryCounts || {})
        .map(([id, total]) => ({ id, label: categoryMap.get(id) || id, total }))
        .sort((left, right) => right.total - left.total)
        .slice(0, 6),
    [categoryMap, stats]
  );
  const copy = COPY[localeMode];
  const localeCode = localeMode === "ru" ? "ru-RU" : "en-IE";
  const numberFormatter = useMemo(() => new Intl.NumberFormat(localeCode), [localeCode]);
  const moneyFormatter = useMemo(
    () =>
      new Intl.NumberFormat(localeCode, {
        style: "currency",
        currency: "RUB",
        maximumFractionDigits: 0,
      }),
    [localeCode]
  );
  const formatPrice = (value) => `${moneyFormatter.format(Number(value || 0))}/${localeMode === "ru" ? "чел" : "guest"}`;
  const formatMoney = (value) => moneyFormatter.format(Number(value || 0));
  const formatDate = (value) => (value ? new Date(value).toLocaleString(localeCode) : localeMode === "ru" ? "ещё не обновлялось" : "not updated yet");
  const sortOptions = SORT_OPTIONS.map((option) => ({
    ...option,
    label: copy.sort[option.value],
  }));

  const visibleCities = (deferredCityInput.trim() ? citySuggestions : quickCities).slice(0, 12);
  const visibleQueries = deferredSearchInput.trim() ? searchSuggestions.slice(0, 10) : [];
  const progressPercent = `${Math.round(progressRatio(count, isRefreshing) * 100)}%`;
  const liveStageLabel = copy.stage[refreshStage] || (localeMode === "ru" ? "поиск" : "search");
  const sourceLabel = stats?.cacheSource === "live_putevka_partial" ? "live partial" : stats?.cacheSource || "snapshot";
  const plannerMinBudget = stats?.priceMin ? stats.priceMin * planner.people * planner.nights : null;
  const plannerAverageBudget = stats?.priceAvg ? stats.priceAvg * planner.people * planner.nights : null;
  const activeFilters = [
    ...(filters.city ? [{ key: "city", label: displayText(filters.city), onClick: () => applyCity("") }] : []),
    ...(filters.query ? [{ key: "query", label: filters.query, onClick: clearQuery }] : []),
    ...(filters.price ? [{ key: "price", label: formatPrice(filters.price), onClick: clearPrice }] : []),
    ...filters.categories.map((id) => ({ key: id, label: categoryMap.get(id) || id, onClick: () => toggleCategory(id) })),
  ];

  useEffect(() => {
    async function bootstrap() {
      try {
        const [categoriesRes, pricesRes, statsRes, sessionRes] = await Promise.all([
          fetch("/api/categories"),
          fetch("/api/price-options"),
          fetch("/api/stats"),
          fetch("/api/auth/session"),
        ]);
        if (!categoriesRes.ok || !pricesRes.ok || !statsRes.ok || !sessionRes.ok) throw new Error("Не удалось загрузить стартовые данные");
        const categoriesPayload = await categoriesRes.json();
        const pricesPayload = await pricesRes.json();
        const statsPayload = await statsRes.json();
        const sessionPayload = await sessionRes.json();
        setCategories(categoriesPayload.categories || []);
        setPriceOptions(pricesPayload.options || []);
        setStats(statsPayload);
        setCount(Number(statsPayload.totalTours || 0));
        setLastParsedAt(statsPayload.lastParsedAt || null);
        setIsRefreshing(Boolean(statsPayload.isRefreshing));
        setRefreshStage(statsPayload.refreshStage || "");
        setCurrentUser(sessionPayload.isAuthenticated ? { username: sessionPayload.username } : null);
        setIsReady(true);
      } catch (bootstrapError) {
        setError(bootstrapError.message || "Ошибка запуска");
      }
    }
    bootstrap();
  }, []);

  useEffect(() => { if (isReady) loadTours(); }, [isReady, filters, currentPage]);
  useEffect(() => { if (isReady) loadQuickCities(); }, [isReady, filters.query, filters.price, filters.categories]);

  useEffect(() => {
    if (!isReady) return;
    let ignore = false;
    fetch("/api/parse", { method: "POST" })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload) => {
        if (!payload || ignore) return;
        setIsRefreshing(Boolean(payload.isRefreshing));
        setRefreshStage(payload.refreshStage || "");
      })
      .catch(() => {});
    return () => { ignore = true; };
  }, [isReady]);

  useEffect(() => {
    if (!isReady) return undefined;
    const intervalId = window.setInterval(async () => {
      if (document.hidden || liveSyncRef.current) return;
      liveSyncRef.current = true;
      pollTickRef.current += 1;
      try {
        await loadTours({ silent: true });
        if (pollTickRef.current % 4 === 0) await loadQuickCities();
        if (pollTickRef.current % 6 === 0) await loadStats();
      } finally {
        liveSyncRef.current = false;
      }
    }, 1000);
    return () => window.clearInterval(intervalId);
  }, [isReady, filters, currentPage]);

  useEffect(() => {
    if (!isReady) return;
    const prefix = deferredCityInput.trim();
    if (!prefix) return void setCitySuggestions(quickCities);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsCityLoading(true);
      try {
        const response = await fetch(`/api/cities?${buildCityParams(prefix, 18).toString()}`, { signal: controller.signal });
        if (!response.ok) throw new Error();
        const payload = await response.json();
        startTransition(() => setCitySuggestions(payload.cities || []));
      } catch (err) {
        if (err.name !== "AbortError") setCitySuggestions([]);
      } finally {
        setIsCityLoading(false);
      }
    }, 220);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [deferredCityInput, isReady, quickCities, filters.query, filters.price, filters.categories]);

  useEffect(() => {
    if (!isReady) return;
    const prefix = deferredSearchInput.trim();
    if (!prefix) return void setSearchSuggestions([]);
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setIsSearchLoading(true);
      try {
        const response = await fetch(`/api/search-suggestions?${buildSearchSuggestionParams(prefix, 14).toString()}`, { signal: controller.signal });
        if (!response.ok) throw new Error();
        const payload = await response.json();
        startTransition(() => setSearchSuggestions(payload.queries || []));
      } catch (err) {
        if (err.name !== "AbortError") setSearchSuggestions([]);
      } finally {
        setIsSearchLoading(false);
      }
    }, 220);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [deferredSearchInput, isReady, filters.city, filters.price, filters.categories]);

  useEffect(() => {
    if (currentPage > totalPages) setCurrentPage(totalPages);
  }, [currentPage, totalPages]);

  useEffect(() => {
    document.documentElement.dataset.theme = "night";
    document.documentElement.dataset.locale = localeMode;
    document.title = copy.title;
  }, [localeMode, copy.title]);

  useEffect(() => {
    function handleKeyDown(event) {
      if (event.key === "Escape") {
        setReviewModalTour(null);
        setReviewItems([]);
        setReviewsError("");
        setDetailModalTour(null);
        setDetailData(null);
        setDetailError("");
        setBookingError("");
        setBookingSuccess("");
        setIsAuthModalOpen(false);
        setAuthError("");
      }
    }
    if (reviewModalTour || detailModalTour || isAuthModalOpen) {
      document.body.style.overflow = "hidden";
      window.addEventListener("keydown", handleKeyDown);
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [reviewModalTour, detailModalTour, isAuthModalOpen]);

  function buildCommonParams() {
    const params = new URLSearchParams();
    if (filters.query) params.set("q", filters.query);
    if (filters.city) params.set("city", filters.city);
    if (filters.price) params.set("pricePerPerson", filters.price);
    params.set("sort", filters.sort);
    for (const categoryId of filters.categories) params.append("category", categoryId);
    return params;
  }

  function buildCityParams(prefix, limit) {
    const params = new URLSearchParams();
    if (filters.query) params.set("tourQuery", filters.query);
    if (filters.price) params.set("pricePerPerson", filters.price);
    for (const categoryId of filters.categories) params.append("category", categoryId);
    if (prefix) params.set("prefix", prefix);
    params.set("limit", String(limit));
    return params;
  }

  function buildSearchSuggestionParams(prefix, limit) {
    const params = new URLSearchParams();
    if (filters.city) params.set("city", filters.city);
    if (filters.price) params.set("pricePerPerson", filters.price);
    for (const categoryId of filters.categories) params.append("category", categoryId);
    params.set("prefix", prefix);
    params.set("limit", String(limit));
    return params;
  }

  async function loadStats() {
    try {
      const response = await fetch("/api/stats");
      if (!response.ok) return;
      const payload = await response.json();
      startTransition(() => {
        setStats(payload);
        setLastParsedAt(payload.lastParsedAt || null);
        setIsRefreshing(Boolean(payload.isRefreshing));
        setRefreshStage(payload.refreshStage || "");
      });
    } catch (_error) {}
  }

  async function loadQuickCities() {
    try {
      const response = await fetch(`/api/cities?${buildCityParams("", 12).toString()}`);
      if (!response.ok) return;
      const payload = await response.json();
      startTransition(() => {
        setQuickCities(payload.cities || []);
        if (!deferredCityInput.trim()) setCitySuggestions(payload.cities || []);
      });
    } catch (_error) {}
  }

  async function loadTours(options = {}) {
    const silent = options.silent === true;
    const requestId = ++toursRequestRef.current;
    if (!silent) { setIsLoading(true); setError(""); }
    try {
      const params = buildCommonParams();
      params.set("limit", String(PAGE_SIZE));
      params.set("offset", String((currentPage - 1) * PAGE_SIZE));
      const response = await fetch(`/api/tours?${params.toString()}`);
      if (!response.ok) throw new Error("Ошибка загрузки каталога");
      const payload = await response.json();
      startTransition(() => {
        setTours(payload.tours || []);
        setCount(Number(payload.count || 0));
        setLastParsedAt(payload.lastParsedAt || null);
        setIsRefreshing(Boolean(payload.isRefreshing));
        setRefreshStage(payload.refreshStage || "");
      });
    } catch (loadError) {
      if (requestId !== toursRequestRef.current) return;
      if (!silent && requestId === toursRequestRef.current) {
        setTours([]);
        setCount(0);
        if (loadError?.message === "Failed to fetch") {
          loadError.message = localeMode === "ru" ? "Не удалось соединиться с сервером" : "Could not reach the server";
        }
      }
      if (!silent) setError(loadError.message || "Не удалось загрузить путёвки");
    } finally {
      if (!silent && requestId === toursRequestRef.current) setIsLoading(false);
    }
  }

  async function refreshCatalog() {
    setIsStartingRefresh(true);
    try {
      const response = await fetch("/api/parse", { method: "POST" });
      if (!response.ok) throw new Error("Не удалось обновить поиск");
      const payload = await response.json();
      setIsRefreshing(Boolean(payload.isRefreshing));
      setRefreshStage(payload.refreshStage || "");
      await Promise.all([loadStats(), loadQuickCities(), loadTours()]);
    } catch (refreshError) {
      setError(refreshError.message || "Не удалось обновить данные");
    } finally {
      setIsStartingRefresh(false);
    }
  }

  function submitSearch(event) {
    event.preventDefault();
    const exactCity = citySuggestions.find((item) => normalizeText(item.city) === normalizeText(cityInput));
    const nextCity = cityInput.trim() ? (exactCity || citySuggestions[0] || { city: cityInput.trim() }).city : "";
    setFilters((prev) => ({ ...prev, query: searchInput.trim(), city: nextCity }));
    setCityInput(nextCity);
    setCurrentPage(1);
  }

  const clearQuery = () => { setFilters((prev) => ({ ...prev, query: "" })); setSearchInput(""); setCurrentPage(1); };
  const clearPrice = () => { setFilters((prev) => ({ ...prev, price: "" })); setCurrentPage(1); };
  const applyCity = (city) => { const normalized = String(city || "").trim(); setFilters((prev) => ({ ...prev, city: normalized })); setCityInput(normalized); setCurrentPage(1); };
  const applyRegion = (region) => { const normalized = String(region || "").trim(); setFilters((prev) => ({ ...prev, query: normalized, city: "" })); setSearchInput(normalized); setCityInput(""); setCurrentPage(1); };
  const applySearchSuggestion = (query) => { const normalized = String(query || "").trim(); setFilters((prev) => ({ ...prev, query: normalized })); setSearchInput(normalized); setCurrentPage(1); };
  const resetFilters = () => { setFilters({ query: "", city: "", price: "", sort: "price_asc", categories: [] }); setSearchInput(""); setCityInput(""); setCurrentPage(1); };
  const toggleCategory = (categoryId) => { setFilters((prev) => ({ ...prev, categories: prev.categories.includes(categoryId) ? prev.categories.filter((item) => item !== categoryId) : [...prev.categories, categoryId] })); setCurrentPage(1); };
  const openTourLink = (url) => { const normalized = String(url || "").trim(); if (normalized && normalized !== "#") window.open(normalized, "_blank", "noopener,noreferrer"); };
  const closeDetail = () => {
    setDetailModalTour(null);
    setDetailData(null);
    setDetailError("");
    setBookingError("");
    setBookingSuccess("");
    setIsBookingPending(false);
  };
  const closeReviews = () => { setReviewModalTour(null); setReviewItems([]); setReviewsError(""); };
  const openAuthModal = (mode = "login") => { setAuthMode(mode); setAuthError(""); setIsAuthModalOpen(true); };
  const closeAuthModal = () => { setIsAuthModalOpen(false); setAuthError(""); };

  async function openTourDetails(event, tour) {
    if (event) event.stopPropagation();
    setDetailModalTour(tour);
    setDetailData(null);
    setDetailError("");
    setBookingError("");
    setBookingSuccess("");
    setBookingForm((prev) => ({ ...prev, comment: "" }));
    setIsDetailLoading(true);
    try {
      const params = new URLSearchParams();
      if (tour?.id) params.set("tourId", tour.id);
      if (tour?.link) params.set("link", tour.link);
      const response = await fetch(`/api/tour-detail?${params.toString()}`);
      if (!response.ok) throw new Error(localeMode === "ru" ? "Не удалось открыть объект" : "Could not open property");
      const payload = await response.json();
      setDetailData(payload.detail || payload);
    } catch (detailLoadError) {
      setDetailError(detailLoadError.message || (localeMode === "ru" ? "Не удалось загрузить детали" : "Could not load details"));
    } finally {
      setIsDetailLoading(false);
    }
  }

  async function openReviews(event, tour) {
    event.stopPropagation();
    setReviewModalTour(tour);
    setReviewItems([]);
    setReviewsError("");
    setIsReviewsLoading(true);
    try {
      const params = new URLSearchParams();
      if (tour?.id) params.set("tourId", tour.id);
      if (tour?.link) params.set("link", tour.link);
      const response = await fetch(`/api/reviews?${params.toString()}`);
      if (!response.ok) throw new Error(localeMode === "ru" ? "Не удалось загрузить отзывы" : "Could not load reviews");
      const payload = await response.json();
      setReviewItems(Array.isArray(payload.reviews) ? payload.reviews : []);
    } catch (reviewsLoadError) {
      setReviewsError(reviewsLoadError.message || (localeMode === "ru" ? "Не удалось загрузить отзывы" : "Could not load reviews"));
    } finally {
      setIsReviewsLoading(false);
    }
  }

  async function submitBooking(event) {
    event.preventDefault();
    if (!detailModalTour) return;
    const customerName = String(bookingForm.customerName || "").trim();
    const phone = String(bookingForm.phone || "").trim();
    const email = String(bookingForm.email || "").trim();
    const comment = String(bookingForm.comment || "").trim();
    if (!customerName || !phone) {
      setBookingError(localeMode === "ru" ? "Заполните имя и телефон." : "Fill name and phone.");
      return;
    }

    setIsBookingPending(true);
    setBookingError("");
    setBookingSuccess("");
    try {
      const response = await fetch("/api/bookings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tourId: detailModalTour.id,
          link: detailModalTour.link,
          title: detailModalTour.title,
          city: detailModalTour.city,
          region: detailModalTour.region,
          pricePerPerson: Number(detailModalTour.pricePerPerson || detailData?.prices?.[0]?.price || 0),
          nights: planner.nights,
          people: planner.people,
          customerName,
          phone,
          email,
          comment,
        }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || (localeMode === "ru" ? "Не удалось сохранить бронь" : "Could not save booking"));
      }
      setBookingSuccess(localeMode === "ru" ? "Бронь сохранена. Мы получили заявку." : "Booking saved. We received the request.");
      setBookingForm({ customerName: "", phone: "", email: "", comment: "" });
    } catch (bookingRequestError) {
      setBookingError(bookingRequestError.message || (localeMode === "ru" ? "Не удалось сохранить бронь" : "Could not save booking"));
    } finally {
      setIsBookingPending(false);
    }
  }

  async function submitAuth(event) {
    event.preventDefault();
    const username = String(authForm.username || "").trim();
    const password = String(authForm.password || "");
    const confirmPassword = String(authForm.confirmPassword || "");

    if (!username || !password) {
      setAuthError(copy.authRequired);
      return;
    }
    if (authMode === "register" && password !== confirmPassword) {
      setAuthError(copy.authPasswordMismatch);
      return;
    }

    setIsAuthPending(true);
    setAuthError("");
    try {
      const endpoint = authMode === "register" ? "/api/auth/register" : "/api/auth/login";
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        throw new Error(payload.message || (localeMode === "ru" ? "Не удалось выполнить вход" : "Could not complete authentication"));
      }
      setCurrentUser({ username: payload.username });
      setAuthForm({ username: "", password: "", confirmPassword: "" });
      setIsAuthModalOpen(false);
    } catch (authRequestError) {
      setAuthError(authRequestError.message || (localeMode === "ru" ? "Не удалось выполнить вход" : "Could not complete authentication"));
    } finally {
      setIsAuthPending(false);
    }
  }

  async function logoutUser() {
    try {
      const response = await fetch("/api/auth/logout", { method: "POST" });
      const payload = await response.json();
      if (!response.ok || !payload.ok) throw new Error();
      setCurrentUser(null);
    } catch (_error) {
      setAuthError(localeMode === "ru" ? "Не удалось выйти из аккаунта" : "Could not log out");
    }
  }

  return html`
    <div className="shell" ref=${shellRef} onMouseMove=${(event) => {
      const rect = shellRef.current?.getBoundingClientRect();
      if (!rect) return;
      const x = (event.clientX - rect.left) / rect.width - 0.5;
      const y = (event.clientY - rect.top) / rect.height - 0.5;
      shellRef.current.style.setProperty("--mx", `${(x * 20).toFixed(2)}px`);
      shellRef.current.style.setProperty("--my", `${(y * 20).toFixed(2)}px`);
    }} onMouseLeave=${() => {
      if (!shellRef.current) return;
      shellRef.current.style.setProperty("--mx", "0px");
      shellRef.current.style.setProperty("--my", "0px");
    }}>
      <div className="shell__nebula shell__nebula--a" aria-hidden="true"></div>
      <div className="shell__nebula shell__nebula--b" aria-hidden="true"></div>
      <div className="shell__glow shell__glow--a" aria-hidden="true"></div>
      <div className="shell__glow shell__glow--b" aria-hidden="true"></div>
      <div className="shell__stage" aria-hidden="true">
        <div className="stage-orb stage-orb--hero"></div>
        <div className="stage-orb stage-orb--echo"></div>
        <div className="stage-glass stage-glass--a"></div>
        <div className="stage-glass stage-glass--b"></div>
        <div className="stage-shard stage-shard--a"></div>
      </div>
      <div className="shell__inner">
        <header className="hero-panel">
          <section className="card hero-panel__main">
            <div className="eyebrow-row">
              <span className="eyebrow">${copy.eyebrow}</span>
              <span className=${isRefreshing ? "status-dot status-dot--live" : "status-dot"}>
                ${isRefreshing ? liveStageLabel : copy.calm}
              </span>
            </div>
            <div className="hero-utilities">
              <div className="switcher">
                <button className=${localeMode === "ru" ? "switcher__button switcher__button--active" : "switcher__button"} type="button" onClick=${() => setLocaleMode("ru")}>RU</button>
                <button className=${localeMode === "eu" ? "switcher__button switcher__button--active" : "switcher__button"} type="button" onClick=${() => setLocaleMode("eu")}>EU</button>
              </div>
              ${currentUser
                ? html`<div className="auth-strip"><span className="auth-chip">${currentUser.username}</span><button className="action-button action-button--ghost action-button--small" type="button" onClick=${logoutUser}>${copy.authLogout}</button></div>`
                : html`<button className="action-button action-button--ghost action-button--small" type="button" onClick=${() => openAuthModal("login")}>${copy.authOpen}</button>`}
            </div>
            <h1>${copy.title}</h1>
            <p className="hero-copy">${copy.heroCopy}</p>
            <div className="hero-stats">
              <article className="hero-stat hero-stat--warm"><span>${copy.variants}</span><strong>${numberFormatter.format(count || 0)}</strong></article>
              <article className="hero-stat hero-stat--cool"><span>${copy.averagePrice}</span><strong>${stats?.priceAvg ? formatPrice(stats.priceAvg) : "..."}</strong></article>
              <article className="hero-stat hero-stat--rose"><span>${copy.trip}</span><strong>${copy.tripMeta(planner.nights, planner.people)}</strong></article>
            </div>
          </section>
          <section className="card card--dark hero-panel__aside">
            <div className="signal-head">
              <div><span>${copy.flow}</span><strong>${numberFormatter.format(count || 0)}</strong></div>
              <button className="action-button action-button--ghost" type="button" onClick=${refreshCatalog} disabled=${isStartingRefresh || isRefreshing}>
                ${isStartingRefresh || isRefreshing ? copy.updating : copy.launchSearch}
              </button>
            </div>
            <div className="signal-track" aria-hidden="true"><div className="signal-track__bar" style=${{ width: progressPercent }}></div></div>
            <div className="signal-grid">
              <div className="signal-cell"><span>${copy.source}</span><strong>${sourceLabel}</strong></div>
              <div className="signal-cell"><span>${copy.updated}</span><strong>${formatDate(lastParsedAt || stats?.lastParsedAt)}</strong></div>
              <div className="signal-cell"><span>${copy.minimum}</span><strong>${stats?.priceMin ? formatPrice(stats.priceMin) : "..."}</strong></div>
              <div className="signal-cell"><span>${copy.maximum}</span><strong>${stats?.priceMax ? formatPrice(stats.priceMax) : "..."}</strong></div>
            </div>
            <p className="signal-note">
              ${isRefreshing
                ? copy.liveNote(numberFormatter.format(count || 0))
                : copy.stableNote}
            </p>
          </section>
        </header>

        <section className="card search-deck">
          <form className="search-deck__form" onSubmit=${submitSearch}>
            <label className="search-field search-field--query"><span>${copy.searchLabel}</span><input className="search-control" value=${searchInput} onInput=${(event) => setSearchInput(event.target.value)} placeholder=${copy.searchPlaceholder} /></label>
            <label className="search-field"><span>${copy.cityLabel}</span><input className="search-control" value=${cityInput} onInput=${(event) => setCityInput(event.target.value)} placeholder=${copy.cityPlaceholder} /></label>
            <label className="search-field"><span>${copy.priceLabel}</span><select className="search-control" value=${filters.price} onChange=${(event) => { setFilters((prev) => ({ ...prev, price: event.target.value })); setCurrentPage(1); }}><option value="">${copy.anyPrice}</option>${priceOptions.map((price) => html`<option key=${String(price)} value=${String(price)}>${formatPrice(price)}</option>`)}</select></label>
            <label className="search-field search-field--small"><span>${copy.nightsLabel}</span><select className="search-control" value=${String(planner.nights)} onChange=${(event) => setPlanner((prev) => ({ ...prev, nights: Number(event.target.value) }))}>${NIGHT_OPTIONS.map((nights) => html`<option key=${String(nights)} value=${String(nights)}>${nights}</option>`)}</select></label>
            <label className="search-field search-field--small"><span>${copy.peopleLabel}</span><select className="search-control" value=${String(planner.people)} onChange=${(event) => setPlanner((prev) => ({ ...prev, people: Number(event.target.value) }))}>${PEOPLE_OPTIONS.map((people) => html`<option key=${String(people)} value=${String(people)}>${people}</option>`)}</select></label>
            <label className="search-field"><span>${copy.sortLabel}</span><select className="search-control" value=${filters.sort} onChange=${(event) => { setFilters((prev) => ({ ...prev, sort: event.target.value })); setCurrentPage(1); }}>${sortOptions.map((option) => html`<option key=${option.value} value=${option.value}>${option.label}</option>`)}</select></label>
            <div className="search-actions">
              <button className="action-button action-button--primary" type="submit">${copy.searchAction}</button>
              <button className="action-button action-button--soft" type="button" onClick=${resetFilters}>${copy.resetAction}</button>
            </div>
          </form>
          <div className="deck-bands">
            ${visibleQueries.length || isSearchLoading ? html`<div className="deck-band"><span className="deck-band__label">${isSearchLoading ? copy.hintsLoading : copy.hints}</span><div className="token-row">${visibleQueries.map((item) => html`<button key=${item.query} type="button" className="token token--query" onClick=${() => applySearchSuggestion(item.query)}><strong>${item.query}</strong><span>${item.count}</span></button>`)}</div></div>` : null}
              <div className="deck-band"><span className="deck-band__label">${isCityLoading ? copy.citiesLoading : copy.cities}</span><div className="token-row">${visibleCities.map((item) => html`<button key=${item.city} type="button" className=${normalizeText(filters.city) === normalizeText(item.city) ? "token token--city token--active" : "token token--city"} onClick=${() => applyCity(item.city)}><strong>${displayText(item.city)}</strong><span>${item.count}</span></button>`)}</div></div>
            ${activeFilters.length ? html`<div className="deck-band"><span className="deck-band__label">${copy.chosen}</span><div className="token-row">${activeFilters.map((item) => html`<button key=${item.key} className="token token--filter" type="button" onClick=${item.onClick}>${item.label} ×</button>`)}</div></div>` : null}
          </div>
        </section>

        <main className="board">
          <aside className="board__sidebar">
            <section className="card stack-card stack-card--sticky">
              <div className="stack-card__head"><h2>${copy.navigator}</h2><span>${filters.categories.length ? copy.activeCategories(filters.categories.length) : copy.allCategories}</span></div>
              <div className="category-list">${categories.map((category, index) => {
                const categoryContent = getCategoryContent(category.id, localeMode, category);
                return html`<button key=${category.id} type="button" className=${filters.categories.includes(category.id) ? "category-row category-row--active" : "category-row"} onClick=${() => toggleCategory(category.id)} style=${{ "--tile-delay": `${index * 30}ms` }}><strong>${categoryContent.label}</strong><span>${categoryContent.description}</span></button>`;
              })}</div>
            </section>
            <section className="card stack-card">
              <div className="stack-card__head"><h2>${copy.plan}</h2><span>${copy.concise}</span></div>
              <div className="mini-grid">
                <div className="mini-grid__item"><span>${copy.duration}</span><strong>${planner.nights} ${localeMode === "ru" ? "ночей" : "nights"}</strong></div>
                <div className="mini-grid__item"><span>${copy.party}</span><strong>${planner.people} ${localeMode === "ru" ? "чел." : "guests"}</strong></div>
                <div className="mini-grid__item"><span>${copy.start}</span><strong>${plannerMinBudget ? formatMoney(plannerMinBudget) : "..."}</strong></div>
                <div className="mini-grid__item"><span>${copy.averageBill}</span><strong>${plannerAverageBudget ? formatMoney(plannerAverageBudget) : "..."}</strong></div>
              </div>
            </section>
          </aside>

          <section className="board__main">
            <section className="card destination-stage">
              <div className="destination-stage__head"><h2>${copy.destinations}</h2><span>${copy.destinationHint}</span></div>
              <div className="destination-stage__rail">${quickCities.map((item, index) => html`<button key=${item.city} type="button" className=${normalizeText(filters.city) === normalizeText(item.city) ? "destination-card destination-card--active" : "destination-card"} onClick=${() => applyCity(item.city)} style=${{ "--city-delay": `${index * 40}ms` }}><span>${displayText(item.city)}</span><strong>${item.count}</strong></button>`)}</div>
            </section>
            <section className="card results-banner">
              <div><h2>${numberFormatter.format(count || 0)} ${copy.results}</h2><div className="results-banner__meta"><span>${filters.city ? copy.cityOne(displayText(filters.city)) : copy.cityAll}</span><span>${copy.page(currentPage, totalPages)}</span><span>${copy.tripMeta(planner.nights, planner.people)}</span><span>${formatDate(lastParsedAt)}</span></div></div>
              <div className="view-toggle"><button className=${viewMode === "grid" ? "toggle-button toggle-button--active" : "toggle-button"} type="button" onClick=${() => setViewMode("grid")}>${copy.tile}</button><button className=${viewMode === "list" ? "toggle-button toggle-button--active" : "toggle-button"} type="button" onClick=${() => setViewMode("list")}>${copy.list}</button></div>
            </section>
            ${error ? html`<div className="card notice notice--error">${error}</div>` : null}
            ${isLoading
              ? html`<div className=${viewMode === "list" ? "catalog catalog--list" : "catalog catalog--grid"}>${Array.from({ length: 8 }).map((_, index) => html`<div key=${`skeleton_${index}`} className="card offer-card skeleton" style=${{ "--card-delay": `${index * 50}ms` }}></div>`)}</div>`
              : tours.length
                  ? html`<div className=${viewMode === "list" ? "catalog catalog--list" : "catalog catalog--grid"}>${tours.map((tour, index) => html`
                    <article key=${tour.id} className="card offer-card" role="button" tabIndex="0" style=${{ "--card-delay": `${index * 40}ms` }} onClick=${(event) => openTourDetails(event, tour)} onKeyDown=${(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openTourDetails(event, tour);
                      }
                    }}>
                      <div className="offer-card__photo-wrap">
                        <img
                          className="offer-card__photo"
                          src=${getTourPhotoUrl(tour)}
                          alt=${displayText(placeLabelFromTour(tour))}
                          loading="lazy"
                          decoding="async"
                          onError=${(event) => {
                            const target = event.currentTarget;
                            if (target.dataset.fallbackApplied === "1") return;
                            target.dataset.fallbackApplied = "1";
                            target.src = getTourPhotoFallbackUrl(tour);
                          }}
                        />
                      </div>
                      <div className="offer-card__top">
                        <p className="offer-card__place">${displayText(placeLabelFromTour(tour))}</p>
                        <span className="offer-card__stay">${formatMinNights(tour.minNights || tour.days, localeMode)}</span>
                      </div>
                      <h3>${tour.title}</h3>
                      <div className="offer-card__chips">${(tour.categories || []).slice(0, 4).map((categoryId) => html`<span key=${`${tour.id}_${categoryId}`} className="soft-mark">${categoryMap.get(categoryId) || categoryId}</span>`)}</div>
                      <div className="offer-card__review-bar">
                        <button className="offer-card__reviews-button" type="button" onClick=${(event) => openReviews(event, tour)}>${copy.reviewButton}</button>
                        ${(tour.ratingValue || tour.reviewCount) ? html`<span className="offer-card__reviews-meta">${tour.ratingValue ? `★ ${Number(tour.ratingValue).toFixed(1)}` : ""}${tour.reviewCount ? `${tour.ratingValue ? " · " : ""}${copy.reviewCount(tour.reviewCount)}` : ""}</span>` : null}
                      </div>
                      <div className="offer-card__bottom"><div className="offer-card__price"><strong>${formatPrice(tour.pricePerPerson)}</strong><span>${copy.exactPrice}</span></div><button className="offer-card__open-button" type="button" onClick=${(event) => openTourDetails(event, tour)}>${localeMode === "ru" ? "подробнее" : "details"}</button></div>
                    </article>`)}
                  </div>`
                : html`<div className="card notice">${copy.noOptions}</div>`}
            <div className="pager"><button className="pager-button" type="button" disabled=${currentPage === 1 || isLoading} onClick=${() => setCurrentPage((page) => Math.max(1, page - 1))}>${copy.back}</button>${pageTokens.map((token, index) => token === "..." ? html`<span key=${`dots_${index}`} className="pager__dots">…</span>` : html`<button key=${String(token)} className=${token === currentPage ? "pager-button pager-button--active" : "pager-button"} type="button" onClick=${() => setCurrentPage(token)} disabled=${isLoading}>${String(token)}</button>`)}<button className="pager-button" type="button" disabled=${currentPage >= totalPages || isLoading} onClick=${() => setCurrentPage((page) => Math.min(totalPages, page + 1))}>${copy.forward}</button></div>
          </section>

          <aside className="board__aside">
            <section className="card stack-card stack-card--accent">
              <div className="stack-card__head"><h2>${copy.pulse}</h2><span>${isRefreshing ? copy.searching : copy.done}</span></div>
              <div className="mini-grid mini-grid--single">
                <div className="mini-grid__item"><span>${copy.inCatalog}</span><strong>${numberFormatter.format(count || 0)}</strong></div>
                <div className="mini-grid__item"><span>${copy.averagePrice}</span><strong>${stats?.priceAvg ? formatPrice(stats.priceAvg) : "..."}</strong></div>
                <div className="mini-grid__item"><span>${copy.minimum}</span><strong>${stats?.priceMin ? formatPrice(stats.priceMin) : "..."}</strong></div>
              </div>
            </section>
            <section className="card stack-card"><div className="stack-card__head"><h2>${copy.regions}</h2><span>${copy.regionsHint}</span></div><div className="stack-list">${(stats?.topRegions || []).map((item) => html`<button key=${item.region} type="button" className="stack-link" onClick=${() => applyRegion(item.region)}><span>${displayText(item.region)}</span><strong>${item.count}</strong></button>`)}</div></section>
            <section className="card stack-card"><div className="stack-card__head"><h2>${copy.typeSlice}</h2><span>${copy.typeHint}</span></div><div className="stack-list">${topCategoryRows.map((item) => html`<button key=${item.id} type="button" className="stack-link" onClick=${() => toggleCategory(item.id)}><span>${item.label}</span><strong>${item.total}</strong></button>`)}</div></section>
          </aside>
        </main>
      </div>
      ${detailModalTour ? html`
        <div className="modal-backdrop" role="presentation" onClick=${closeDetail}>
          <section className="modal-card modal-card--detail" role="dialog" aria-modal="true" aria-label=${localeMode === "ru" ? "Карточка объекта" : "Property details"} onClick=${(event) => event.stopPropagation()}>
            <div className="modal-card__head">
              <div>
                <span className="modal-card__eyebrow">${localeMode === "ru" ? "объект" : "property"}</span>
                <h3 className="modal-card__title">${detailModalTour.title}</h3>
                <p className="modal-card__place">${displayText(placeLabelFromTour(detailModalTour))}</p>
              </div>
              <button className="modal-card__close" type="button" onClick=${closeDetail}>${copy.close}</button>
            </div>
            <div className="modal-card__body">
              ${isDetailLoading ? html`<div className="modal-card__notice">${localeMode === "ru" ? "Загружаем объект..." : "Loading property..."}</div>` : null}
              ${!isDetailLoading && detailError ? html`<div className="modal-card__notice modal-card__notice--error">${detailError}</div>` : null}
              ${!isDetailLoading && !detailError ? html`
                <div className="detail-layout">
                  <div className="detail-layout__main">
                    <div className="detail-gallery">
                      ${(detailData?.photos?.length ? detailData.photos : [getTourPhotoUrl(detailModalTour)]).slice(0, 12).map((photo, index) => html`<img key=${`${detailModalTour.id || detailModalTour.link}_${index}`} className="detail-gallery__photo" src=${photo} alt=${detailModalTour.title} loading="lazy" decoding="async" />`)}
                    </div>
                    ${detailData?.description ? html`<section className="detail-section"><h4>${localeMode === "ru" ? "Описание" : "Description"}</h4><p>${detailData.description}</p></section>` : null}
                    ${detailData?.food ? html`<section className="detail-section"><h4>${localeMode === "ru" ? "Питание" : "Food"}</h4><p>${detailData.food}</p></section>` : null}
                    ${detailData?.infrastructure?.length ? html`<section className="detail-section"><h4>${localeMode === "ru" ? "Инфраструктура" : "Infrastructure"}</h4><div className="detail-bullets">${detailData.infrastructure.map((item, index) => html`<span key=${`${detailModalTour.id}_infra_${index}`} className="soft-mark">${item}</span>`)}</div></section>` : null}
                    <section className="detail-section"><div className="detail-section__head"><h4>${localeMode === "ru" ? "Цены" : "Prices"}</h4><button className="offer-card__reviews-button" type="button" onClick=${(event) => openReviews(event, detailModalTour)}>${copy.reviewButton}</button></div><div className="detail-price-list">${(detailData?.prices?.length ? detailData.prices : [{ title: detailModalTour.title, price: detailModalTour.pricePerPerson, currency: "RUB", image: getTourPhotoUrl(detailModalTour) }]).map((item, index) => html`<article key=${`${detailModalTour.id}_price_${index}`} className="detail-price-card"><div>${item.title ? html`<strong>${item.title}</strong>` : null}${item.description ? html`<p>${item.description}</p>` : null}</div><span>${formatMoney(item.price)}</span></article>`)}</div></section>
                  </div>
                  <aside className="detail-layout__aside">
                    <section className="detail-section detail-section--booking">
                      <span className="detail-booking__eyebrow">${localeMode === "ru" ? "бронь на сайте" : "booking on site"}</span>
                      <div className="detail-booking__top">
                        <h4>${localeMode === "ru" ? "Забронировать" : "Book now"}</h4>
                        <div className="detail-booking__badge">${localeMode === "ru" ? "в базу" : "to database"}</div>
                      </div>
                      <div className="detail-booking__meta">
                        <span>${planner.nights} ${localeMode === "ru" ? "ночей" : "nights"}</span>
                        <span>${planner.people} ${localeMode === "ru" ? "чел." : "guests"}</span>
                        <strong>${formatMoney((Number(detailModalTour.pricePerPerson || detailData?.prices?.[0]?.price || 0) * Math.max(planner.people, 1)) || 0)}</strong>
                      </div>
                      <form className="auth-form detail-booking-form" onSubmit=${submitBooking}>
                        <label className="auth-form__field"><span>${localeMode === "ru" ? "Имя" : "Name"}</span><input value=${bookingForm.customerName} onInput=${(event) => setBookingForm((prev) => ({ ...prev, customerName: event.target.value }))} placeholder=${localeMode === "ru" ? "Как к вам обращаться" : "Your name"} /></label>
                        <label className="auth-form__field"><span>${localeMode === "ru" ? "Телефон" : "Phone"}</span><input value=${bookingForm.phone} onInput=${(event) => setBookingForm((prev) => ({ ...prev, phone: event.target.value }))} placeholder=${localeMode === "ru" ? "+7..." : "+7..."} /></label>
                        <label className="auth-form__field"><span>Email</span><input value=${bookingForm.email} onInput=${(event) => setBookingForm((prev) => ({ ...prev, email: event.target.value }))} placeholder="mail@example.com" /></label>
                        <label className="auth-form__field"><span>${localeMode === "ru" ? "Комментарий" : "Comment"}</span><textarea rows="4" value=${bookingForm.comment} onInput=${(event) => setBookingForm((prev) => ({ ...prev, comment: event.target.value }))} placeholder=${localeMode === "ru" ? "Пожелания по брони" : "Booking notes"}></textarea></label>
                        ${bookingError ? html`<div className="modal-card__notice modal-card__notice--error">${bookingError}</div>` : null}
                        ${bookingSuccess ? html`<div className="modal-card__notice">${bookingSuccess}</div>` : null}
                        <div className="detail-actions">
                          <button className="action-button action-button--primary" type="submit" disabled=${isBookingPending}>${isBookingPending ? (localeMode === "ru" ? "сохраняем..." : "saving...") : (localeMode === "ru" ? "забронировать" : "book")}</button>
                          <button className="action-button action-button--ghost" type="button" onClick=${() => openTourLink(detailModalTour.link)}>${copy.open}</button>
                        </div>
                      </form>
                    </section>
                  </aside>
                </div>` : null}
            </div>
          </section>
        </div>` : null}
      ${reviewModalTour ? html`
        <div className="modal-backdrop" role="presentation" onClick=${closeReviews}>
          <section className="modal-card" role="dialog" aria-modal="true" aria-label=${copy.reviewsTitle} onClick=${(event) => event.stopPropagation()}>
            <div className="modal-card__head">
              <div>
                <span className="modal-card__eyebrow">${copy.reviewsTitle}</span>
                <h3 className="modal-card__title">${reviewModalTour.title}</h3>
                <p className="modal-card__place">${displayText(placeLabelFromTour(reviewModalTour))}</p>
              </div>
              <button className="modal-card__close" type="button" onClick=${closeReviews}>${copy.close}</button>
            </div>
            <div className="modal-card__body">
              ${isReviewsLoading ? html`<div className="modal-card__notice">${copy.reviewsLoading}</div>` : null}
              ${!isReviewsLoading && reviewsError ? html`<div className="modal-card__notice modal-card__notice--error">${reviewsError}</div>` : null}
              ${!isReviewsLoading && !reviewsError && !reviewItems.length ? html`<div className="modal-card__notice">${copy.reviewsEmpty}</div>` : null}
              ${!isReviewsLoading && !reviewsError && reviewItems.length ? html`<div className="review-list">${reviewItems.map((item, index) => html`
                <article key=${`${reviewModalTour.id || reviewModalTour.link}_${index}`} className="review-item">
                  <div className="review-item__head">
                    <strong>${item.author || copy.guestLabel}</strong>
                    <span>${[item.rating ? `★ ${Number(item.rating).toFixed(1)}` : "", formatReviewDate(item.date, localeCode)].filter(Boolean).join(" · ")}</span>
                  </div>
                  ${item.title ? html`<h4>${item.title}</h4>` : null}
                  <p>${item.text}</p>
                </article>`)}
              </div>` : null}
            </div>
            <div className="modal-card__foot">
              <a href=${reviewModalTour.link} target="_blank" rel="noreferrer" onClick=${(event) => event.stopPropagation()}>${copy.reviewsOpen}</a>
            </div>
          </section>
        </div>` : null}
      ${isAuthModalOpen ? html`
        <div className="modal-backdrop" role="presentation" onClick=${closeAuthModal}>
          <section className="modal-card modal-card--auth" role="dialog" aria-modal="true" aria-label=${copy.authTitle} onClick=${(event) => event.stopPropagation()}>
            <div className="modal-card__head">
              <div>
                <span className="modal-card__eyebrow">${copy.authTitle}</span>
                <h3 className="modal-card__title">${copy.authTitle}</h3>
                <p className="modal-card__place">${copy.authSubtitle}</p>
              </div>
              <button className="modal-card__close" type="button" onClick=${closeAuthModal}>${copy.close}</button>
            </div>
            <div className="modal-card__body">
              <div className="switcher">
                <button className=${authMode === "login" ? "switcher__button switcher__button--active" : "switcher__button"} type="button" onClick=${() => { setAuthMode("login"); setAuthError(""); }}>${copy.authLoginTab}</button>
                <button className=${authMode === "register" ? "switcher__button switcher__button--active" : "switcher__button"} type="button" onClick=${() => { setAuthMode("register"); setAuthError(""); }}>${copy.authRegisterTab}</button>
              </div>
              ${currentUser ? html`<div className="modal-card__notice">${copy.authLoggedIn(currentUser.username)}</div>` : html`
                <form className="auth-form" onSubmit=${submitAuth}>
                  <label className="search-field"><span>${copy.usernameLabel}</span><input className="search-control" value=${authForm.username} onInput=${(event) => setAuthForm((prev) => ({ ...prev, username: event.target.value }))} placeholder=${copy.usernamePlaceholder} autoComplete="username" /></label>
                  <label className="search-field"><span>${copy.passwordLabel}</span><input className="search-control" type="password" value=${authForm.password} onInput=${(event) => setAuthForm((prev) => ({ ...prev, password: event.target.value }))} placeholder=${copy.passwordPlaceholder} autoComplete=${authMode === "login" ? "current-password" : "new-password"} /></label>
                  ${authMode === "register" ? html`<label className="search-field"><span>${copy.confirmPasswordLabel}</span><input className="search-control" type="password" value=${authForm.confirmPassword} onInput=${(event) => setAuthForm((prev) => ({ ...prev, confirmPassword: event.target.value }))} placeholder=${copy.confirmPasswordPlaceholder} autoComplete="new-password" /></label>` : null}
                  ${authError ? html`<div className="modal-card__notice modal-card__notice--error">${authError}</div>` : null}
                  <div className="auth-form__actions">
                    <button className="action-button action-button--primary" type="submit" disabled=${isAuthPending}>${isAuthPending ? "..." : authMode === "register" ? copy.authRegisterAction : copy.authLoginAction}</button>
                  </div>
                </form>`}
            </div>
          </section>
        </div>` : null}
    </div>
  `;
}

createRoot(document.getElementById("root")).render(html`<${App} />`);
