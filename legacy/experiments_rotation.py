# experiments_rotation.py
import simpy
import matplotlib.pyplot as plt
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_rotation_experiment(rotate_shard_id, num_shards=10, simulation_time=1000, epoch_len=100):
    env = simpy.Environment()
    beacon = BeaconChain(env, num_shards, engine_type='dlo', rotate_shard_id=rotate_shard_id, epoch_len=epoch_len)
    
    shards = []
    for i in range(num_shards):
        # Không cần attacker vì đang test tính công bằng phân bổ quyền lực
        shards.append(Shard(env, i, beacon, is_malicious=False))
        
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    # Tỷ lệ Shard 0 giành được quyền ưu tiên số 1 (Tie-breaker Win Rate)
    total_heights = beacon.current_height - 1
    win_rate = (beacon.shard_0_win_count / total_heights) * 100 if total_heights > 0 else 0
    
    return fvr, win_rate

def main():
    print("Bắt đầu thực nghiệm: Xoay vòng Shard_ID chống kiểm duyệt (Censorship Resistance)...")
    
    # Kịch bản 1: Static (Bài báo gốc)
    fvr_static, win_static = run_rotation_experiment(rotate_shard_id=False)
    print(f"[Static DLO]  FVR: {fvr_static:.2f}% | Shard 0 Priority Win Rate: {win_static:.2f}%")
    
    # Kịch bản 2: Rotated (Đề xuất thêm)
    fvr_rotated, win_rotated = run_rotation_experiment(rotate_shard_id=True)
    print(f"[Rotated DLO] FVR: {fvr_rotated:.2f}% | Shard 0 Priority Win Rate: {win_rotated:.2f}%")

    # --- VẼ BIỂU ĐỒ BAR SO SÁNH ---
    labels = ['Static Shard_ID', 'Rotated Shard_ID']
    win_rates = [win_static, win_rotated]
    
    plt.figure(figsize=(7, 6))
    bars = plt.bar(labels, win_rates, color=['red', 'green'], alpha=0.8, width=0.5)
    
    plt.title('Censorship Resistance: Shard 0 Priority Domination', fontweight='bold', fontsize=14)
    plt.ylabel('Priority Win Rate (%)', fontsize=12)
    plt.ylim(0, 110)
    
    # Thêm đường kỳ vọng lý tưởng (Phân bổ đều 10 Shard -> 10%)
    plt.axhline(y=10, color='blue', linestyle='--', linewidth=2, label='Ideal Fair Share (10%)')
    plt.legend()
    
    for bar in bars:
        yval = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2, yval + 2, f"{yval:.1f}%", ha='center', fontweight='bold', fontsize=12)
        
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.savefig('rotation_censorship.png', dpi=300, bbox_inches='tight')
    print("\nĐã lưu biểu đồ: rotation_censorship.png")

if __name__ == "__main__":
    main()