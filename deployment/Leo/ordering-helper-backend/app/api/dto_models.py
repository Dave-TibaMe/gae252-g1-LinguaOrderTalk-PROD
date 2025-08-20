# =============================================================================
# 檔案名稱：app/api/dto_models.py
# 功能描述：DTO (Data Transfer Object) 模型，用於處理雙語菜單項目
# 主要職責：
# - 定義 Pydantic 模型來管理原文和翻譯版本
# - 提供雙語菜單項目的序列化功能
# - 支援動態語言切換
# =============================================================================

from pydantic import BaseModel, computed_field
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

class MenuItemName(BaseModel):
    """菜單項目名稱模型（支援雙語）"""
    original: str  # 原始中文名稱
    translated: str  # 翻譯後名稱
    
    def __init__(self, original: str, translated: str = None, **kwargs):
        # 如果沒有提供翻譯，預設使用原文
        if translated is None:
            translated = original
        super().__init__(original=original, translated=translated, **kwargs)

class MenuItemDTO(BaseModel):
    """菜單項目 DTO 模型"""
    id: int
    name_source: str  # 資料庫中的原始名稱（中文）
    price_small: int
    price_big: Optional[int] = None
    name_ui: str  # 使用者介面顯示名稱（根據語言決定）
    
    @computed_field
    @property
    def display_name(self) -> str:
        """動態計算顯示名稱"""
        return self.name_ui
    
    @computed_field
    @property
    def original_name(self) -> str:
        """保留原始中文名稱"""
        return self.name_source
    
    def get_name_for_language(self, language: str) -> str:
        """根據語言取得對應的名稱"""
        if language.startswith('zh'):
            return self.name_source  # 中文使用者顯示原文
        else:
            return self.name_ui  # 其他語言使用者顯示翻譯

class OrderItemDTO(BaseModel):
    """訂單項目 DTO 模型"""
    menu_item_id: Optional[int] = None
    name: MenuItemName
    quantity: int
    price: int
    subtotal: int
    
    @computed_field
    @property
    def display_name(self) -> str:
        """動態計算顯示名稱"""
        return self.name.original  # 預設顯示原文
    
    def get_name_for_language(self, language: str) -> str:
        """根據語言取得對應的名稱"""
        if language.startswith('zh'):
            return self.name.original
        else:
            return self.name.translated

class OrderSummaryDTO(BaseModel):
    """訂單摘要 DTO 模型"""
    store_name: str
    items: List[OrderItemDTO]
    total_amount: int
    user_language: str
    
    @computed_field
    @property
    def chinese_summary(self) -> str:
        """生成中文摘要（使用原文）"""
        items_text = []
        for item in self.items:
            items_text.append(f"- {item.name.original} x{item.quantity}")
        
        summary = f"店家：{self.store_name}\n"
        summary += "訂購項目：\n"
        summary += "\n".join(items_text)
        summary += f"\n總金額：${self.total_amount}"
        
        return summary
    
    @computed_field
    @property
    def user_language_summary(self) -> str:
        """生成使用者語言摘要（使用 display 欄位）"""
        items_text = []
        for item in self.items:
            # 使用者語言摘要：根據語言選擇 display 名稱
            if self.user_language.startswith('zh'):
                # 中文使用者：使用原始中文名稱
                display_name = item.name.original
            else:
                # 其他語言使用者：使用翻譯名稱
                display_name = item.name.translated
            items_text.append(f"- {display_name} x{item.quantity} (${item.price})")
        
        # 使用者語言摘要：使用 display 店名（需要根據語言翻譯）
        # 這裡的 store_name 應該已經被翻譯過了
        summary = f"Store: {self.store_name}\n"
        summary += "Items:\n"
        summary += "\n".join(items_text)
        summary += f"\nTotal: ${self.total_amount}"
        
        return summary
    
    @computed_field
    @property
    def voice_text(self) -> str:
        """生成語音文字（使用中文原文）"""
        items_text = []
        for item in self.items:
            if item.quantity == 1:
                items_text.append(f"{item.name.original}一份")
            else:
                items_text.append(f"{item.name.original}{item.quantity}份")
        
        return f"老闆，我要{'、'.join(items_text)}，謝謝。"

def build_menu_item_dto(row, user_language: str) -> MenuItemDTO:
    """
    從資料庫查詢結果建立 MenuItemDTO
    
    Args:
        row: 資料庫查詢結果行
        user_language: 使用者語言
    
    Returns:
        MenuItemDTO 物件
    """
    try:
        # 取得原始中文名稱
        name_source = getattr(row, 'name_source', getattr(row, 'item_name', ''))
        
        # 根據使用者語言決定 UI 顯示名稱
        if user_language.startswith('zh'):
            name_ui = name_source  # 中文使用者顯示原文
        else:
            # 其他語言使用者顯示翻譯（如果有的話）
            name_ui = getattr(row, 'translated_name', name_source)
        
        return MenuItemDTO(
            id=getattr(row, 'menu_item_id', getattr(row, 'id', 0)),
            name_source=name_source,
            price_small=getattr(row, 'price_small', 0),
            price_big=getattr(row, 'price_big', None),
            name_ui=name_ui
        )
    except Exception as e:
        logger.error(f"建立 MenuItemDTO 失敗: {e}")
        # 回傳預設值
        return MenuItemDTO(
            id=0,
            name_source="未知項目",
            price_small=0,
            name_ui="未知項目"
        )

def build_order_item_dto(item_data: dict, user_language: str) -> OrderItemDTO:
    """
    從訂單資料建立 OrderItemDTO
    
    Args:
        item_data: 訂單項目資料
        user_language: 使用者語言
    
    Returns:
        OrderItemDTO 物件
    """
    try:
        # 確保有原始名稱和翻譯名稱
        original_name = item_data.get('original_name', item_data.get('name', ''))
        translated_name = item_data.get('translated_name', original_name)
        
        # 如果檢測到欄位顛倒（original 是英文，translated 是中文），交換一次
        if not contains_cjk(original_name) and contains_cjk(translated_name):
            logger.warning("🔄 檢測到欄位顛倒，交換 original 和 translated")
            original_name, translated_name = translated_name, original_name
        
        return OrderItemDTO(
            menu_item_id=item_data.get('menu_item_id'),
            name=MenuItemName(original=original_name, translated=translated_name),
            quantity=item_data.get('quantity', 0),
            price=item_data.get('price', 0),
            subtotal=item_data.get('subtotal', 0)
        )
    except Exception as e:
        logger.error(f"建立 OrderItemDTO 失敗: {e}")
        return OrderItemDTO(
            name=MenuItemName(original="未知項目", translated="Unknown Item"),
            quantity=0,
            price=0,
            subtotal=0
        )

def contains_cjk(text: str) -> bool:
    """
    檢查文字是否包含中日韓字符
    
    Args:
        text: 要檢查的文字
    
    Returns:
        是否包含中日韓字符
    """
    if not text:
        return False
    
    for char in text:
        if '\u4e00' <= char <= '\u9fff':  # 中文
            return True
        if '\u3040' <= char <= '\u309f':  # 平假名
            return True
        if '\u30a0' <= char <= '\u30ff':  # 片假名
            return True
        if '\uac00' <= char <= '\ud7af':  # 韓文
            return True
    
    return False
