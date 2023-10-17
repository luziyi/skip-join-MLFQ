
# Define class
class SkipJoinMLFQScheduler:

    def __init__(self, first_quantum=6, quantum_rate=4, queue_num=4):
        # super().__init__()
        self.quantum_list = []
        self.multi_level_priority_queue = []
        self.executed = 0  # 已经完成的请求数量

        # first quantum/Q1 is the min iteration time
        for i in range(queue_num):
            self.quantum_list.append(quantum_rate ** i)
            temp_q = queue.Queue(-1) 
            self.multi_level_priority_queue.append(temp_q)
            
        self.ave_jct = []

    def getNewRequest(self, request: Request):
        # Todo: 处理缓冲区中新到达的request，根据他们的输入长度放入多级队列中
        pass
    
    def demoteRequest(self, job):
        # Todo: 将完成了推理但还没生成完毕的请求放入下一级队列
        pass
    
    def getInferenceJob(self):
        # Todo: 返回在最高优先级的队列中的队首请求
        pass
        
# 推理线程
def run(scheduler):
    while scheduler.executed != JOB_NUM:
        for i in range(request_queue.qsize())
            req = request_queue.get()
            scheduler.getNewRequest(req)

        job = scheduler.getInferenceJob()

        if job.iter_count == 0:
            iter_time = job.first_iter_time
        else:
            iter_time = job.next_iter_time

        args = [iter_time, job, scheduler]
        # 调用模拟推理线程
        temp_thread = thread_pool.submit(lambda p: simulate_forward(*p), args)
