# experiments_het.py
import simpy
import matplotlib.pyplot as plt
import numpy as np
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_het_experiment(num_shards, slow_frac, slow_mult, use_logical_ordering, simulation_time=1000):
    env = simpy.Environment()
    beacon = BeaconChain(env, num_shards, use_logical_ordering=use_logical_ordering)
    
    shards = []
    num_slow_shards = int(num_shards * slow_frac)
    
    for i in range(num_shards):
        # Shard 0 luôn là attacker
        is_mal = (i == 0)
        
        # ĐỔI LẠI: Cho các Shard ở CUỐI danh sách làm Shard chậm
        if i >= (num_shards - num_slow_shards):
            cycle = 2.0 * slow_mult
        else:
            cycle = 2.0
            
        shards.append(Shard(env, i, beacon, is_malicious=is_mal, max_skew=1.0, block_cycle=cycle))
        
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    avg_latency = sum(beacon.tx_latencies) / len(beacon.tx_latencies) if beacon.tx_latencies else 0
    
    return fvr, avg_latency

def main():
    print("Bắt đầu chạy kịch bản Mạng Bất Đồng Nhất (Heterogeneous Shards)...")
    num_shards = 10
    slow_frac = 0.2 # 20% số nút bị chậm (2 Shards)
    slow_multipliers = [1, 2, 5, 10] # Chậm gấp 1 lần (bình thường), 2 lần, 5 lần, 10 lần
    
    dlo_latencies = []
    dlo_fvrs = []
    
    for mult in slow_multipliers:
        print(f"Đang mô phỏng với 20% Shards chạy chậm gấp {mult} lần...")
        fvr_def, lat_def = run_het_experiment(num_shards, slow_frac, mult, True)
        dlo_latencies.append(lat_def)
        dlo_fvrs.append(fvr_def)
        
    # In kết quả FVR ra terminal để chứng minh an toàn tuyệt đối
    print(f"\nKết quả FVR của DLO qua các mức độ chậm: {dlo_fvrs} (Kỳ vọng toàn 0.0%)")

    # --- VẼ BIỂU ĐỒ SỰ XUỐNG CẤP ĐỘ TRỄ (LATENCY DEGRADATION) ---
    plt.figure(figsize=(8, 6))
    plt.plot(slow_multipliers, dlo_latencies, marker='s', color='green', linestyle='-', label='DLO (Proposed) Latency')
    
    plt.title('Latency Degradation under Heterogeneous Load (20% Slow Shards)', fontweight='bold', fontsize=14)
    plt.xlabel('Slow Shard Block Cycle Multiplier (x times slower)', fontsize=12)
    plt.ylabel('Average Finalization Latency (seconds)', fontsize=12)
    plt.xticks(slow_multipliers, [f"{m}x" for m in slow_multipliers])
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    
    plt.savefig('latency_heterogeneous.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("Đã lưu biểu đồ: latency_heterogeneous.png")

if __name__ == "__main__":
    main()