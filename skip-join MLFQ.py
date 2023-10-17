#用户请求发送线程示例代码：
from concurrent.futures import ThreadPoolExecutor
import csv
import time
import threading
import numpy as np
import queue
thread_pool = ThreadPoolExecutor(max_workers=3)

JOB_NUM = 100  # 发送请求的个数

# 在opt-1.3B上的实验数据 单位: ms
x = [1, 4, 16, 64, 256, 512, 1024]
first_time = [5.88, 5.93, 6.57, 8.04, 23.8, 43.9, 98.5]
next_time = [5.13, 5.11, 5.16, 5.22, 5.52, 5.72, 5.82]

# 通过实验数据拟合每次迭代推理时间
z1 = np.polyfit(x, first_time, 1)
p1 = np.poly1d(z1)

z2 = np.polyfit(x, next_time, 1)
p2 = np.poly1d(z2)

class Request:  # 推理请求，理论上输出长度未知，但为仿真实验，需要事先确定
    def __init__(self, j_id, prompt_length, output_length):
        self.j_id = j_id
        self.prompt_length = int(prompt_length)
        self.output_length = int(output_length)
        self.first_iter_time = fit_first_iter_time(prompt_length)
        self.next_iter_time  = fit_next_iter_time(prompt_length)
        self.iter_count = 0 # 请求执行了几次迭代，iter_count==output_length时完成整个推理   
        self.priority = -1  # 请求目前处于第几级队列
        
        self.create_time = time.time()  # 请求创建时间
        
class RequestGenerator(threading.Thread):

    def __init__(self, arrival_rate):
        super().__init__()
        self.arrival_rate = arrival_rate  # arrival rate = 1s / job interval
        
    def run(self):
        prompt_length_list = []
        output_length_list = []
        
        # 此处为读取orca数据集中的数据来构造request，可自行修改路径
        f = open('/orca_100k.csv', 'r')
        count=0
        with f:
            reader = csv.reader(f)
            for row in reader:
                if count == 0:
                    count += 1
                    continue

                prompt_length_list.append(row[0])
                output_length_list.append(row[1])
                
        j_id = 0

        while j_id < JOB_NUM:
            output_ = output_length_list[j_id]
            input_ = prompt_length_list[j_id]
            request = Request(j_id, input_, output_) # 创建新的请求  
            request_queue.put(request)
            j_id += 1
            time.sleep(1 / self.arrival_rate)


#skip-join mlfq调度器示例代码
# Define class
class SkipJoinMLFQScheduler:

    def __init__(self, first_quantum=6, quantum_rate=4, queue_num=4):
        # super().__init__() 
        self.quantum_list = []
        self.multi_level_priority_queue = []
        self.executed = 0  # 已经完成的请求数量

        #第一级队列的最小迭代时间
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
        for i in range(request_queue.qsize()):
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


#用于模拟过程推理的函数
def simulate_forward(iteration_time, job, scheduler):
    
    iteration_num = scheduler.quantum_list[job.priority]  # 获取当前任务在这次推理中需要执行多少轮
    
    if iteration_num >= job.output_length - job.iter_count:
        iteration_num = job.output_length - job.iter_count

        for i in range(iteration_num):
            time.sleep(iteration_time / 1000)  # ms
            job.iter_count += 1

        jct = time.time() - job.create_time                     
        scheduler.ave_jct.append(jct)
        
        scheduler.executed += 1
        
    else:
        for i in range(iteration_num):
            time.sleep(iteration_time / 1000)  # ms
            job.iter_count += 1

        scheduler.demoteRequest(job)

#主程序启动示例代码
if __name__ == '__main__':
    # 定义并启动发送请求的用户线程
    generator = RequestGenerator(arrival_rate=800)
    generator.start()#把请求的对象放入request_queue中
    
    # 定义并启动调度器线程
    scheduler = SkipJoinMLFQScheduler(first_quantum=1,
                                      quantum_rate=2,
                                      queue_num=4)
    run(scheduler)

