# experiments_jitter.py
import simpy
import matplotlib.pyplot as plt
import numpy as np
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_jitter_experiment(jitter_type, num_shards=10, simulation_time=2000):
    env = simpy.Environment()
    # Ở đây ta mặc định test DLO (True) vì đã biết Haechi thất bại
    beacon = BeaconChain(env, num_shards, use_logical_ordering=True)
    
    shards = []
    for i in range(num_shards):
        # Có 1 Attacker để đảm bảo FVR luôn bị thử thách
        is_mal = (i == 0)
        shards.append(Shard(env, i, beacon, is_malicious=is_mal, max_skew=1.0, block_cycle=2.0, jitter_type=jitter_type))
        
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    return fvr, beacon.tx_latencies

def main():
    print("Bắt đầu kịch bản Độ nhiễu mạng đuôi dài (Long-tail Jitter)...")
    jitter_types = ['uniform', 'lognormal', 'pareto']
    colors = {'uniform': 'blue', 'lognormal': 'orange', 'pareto': 'red'}
    
    plt.figure(figsize=(8, 6))
    
    for jtype in jitter_types:
        print(f"Đang chạy mô phỏng với mạng: {jtype.upper()}...")
        fvr, latencies = run_jitter_experiment(jtype)
        print(f" -> FVR ({jtype}): {fvr:.2f}% (Kỳ vọng 0.0%)")
        
        if latencies:
            # Tính toán phân phối CDF
            sorted_latencies = np.sort(latencies)
            p = 1. * np.arange(len(sorted_latencies)) / (len(sorted_latencies) - 1)
            
            # Tính p99 (99% giao dịch hoàn thành trước độ trễ này)
            p99_val = np.percentile(sorted_latencies, 99)
            
            plt.plot(sorted_latencies, p, label=f'{jtype.capitalize()} (p99={p99_val:.2f}s)', color=colors[jtype], linewidth=2)

    plt.title('Latency CDF under Long-tail Network Jitter', fontweight='bold', fontsize=14)
    plt.xlabel('Finalization Latency (seconds)', fontsize=12)
    plt.ylabel('Cumulative Probability (CDF)', fontsize=12)
    
    # Giới hạn trục X từ 0 đến 1 giây để nhìn rõ đường cong đuôi dài
    plt.xlim(0, 1.0)
    plt.ylim(0, 1.05)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(fontsize=11)
    
    plt.savefig('latency_cdf_jitter.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("\nĐã lưu biểu đồ: latency_cdf_jitter.png")

if __name__ == "__main__":
    main()