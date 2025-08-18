# 導入 Python 內建的 `logging` 模組，用於記錄程式運行時的事件、錯誤和資訊。
import logging

# 從 Google API 核心函式庫中導入特定的例外類別。
# `ClientError`: 通常指客戶端設定或請求格式等問題的錯誤。
# `GoogleAPICallError`: 指 API 呼叫本身失敗的錯誤，例如網路問題或伺服器端錯誤。
# 捕獲這些特定的例外，可以讓錯誤處理更加精確。
from google.api_core.exceptions import ClientError, GoogleAPICallError
# 從 Google Cloud Translate V2 函式庫中導入 `translate` 模組，並將其別名為 `translate` 以方便使用。
from google.cloud import translate_v2 as translate

# 取得一個日誌記錄器（logger）實例。
# 參數 "uvicorn.error" 表示這個 logger 會整合到 uvicorn 伺服器的錯誤日誌系統中。
# 透過這個 logger 輸出的訊息，會與 uvicorn 的日誌一起顯示，方便集中管理和查看。
logger = logging.getLogger("uvicorn.error")


# 定義一個函式，用於初始化所有需要用到的 Google 服務客戶端。
def initialize_google_clients():
    # 使用 try...except 區塊來包裹可能會發生錯誤的初始化過程，例如認證失敗、網路問題等。
    try:
        # 記錄一條參考訊息，表示正在開始初始化 Google Translate API 客戶端。
        logger.info("Initializing Google Translate API client...")
        # 建立 Google Translate API V2 的客戶端實例。
        # 在背景中，`translate.Client()` 會自動尋找環境變數 `GOOGLE_APPLICATION_CREDENTIALS` 或其他 GCP 預設的認證方式來進行驗證。
        translate_client_instance = translate.Client()

        # 執行一個簡單的 API 呼叫 (`get_languages`) 來驗證客戶端是否設定成功且能夠正常連線。
        # 如果認證失敗或網路不通，這行程式碼會拋出例外。
        # 這是一個很好的實踐，可以在應用程式啟動初期就發現設定問題，而不是等到第一次實際需要翻譯時才出錯。
        translate_client_instance.get_languages(target_language="en")

        # 如果上面的 API 呼叫成功，記錄一條成功訊息。
        logger.info("Google Translate API client initialized successfully.")
        # 返回成功建立並驗證過的客戶端實例。
        return translate_client_instance
    # 捕獲多種類型的例外：Google API 呼叫錯誤、客戶端設定錯誤，以及所有其他可能的通用例外。
    except (GoogleAPICallError, ClientError, Exception) as e:
        # 如果在初始化過程中發生任何錯誤，記錄一條詳細的錯誤訊息。
        # `exc_info=True` 會一併記錄完整的錯誤堆疊追蹤（traceback），對於除錯非常有幫助。
        logger.error(f"Failed to initialize Google Translate API client: {e}", exc_info=True)
        # 記錄一條警告訊息，告知開發者或維運人員，機器人將在功能降級的模式下運行（翻譯功能將不可用）。
        logger.warning("Bot will run in degraded mode (translation features disabled).")
        # 返回 False，讓呼叫此函式的地方可以根據返回值判斷初始化是否成功，並作出相應的處理。
        return False