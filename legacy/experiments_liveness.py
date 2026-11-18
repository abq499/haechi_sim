# experiments_liveness.py
import simpy
import matplotlib.pyplot as plt
from simulation import Shard, BeaconChain
from evaluation import calculate_fvr

def run_liveness_experiment(tau_max, num_shards=5, simulation_time=100):
    env = simpy.Environment()
    # Khởi tạo BeaconChain với Timeout bảo vệ
    beacon = BeaconChain(env, num_shards, use_logical_ordering=True, tau_max=tau_max)
    
    shards = []
    for i in range(num_shards):
        is_mal = (i == 0)
        # Shard cuối cùng bị "rút điện" ở giây thứ 30
        halt_time = 30 if i == (num_shards - 1) else None
        
        shards.append(Shard(env, i, beacon, is_malicious=is_mal, max_skew=1.0, halt_at=halt_time))
        
    env.run(until=simulation_time)
    
    fvr = calculate_fvr(beacon.global_execution_order)
    # Trả về Tổng số giao dịch xử lý được (Tính khả dụng - Availability)
    total_txs = len(beacon.global_execution_order)
    return fvr, total_txs

def main():
    print("Bắt đầu kịch bản Sự cố Đứt mạng (Liveness Failure) & Khắc phục...")
    timeouts = [0.5, 1.0, 2.0, 5.0]
    processed_txs = []
    
    for tau in timeouts:
        print(f"Đang chạy mô phỏng với mức Timeout = {tau}s...")
        fvr, total_tx = run_liveness_experiment(tau_max=tau)
        processed_txs.append(total_tx)
        print(f" -> Xử lý được: {total_tx} giao dịch | FVR: {fvr:.2f}%")

    # VẼ BIỂU ĐỒ TÍNH KHẢ DỤNG (AVAILABILITY)
    plt.figure(figsize=(8, 6))
    plt.plot(timeouts, processed_txs, marker='D', color='purple', linewidth=2, markersize=8)
    
    plt.title('System Availability post-Liveness Failure (Halt at 30s)', fontweight='bold', fontsize=14)
    plt.xlabel('Timeout Threshold $\\tau_{max}$ (seconds)', fontsize=12)
    plt.ylabel('Total Transactions Processed (100s window)', fontsize=12)
    
    plt.grid(True, linestyle='--', alpha=0.7)
    # Thêm chú thích logic
    plt.annotate('Fast Recovery\n(High TPS)', xy=(0.5, processed_txs[0]), xytext=(1.0, processed_txs[0]-20),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5))
    plt.annotate('Slow Recovery\n(Low TPS)', xy=(5.0, processed_txs[-1]), xytext=(3.5, processed_txs[-1]+20),
                 arrowprops=dict(facecolor='black', shrink=0.05, width=1, headwidth=5))
                 
    plt.savefig('availability_liveness.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("\nĐã lưu biểu đồ: availability_liveness.png")

if __name__ == "__main__":
    main()