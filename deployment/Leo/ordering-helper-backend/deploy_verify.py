#!/usr/bin/env python3
"""
Cloud Run 部署驗證腳本
檢查應用程式是否正確配置以在 Cloud Run 上運行
"""

import os
import sys
import importlib.util

def check_file_exists(filepath, description):
    """檢查檔案是否存在"""
    if os.path.exists(filepath):
        print(f"✓ {description}: {filepath}")
        return True
    else:
        print(f"✗ {description}: {filepath} (不存在)")
        return False

def check_import(module_name, description):
    """檢查模組是否可以導入"""
    try:
        importlib.import_module(module_name)
        print(f"✓ {description}: {module_name}")
        return True
    except ImportError as e:
        print(f"✗ {description}: {module_name} (導入失敗: {e})")
        return False

def check_environment_variables():
    """檢查環境變數配置"""
    print("\n=== 環境變數檢查 ===")
    
    required_vars = [
        'DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_DATABASE',
        'LINE_CHANNEL_ACCESS_TOKEN', 'LINE_CHANNEL_SECRET'
    ]
    
    optional_vars = ['PORT', 'GOOGLE_APPLICATION_CREDENTIALS']
    
    all_good = True
    
    for var in required_vars:
        if os.getenv(var):
            print(f"✓ {var}: 已設定")
        else:
            print(f"⚠️ {var}: 未設定 (部署時需要)")
            all_good = False
    
    for var in optional_vars:
        if os.getenv(var):
            print(f"✓ {var}: {os.getenv(var)}")
        else:
            print(f"ℹ️ {var}: 未設定 (可選)")
    
    return all_good

def check_flask_app():
    """檢查 Flask 應用程式配置"""
    print("\n=== Flask 應用程式檢查 ===")
    
    try:
        # 設定測試環境變數
        os.environ['PORT'] = '8080'
        
        # 導入應用程式
        from run import app
        
        print("✓ Flask 應用程式導入成功")
        
        # 檢查端口配置
        port = app.config.get('PORT', 8080)
        print(f"✓ 應用程式端口配置: {port}")
        
        # 檢查路由
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append(f"{', '.join(rule.methods)} {rule.rule}")
        
        print(f"✓ 註冊的路由數量: {len(routes)}")
        
        # 檢查關鍵路由
        key_routes = ['/', '/health', '/api/test', '/webhook/line']
        for route in key_routes:
            if any(route in r for r in routes):
                print(f"✓ 關鍵路由存在: {route}")
            else:
                print(f"⚠️ 關鍵路由缺失: {route}")
        
        return True
        
    except Exception as e:
        print(f"✗ Flask 應用程式檢查失敗: {e}")
        return False

def check_dockerfile():
    """檢查 Dockerfile 配置"""
    print("\n=== Dockerfile 檢查 ===")
    
    if not check_file_exists('Dockerfile', 'Dockerfile'):
        return False
    
    with open('Dockerfile', 'r') as f:
        content = f.read()
    
    checks = [
        ('EXPOSE 8080', '端口暴露'),
        ('CMD ["./startup_simple.sh"]', '啟動命令'),
        ('ENV PORT=8080', '環境變數設定'),
        ('gunicorn', 'Gunicorn 安裝')
    ]
    
    all_good = True
    for check, description in checks:
        if check in content:
            print(f"✓ {description}: 已配置")
        else:
            print(f"⚠️ {description}: 未配置")
            all_good = False
    
    return all_good

def check_startup_script():
    """檢查啟動腳本"""
    print("\n=== 啟動腳本檢查 ===")
    
    if not check_file_exists('startup_simple.sh', '啟動腳本'):
        return False
    
    with open('startup_simple.sh', 'r') as f:
        content = f.read()
    
    checks = [
        ('--bind "0.0.0.0:$PORT"', '端口綁定'),
        ('gunicorn', 'Gunicorn 使用'),
        ('run:app', '應用程式入口點')
    ]
    
    all_good = True
    for check, description in checks:
        if check in content:
            print(f"✓ {description}: 已配置")
        else:
            print(f"⚠️ {description}: 未配置")
            all_good = False
    
    return all_good

def main():
    """主檢查函數"""
    print("=== Cloud Run 部署驗證 ===")
    
    # 檢查必要檔案
    print("\n=== 檔案檢查 ===")
    files_to_check = [
        ('run.py', 'Flask 應用程式入口點'),
        ('app/__init__.py', 'Flask 應用程式初始化'),
        ('requirements.txt', 'Python 依賴'),
        ('startup_simple.sh', '啟動腳本'),
        ('Dockerfile', 'Docker 配置')
    ]
    
    for filepath, description in files_to_check:
        check_file_exists(filepath, description)
    
    # 檢查 Python 依賴
    print("\n=== Python 依賴檢查 ===")
    dependencies = [
        ('flask', 'Flask 框架'),
        ('gunicorn', 'Gunicorn WSGI 伺服器'),
        ('flask_cors', 'CORS 支援'),
        ('flask_sqlalchemy', 'SQLAlchemy 整合'),
        ('pymysql', 'MySQL 驅動程式')
    ]
    
    for module, description in dependencies:
        check_import(module, description)
    
    # 執行各項檢查
    env_ok = check_environment_variables()
    flask_ok = check_flask_app()
    docker_ok = check_dockerfile()
    startup_ok = check_startup_script()
    
    # 總結
    print("\n=== 檢查總結 ===")
    if all([flask_ok, docker_ok, startup_ok]):
        print("✓ 應用程式配置正確，可以部署到 Cloud Run")
        if env_ok:
            print("✓ 環境變數配置完整")
        else:
            print("⚠️ 環境變數需要在 Cloud Run 中設定")
        return True
    else:
        print("✗ 應用程式配置有問題，需要修復後再部署")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
