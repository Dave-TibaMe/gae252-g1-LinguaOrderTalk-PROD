/**
 * 前端 API 配置示例
 * 用於解決 Azure Static Web Apps 路由問題
 */

// 配置選項
const API_CONFIG = {
  // 方案1: 使用 Azure Static Web Apps 反向代理 (推薦)
  USE_PROXY: true,
  
  // 方案2: 直接調用 Cloud Run (備選)
  // CLOUD_RUN_URL: 'https://ordering-helper-backend-1095766716155.asia-east1.run.app',
  CLOUD_RUN_URL: 'https://gae252-g1-cloud-run-leo-876094834622.asia-east1.run.app',
  
  
  // Azure Static Web Apps 域名
  SWA_DOMAIN: 'https://green-beach-0f9762500.1.azurestaticapps.net'
};

/**
 * 獲取 API 基礎 URL
 */
function getApiBaseUrl() {
  if (API_CONFIG.USE_PROXY) {
    // 使用 Azure Static Web Apps 反向代理
    return API_CONFIG.SWA_DOMAIN;
  } else {
    // 直接調用 Cloud Run
    return API_CONFIG.CLOUD_RUN_URL;
  }
}

/**
 * 通用 API 調用函數
 */
async function apiCall(endpoint, options = {}) {
  const baseUrl = getApiBaseUrl();
  const url = `${baseUrl}${endpoint}`;
  
  // 默認配置
  const defaultOptions = {
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include', // 包含 cookies
  };
  
  // 合併配置
  const finalOptions = {
    ...defaultOptions,
    ...options,
    headers: {
      ...defaultOptions.headers,
      ...options.headers,
    },
  };
  
  try {
    console.log(`🌐 API 調用: ${url}`);
    const response = await fetch(url, finalOptions);
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    const data = await response.json();
    console.log(`✅ API 回應:`, data);
    return data;
  } catch (error) {
    console.error(`❌ API 錯誤:`, error);
    throw error;
  }
}

/**
 * 訂單相關 API
 */
const OrderAPI = {
  /**
   * 提交訂單
   */
  async submitOrder(orderData) {
    return apiCall('/api/orders/simple', {
      method: 'POST',
      body: JSON.stringify(orderData)
    });
  },
  
  /**
   * 提交 OCR 訂單
   */
  async submitOcrOrder(orderData) {
    return apiCall('/api/orders/ocr', {
      method: 'POST',
      body: JSON.stringify(orderData)
    });
  },
  
  /**
   * 獲取訂單歷史
   */
  async getOrderHistory(lineUserId) {
    return apiCall(`/api/orders/history?line_user_id=${lineUserId}`);
  }
};

/**
 * 菜單相關 API
 */
const MenuAPI = {
  /**
   * 上傳菜單圖片進行 OCR
   */
  async uploadMenuImage(formData) {
    const baseUrl = getApiBaseUrl();
    const url = `${baseUrl}/api/upload-menu-image`;
    
    try {
      console.log(`🌐 上傳菜單圖片: ${url}`);
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        credentials: 'include'
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log(`✅ 圖片上傳成功:`, data);
      return data;
    } catch (error) {
      console.error(`❌ 圖片上傳失敗:`, error);
      throw error;
    }
  },
  
  /**
   * 獲取 OCR 菜單
   */
  async getOcrMenu(ocrMenuId, lang = 'en') {
    return apiCall(`/api/menu/ocr/${ocrMenuId}?lang=${lang}`);
  }
};

/**
 * 店家相關 API
 */
const StoreAPI = {
  /**
   * 檢查店家合作狀態
   */
  async checkPartnerStatus(placeId) {
    return apiCall(`/api/stores/check-partner-status?place_id=${placeId}`);
  },
  
  /**
   * 獲取店家菜單
   */
  async getStoreMenu(storeId, lang = 'zh-TW') {
    return apiCall(`/api/menu/${storeId}?lang=${lang}`);
  }
};

/**
 * 使用示例
 */
async function exampleUsage() {
  try {
    // 1. 檢查店家合作狀態
    const partnerStatus = await StoreAPI.checkPartnerStatus('ChIJ0boght2rQjQRsH-_buCo3S4');
    console.log('店家狀態:', partnerStatus);
    
    // 2. 提交訂單
    const orderData = {
      items: [
        {
          name: "蜂蜜茶",
          quantity: 1,
          price: 100
        }
      ],
      line_user_id: "U1234567890abcdef",
      lang: "zh-TW"
    };
    
    const orderResult = await OrderAPI.submitOrder(orderData);
    console.log('訂單結果:', orderResult);
    
  } catch (error) {
    console.error('示例執行失敗:', error);
  }
}

/**
 * LIFF 整合示例
 */
async function liffIntegration() {
  // 確保 LIFF 已初始化
  if (!liff.isLoggedIn()) {
    liff.login();
    return;
  }
  
  try {
    // 獲取用戶資料
    const profile = await liff.getProfile();
    const idToken = liff.getIDToken();
    
    console.log('LIFF 用戶資料:', profile);
    
    // 使用 LIFF 用戶 ID 提交訂單
    const orderData = {
      items: [
        {
          name: "測試商品",
          quantity: 1,
          price: 100
        }
      ],
      line_user_id: profile.userId,
      lang: "zh-TW"
    };
    
    const result = await OrderAPI.submitOrder(orderData);
    console.log('LIFF 訂單結果:', result);
    
  } catch (error) {
    console.error('LIFF 整合失敗:', error);
  }
}

// 導出 API 對象
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    OrderAPI,
    MenuAPI,
    StoreAPI,
    apiCall,
    getApiBaseUrl,
    exampleUsage,
    liffIntegration
  };
} else {
  // 瀏覽器環境
  window.OrderAPI = OrderAPI;
  window.MenuAPI = MenuAPI;
  window.StoreAPI = StoreAPI;
  window.apiCall = apiCall;
  window.getApiBaseUrl = getApiBaseUrl;
  window.exampleUsage = exampleUsage;
  window.liffIntegration = liffIntegration;
}
