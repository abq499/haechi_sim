# main.py
import simpy
from simulation import Shard, BeaconChain

# Gọi hàm tính toán từ file evaluation.py vừa tạo
from evaluation import calculate_fvr 

# Khởi tạo môi trường
env = simpy.Environment()
num_shards = 3

beacon = BeaconChain(env, num_shards)

# Khởi tạo 3 Shard, trong đó Shard 0 là malicious (Attacker)
shards = [
    Shard(env, 0, beacon, is_malicious=True),
    Shard(env, 1, beacon, is_malicious=False),
    Shard(env, 2, beacon, is_malicious=False)
]

# Chạy mô phỏng trong 1000 đơn vị thời gian
print("Bắt đầu chạy mô phỏng...")
env.run(until=1000)

print(f"Tổng số TX được order: {len(beacon.global_execution_order)}")

# Lấy con số FVR từ hàm calculate_fvr và in ra màn hình
fvr_score = calculate_fvr(beacon.global_execution_order)
print(f"Fairness Violation Rate (FVR): {fvr_score:.2f}%")