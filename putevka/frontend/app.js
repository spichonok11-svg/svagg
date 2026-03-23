import React, { useEffect, useMemo, useRef, useState } from "https://esm.sh/react@18.2.0";
import { createRoot } from "https://esm.sh/react-dom@18.2.0/client";

const h = React.createElement;
const currency = new Intl.NumberFormat("ru-RU");
const PAGE_SIZE = 12;
const SORT_OPTIONS = [
  { value: "price_asc", label: "Сначала дешевые" },
  { value: "price_desc", label: "Сначала дорогие" },
  { value: "days_asc", label: "Сначала короткие" },
  { value: "days_desc", label: "Сначала длинные" },
];

function formatPrice(value) {
  return `${currency.format(Number(value))} ₽/чел`;
}

function formatDate(value) {
  if (!value) {
    return "не обновлялось";
  }
  return new Date(value).toLocaleString("ru-RU");
}

function buildPageTokens(currentPage, totalPages) {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }
  const tokens = [1];
  const start = Math.max(2, currentPage - 1);
  const end = Math.min(totalPages - 1, currentPage + 1);
  if (start > 2) {
    tokens.push("...");
  }
  for (let page = start; page <= end; page += 1) {
    tokens.push(page);
  }
  if (end < totalPages - 1) {
    tokens.push("...");
  }
  tokens.push(totalPages);
  return tokens;
}

function tourDescription(tour) {
  const text = String(tour.description || "").trim();
  if (!text || text.startsWith("Актуальная путевка")) {
    return `Комфортный отдых в регионе ${tour.region}. Бронирование по актуальной цене.`;
  }
  return text;
}

function App() {
  const shellRef = useRef(null);
  const [categories, setCategories] = useState([]);
  const [priceOptions, setPriceOptions] = useState([]);
  const [popularCities, setPopularCities] = useState([]);
  const [citySuggestions, setCitySuggestions] = useState([]);
  const [cityInput, setCityInput] = useState("");
  const [selectedCity, setSelectedCity] = useState("");
  const [isCityLoading, setIsCityLoading] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedPrice, setSelectedPrice] = useState("");
  const [sort, setSort] = useState("price_asc");
  const [currentPage, setCurrentPage] = useState(1);
  const [viewMode, setViewMode] = useState("grid");
  const [tours, setTours] = useState([]);
  const [count, setCount] = useState(0);
  const [lastParsedAt, setLastParsedAt] = useState(null);
  const [isReady, setIsReady] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    async function bootstrap() {
      try {
        const [categoriesRes, pricesRes] = await Promise.all([
          fetch("/api/categories"),
          fetch("/api/price-options"),
        ]);
        if (!categoriesRes.ok || !pricesRes.ok) {
          throw new Error("Не удалось загрузить фильтры");
        }
        const categoriesPayload = await categoriesRes.json();
        const pricesPayload = await pricesRes.json();
        setCategories(categoriesPayload.categories || []);
        setPriceOptions(pricesPayload.options || []);
        setIsReady(true);
      } catch (bootstrapError) {
        setError(bootstrapError.message || "Ошибка запуска");
      }
    }
    bootstrap();
  }, []);

  useEffect(() => {
    if (!isReady) {
      return;
    }
    loadTours();
  }, [isReady, selectedCategories, selectedPrice, selectedCity, sort, currentPage]);

  useEffect(() => {
    if (!isReady) {
      return;
    }
    let ignore = false;
    async function loadPopularCities() {
      try {
        const response = await fetch("/api/cities?limit=12");
        if (!response.ok) {
          return;
        }
        const payload = await response.json();
        if (!ignore) {
          setPopularCities(payload.cities || []);
        }
      } catch (_error) {
        // Non-blocking request, ignore network issues here.
      }
    }
    loadPopularCities();
    return () => {
      ignore = true;
    };
  }, [isReady]);

  useEffect(() => {
    if (!isReady) {
      return;
    }
    const trimmed = cityInput.trim();
    if (!trimmed) {
      setCitySuggestions(popularCities);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setIsCityLoading(true);
      try {
        const response = await fetch(`/api/cities?q=${encodeURIComponent(trimmed)}&limit=12`, {
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error("Не удалось получить города");
        }
        const payload = await response.json();
        setCitySuggestions(payload.cities || []);
      } catch (citiesError) {
        if (citiesError.name !== "AbortError") {
          setCitySuggestions([]);
        }
      } finally {
        setIsCityLoading(false);
      }
    }, 220);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [cityInput, isReady, popularCities]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [currentPage]);

  function handlePointerMove(event) {
    if (!shellRef.current) {
      return;
    }
    const rect = shellRef.current.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    shellRef.current.style.setProperty("--mx", `${(x * 20).toFixed(2)}px`);
    shellRef.current.style.setProperty("--my", `${(y * 20).toFixed(2)}px`);
  }

  function resetPointer() {
    if (!shellRef.current) {
      return;
    }
    shellRef.current.style.setProperty("--mx", "0px");
    shellRef.current.style.setProperty("--my", "0px");
  }

  async function loadTours() {
    setIsLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (selectedPrice) {
      params.set("pricePerPerson", selectedPrice);
    }
    if (selectedCity) {
      params.set("city", selectedCity);
    }
    params.set("sort", sort);
    params.set("limit", String(PAGE_SIZE));
    params.set("offset", String((currentPage - 1) * PAGE_SIZE));
    for (const categoryId of selectedCategories) {
      params.append("category", categoryId);
    }

    try {
      const response = await fetch(`/api/tours?${params.toString()}`);
      if (!response.ok) {
        throw new Error("Ошибка загрузки туров");
      }
      const payload = await response.json();
      setTours(payload.tours || []);
      setCount(Number(payload.count || 0));
      setLastParsedAt(payload.lastParsedAt || null);
    } catch (loadError) {
      setError(loadError.message || "Не удалось загрузить туры");
    } finally {
      setIsLoading(false);
    }
  }

  async function onRefreshParse() {
    setIsLoading(true);
    setError("");
    try {
      const response = await fetch("/api/parse", { method: "POST" });
      if (!response.ok) {
        throw new Error("Не удалось обновить парсер");
      }
      await loadTours();
    } catch (refreshError) {
      setError(refreshError.message || "Не удалось обновить данные");
    } finally {
      setIsLoading(false);
    }
  }

  function onCategoryToggle(categoryId, enabled) {
    setCurrentPage(1);
    if (enabled) {
      setSelectedCategories((prev) => (prev.includes(categoryId) ? prev : [...prev, categoryId]));
    } else {
      setSelectedCategories((prev) => prev.filter((item) => item !== categoryId));
    }
  }

  function removeCategory(categoryId) {
    setSelectedCategories((prev) => prev.filter((item) => item !== categoryId));
    setCurrentPage(1);
  }

  function applyCity(cityName) {
    const normalized = String(cityName || "").trim();
    setSelectedCity(normalized);
    setCityInput(normalized);
    setCurrentPage(1);
  }

  function clearCity() {
    setSelectedCity("");
    setCityInput("");
    setCurrentPage(1);
  }

  function openTourLink(url) {
    const normalized = String(url || "").trim();
    if (!normalized || normalized === "#") {
      return;
    }
    window.open(normalized, "_blank", "noopener,noreferrer");
  }

  function resetFilters() {
    setSelectedCategories([]);
    setSelectedPrice("");
    setSelectedCity("");
    setCityInput("");
    setSort("price_asc");
    setCurrentPage(1);
  }

  const totalPages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const pageTokens = useMemo(
    () => buildPageTokens(currentPage, totalPages),
    [currentPage, totalPages]
  );

  const categoryMap = useMemo(() => {
    const map = new Map();
    for (const category of categories) {
      map.set(category.id, category.label);
    }
    return map;
  }, [categories]);

  return h(
    "div",
    {
      className: "page-shell",
      ref: shellRef,
      onMouseMove: handlePointerMove,
      onMouseLeave: resetPointer,
    },
    h("div", { className: "scene", "aria-hidden": "true" },
      h("div", { className: "scene__grid" }),
      h("div", { className: "scene__blob scene__blob--a" }),
      h("div", { className: "scene__blob scene__blob--b" }),
      h("div", { className: "scene__blob scene__blob--c" }),
      h("div", { className: "scene__ring scene__ring--a" }),
      h("div", { className: "scene__ring scene__ring--b" })
    ),
    h(
      "header",
      { className: "hero" },
      h(
        "div",
        { className: "hero__content" },
        h("p", { className: "hero__eyebrow" }, "Каталог путевок"),
        h("h1", null, "Путевки по России"),
        h(
          "p",
          { className: "hero__subtitle" },
          "Живая витрина путевок: листай страницы, выбирай категории и находи лучший отдых."
        )
      )
    ),
    h(
      "main",
      { className: "layout" },
      h(
        "aside",
        { className: "panel filters" },
        h("h2", null, "Фильтры"),
        h("label", { className: "label", htmlFor: "sortSelect" }, "Сортировка"),
        h(
          "select",
          {
            id: "sortSelect",
            className: "select",
            value: sort,
            onChange: (event) => {
              setSort(event.target.value);
              setCurrentPage(1);
            },
          },
          ...SORT_OPTIONS.map((option) => h("option", { key: option.value, value: option.value }, option.label))
        ),
        h("label", { className: "label", htmlFor: "priceSelect" }, "Цена на человека"),
        h(
          "select",
          {
            id: "priceSelect",
            className: "select",
            value: selectedPrice,
            onChange: (event) => {
              setSelectedPrice(event.target.value);
              setCurrentPage(1);
            },
          },
          h("option", { value: "" }, "Любая"),
          ...priceOptions.map((price) =>
            h("option", { key: price, value: String(price) }, formatPrice(price))
          )
        ),
        h("label", { className: "label", htmlFor: "cityInput" }, "Город"),
        h(
          "div",
          { className: "city-search" },
          h(
            "div",
            { className: "city-search__row" },
            h("input", {
              id: "cityInput",
              className: "input",
              type: "text",
              value: cityInput,
              placeholder: "Начни вводить город",
              onChange: (event) => {
                const nextValue = event.target.value;
                setCityInput(nextValue);
                if (!nextValue.trim()) {
                  setSelectedCity("");
                  setCurrentPage(1);
                }
              },
              onKeyDown: (event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  applyCity(cityInput);
                }
              },
            }),
            selectedCity
              ? h(
                  "button",
                  {
                    className: "city-search__clear",
                    type: "button",
                    onClick: clearCity,
                    title: "Очистить город",
                  },
                  "×"
                )
              : null
          ),
          cityInput.trim() && isCityLoading
            ? h("p", { className: "city-search__status" }, "Ищем города...")
            : null,
          citySuggestions.length > 0
            ? h(
                "div",
                { className: "city-suggestions" },
                ...citySuggestions.map((item) =>
                  h(
                    "button",
                    {
                      key: `city_suggestion_${item.city}`,
                      className:
                        selectedCity === item.city
                          ? "city-suggestion city-suggestion--active"
                          : "city-suggestion",
                      type: "button",
                      onClick: () => applyCity(item.city),
                    },
                    `${item.city} (${item.count})`
                  )
                )
              )
            : cityInput.trim()
              ? h("p", { className: "city-search__status" }, "Городов по этому префиксу нет")
              : null,
          h(
            "button",
            {
              className: "btn btn--city",
              type: "button",
              onClick: () => applyCity(cityInput),
              disabled: !cityInput.trim(),
            },
            selectedCity ? `Применен: ${selectedCity}` : "Применить город"
          )
        ),
        popularCities.length > 0
          ? h(
              "div",
              { className: "popular-cities" },
              h("p", { className: "label label--compact" }, "Популярные города"),
              h(
                "div",
                { className: "popular-cities__list" },
                ...popularCities.slice(0, 8).map((item) =>
                  h(
                    "button",
                    {
                      key: `city_popular_${item.city}`,
                      className: "popular-cities__chip",
                      type: "button",
                      onClick: () => applyCity(item.city),
                    },
                    item.city
                  )
                )
              )
            )
          : null,
        h("p", { className: "label" }, "Категории"),
        h(
          "div",
          { className: "category-list" },
          ...categories.map((category) =>
            h(
              "label",
              { className: "category-item", key: category.id },
              h("input", {
                type: "checkbox",
                checked: selectedCategories.includes(category.id),
                onChange: (event) => onCategoryToggle(category.id, event.target.checked),
              }),
              h("span", { className: "category-item__title" }, category.label),
              h("span", { className: "category-item__desc" }, category.description)
            )
          )
        ),
        h(
          "div",
          { className: "button-row" },
          h(
            "button",
            { className: "btn", type: "button", onClick: onRefreshParse, disabled: isLoading },
            isLoading ? "Обновление..." : "Обновить парсер"
          ),
          h(
            "button",
            { className: "btn btn--secondary", type: "button", onClick: resetFilters, disabled: isLoading },
            "Сбросить фильтры"
          )
        )
      ),
      h(
        "section",
        { className: "panel results" },
        error ? h("div", { className: "error-box" }, error) : null,
        h(
          "div",
          { className: "results__head" },
          h(
            "div",
            { className: "results__meta" },
            h("strong", null, `Найдено: ${count}`),
            h("span", null, `Страница: ${currentPage} из ${totalPages}`),
            h("span", null, selectedCity ? `Город: ${selectedCity}` : "Город: все"),
            h("span", null, `Обновлено: ${formatDate(lastParsedAt)}`)
          ),
          h(
            "div",
            { className: "view-switch" },
            h(
              "button",
              {
                className: viewMode === "grid" ? "view-switch__btn view-switch__btn--active" : "view-switch__btn",
                type: "button",
                onClick: () => setViewMode("grid"),
              },
              "Сетка"
            ),
            h(
              "button",
              {
                className: viewMode === "list" ? "view-switch__btn view-switch__btn--active" : "view-switch__btn",
                type: "button",
                onClick: () => setViewMode("list"),
              },
              "Список"
            )
          )
        ),
        selectedCategories.length > 0 || Boolean(selectedCity)
          ? h(
              "div",
              { className: "active-filters" },
              selectedCity
                ? h(
                    "button",
                    {
                      key: "active_city",
                      className: "active-filter",
                      type: "button",
                      onClick: clearCity,
                    },
                    `Город: ${selectedCity} ×`
                  )
                : null,
              ...selectedCategories.map((categoryId) =>
                h(
                  "button",
                  {
                    key: `active_${categoryId}`,
                    className: "active-filter",
                    type: "button",
                    onClick: () => removeCategory(categoryId),
                  },
                  `${categoryMap.get(categoryId) || categoryId} ×`
                )
              )
            )
          : null,
        isLoading
          ? h(
              "div",
              { className: viewMode === "list" ? "cards cards--list" : "cards cards--grid" },
              ...Array.from({ length: 8 }).map((_, index) =>
                h("div", { key: `skeleton_${index}`, className: "tour-card skeleton" })
              )
            )
          : null,
        !isLoading && tours.length === 0
          ? h("div", { className: "empty" }, "По выбранным фильтрам путевки не найдены.")
          : null,
        !isLoading
          ? h(
              "div",
              { className: viewMode === "list" ? "cards cards--list" : "cards cards--grid" },
              ...tours.map((tour) =>
                h(
                  "article",
                  {
                    className: "tour-card",
                    key: tour.id,
                    role: "link",
                    tabIndex: 0,
                    onClick: () => openTourLink(tour.link),
                    onKeyDown: (event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openTourLink(tour.link);
                      }
                    },
                  },
                  h(
                    "p",
                    { className: "tour-card__region" },
                    `${tour.city && tour.city !== tour.region ? `${tour.city}, ${tour.region}` : tour.city || tour.region} • ${tour.days} ночей`
                  ),
                  h("h3", { className: "tour-card__title" }, tour.title),
                  h("p", { className: "tour-card__price" }, formatPrice(tour.pricePerPerson)),
                  h(
                    "div",
                    { className: "chip-list" },
                    ...tour.categories.slice(0, 4).map((categoryId) =>
                      h(
                        "span",
                        { className: "chip", key: `${tour.id}_${categoryId}` },
                        categoryMap.get(categoryId) || categoryId
                      )
                    )
                  ),
                  h("p", { className: "tour-card__desc" }, tourDescription(tour)),
                  h(
                    "a",
                    {
                      className: "tour-card__link",
                      href: tour.link,
                      target: "_blank",
                      rel: "noreferrer",
                      onClick: (event) => event.stopPropagation(),
                    },
                    "Подробнее"
                  )
                )
              )
            )
          : null,
        h(
          "div",
          { className: "pager pager--numbers" },
          h(
            "button",
            {
              className: "pager__btn",
              type: "button",
              disabled: currentPage === 1 || isLoading,
              onClick: () => setCurrentPage((page) => Math.max(1, page - 1)),
            },
            "Назад"
          ),
          ...pageTokens.map((token, index) =>
            token === "..."
              ? h("span", { className: "pager__dots", key: `dots_${index}` }, "…")
              : h(
                  "button",
                  {
                    key: `page_${token}`,
                    className:
                      token === currentPage ? "pager__btn pager__btn--active" : "pager__btn",
                    type: "button",
                    onClick: () => setCurrentPage(token),
                    disabled: isLoading,
                  },
                  String(token)
                )
          ),
          h(
            "button",
            {
              className: "pager__btn",
              type: "button",
              disabled: currentPage >= totalPages || isLoading,
              onClick: () => setCurrentPage((page) => Math.min(totalPages, page + 1)),
            },
            "Вперед"
          )
        )
      )
    )
  );
}

createRoot(document.getElementById("root")).render(h(App));
