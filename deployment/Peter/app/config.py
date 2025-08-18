# 導入 `os` 模組，用於與作業系統進行互動，如此處用來處理檔案路徑和讀取環境變數。
import os

# 從 `dotenv` 函式庫中導入 `load_dotenv` 函式。
# 這個函式可以讀取 `.env` 檔案，並將其中定義的變數載入到系統的環境變數中。
from dotenv import load_dotenv

# 取得專案的根目錄路徑。
# `__file__` 是目前檔案 (`config.py`) 的路徑。
# `os.path.abspath(__file__)` 取得該檔案的絕對路徑。
# `os.path.dirname()` 取得路徑所在的目錄。第一次呼叫會得到 `app` 目錄，第二次呼叫則會得到專案的根目錄。
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 使用 `os.path.join` 組合專案根目錄和 ".env" 檔名，形成 `.env` 檔案的完整路徑。
# 接著呼叫 `load_dotenv` 函式，讀取該檔案中的鍵值對，並將它們設定為環境變數，讓 `os.environ` 可以讀取到。
load_dotenv(os.path.join(project_root, ".env"))


# 定義一個 `Config` 類別，用來集中存放所有從環境變數讀取的設定值。
# 使用類別來管理設定，可以讓程式碼在引用設定時更加清晰（例如 `Config.CHANNEL_ACCESS_TOKEN`）。
class Config:
    # --- LINE Bot 設定 ---
    # 從環境變數中讀取 LINE Channel Access Token。
    # 使用 `os.environ[...]` 的方括號語法，如果環境變數未設定，程式會立即拋出 `KeyError` 例外並終止，這有助於及早發現缺少關鍵設定的問題。
    CHANNEL_ACCESS_TOKEN = os.environ["CHANNEL_ACCESS_TOKEN"]
    CHANNEL_SECRET = os.environ["CHANNEL_SECRET"] # 從環境變數中讀取 LINE Channel Secret，同樣為必要設定。

    # --- 資料庫設定 ---
    DATABASE_URL = os.environ["DATABASE_URL"] # 從環境變數中讀取資料庫連線 URL，同樣為必要設定。

    # --- LIFF (LINE Front-end Framework) 設定 ---
    # 從環境變數中讀取 LIFF 的 ID。
    # 使用 `.get()` 方法，如果該環境變數不存在，會返回 `None` 而不是拋出錯誤，表示這是一個可選設定。
    LIFF_ID = os.environ.get("LIFF_ID")

    # --- Google Maps API 設定 ---
    MAPS_API_KEY = os.environ.get("MAPS_API_KEY") # 從環境變數中讀取 Google Maps API 金鑰，為可選設定。

    # --- 應用程式通用設定 ---
    # 從環境變數中讀取應用程式的公開基礎 URL，例如 `https://your-domain.com`。
    # 這個設定可能用於產生絕對路徑的 URL（例如圖片連結），是一個可選設定。
    BASE_URL = os.environ.get("BASE_URL")

    # --- Google Places API 詳細設定 ---
    PLACES_API_BASE_URL = "https://places.googleapis.com/v1/places" # 設定 Google Places API 的基礎 URL。
    _PLACES_NEARBY_SEARCH_ENDPOINT = ":searchNearby" # 設定 Places API 的「附近搜尋」(Nearby Search) 端點路徑。前面的底線 `_` 是一個慣例，表示這是一個內部使用的變數。
    _PLACES_TEXT_SEARCH_ENDPOINT = ":searchText" # 設定 Places API 的「文字搜尋」(Text Search) 端點路徑。

    # 設定「附近搜尋」的半徑（單位：公尺）。
    # 使用 `.get()` 並提供第二個參數 `"200.0"` 作為預設值。如果環境變數未設定，就會使用這個預設值。
    # 最後使用 `float()` 將字串轉換為浮點數。
    PLACES_NEARBY_SEARCH_RADIUS = float(
        os.environ.get("PLACES_NEARBY_SEARCH_RADIUS", "200.0")
    )
    # 設定「附近搜尋」返回的最大結果數量，預設為 10。
    PLACES_NEARBY_SEARCH_MAX_RESULTS = int(
        os.environ.get("PLACES_NEARBY_SEARCH_MAX_RESULTS", "10")
    )
    # 設定「附近搜尋」要篩選的主要地點類型。
    # 預設值為 "restaurant"。如果環境變數中設定了多個類型（以逗號分隔，例如 "restaurant,cafe"），`.split(',')` 會將其轉換成一個列表。
    PLACES_NEARBY_PRIMARY_TYPES = os.environ.get(
        "PLACES_NEARBY_PRIMARY_TYPES", "restaurant"
    ).split(",")
    # 設定「附近搜尋」的排序偏好，預設為 `POPULARITY` (人氣)。
    PLACES_NEARBY_RANK_PREFERENCE = os.environ.get(
        "PLACES_NEARBY_RANK_PREFERENCE", "POPULARITY"
    )

    # 設定「文字搜尋」時，位置偏誤的半徑（單位：公尺），預設為 50.0。
    # 這會讓搜尋結果偏向於使用者目前位置附近的地點。
    PLACES_TEXT_SEARCH_RADIUS_BIAS = float(
        os.environ.get("PLACES_TEXT_SEARCH_RADIUS_BIAS", "50.0")
    )
    # 設定「文字搜尋」返回的最大結果數量，預設為 1。
    PLACES_TEXT_SEARCH_MAX_RESULTS = int(
        os.environ.get("PLACES_TEXT_SEARCH_MAX_RESULTS", "1")
    )

    # --- 組合 API URL 與欄位遮罩 ---
    # 組合基礎 URL 和端點路徑，產生「附近搜尋」的完整 API URL。
    PLACES_NEARBY_SEARCH_URL = f"{PLACES_API_BASE_URL}{_PLACES_NEARBY_SEARCH_ENDPOINT}"
    # 組合基礎 URL 和端點路徑，產生「文字搜尋」的完整 API URL。
    PLACES_TEXT_SEARCH_URL = f"{PLACES_API_BASE_URL}{_PLACES_TEXT_SEARCH_ENDPOINT}"

    # 設定「附近搜尋」API 的欄位遮罩（Field Mask）。
    # 這會告訴 Google API 只返回我們需要的特定欄位 (`places.displayName`, `places.id` 等)，可以減少資料傳輸量並可能降低 API 費用。
    PLACES_NEARBY_FIELD_MASK = "places.displayName,places.id,places.photos,places.location"
    # 設定「文字搜尋」API 的欄位遮罩。
    PLACES_TEXT_FIELD_MASK = (
        "places.id,places.displayName,places.photos,places.types,places.location"
    )