# experiments_batched.py
import simpy
import matplotlib.pyplot as plt
from simulation import Shard, BeaconChain

def run_batched_experiment(num_shards, batch_size, simulation_time=100):
    env = simpy.Environment()
    # Chạy luôn trên nền DLO
    beacon = BeaconChain(env, num_shards, engine_type='dlo')
    
    shards = []
    for i in range(num_shards):
        # Kịch bản đo lường hiệu năng thuần túy nên không cần hacker
        shards.append(Shard(env, i, beacon, is_malicious=False, batch_size=batch_size))
        
    env.run(until=simulation_time)
    
    # Tính TPS
    total_tx = len(beacon.global_execution_order)
    tps = total_tx / simulation_time
    return tps

def main():
    print("Bắt đầu mô phỏng Thông lượng Thực tế (Production Throughput)...")
    shard_counts = [3, 10, 20, 30]
    batch_sizes = [100, 500, 1000, 2000]
    
    plt.figure(figsize=(9, 6))
    colors = ['blue', 'green', 'orange', 'red']
    markers = ['o', 's', '^', 'D']
    
    for idx, b_size in enumerate(batch_sizes):
        tps_list = []
        print(f"\n--- Đang chạy với kích thước khối (Batch Size) = {b_size} ---")
        for count in shard_counts:
            tps = run_batched_experiment(count, b_size)
            tps_list.append(tps)
            print(f"Shards: {count:2d} -> Throughput: {tps:,.2f} TPS")
            
        plt.plot(shard_counts, tps_list, marker=markers[idx], color=colors[idx], 
                 linewidth=2, markersize=8, label=f'Batch Size = {b_size}')

    # Làm đẹp đồ thị
    plt.title('Production Throughput Projection (Batched CrossLinks)', fontweight='bold', fontsize=14)
    plt.xlabel('Number of Shards', fontsize=12)
    plt.ylabel('System Throughput (TPS)', fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend(title="Transactions per Block", fontsize=11)
    
    # Định dạng trục Y hiển thị số có dấu phẩy (vd: 10,000 thay vì 10000)
    ax = plt.gca()
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: "{:,}".format(int(x))))
    
    plt.savefig('throughput_batched.png', dpi=300, bbox_inches='tight')
    plt.close()
    print("\nĐã lưu biểu đồ: throughput_batched.png")

if __name__ == "__main__":
    main()