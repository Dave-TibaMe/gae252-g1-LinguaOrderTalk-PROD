import os
import json
import requests
from dotenv import load_dotenv

def main():
    """
    一個完整的腳本，用來建立、上傳並設定一個三格按鈕的預設圖文選單。
    """
    # --- 準備工作 ---
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(project_root, '.env'))

    channel_access_token = os.environ.get('CHANNEL_ACCESS_TOKEN')
    if not channel_access_token:
        print("錯誤：請在 .env 檔案中設定 CHANNEL_ACCESS_TOKEN")
        return

    headers = {
        'Authorization': f'Bearer {channel_access_token}',
        'Content-Type': 'application/json'
    }

    # --- 步驟一：【已修改】準備三格按鈕的 JSON 設計圖 ---
    rich_menu_object = {
        # 將尺寸改為 2500x843 以符合單行三按鈕的版面
        "size": {"width": 2500, "height": 843},
        "selected": True,
        # 更新選單名稱
        "name": "Three Button Menu v1",
        "chatBarText": "開啟選單",
        # 重新定義三個按鈕的區域與動作
        "areas": [
            {
                # 按鈕一：我要點餐
                "bounds": {"x": 0, "y": 0, "width": 833, "height": 843},
                "action": {"type": "message", "text": "Order Now"}
            },
            {
                # 按鈕二：點餐記錄
                "bounds": {"x": 833, "y": 0, "width": 834, "height": 843},
                "action": {"type": "message", "text": "Order History"}
            },
            {
                # 按鈕三：語言設定
                "bounds": {"x": 1667, "y": 0, "width": 833, "height": 843},
                "action": {"type": "message", "text": "Change Language"}
            }
        ]
    }

    # --- 後續步驟維持不變 ---
    
    # 步驟二：註冊設計圖
    print("步驟 2/4: 正在建立圖文選單物件...")
    try:
        req = requests.post(
            'https://api.line.me/v2/bot/richmenu',
            headers=headers,
            data=json.dumps(rich_menu_object)
        )
        req.raise_for_status()
        rich_menu_id = req.json()['richMenuId']
        print(f"成功！ 取得 Rich Menu ID: {rich_menu_id}")
    except requests.exceptions.RequestException as e:
        print(f"建立圖文選單失敗: {e.response.text}")
        return

    # 步驟三：上傳圖片
    print("\n步驟 3/4: 正在上傳圖文選單圖片...")
    # 【注意】請確認您的圖片檔名為 'rich_menu_3_buttons.jpg'
    image_path = os.path.join(os.path.dirname(__file__), 'rich_menu_3_buttons.jpg')
    
    if not os.path.exists(image_path):
        print(f"錯誤：找不到圖片檔案於 {image_path}")
        return

    try:
        with open(image_path, 'rb') as f:
            upload_headers = {'Authorization': f'Bearer {channel_access_token}', 'Content-Type': 'image/jpeg'}
            req = requests.post(
                f'https://api-data.line.me/v2/bot/richmenu/{rich_menu_id}/content',
                headers=upload_headers,
                data=f
            )
            req.raise_for_status()
            print("圖片上傳成功！")
    except requests.exceptions.RequestException as e:
        print(f"上傳圖片失敗: {e.response.text}")
        return

    # 步驟四：設定為預設
    print("\n步驟 4/4: 正在將此選單設定為預設...")
    try:
        req = requests.post(
            f'https://api.line.me/v2/bot/user/all/richmenu/{rich_menu_id}',
            headers={'Authorization': f'Bearer {channel_access_token}'}
        )
        req.raise_for_status()
        print("成功將圖文選單設定為預設！")
    except requests.exceptions.RequestException as e:
        print(f"設定預設選單失敗: {e.response.text}")
        return

    print("\n✅ 所有步驟已完成！")


if __name__ == "__main__":
    main()