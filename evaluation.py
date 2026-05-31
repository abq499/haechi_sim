# evaluation.py

def calculate_fvr(execution_order):
    violation_count = 0
    total_pairs = 0
    
    # Kiểm tra từng cặp giao dịch xem thứ tự thực thi có trái với thứ tự xử lý thực tế không
    for i in range(len(execution_order)):
        for j in range(i + 1, len(execution_order)):
            total_pairs += 1
            # Nếu TX_i thực thi trước nhưng thực tế lại sinh ra sau TX_j -> Violation!
            if execution_order[i].processing_time > execution_order[j].processing_time:
                violation_count += 1
                
    # Trả về con số FVR để các file khác (như file vẽ biểu đồ) có thể lấy dữ liệu
    if total_pairs == 0:
        return 0.0
    return (violation_count / total_pairs) * 100