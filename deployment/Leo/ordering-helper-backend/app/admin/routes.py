# =============================================================================
# 檔案名稱：app/admin/routes.py
# 功能描述：後台管理系統的路由和介面設定
# 主要職責：
# - 提供管理員儀表板
# - 管理店家資訊
# - 管理菜單內容
# - 查看訂單記錄
# - 生成統計報表
# 支援功能：
# - 圖形化管理介面
# - 資料 CRUD 操作
# - 權限管理
# - 統計圖表
# =============================================================================

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from ..models import db, Store, Menu, MenuItem, MenuTranslation, User, Order, StoreTranslation, Language
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.form import SecureForm

admin_bp = Blueprint('admin', __name__)

# 後台管理介面設定
class SecureModelView(ModelView):
    form_base_class = SecureForm
    
    def is_accessible(self):
        # TODO: 實作權限檢查
        return True
    
    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.login'))

class StoreView(SecureModelView):
    column_list = ['store_id', 'store_name', 'partner_level', 'address', 'created_at']
    column_searchable_list = ['store_name', 'address']
    column_filters = ['partner_level', 'created_at']
    form_excluded_columns = ['menus', 'orders']

class MenuView(SecureModelView):
    column_list = ['menu_id', 'store.store_name', 'version', 'created_at']
    column_searchable_list = ['store.store_name']
    column_filters = ['created_at']

class UserView(SecureModelView):
    column_list = ['user_id', 'line_user_id', 'preferred_lang', 'created_at']
    column_searchable_list = ['line_user_id']
    column_filters = ['preferred_lang', 'created_at']

class OrderView(SecureModelView):
    column_list = ['order_id', 'user.line_user_id', 'store.store_name', 'total_amount', 'status', 'order_time']
    column_searchable_list = ['user.line_user_id', 'store.store_name']
    column_filters = ['status', 'order_time']

# 自定義管理頁面
@admin_bp.route('/dashboard')
def dashboard():
    """管理儀表板"""
    stats = {
        'total_stores': Store.query.count(),
        'total_users': User.query.count(),
        'total_orders': Order.query.count(),
        'recent_orders': Order.query.order_by(Order.order_time.desc()).limit(5).all()
    }
    return render_template('admin/dashboard.html', stats=stats)

@admin_bp.route('/stores')
def stores():
    """店家管理"""
    stores = Store.query.all()
    return render_template('admin/stores.html', stores=stores)

@admin_bp.route('/stores/<int:store_id>/menus')
def store_menus(store_id):
    """店家菜單管理"""
    store = Store.query.get_or_404(store_id)
    menus = Menu.query.filter_by(store_id=store_id).all()
    return render_template('admin/store_menus.html', store=store, menus=menus)

@admin_bp.route('/orders')
def orders():
    """訂單管理"""
    orders = Order.query.order_by(Order.order_time.desc()).all()
    return render_template('admin/orders.html', orders=orders)

@admin_bp.route('/reports')
def reports():
    """報表查詢"""
    # TODO: 實作報表功能
    return render_template('admin/reports.html')

# API 端點
@admin_bp.route('/api/stores', methods=['GET'])
def api_stores():
    """取得店家列表 API"""
    stores = Store.query.all()
    return jsonify([{
        'store_id': store.store_id,
        'store_name': store.store_name,
        'partner_level': store.partner_level,
        'address': store.address
    } for store in stores])

@admin_bp.route('/api/stores', methods=['POST'])
def api_create_store():
    """建立店家 API"""
    data = request.get_json()
    
    new_store = Store(
        store_name=data['store_name'],
        partner_level=data.get('partner_level', 0),
        latitude=data.get('latitude'),
        longitude=data.get('longitude'),
        address=data.get('address'),
        description=data.get('description')
    )
    
    db.session.add(new_store)
    db.session.commit()
    
    return jsonify({'message': '店家建立成功', 'store_id': new_store.store_id}), 201

@admin_bp.route('/api/orders/stats', methods=['GET'])
def api_order_stats():
    """訂單統計 API"""
    # TODO: 實作訂單統計
    stats = {
        'total_orders': Order.query.count(),
        'total_revenue': sum(order.total_amount for order in Order.query.all()),
        'recent_orders': Order.query.order_by(Order.order_time.desc()).limit(10).count()
    }
    return jsonify(stats) 