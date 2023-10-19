#用户请求发送线程示例代码：
from concurrent.futures import ThreadPoolExecutor
import csv
import time
import threading
import numpy as np
import queue
thread_pool = ThreadPoolExecutor(max_workers=1)
lock = threading.Lock() # 线程锁 确保同一时间只有一个线程在访问全局数据
JOB_NUM = 99  # 发送请求的个数
global time_n
time_n=0.0
#初始化请求队列
request_queue = queue.Queue(-1)

# 在opt-1.3B上的实验数据 单位: ms
x = [1, 4, 16, 64, 256, 512, 1024]
first_time = [5.88, 5.93, 6.57, 8.04, 23.8, 43.9, 98.5]
next_time = [5.13, 5.11, 5.16, 5.22, 5.52, 5.72, 5.82]

# 通过实验数据拟合每次迭代推理时间
z1 = np.polyfit(x, first_time, 2)
p1 = np.poly1d(z1)

z2 = np.polyfit(x, next_time, 1)
p2 = np.poly1d(z2)
#定义first_iter_time和next_iter_time的拟合函数
def fit_first_iter_time(prompt_length):
    return p1(float(prompt_length))
def fit_next_iter_time(prompt_length):
    return p2(float(prompt_length))


        
class RequestGenerator(threading.Thread):

    def __init__(self, arrival_rate):
        super().__init__()
        self.arrival_rate = arrival_rate  # 每秒到达的请求数量=1/平均间隔时间
        
    def run(self):
        prompt_length_list = []
        output_length_list = []
        global time_n
        time_n=0.0
        # 此处为读取orca数据集中的数据来构造request，可自行修改路径
        f = open('./orca_100k.csv', 'r')
        count=0
        with f:
            reader = csv.reader(f)
            for row in reader:
                if count == 0:
                    count += 1
                    continue

                prompt_length_list.append(row[0])
                output_length_list.append(row[1])
                
        j_id = 1

        while j_id <= JOB_NUM:
            with lock:
                if j_id <= len(output_length_list):
                    output_ = output_length_list[j_id-1]
                    input_ = prompt_length_list[j_id-1]
                    time_n += (1 / self.arrival_rate) / 100
                    request = Request(j_id, input_, output_,time_n) # 创建新的请求  
                    request_queue.put(request)
                    j_id += 1
                else:
                    break
class Request:  # 初始化请求类，所有请求对象都是这个类的实例
    def __init__(self, j_id, prompt_length, output_length,time_n):
        self.j_id = j_id
        self.prompt_length = int(prompt_length)
        self.output_length = int(output_length)
        self.first_iter_time = fit_first_iter_time(prompt_length)
        self.next_iter_time  = fit_next_iter_time(prompt_length)
        self.iter_count = 0 # 请求执行了几次迭代，iter_count==output_length时完成整个推理   
        self.priority = -1  # 请求目前处于第几级队列
        self.create_time = time_n  # 请求创建时间


#skip-join mlfq调度器示例代码
class SkipJoinMLFQScheduler:#skip-join mlfq调度器示例代码
    def __init__(self, first_quantum=6, quantum_rate=4, queue_num=4): 
        # super().__init__()  #初始化父类 
        self.execution_order = [] #记录任务执行顺序
        self.quantum_list = [] # 每个队列的时间片大小
        self.multi_level_priority_queue = [] # 多级队列
        self.executed = 0  # 已经完成的请求数量
        self.result=[]
        #第一级队列的最小迭代时间
        self.quantum_list.append(first_quantum)
        temp_q = queue.Queue(-1)
        self.multi_level_priority_queue.append(temp_q)
        #print("quantum %d: %d" % (0,first_quantum))
        for i in range(0,queue_num-1):
            self.quantum_list.append(first_quantum*(quantum_rate ** (i+1))) # 每个队列的时间片大小
            temp_q = queue.Queue(-1)            #初始化每个队列  
            self.multi_level_priority_queue.append(temp_q) # 多级队列
            #print("quantum %d: %d" % (i+1, first_quantum*(quantum_rate ** (i+1))))
        self.ave_jct = []

    def getNewRequest(self, request: Request):
        # 处理新到达的请求，根据输入长度将其放入多级队列中
        prompt_length = request.prompt_length
        for i in range(len(self.quantum_list)):
            if prompt_length <= self.quantum_list[i]:
                priority=i
                break
            else:
                priority = len(self.quantum_list) - 1
        request.priority = priority
        self.multi_level_priority_queue[priority].put(request)
        #print("job %d, priority %d, prompt_length %d, output_length %d, first_iter_time %d, next_iter_time %d" % (request.j_id, request.priority, request.prompt_length, request.output_length, request.first_iter_time, request.next_iter_time))

    def demoteRequest(self, job):
        #print("demoteRequest")
        # 将完成了推理但还没生成完毕的请求放入下一级队列
        current_priority = job.priority
        if current_priority < len(self.multi_level_priority_queue) - 1:
            job.priority = current_priority + 1
        self.multi_level_priority_queue[job.priority].put(job) #在下一级队列中加入该请求

    def getInferenceJob(self):
        # 返回在最高优先级的队列中的队首请求
        with lock: 
            for i in range(len(self.multi_level_priority_queue)):
                if not self.multi_level_priority_queue[i].empty():
                    #print("get job %d from queue %d" % (self.multi_level_priority_queue[i].queue[0].j_id, i))
                    return self.multi_level_priority_queue[i].get()
            #print("All queues are empty.")
        return None
# 推理线程
def run(scheduler):
    while scheduler.executed != JOB_NUM:
        for i in range(request_queue.qsize()): 
            req = request_queue.get()
            scheduler.getNewRequest(req)
        job = scheduler.getInferenceJob()
        if job == None:
            #print("No job to execute.")
            continue
        else:
            first_iter_time=job.first_iter_time
            next_iter_time=job.next_iter_time
            args = [first_iter_time,next_iter_time, job, scheduler,time_n]
            # 调用模拟推理线程
            temp_thread = thread_pool.submit(lambda p: simulate_forward(*p), args)
    thread_pool.shutdown(wait=True)



#用于模拟过程推理的函数
def simulate_forward(first_iter_time,next_iter_time, job, scheduler,time_n):
    scheduler.execution_order.append(job.j_id)
    #print("first_iter_time: %f  next_iter_time: %f" % (first_iter_time/10000, next_iter_time*job.output_length/10000))
    iteration_num = job.output_length - 1
    time_n += first_iter_time/100 + next_iter_time*iteration_num/100
    job.iter_count = job.output_length
    jct = time_n 
    #print(jct)
    scheduler.ave_jct.append(round(jct,4))
    scheduler.result.append((job.j_id, round(jct,4)))
    #print(scheduler.ave_jct)
    scheduler.executed += 1


#主程序启动示例代码
if __name__ == '__main__':
    # 定义并启动发送请求的用户线程
    generator = RequestGenerator(arrival_rate=10)
    generator.start()#把请求的对象放入request_queue中


    first_quantum=100000
    quantum_rate=1
    queue_num=1

    # 定义并启动调度器线程 这里定义了一个skip-join mlfq调度器 并且给出了第一个时间片大小，时间片增长率，队列数量
    scheduler = SkipJoinMLFQScheduler(first_quantum,quantum_rate,queue_num)

    run(scheduler)
    print("FCFS:")
    print("first_quantum: --,  quantum_rate: --, queue_num: --")
    print("-----------------------------------------------------------------------------------------------------")
    print("average jct: ", sum(scheduler.ave_jct) / len(scheduler.ave_jct))
    print("execution order: ", scheduler.execution_order)
    print("JCT: ")
    for result in scheduler.result:
        print("id: {}, jct: {}".format(result[0], result[1]))
