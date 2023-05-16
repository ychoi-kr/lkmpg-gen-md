14. Scheduling Tasks

There are two main ways of running tasks: tasklets and work queues. 14.1. Tasklets are a quick and easy way of scheduling a single function to be run. For example, when triggered from an interrupt, whereas work queues are more complicated but also better suited to running multiple things in a sequence.

<a name="sec:tasklet"></a>
## 14.1. Tasklets

Here is an example tasklet module. The `tasklet_fn` function runs for a few seconds. In the meantime, execution of the `example_tasklet_init` function may continue to the exit point, depending on whether it is interrupted by **softirq**.

    /*
     * example_tasklet.c
     */
    #include <linux/delay.h>
    #include <linux/interrupt.h>
    #include <linux/module.h>
    #include <linux/printk.h>

    /* Macro DECLARE_TASKLET_OLD exists for compatibility.
     * See https://lwn.net/Articles/830964/
     */
    #ifndef DECLARE_TASKLET_OLD
    #define DECLARE_TASKLET_OLD(arg1, arg2) DECLARE_TASKLET(arg1, arg2, 0L)
    #endif

    static void tasklet_fn(unsigned long data)
    {
        pr_info("Example tasklet starts\n");
        mdelay(5000);
        pr_info("Example tasklet ends\n");
    }

    static DECLARE_TASKLET_OLD(mytask, tasklet_fn);

    static int example_tasklet_init(void)
    {
        pr_info("tasklet example init\n");
        tasklet_schedule(&mytask);
        mdelay(200);
        pr_info("Example tasklet init continues...\n");
        return 0;
    }

    static void example_tasklet_exit(void)
    {
        pr_info("tasklet example exit\n");
        tasklet_kill(&mytask);
    }

    module_init(example_tasklet_init);
    module_exit(example_tasklet_exit);

    MODULE_DESCRIPTION("Tasklet example");
    MODULE_LICENSE("GPL");

So with this example loaded `dmesg` should show:

    tasklet example init
    Example tasklet starts
    Example tasklet init continues...
    Example tasklet ends

Although tasklet is easy to use, it comes with several defators, and developers are discussing about getting rid of tasklet in linux kernel. The tasklet callback runs in atomic context, inside a software interrupt, meaning that it cannot sleep or access user-space data, so not all work can be done in a tasklet handler. Also, the kernel only allows one instance of any given tasklet to be running at any given time; multiple different tasklet callbacks can run in parallel.

In recent kernels, tasklets can be replaced by workqueues, timers, or threaded interrupts.[^1] While the removal of tasklets remains a longer-term goal, the current kernel contains more than a hundred uses of tasklets. Now developers are proceeding with the API changes and the macro `DECLARE_TASKLET_OLD` exists for compatibility. For further information, see <https://lwn.net/Articles/830964/>.

<a name="sec:workqueue"></a>
## 14.2. Work queues

To add a task to the scheduler we can use a workqueue. The kernel then uses the Completely Fair Scheduler (CFS) to execute work within the queue.

    /*
     * sched.c
     */
    #include <linux/init.h>
    #include <linux/module.h>
    #include <linux/workqueue.h>

    static struct workqueue_struct *queue = NULL;
    static struct work_struct work;

    static void work_handler(struct work_struct *data)
    {
        pr_info("work handler function.\n");
    }

    static int __init sched_init(void)
    {
        queue = alloc_workqueue("HELLOWORLD", WQ_UNBOUND, 1);
        INIT_WORK(&work, work_handler);
        schedule_work(&work);
        return 0;
    }

    static void __exit sched_exit(void)
    {
        destroy_workqueue(queue);
    }

    module_init(sched_init);
    module_exit(sched_exit);

    MODULE_LICENSE("GPL");
    MODULE_DESCRIPTION("Workqueue example");
