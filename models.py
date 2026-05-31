# models.py
class Transaction:
    def __init__(self, tx_id, processing_time):
        self.tx_id = tx_id
        # Thời gian thực tế giao dịch được đưa vào khối (Ground truth để đo lường)
        self.processing_time = processing_time 

class CrossLink:
    def __init__(self, shard_id, height, block_ts, tx_list):
        self.shard_id = shard_id
        self.height = height
        # block_ts là timestamp vật lý có thể bị attacker thao túng
        self.block_ts = block_ts
        self.tx_list = tx_list