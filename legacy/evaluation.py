# evaluation.py
def calculate_fvr(execution_order):
    violation_count = 0
    total_pairs = 0
    
    for i in range(len(execution_order)):
        for j in range(i + 1, len(execution_order)):
            # Lấy Height của 2 giao dịch để so sánh
            h_i = int(execution_order[i].tx_id.split('-')[1])
            h_j = int(execution_order[j].tx_id.split('-')[1])
            
            # CHỈ SO SÁNH CÁC GIAO DỊCH CÙNG HEIGHT
            # Vì nếu khác Height, việc cái này đợi cái kia là do thiết kế rào chắn đồng bộ (CAP Trade-off)
            if h_i == h_j:
                total_pairs += 1
                if execution_order[i].processing_time > execution_order[j].processing_time:
                    violation_count += 1
                    
    if total_pairs == 0:
        return 0.0
    return (violation_count / total_pairs) * 100