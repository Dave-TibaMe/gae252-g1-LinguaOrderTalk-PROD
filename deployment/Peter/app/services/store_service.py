# 導入 asyncio 模組，用於非同步 I/O 操作，特別是同時執行多個任務。
import asyncio
# 導入 logging 模組，用於記錄程式運行時的資訊、警告和錯誤。
import logging
# 從 typing 模組導入型別提示，以增強程式碼可讀性。
# Any: 表示可以是任何型別。
# Dict: 表示字典型別。
# List: 表示列表型別。
# Optional: 表示一個值可以是某個指定型別，也可以是 None。
from typing import Any, Dict, List, Optional

# 導入 aiohttp 模組，用於發送非同步 HTTP 請求。
import aiohttp
# 從 sqlalchemy.ext.asyncio 導入 AsyncSession，用於型別提示資料庫會話物件。
from sqlalchemy.ext.asyncio import AsyncSession

# 從上層目錄 (app/) 導入 crud 模組，用於資料庫操作。
from .. import crud
# 從上層目錄導入 Config 類別，用於讀取設定檔中的參數。
from ..config import Config
# 從上層目錄導入 Store 模型，用於型別提示。
from ..models import Store

# 取得一個 logger 實例，用於記錄日誌。
logger = logging.getLogger(__name__)


async def find_and_sync_nearby_stores(
    db: AsyncSession,
    aiohttp_session: aiohttp.ClientSession,
    user_lat: float,
    user_lng: float,
    title: Optional[str] = None,
    address: Optional[str] = None,
) -> List[Store]:
    """
    根據使用者位置，呼叫 Google Places API 搜尋附近的店家，
    並將新店家同步到資料庫，最後返回一個排序後的店家列表。
    """
    # 準備 Google Places API Nearby Search 請求所需的標頭 (headers)。
    # 設置 Content-Type 為 JSON，並將 API 金鑰和欄位遮罩 (Field Mask) 加入標頭。
    nearby_headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": Config.MAPS_API_KEY,
        "X-Goog-FieldMask": Config.PLACES_NEARBY_FIELD_MASK,
    }
    # 準備 Nearby Search 請求的 JSON 主體 (payload)。
    # 包含要搜尋的主要類型、最大結果數、以使用者位置為中心的圓形區域限制，以及排序偏好和語言代碼。
    nearby_payload = {
        "includedPrimaryTypes": Config.PLACES_NEARBY_PRIMARY_TYPES,
        "maxResultCount": Config.PLACES_NEARBY_SEARCH_MAX_RESULTS,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": user_lat, "longitude": user_lng},
                "radius": Config.PLACES_NEARBY_SEARCH_RADIUS,
            }
        },
        "rankPreference": Config.PLACES_NEARBY_RANK_PREFERENCE,
        "languageCode": "zh-TW",
    }

    # 初始化一個列表來存放所有要同時執行的 API 請求任務。
    tasks = []
    # 創建一個非同步任務，用於發送 Nearby Search 請求，並將其加入任務列表。
    nearby_task = aiohttp_session.post(
        Config.PLACES_NEARBY_SEARCH_URL, headers=nearby_headers, json=nearby_payload
    )
    tasks.append(nearby_task)

    # 處理第二個可能的搜尋請求：文字搜尋 (Text Search)。
    text_task = None
    # 如果使用者傳送的位置訊息包含標題 (title) 和地址 (address)，則執行文字搜尋。
    if title and address:
        logger.info(f"Executing Text Search for landmark: '{title}'")
        # 準備 Text Search 請求所需的標頭。
        text_headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": Config.MAPS_API_KEY,
            "X-Goog-FieldMask": Config.PLACES_TEXT_FIELD_MASK,
        }
        # 準備 Text Search 請求的 JSON 主體。
        # 使用使用者傳送的標題和地址作為查詢關鍵字。
        text_payload = {
            "textQuery": f"{title} {address}",
            "maxResultCount": Config.PLACES_TEXT_SEARCH_MAX_RESULTS,
            "locationBias": {
                "circle": {
                    "center": {"latitude": user_lat, "longitude": user_lng},
                    "radius": Config.PLACES_TEXT_SEARCH_RADIUS_BIAS,
                }
            },
            "languageCode": "zh-TW",
        }
        # 創建一個非同步任務，用於發送 Text Search 請求，並將其加入任務列表。
        text_task = aiohttp_session.post(
            Config.PLACES_TEXT_SEARCH_URL, headers=text_headers, json=text_payload
        )
        tasks.append(text_task)

    # 同時執行所有 API 請求任務。
    # `asyncio.gather` 會等待所有任務完成，並返回一個包含每個任務結果的列表。
    # `return_exceptions=True` 確保即使其中一個任務失敗，也不會中斷整個函式，而是將例外作為結果返回。
    logger.info(f"Executing {len(tasks)} Google Places API requests concurrently.")
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 初始化列表，用於存放最終篩選後的 Google Places API 結果。
    final_places: List[Dict[str, Any]] = []
    # 初始化變數，用於存放地標（由文字搜尋找到的店家）。
    landmark_place = None

    # 處理 Nearby Search 的結果。
    nearby_result_or_exc = results[0]
    # 如果結果是一個例外，表示請求失敗。
    if isinstance(nearby_result_or_exc, Exception):
        logger.error(f"Google Nearby Search API request failed: {nearby_result_or_exc}")
    else:
        try:
            # 檢查 HTTP 回應狀態碼，如果不是 2xx，則拋出例外。
            nearby_result_or_exc.raise_for_status()
            # 解析 JSON 回應。
            nearby_result = await nearby_result_or_exc.json()
            # 從回應中提取店家列表。
            final_places = nearby_result.get("places", [])
            logger.info(f"Nearby Search found {len(final_places)} potential places.")
        except Exception as e:
            logger.error(f"Error processing Nearby Search response: {e}")

    # 如果有 Text Search 任務，則處理其結果。
    if text_task:
        text_result_or_exc = results[1]
        # 如果結果是一個例外，表示請求失敗。
        if isinstance(text_result_or_exc, Exception):
            logger.error(f"Google Text Search API request failed: {text_result_or_exc}")
        else:
            try:
                # 檢查 HTTP 回應狀態碼。
                text_result_or_exc.raise_for_status()
                # 解析 JSON 回應，並取得第一個（也是唯一一個）店家結果。
                text_result = await text_result_or_exc.json()
                landmark_place = text_result.get("places", [None])[0]
            except Exception as e:
                logger.error(f"Error processing Text Search response: {e}")

    # 如果所有搜尋都沒有找到店家，記錄警告並返回空列表。
    if not final_places:
        logger.warning("No places found after API calls.")
        return []

    # 如果文字搜尋找到了店家，並且該店家類型是餐廳或食品店，則將其置於列表最前端。
    landmark_place_id = None
    if landmark_place and (
        "restaurant" in landmark_place.get("types", [])
        or "food_store" in landmark_place.get("types", [])
    ):
        logger.info(f"Landmark '{title}' is a restaurant or food store. Prepending to the list.")
        landmark_place_id = landmark_place.get("id")
        # 從 Nearby Search 的結果中移除與地標重複的店家，避免重複顯示。
        final_places = [p for p in final_places if p.get("id") != landmark_place_id]
        # 將地標店家插入到列表的最前面。
        final_places.insert(0, landmark_place)

    # 取得所有 Google Place ID，用於後續批次查詢資料庫。
    place_ids_from_api = [place.get("id") for place in final_places if place.get("id")]
    # 根據 Place ID 列表，從資料庫批次查詢已存在的店家。
    existing_stores_result = await crud.get_stores_by_place_ids(db, place_ids_from_api)
    # 將查詢結果轉換為一個字典，以 Place ID 為鍵，方便快速查找。
    existing_stores_map = {store.place_id: store for store in existing_stores_result}

    # 初始化列表，用於存放最終需要回傳的店家物件。
    synced_stores: List[Store] = []
    # 初始化列表，用於存放需要新增到資料庫的新店家物件。
    new_stores_to_add: List[Store] = []
    # 遍歷從 Google Places API 獲得的店家列表（最多前10個）。
    for place in final_places[:10]:
        place_id = place.get("id")
        if not place_id:
            continue

        # 檢查該店家是否已經存在於資料庫中。
        store_in_db = existing_stores_map.get(place_id)
        if not store_in_db:
            logger.info(f"Store with place_id {place_id} not in DB. Creating new entry.")
            # 取得店家的顯示名稱。
            new_store_name = place.get("displayName", {}).get("text", "N/A")

            # 處理店家照片 URL。
            new_photo_url = None
            if place.get("photos"):
                # 取得第一張照片的資源名稱。
                photo_name = place["photos"][0]["name"]
                # 組合一個指向我們代理 API 端點的 URL。
                new_photo_url = f"/api/v1/places/photo/{photo_name}"

            # 創建一個新的 Store ORM 物件。
            store_in_db = Store(
                store_name=new_store_name,
                partner_level=0, # 預設合作等級為 0。
                gps_lat=place.get("location", {}).get("latitude"),
                gps_lng=place.get("location", {}).get("longitude"),
                place_id=place_id,
                main_photo_url=new_photo_url,
            )
            # 將新的 Store 物件加入到待新增列表中。
            new_stores_to_add.append(store_in_db)

        # 將已存在或新創建的 Store 物件加入到最終的回傳列表中。
        synced_stores.append(store_in_db)

    # 如果有任何新店家需要新增...
    if new_stores_to_add:
        logger.info(f"Committing {len(new_stores_to_add)} new stores to the database.")
        # 使用 `crud.add_stores` 函式將所有新店家一次性寫入資料庫，以減少 I/O 次數。
        await crud.add_stores(db, new_stores_to_add)

    # 根據是否找到地標店家，對列表進行排序。
    landmark_store = None
    other_stores = []
    if landmark_place_id:
        for store in synced_stores:
            if store.place_id == landmark_place_id:
                landmark_store = store
            else:
                other_stores.append(store)
    else:
        other_stores = synced_stores

    logger.info(f"Sorting {len(other_stores)} other stores by partner_level.")
    # 對非地標店家進行排序，合作等級高的排在前面。
    sorted_other_stores = sorted(
        other_stores, key=lambda s: s.partner_level, reverse=True
    )

    # 將地標店家（如果存在）放在列表最前面，並將其他排序好的店家接在其後。
    if landmark_store:
        logger.info(f"Landmark store '{landmark_store.store_name}' is placed at the top.")
        final_sorted_list = [landmark_store] + sorted_other_stores
    else:
        final_sorted_list = sorted_other_stores

    logger.info(
        f"Service finished. Returning {len(final_sorted_list)} sorted store objects."
    )
    # 返回最終排序好的店家列表。
    return final_sorted_list