# experiments_collusion.py
import simpy
import matplotlib.pyplot as plt
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_collusion_experiment(num_shards, num_attackers, simulation_time=500):
    env = simpy.Environment()
    # Chạy thuật toán DLO
    beacon = BeaconChain(env, num_shards, engine_type='dlo')
    
    shards = []
    for i in range(num_shards):
        # Cấp quyền Hacker cho 'num_attackers' Shard đầu tiên
        # Các hacker này sẽ cùng nhau lùi block_ts cực mạnh (max_skew = 2.0s)
        is_mal = (i < num_attackers)
        shards.append(Shard(env, i, beacon, is_malicious=is_mal, max_skew=2.0))
        
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    return fvr

def main():
    print("Bắt đầu thử thách: Đa Hacker Thông đồng (Multi-malicious Collusion)...")
    num_shards = 10
    attacker_counts = [1, 2, 3] # Thử nghiệm 10%, 20%, 30% mạng lưới bị hack
    
    fvrs = []
    for count in attacker_counts:
        print(f"Đang mô phỏng với {count} Shards độc hại (Hackers) cùng lúc...")
        fvr = run_collusion_experiment(num_shards, count)
        fvrs.append(fvr)
        print(f" -> FVR: {fvr:.2f}% (Kỳ vọng: 0.00%)")

    # --- VẼ BIỂU ĐỒ BAR SO SÁNH ---
    plt.figure(figsize=(7, 5))
    bars = plt.bar([f"{c} Attackers" for c in attacker_counts], fvrs, color='red', alpha=0.7, edgecolor='darkred', linewidth=1.5)
    
    plt.title('DLO Security under Multi-Shard Collusion (10 Shards)', fontweight='bold', fontsize=14)
    plt.ylabel('Fairness Violation Rate (FVR %)', fontsize=12)
    
    # Đặt giới hạn trục Y là 1.0% để thấy sự an toàn tuyệt đối (Cột trống trơn)
    plt.ylim(0, 1.0) 
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 0.02, f"{yval:.2f}%", ha='center', fontweight='bold', fontsize=12)
        
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    
    plt.savefig('collusion_security.png', dpi=300, bbox_inches='tight')
    print("\nĐã lưu biểu đồ: collusion_security.png")

if __name__ == "__main__":
    main()