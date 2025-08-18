# 導入 Python 內建的 `enum` 模組中的 `Enum` 類別。
# `Enum` 是用來建立列舉型別的基底類別，列舉是一組綁定了唯一常數值的符號名稱。
from enum import Enum


# 定義一個名為 `ActionType` 的列舉類別，它同時繼承自 `str` 和 `Enum`。
# 繼承 `str` 讓這個列舉的成員在使用時行為和字串完全一樣，
# 例如可以直接與字串比較，或是在序列化成 JSON 時會自動變成其字串值。
# 這在處理來自 LINE Postback 的 JSON 資料時非常方便。
class ActionType(str, Enum):
    # 定義「顯示訂單詳情」的動作常數。
    # 在程式碼中可以用 `ActionType.SHOW_ORDER_DETAILS` 來引用，其值為 "show_order_details"。
    SHOW_ORDER_DETAILS = "show_order_details"
    
    # 定義「顯示店家介紹」的動作常數。
    SHOW_STORE_SUMMARY = "show_store_summary"
    
    # 定義「查詢歷史訂單」的動作常數。
    ORDER_HISTORY = "order_history"
    
    # 定義「變更語言（觸發語言選單）」的動作常數。
    CHANGE_LANGUAGE = "change_language"
    
    # 定義「設定語言（選擇具體語言後）」的動作常數。
    SET_LANGUAGE = "set_language"