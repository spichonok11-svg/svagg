TOUR_CATEGORIES = [
    {
        "id": "with_hotel",
        "label": "С отелем",
        "description": "Размещение в отеле включено",
    },
    {
        "id": "without_hotel",
        "label": "Без отеля",
        "description": "Только программа отдыха без отеля",
    },
    {
        "id": "with_pool",
        "label": "С бассейном",
        "description": "Есть бассейн на территории",
    },
    {
        "id": "without_pool",
        "label": "Без бассейна",
        "description": "Без бассейна на территории",
    },
    {
        "id": "mountains",
        "label": "Горы",
        "description": "Горные маршруты и локации",
    },
    {
        "id": "forest",
        "label": "Лес",
        "description": "Лесные направления и эко-туризм",
    },
    {
        "id": "recreation_base",
        "label": "Базы отдыха",
        "description": "Отдых на базах и турбазах",
    },
    {
        "id": "waterfront",
        "label": "У воды",
        "description": "Рядом море, озеро или река",
    },
    {
        "id": "family",
        "label": "Семейный",
        "description": "Подходит для поездки с детьми",
    },
    {
        "id": "all_inclusive",
        "label": "Все включено",
        "description": "Питание и часть активностей включены",
    },
]

PRICE_OPTIONS = list(range(5000, 100001, 500))

VALID_CATEGORY_IDS = {category["id"] for category in TOUR_CATEGORIES}
