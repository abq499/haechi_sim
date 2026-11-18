# simulation.py
import simpy
import random
import numpy as np
from models import Transaction, CrossLink

class Shard:
    # Thêm tham số max_skew
    def __init__(self, env, shard_id, beacon, is_malicious=False, max_skew=0.5, block_cycle=2.0, jitter_type='uniform', halt_at=None, batch_size=1):
        self.env = env
        self.shard_id = shard_id
        self.beacon = beacon
        self.height = 0
        self.is_malicious = is_malicious
        self.max_skew = max_skew # Mức độ ăn gian thời gian
        self.block_cycle = block_cycle
        self.jitter_type = jitter_type
        self.halt_at = halt_at
        self.batch_size = batch_size
        self.action = env.process(self.run())

    def run(self):
        while True:
            if self.halt_at and self.env.now >= self.halt_at:
                yield self.env.timeout(999999)
                continue
            # Nhịp đập đồng bộ của mạng lưới
            yield self.env.timeout(self.block_cycle)
            
            self.height += 1
            
            # 1. Thêm độ nhiễu (Jitter) có định hướng
            # Đảm bảo thứ tự tự nhiên (Ground Truth): Shard 0 -> Shard 1 -> Shard 2
            #base_delay = self.shard_id * 0.001  
            #processing_delay = base_delay + random.uniform(0.01, 0.05)
            #real_time = self.env.now + processing_delay
            base_delay = self.shard_id * 0.001  
            real_time = self.env.now + base_delay
            
            # 2. Gán Timestamp vật lý
            block_ts = real_time
            if self.is_malicious:
                # Max Skew càng lớn, xác suất lùi timestamp vượt mặt người khác càng cao
                block_ts = real_time - random.uniform(0.0, self.max_skew)
            
            # 3. Khởi tạo TX
            tx_list = []
            for k in range(self.batch_size):
                tx = Transaction(
                    tx_id=f"S{self.shard_id}-{self.height}-{k}",
                    processing_time=real_time
                )
                tx_list.append(tx)

            cross_link = CrossLink(self.shard_id, self.height, block_ts, tx_list)
            self.env.process(self.network_delay(cross_link))

    def network_delay(self, cross_link):
        if self.jitter_type == 'lognormal':
            delay = np.random.lognormal(mean=-2.99, sigma=0.6)

        elif self.jitter_type == 'pareto':
            delay = (np.random.pareto(a=1.5) + 1) * 0.02

        else:
            delay = random.uniform(0.01, 0.05)

        yield self.env.timeout(delay)
        self.beacon.receive_crosslink(cross_link)

class BeaconChain:
    # MỚI: Thêm 2 tham số rotate_shard_id và epoch_len
    def __init__(self, env, num_shards, engine_type='dlo', tau_max=None, rotate_shard_id=False, epoch_len=100):
        self.env = env
        self.num_shards = num_shards
        self.engine_type = engine_type.lower()
        self.tau_max = tau_max
        self.rotate_shard_id = rotate_shard_id # Cờ bật/tắt xoay vòng
        self.epoch_len = epoch_len             # Độ dài 1 Epoch
        
        self.crosslink_pool = {i: [] for i in range(num_shards)}
        self.global_execution_order = []
        self.tx_latencies = [] 
        self.current_height = 1 
        # Biến đếm xem Shard 0 "thắng" quyền ưu tiên xếp trước bao nhiêu lần
        self.shard_0_win_count = 0 
        
        self.env.process(self.run_coordinator())
        
    def receive_crosslink(self, cross_link):
        self.crosslink_pool[cross_link.shard_id].append(cross_link)

    def run_coordinator(self):
        while True:
            start_wait = self.env.now
            
            while not self.has_all_blocks_for_height(self.current_height):
                if self.tau_max and (self.env.now - start_wait) >= self.tau_max:
                    break
                yield self.env.timeout(0.01)

            for i in range(self.num_shards):
                for block in self.crosslink_pool[i]:
                    if block.height < self.current_height:
                        block.height = self.current_height

            self.order_phase(self.current_height)
            self.current_height += 1

    def has_all_blocks_for_height(self, height):
        for i in range(self.num_shards):
            if not any(block.height == height for block in self.crosslink_pool[i]):
                return False
        return True
            
    def order_phase(self, height):
        blocks_to_order = []
        for i in range(self.num_shards):
            for j, block in enumerate(self.crosslink_pool[i]):
                if block.height == height:
                    blocks_to_order.append(self.crosslink_pool[i].pop(j))
                    break
        
        if self.engine_type == 'dlo':
            if self.rotate_shard_id:
                # MỚI: Logic xoay vòng (Shard_ID + Epoch) % Tổng số Shard
                epoch = height // self.epoch_len
                blocks_to_order.sort(key=lambda x: (x.height, (x.shard_id + epoch) % self.num_shards))
            else:
                # Logic tĩnh: Shard nhỏ luôn ưu tiên trước
                blocks_to_order.sort(key=lambda x: (x.height, x.shard_id))
            overhead_delay = 0.0
        else:
            blocks_to_order.sort(key=lambda x: x.block_ts)
            overhead_delay = 0.0
        
        # Thống kê xem khối của Shard 0 có được xếp ở vị trí ĐẦU TIÊN (Ưu tiên nhất) trong nhịp này không
        if blocks_to_order and blocks_to_order[0].shard_id == 0:
            self.shard_0_win_count += 1
            
        for block in blocks_to_order:
            for tx in block.tx_list:
                latency = (self.env.now - tx.processing_time) + overhead_delay
                self.tx_latencies.append(latency)
            self.global_execution_order.extend(block.tx_list)