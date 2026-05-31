# simulation.py
import simpy
import random
from models import Transaction, CrossLink

class Shard:
    # Thêm tham số max_skew
    def __init__(self, env, shard_id, beacon, is_malicious=False, max_skew=0.5):
        self.env = env
        self.shard_id = shard_id
        self.beacon = beacon
        self.height = 0
        self.is_malicious = is_malicious
        self.max_skew = max_skew # Mức độ ăn gian thời gian
        
        self.action = env.process(self.run())

    def run(self):
        while True:
            # Nhịp đập đồng bộ của mạng lưới
            yield self.env.timeout(2.0)
            
            self.height += 1
            
            # 1. Thêm độ nhiễu (Jitter) có định hướng
            # Đảm bảo thứ tự tự nhiên (Ground Truth): Shard 0 -> Shard 1 -> Shard 2
            base_delay = self.shard_id * 0.001  
            processing_delay = base_delay + random.uniform(0.01, 0.05)
            real_time = self.env.now + processing_delay
            
            # 2. Gán Timestamp vật lý
            block_ts = real_time
            if self.is_malicious:
                # Max Skew càng lớn, xác suất lùi timestamp vượt mặt người khác càng cao
                block_ts = real_time - random.uniform(0.0, self.max_skew)
            
            # 3. Khởi tạo TX
            tx = Transaction(tx_id=f"S{self.shard_id}-{self.height}", processing_time=real_time)
            cross_link = CrossLink(self.shard_id, self.height, block_ts, [tx])
            self.env.process(self.network_delay(cross_link))

    def network_delay(self, cross_link):
        yield self.env.timeout(random.uniform(0.1, 0.3))
        self.beacon.receive_crosslink(cross_link)

class BeaconChain:
    def __init__(self, env, num_shards, use_logical_ordering=False):
        self.env = env
        self.num_shards = num_shards
        self.use_logical_ordering = use_logical_ordering
        self.crosslink_pool = {i: [] for i in range(num_shards)}
        self.global_execution_order = []
        
        # MỚI: Mảng lưu trữ độ trễ của từng giao dịch
        self.tx_latencies = [] 
        
    def receive_crosslink(self, cross_link):
        self.crosslink_pool[cross_link.shard_id].append(cross_link)
        self.check_and_order()
        
    def check_and_order(self):
        if all(len(self.crosslink_pool[i]) > 0 for i in range(self.num_shards)):
            self.order_phase()
            
    def order_phase(self):
        blocks_to_order = [self.crosslink_pool[i].pop(0) for i in range(self.num_shards)]
        
        if self.use_logical_ordering:
            blocks_to_order.sort(key=lambda x: (x.height, x.shard_id))
        else:
            blocks_to_order.sort(key=lambda x: x.block_ts)
        
        for block in blocks_to_order:
            for tx in block.tx_list:
                # MỚI: Tính Latency = Thời gian hiện tại (lúc chốt order) - Thời gian sinh ra
                latency = self.env.now - tx.processing_time
                self.tx_latencies.append(latency)
                
            self.global_execution_order.extend(block.tx_list)