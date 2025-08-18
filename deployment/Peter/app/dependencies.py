# 從 `typing` 模組導入型別提示，用於程式碼靜態分析和提升可讀性。
# `Any`: 表示可以是任何型別。
# `Dict`: 表示字典型別。
# `List`: 表示列表型別。
from typing import Any, Dict, List

# 導入 `aiohttp` 函式庫，這裡主要是為了型別提示 `aiohttp.ClientSession`。
import aiohttp
# 從 `fastapi` 導入 `Request` 物件，這個物件代表了客戶端發送的 HTTP 請求。
# 我們可以透過 `request.app` 來存取 FastAPI 的應用程式實例。
from fastapi import Request


def get_aiohttp_session(request: Request) -> aiohttp.ClientSession:
    """
    FastAPI 依賴項：取得在應用程式啟動時建立的全域 aiohttp ClientSession。
    
    透過 `request.app.state` 可以存取在 `lifespan` 事件中初始化的物件。
    這樣可以確保整個應用程式共享同一個 ClientSession，從而有效地重用連線，提升效能。
    """
    # 從 request 物件中存取 FastAPI 應用程式實例 (`request.app`)，
    # 再從應用程式的狀態儲存 (`state`) 中，取得名為 `aiohttp_session` 的屬性並返回。
    return request.app.state.aiohttp_session


def get_translate_client(request: Request) -> Any:
    """
    FastAPI 依賴項：取得在應用程式啟動時初始化的 Google Translate 客戶端。
    
    回傳值的型別提示為 `Any`，因為如果初始化失敗，`app.state.translate_client` 的值會是 `False`，
    否則它會是一個 `google.cloud.translate_v2.client.Client` 物件。
    使用這個依賴項的函式需要處理這兩種可能性。
    """
    # 返回儲存在應用程式狀態中的 `translate_client` 實例。
    return request.app.state.translate_client


def get_lang_code_map(request: Request) -> Dict[str, Any]:
    """
    FastAPI 依賴項：取得從資料庫預先載入的語言代碼映射表。
    
    這個映射表在應用程式啟動時一次性從資料庫讀取並快取，
    避免了每次請求都需要查詢資料庫的開銷。
    """
    # 返回儲存在應用程式狀態中的 `lang_code_map` 字典。
    return request.app.state.lang_code_map


def get_native_language_list(request: Request) -> List[Dict[str, Any]]:
    """
    FastAPI 依賴項：取得從 JSON 檔案預先載入的原生語言列表。
    
    這個列表包含了所有支援的語言及其原生名稱，同樣在啟動時載入以供後續使用。
    """
    # 返回儲存在應用程式狀態中的 `native_language_list` 列表。
    return request.app.state.native_language_list


def get_language_display_texts(request: Request) -> Dict[str, str]:
    """
    FastAPI 依賴項：取得在應用程式啟動時預先翻譯並快取的語言顯示文字。
    
    為了加速語言選擇介面的回應速度，應用程式在啟動時就將某些固定文字（如 "將語言設定為...")
    翻譯成所有支援的語言並存成一個字典。這個依賴項就是用來取得該快取字典。
    """
    # 返回儲存在應用程式狀態中的 `language_display_texts` 字典。
    return request.app.state.language_display_texts