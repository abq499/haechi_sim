# experiments_baselines.py
import simpy
import matplotlib.pyplot as plt
import numpy as np
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_engine_experiment(engine, num_shards, simulation_time=500):
    env = simpy.Environment()
    beacon = BeaconChain(env, num_shards, engine_type=engine)
    
    shards = []
    for i in range(num_shards):
        # SỬA Ở ĐÂY: Cho Shard cuối cùng (29) làm Hacker để nó chen hàng lên đầu
        is_mal = (i == num_shards - 1) 
        shards.append(Shard(env, i, beacon, is_malicious=is_mal, max_skew=1.0))
        
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    avg_lat = sum(beacon.tx_latencies) / len(beacon.tx_latencies) if beacon.tx_latencies else 0
    return fvr, avg_lat

def main():
    print("Bắt đầu cuộc đua Baseline Sweep (So sánh 6 thuật toán)...")
    engines = ['haechi', 'dlo', 'aequitas', 'themis', 'wendy', 'pompe']
    colors = ['red', 'green', 'blue', 'orange', 'purple', 'brown']
    
    # Test trên cấu hình 30 Shards để thấy rõ sự khác biệt O(n)
    num_shards = 30 
    
    fvrs = []
    latencies = []
    
    for eng in engines:
        print(f"Đang chạy mô phỏng thuật toán: {eng.upper()}...")
        fvr, lat = run_engine_experiment(eng, num_shards=num_shards)
        fvrs.append(fvr)
        latencies.append(lat)
        print(f" -> FVR: {fvr:.2f}% | Latency: {lat:.3f}s")

    # --- VẼ BIỂU ĐỒ BAR CHART SO SÁNH ---
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
    
    # Biểu đồ 1: FVR (Ai an toàn hơn?)
    bars1 = ax1.bar(engines, fvrs, color=colors, alpha=0.8)
    ax1.set_title('Security: Fairness Violation Rate (FVR)', fontweight='bold')
    ax1.set_ylabel('FVR (%)')
    ax1.set_ylim(0, max(fvrs) * 1.2 if max(fvrs) > 0 else 1.0)
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2, yval + 0.005, f'{yval:.2f}%', ha='center', va='bottom', fontweight='bold')

    # Biểu đồ 2: Latency (Ai nhanh hơn?)
    bars2 = ax2.bar(engines, latencies, color=colors, alpha=0.8)
    ax2.set_title(f'Performance: Finalization Latency ({num_shards} Shards)', fontweight='bold')
    ax2.set_ylabel('Average Latency (seconds)')
    for bar in bars2:
        yval = bar.get_height()
        ax2.text(bar.get_x() + bar.get_width()/2, yval + 0.05, f'{yval:.2f}s', ha='center', va='bottom', fontweight='bold')

    # Làm đẹp
    for ax in [ax1, ax2]:
        # THÊM DÒNG NÀY ĐỂ FIX WARNING
        ax.set_xticks(range(len(engines))) 
        ax.set_xticklabels([e.upper() for e in engines], rotation=45, ha='right')
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
    plt.tight_layout()
    plt.savefig('baselines_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("\nĐã lưu biểu đồ: baselines_comparison.png")

if __name__ == "__main__":
    main()