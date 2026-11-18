# experiments_scalability.py
import simpy
import matplotlib.pyplot as plt
from simulation import Shard, BeaconChain

def run_scalability_experiment(num_shards, use_logical_ordering, simulation_time=1000):
    env = simpy.Environment()
    beacon = BeaconChain(env, num_shards, use_logical_ordering=use_logical_ordering)
    
    # Khởi tạo danh sách Shards động dựa trên tham số num_shards
    shards = []
    for i in range(num_shards):
        # Không cần attacker ở kịch bản đo hiệu năng này
        shards.append(Shard(env, i, beacon, is_malicious=False))
        
    env.run(until=simulation_time)
    
    # 1. Tính Latency Trung bình
    avg_latency = sum(beacon.tx_latencies) / len(beacon.tx_latencies) if beacon.tx_latencies else 0
    
    # 2. Tính Throughput (TPS) = Tổng số TX / Tổng thời gian chạy
    total_tx = len(beacon.global_execution_order)
    tps = total_tx / simulation_time
    
    return tps, avg_latency

def main():
    print("Bắt đầu chạy kịch bản Đánh giá Khả năng mở rộng (Scalability)...")
    
    # Thay đổi số lượng Shard từ 3 đến 30
    shard_counts = [3, 5, 10, 15, 20, 25, 30]
    
    baseline_tps, defense_tps = [], []
    baseline_lat, defense_lat = [], []
    
    for count in shard_counts:
        print(f"Đang mô phỏng hệ thống với {count} Shards...")
        
        # Chạy Haechi Baseline
        tps_base, lat_base = run_scalability_experiment(count, False)
        baseline_tps.append(tps_base)
        baseline_lat.append(lat_base)
        
        # Chạy Proposed Defense
        tps_def, lat_def = run_scalability_experiment(count, True)
        defense_tps.append(tps_def)
        defense_lat.append(lat_def)

    # --- VẼ BIỂU ĐỒ 1: THROUGHPUT (TPS) ---
    plt.figure(figsize=(8, 6))
    plt.plot(shard_counts, baseline_tps, marker='o', color='red', label='Haechi Baseline')
    plt.plot(shard_counts, defense_tps, marker='s', color='green', label='Proposed Defense')
    
    plt.title('System Throughput vs Number of Shards', fontweight='bold', fontsize=14)
    plt.xlabel('Number of Shards', fontsize=12)
    plt.ylabel('Throughput (Transactions Per Second - TPS)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    
    plt.savefig('tps_scalability.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Đã lưu biểu đồ TPS: tps_scalability.png")

    # --- VẼ BIỂU ĐỒ 2: LATENCY VS SHARDS ---
    plt.figure(figsize=(8, 6))
    plt.plot(shard_counts, baseline_lat, marker='o', color='red', linestyle='--', label='Haechi Baseline')
    plt.plot(shard_counts, defense_lat, marker='s', color='green', linestyle='--', label='Proposed Defense')
    
    plt.title('System Latency vs Number of Shards', fontweight='bold', fontsize=14)
    plt.xlabel('Number of Shards', fontsize=12)
    plt.ylabel('Average Latency (seconds)', fontsize=12)
    plt.ylim(0, max(max(baseline_lat), max(defense_lat)) * 1.5) # Dynamic Y limit
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    
    plt.savefig('latency_scalability.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Đã lưu biểu đồ Latency Scalability: latency_scalability.png")

if __name__ == "__main__":
    main()