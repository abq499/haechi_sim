import simpy
import matplotlib.pyplot as plt
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_single_experiment(max_skew, use_logical_ordering, simulation_time=2000):
    env = simpy.Environment()
    num_shards = 3
    beacon = BeaconChain(env, num_shards, use_logical_ordering=use_logical_ordering)
    
    shards = [
        Shard(env, 0, beacon, is_malicious=False),
        Shard(env, 1, beacon, is_malicious=False),
        Shard(env, 2, beacon, is_malicious=True, max_skew=max_skew) 
    ]
    
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    # MỚI: Tính trung bình Latency
    avg_latency = sum(beacon.tx_latencies) / len(beacon.tx_latencies) if beacon.tx_latencies else 0
    
    return fvr, avg_latency

def main():
    skew_levels = [0.1, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    
    baseline_fvr, defense_fvr = [], []
    baseline_lat, defense_lat = [], [] # Mảng lưu Latency
    
    for skew in skew_levels:
        fvr_base, lat_base = run_single_experiment(skew, False)
        baseline_fvr.append(fvr_base)
        baseline_lat.append(lat_base)
        
        fvr_def, lat_def = run_single_experiment(skew, True)
        defense_fvr.append(fvr_def)
        defense_lat.append(lat_def)

    
    
    # ... (phần code trên giữ nguyên) ...

    # XÓA dòng này đi vì chúng ta đã vẽ 2 ảnh rời:
    # fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # --- BIỂU ĐỒ 1: FAIRNESS VIOLATION RATE (FVR) ---
    plt.figure(figsize=(8, 6))
    plt.plot(skew_levels, baseline_fvr, marker='o', color='red', label='Haechi Baseline')
    plt.plot(skew_levels, defense_fvr, marker='s', color='green', label='Proposed Defense')
    
    plt.title('Impact of Clock Skew on Fairness', fontweight='bold', fontsize=14)
    plt.xlabel('Maximum Clock Skew (seconds)', fontsize=12)
    plt.ylabel('Fairness Violation Rate (%)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    
    plt.savefig('fairness_evaluation.png', dpi=300, bbox_inches='tight')
    plt.close() 
    print("Đã lưu biểu đồ FVR thành công: fairness_evaluation.png")


    # --- BIỂU ĐỒ 2: SYSTEM LATENCY ---
    plt.figure(figsize=(8, 6))
    plt.plot(skew_levels, baseline_lat, marker='o', color='red', linestyle='--', label='Haechi Baseline')
    plt.plot(skew_levels, defense_lat, marker='s', color='green', linestyle='--', label='Proposed Defense')
    
    plt.title('System Finalization Latency', fontweight='bold', fontsize=14)
    plt.xlabel('Maximum Clock Skew (seconds)', fontsize=12)
    plt.ylabel('Average Latency (seconds)', fontsize=12)
    
    # FIX: THÊM DÒNG NÀY ĐỂ ÉP TRỤC Y BẮT ĐẦU TỪ 0 (Đến 0.5 giây)
    plt.ylim(0, 0.5) 
    
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    
    plt.savefig('latency_evaluation.png', dpi=300, bbox_inches='tight')
    plt.close() 
    print("Đã lưu biểu đồ Latency thành công: latency_evaluation.png")

if __name__ == "__main__":
    main()