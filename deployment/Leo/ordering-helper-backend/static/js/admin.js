// 後台管理系統 JavaScript

$(document).ready(function() {
    // 初始化工具提示
    $('[data-toggle="tooltip"]').tooltip();
    
    // 初始化彈出視窗
    $('[data-toggle="popover"]').popover();
    
    // 自動隱藏警告訊息
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
    
    // 表格排序功能
    $('.sortable').click(function() {
        var table = $(this).parents('table').eq(0);
        var rows = table.find('tr:gt(0)').toArray().sort(comparer($(this).index()));
        this.asc = !this.asc;
        if (!this.asc) {
            rows = rows.reverse();
        }
        for (var i = 0; i < rows.length; i++) {
            table.append(rows[i]);
        }
    });
    
    // 搜尋功能
    $('#searchInput').on('keyup', function() {
        var value = $(this).val().toLowerCase();
        $('#dataTable tr').filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
        });
    });
    
    // AJAX 表單提交
    $('.ajax-form').submit(function(e) {
        e.preventDefault();
        var form = $(this);
        var url = form.attr('action');
        var method = form.attr('method');
        var data = form.serialize();
        
        $.ajax({
            url: url,
            method: method,
            data: data,
            beforeSend: function() {
                form.find('button[type="submit"]').prop('disabled', true).html('<span class="loading"></span> 處理中...');
            },
            success: function(response) {
                showAlert('success', response.message || '操作成功！');
                if (response.redirect) {
                    setTimeout(function() {
                        window.location.href = response.redirect;
                    }, 1000);
                }
            },
            error: function(xhr) {
                var message = '操作失敗！';
                if (xhr.responseJSON && xhr.responseJSON.error) {
                    message = xhr.responseJSON.error;
                }
                showAlert('danger', message);
            },
            complete: function() {
                form.find('button[type="submit"]').prop('disabled', false).html('提交');
            }
        });
    });
    
    // 確認對話框
    $('.confirm-delete').click(function(e) {
        e.preventDefault();
        var url = $(this).attr('href');
        var itemName = $(this).data('item-name') || '此項目';
        
        if (confirm('確定要刪除 ' + itemName + ' 嗎？此操作無法復原。')) {
            window.location.href = url;
        }
    });
    
    // 即時統計更新
    updateStats();
    setInterval(updateStats, 300000); // 每5分鐘更新一次
});

// 顯示警告訊息
function showAlert(type, message) {
    var alertHtml = `
        <div class="alert alert-${type} alert-dismissible fade show" role="alert">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    $('.container-fluid').prepend(alertHtml);
    
    // 自動隱藏
    setTimeout(function() {
        $('.alert').fadeOut('slow');
    }, 5000);
}

// 更新統計資料
function updateStats() {
    $.ajax({
        url: '/admin/api/stats',
        method: 'GET',
        success: function(data) {
            $('#totalStores').text(data.total_stores || 0);
            $('#totalUsers').text(data.total_users || 0);
            $('#totalOrders').text(data.total_orders || 0);
            $('#todayOrders').text(data.today_orders || 0);
        },
        error: function() {
            console.log('無法更新統計資料');
        }
    });
}

// 表格排序比較器
function comparer(index) {
    return function(a, b) {
        var valA = getCellValue(a, index), valB = getCellValue(b, index);
        return $.isNumeric(valA) && $.isNumeric(valB) ? valA - valB : valA.localeCompare(valB);
    };
}

// 取得表格儲存格值
function getCellValue(row, index) {
    return $(row).children('td').eq(index).text();
}

// 匯出資料
function exportData(format) {
    var table = $('#dataTable');
    var data = [];
    
    // 取得表格標題
    var headers = [];
    table.find('thead th').each(function() {
        headers.push($(this).text());
    });
    data.push(headers);
    
    // 取得表格資料
    table.find('tbody tr').each(function() {
        var row = [];
        $(this).find('td').each(function() {
            row.push($(this).text());
        });
        data.push(row);
    });
    
    if (format === 'csv') {
        downloadCSV(data);
    } else if (format === 'excel') {
        downloadExcel(data);
    }
}

// 下載 CSV
function downloadCSV(data) {
    var csvContent = "data:text/csv;charset=utf-8,";
    data.forEach(function(rowArray) {
        var row = rowArray.join(",");
        csvContent += row + "\r\n";
    });
    
    var encodedUri = encodeURI(csvContent);
    var link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", "data.csv");
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

// 下載 Excel（簡化版）
function downloadExcel(data) {
    // 這裡可以整合 SheetJS 或其他 Excel 生成庫
    alert('Excel 匯出功能需要額外的程式庫支援');
}

// 圖表初始化
function initCharts() {
    // 這裡可以整合 Chart.js 或其他圖表庫
    console.log('圖表功能待實作');
}

// 檔案上傳預覽
function previewFile(input) {
    if (input.files && input.files[0]) {
        var reader = new FileReader();
        reader.onload = function(e) {
            $('#filePreview').attr('src', e.target.result).show();
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// 即時驗證
function validateForm(form) {
    var isValid = true;
    var requiredFields = form.find('[required]');
    
    requiredFields.each(function() {
        if (!$(this).val()) {
            $(this).addClass('is-invalid');
            isValid = false;
        } else {
            $(this).removeClass('is-invalid');
        }
    });
    
    return isValid;
}

// 載入動畫
function showLoading(element) {
    element.html('<div class="loading"></div>');
}

function hideLoading(element, originalContent) {
    element.html(originalContent);
}

// 全域錯誤處理
window.onerror = function(msg, url, lineNo, columnNo, error) {
    console.error('JavaScript 錯誤:', {
        message: msg,
        url: url,
        lineNo: lineNo,
        columnNo: columnNo,
        error: error
    });
    
    showAlert('danger', '發生錯誤，請重新整理頁面或聯繫管理員。');
    return false;
}; 