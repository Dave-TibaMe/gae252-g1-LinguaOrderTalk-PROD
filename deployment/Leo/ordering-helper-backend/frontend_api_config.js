/**
 * 前端 API 配置示例
 * 用於解決 Azure Static Web Apps 路由問題
 */

// 配置選項
const API_CONFIG = {
  // 方案1: 使用 Azure Static Web Apps 反向代理 (推薦)
  USE_PROXY: true,
  
  // 方案2: 直接調用 Cloud Run (備選)
  //CLOUD_RUN_URL: 'https://ordering-helper-backend-1095766716155.asia-east1.run.app',
  CLOUD_RUN_URL: '  https://gae252-g1-cloud-run-leo-876094834622.asia-east1.run.app',
  // Azure Static Web Apps 域名
  //SWA_DOMAIN: 'https://green-beach-0f9762500.1.azurestaticapps.net'
  SWA_DOMAIN: 'https://proud-cliff-0c3c37b00.1.azurestaticapps.net'
};

/**
 * 載入動畫管理
 */
const LoadingManager = {
  /**
   * 顯示載入動畫
   */
  showLoading() {
    // 創建載入動畫元素
    const loadingOverlay = document.createElement('div');
    loadingOverlay.id = 'loading-overlay';
    loadingOverlay.style.cssText = `
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      background-color: rgba(0, 0, 0, 0.5);
      display: flex;
      justify-content: center;
      align-items: center;
      z-index: 9999;
    `;
    
    const loadingSpinner = document.createElement('div');
    loadingSpinner.style.cssText = `
      width: 50px;
      height: 50px;
      border: 4px solid #f3f3f3;
      border-top: 4px solid #3498db;
      border-radius: 50%;
      animation: spin 1s linear infinite;
    `;
    
    const loadingText = document.createElement('div');
    loadingText.textContent = '正在送出訂單...';
    loadingText.style.cssText = `
      color: white;
      font-size: 16px;
      margin-top: 20px;
      text-align: center;
    `;
    
    const loadingContainer = document.createElement('div');
    loadingContainer.style.cssText = `
      display: flex;
      flex-direction: column;
      align-items: center;
    `;
    
    // 添加 CSS 動畫
    const style = document.createElement('style');
    style.textContent = `
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
    `;
    
    // 組裝載入動畫
    loadingContainer.appendChild(loadingSpinner);
    loadingContainer.appendChild(loadingText);
    loadingOverlay.appendChild(loadingContainer);
    document.head.appendChild(style);
    document.body.appendChild(loadingOverlay);
    
    console.log('🔄 顯示載入動畫');
  },
  
  /**
   * 隱藏載入動畫
   */
  hideLoading() {
    const loadingOverlay = document.getElementById('loading-overlay');
    if (loadingOverlay) {
      loadingOverlay.remove();
      console.log('✅ 隱藏載入動畫');
    }
  },
  
  /**
   * 顯示成功訊息
   */
  showSuccess(message = '訂單送出成功！') {
    this.hideLoading();
    
    const successOverlay = document.createElement('div');
    successOverlay.id = 'success-overlay';
    successOverlay.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background-color: #4CAF50;
      color: white;
      padding: 20px 30px;
      border-radius: 8px;
      font-size: 16px;
      z-index: 10000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    successOverlay.textContent = message;
    
    document.body.appendChild(successOverlay);
    
    // 3秒後自動隱藏
    setTimeout(() => {
      if (successOverlay.parentNode) {
        successOverlay.remove();
      }
    }, 3000);
    
    console.log('✅ 顯示成功訊息:', message);
  },
  
  /**
   * 顯示錯誤訊息
   */
  showError(message = '訂單送出失敗，請重試') {
    this.hideLoading();
    
    const errorOverlay = document.createElement('div');
    errorOverlay.id = 'error-overlay';
    errorOverlay.style.cssText = `
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background-color: #f44336;
      color: white;
      padding: 20px 30px;
      border-radius: 8px;
      font-size: 16px;
      z-index: 10000;
      box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    `;
    errorOverlay.textContent = message;
    
    document.body.appendChild(errorOverlay);
    
    // 5秒後自動隱藏
    setTimeout(() => {
      if (errorOverlay.parentNode) {
        errorOverlay.remove();
      }
    }, 5000);
    
    console.log('❌ 顯示錯誤訊息:', message);
  }
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
   * 提交訂單（帶載入動畫）
   */
  async submitOrder(orderData, showLoading = true) {
    try {
      if (showLoading) {
        LoadingManager.showLoading();
      }
      
      const result = await apiCall('/api/orders/simple', {
        method: 'POST',
        body: JSON.stringify(orderData)
      });
      
      if (showLoading) {
        LoadingManager.showSuccess('訂單送出成功！');
      }
      
      return result;
    } catch (error) {
      if (showLoading) {
        LoadingManager.showError('訂單送出失敗，請重試');
      }
      throw error;
    }
  },
  
  /**
   * 提交 OCR 訂單（帶載入動畫）
   */
  async submitOcrOrder(orderData, showLoading = true) {
    try {
      if (showLoading) {
        LoadingManager.showLoading();
      }
      
      const result = await apiCall('/api/orders/ocr', {
        method: 'POST',
        body: JSON.stringify(orderData)
      });
      
      if (showLoading) {
        LoadingManager.showSuccess('訂單送出成功！');
      }
      
      return result;
    } catch (error) {
      if (showLoading) {
        LoadingManager.showError('訂單送出失敗，請重試');
      }
      throw error;
    }
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
