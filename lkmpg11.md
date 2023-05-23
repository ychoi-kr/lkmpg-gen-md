11. Blocking Processes and threads

<a name="sec:sleep"></a>

## 11.1. Sleep

What do you do when somebody asks you for something you can not do right away? If you are a human being and you are bothered by a human being, the only thing you can say is: "*Not right now, I'm busy. Go away!*". But if you are a kernel module and you are bothered by a process, you have another possibility. You can put the process to sleep until you can service it. After all, processes are being put to sleep by the kernel and woken up all the time (that is the way multiple processes appear to run on the same time on a single CPU).

This kernel module is an example of this. The file (called `/proc/sleep`) can only be opened by a single process at a time. If the file is already open, the kernel module calls `wait_event_interruptible`. The easiest way to keep a file open is to open it with:

    tail -f

This function changes the status of the task (a task is the kernel data structure which holds information about a process and the system call it is in, if any) to `TASK_INTERRUPTIBLE`, which means that the task will not run until it is woken up somehow, and adds it to WaitQ, the queue of tasks waiting to access the file. Then, the function calls the scheduler to context switch to a different process, one which has some use for the CPU.

When a process is done with the file, it closes it, and `module_close` is called. That function wakes up all the processes in the queue (there's no mechanism to only wake up one of them). It then returns and the process which just closed the file can continue to run. In time, the scheduler decides that that process has had enough and gives control of the CPU to another process. Eventually, one of the processes which was in the queue will be given control of the CPU by the scheduler. It starts at the point right after the call to `wait_event_interruptible`.

This means that the process is still in kernel mode - as far as the process is concerned, it issued the open system call and the system call has not returned yet. The process does not know somebody else used the CPU for most of the time between the moment it issued the call and the moment it returned.

It can then proceed to set a global variable to tell all the other processes that the file is still open and go on with its life. When the other processes get a piece of the CPU, they'll see that global variable and go back to sleep.

So we will use `tail -f` to keep the file open in the background, while trying to access it with another process (again in the background, so that we need not switch to a different vt). As soon as the first background process is killed with kill %1 , the second is woken up, is able to access the file and finally terminates.

To make our life more interesting, `module_close` does not have a monopoly on waking up the processes which wait to access the file. A signal, such as *Ctrl +c* (**SIGINT**) can also wake up a process. This is because we used `wait_event_interruptible`. We could have used `wait_event` instead, but that would have resulted in extremely angry users whose *Ctrl+c*'s are ignored.

In that case, we want to return with `-EINTR` immediately. This is important so users can, for example, kill the process before it receives the file.

There is one more point to remember. Some times processes don't want to sleep, they want either to get what they want immediately, or to be told it cannot be done. Such processes use the `O_NONBLOCK` flag when opening the file. The kernel is supposed to respond by returning with the error code `-EAGAIN` from operations which would otherwise block, such as opening the file in this example. The program `cat_nonblock`, available in the `examples/other` directory, can be used to open a file with `O_NONBLOCK`.

    $ sudo insmod sleep.ko
    $ cat_nonblock /proc/sleep
    Last input:
    $ tail -f /proc/sleep &
    Last input:
    Last input:
    Last input:
    Last input:
    Last input:
    Last input:
    Last input:
    tail: /proc/sleep: file truncated
    [1] 6540
    $ cat_nonblock /proc/sleep
    Open would block
    $ kill %1
    [1]+  Terminated              tail -f /proc/sleep
    $ cat_nonblock /proc/sleep
    Last input:
    $

    /*
     * sleep.c - create a /proc file, and if several processes try to open it
     * at the same time, put all but one to sleep.
     */

    #include <linux/atomic.h>
    #include <linux/fs.h>
    #include <linux/kernel.h> /* for sprintf() */
    #include <linux/module.h> /* Specifically, a module */
    #include <linux/printk.h>
    #include <linux/proc_fs.h> /* Necessary because we use proc fs */
    #include <linux/types.h>
    #include <linux/uaccess.h> /* for get_user and put_user */
    #include <linux/version.h>
    #include <linux/wait.h> /* For putting processes to sleep and
                                       waking them up */

    #include <asm/current.h>
    #include <asm/errno.h>

    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 6, 0)
    #define HAVE_PROC_OPS
    #endif

    /* Here we keep the last message received, to prove that we can process our
     * input.
     */
    #define MESSAGE_LENGTH 80
    static char message[MESSAGE_LENGTH];

    static struct proc_dir_entry *our_proc_file;
    #define PROC_ENTRY_FILENAME "sleep"

    /* Since we use the file operations struct, we can't use the special proc
     * output provisions - we have to use a standard read function, which is this
     * function.
     */
    static ssize_t module_output(struct file *file, /* see include/linux/fs.h   */
                                 char __user *buf, /* The buffer to put data to
                                                       (in the user segment)    */
                                 size_t len, /* The length of the buffer */
                                 loff_t *offset)
    {
        static int finished = 0;
        int i;
        char output_msg[MESSAGE_LENGTH + 30];

        /* Return 0 to signify end of file - that we have nothing more to say
         * at this point.
         */
        if (finished) {
            finished = 0;
            return 0;
        }

        sprintf(output_msg, "Last input:%s\n", message);
        for (i = 0; i < len && output_msg[i]; i++)
            put_user(output_msg[i], buf + i);

        finished = 1;
        return i; /* Return the number of bytes "read" */
    }

    /* This function receives input from the user when the user writes to the
     * /proc file.
     */
    static ssize_t module_input(struct file *file, /* The file itself */
                                const char __user *buf, /* The buffer with input */
                                size_t length, /* The buffer's length */
                                loff_t *offset) /* offset to file - ignore */
    {
        int i;

        /* Put the input into Message, where module_output will later be able
         * to use it.
         */
        for (i = 0; i < MESSAGE_LENGTH - 1 && i < length; i++)
            get_user(message[i], buf + i);
        /* we want a standard, zero terminated string */
        message[i] = '\0';

        /* We need to return the number of input characters used */
        return i;
    }

    /* 1 if the file is currently open by somebody */
    static atomic_t already_open = ATOMIC_INIT(0);

    /* Queue of processes who want our file */
    static DECLARE_WAIT_QUEUE_HEAD(waitq);

    /* Called when the /proc file is opened */
    static int module_open(struct inode *inode, struct file *file)
    {
        /* If the file's flags include O_NONBLOCK, it means the process does not
         * want to wait for the file. In this case, if the file is already open,
         * we should fail with -EAGAIN, meaning "you will have to try again",
         * instead of blocking a process which would rather stay awake.
         */
        if ((file->f_flags & O_NONBLOCK) && atomic_read(&already_open))
            return -EAGAIN;

        /* This is the correct place for try_module_get(THIS_MODULE) because if
         * a process is in the loop, which is within the kernel module,
         * the kernel module must not be removed.
         */
        try_module_get(THIS_MODULE);

        while (atomic_cmpxchg(&already_open, 0, 1)) {
            int i, is_sig = 0;

            /* This function puts the current process, including any system
             * calls, such as us, to sleep.  Execution will be resumed right
             * after the function call, either because somebody called
             * wake_up(&waitq) (only module_close does that, when the file
             * is closed) or when a signal, such as Ctrl-C, is sent
             * to the process
             */
            wait_event_interruptible(waitq, !atomic_read(&already_open));

            /* If we woke up because we got a signal we're not blocking,
             * return -EINTR (fail the system call).  This allows processes
             * to be killed or stopped.
             */
            for (i = 0; i < _NSIG_WORDS && !is_sig; i++)
                is_sig = current->pending.signal.sig[i] & ~current->blocked.sig[i];

            if (is_sig) {
                /* It is important to put module_put(THIS_MODULE) here, because
                 * for processes where the open is interrupted there will never
                 * be a corresponding close. If we do not decrement the usage
                 * count here, we will be left with a positive usage count
                 * which we will have no way to bring down to zero, giving us
                 * an immortal module, which can only be killed by rebooting
                 * the machine.
                 */
                module_put(THIS_MODULE);
                return -EINTR;
            }
        }

        return 0; /* Allow the access */
    }

    /* Called when the /proc file is closed */
    static int module_close(struct inode *inode, struct file *file)
    {
        /* Set already_open to zero, so one of the processes in the waitq will
         * be able to set already_open back to one and to open the file. All
         * the other processes will be called when already_open is back to one,
         * so they'll go back to sleep.
         */
        atomic_set(&already_open, 0);

        /* Wake up all the processes in waitq, so if anybody is waiting for the
         * file, they can have it.
         */
        wake_up(&waitq);

        module_put(THIS_MODULE);

        return 0; /* success */
    }

    /* Structures to register as the /proc file, with pointers to all the relevant
     * functions.
     */

    /* File operations for our proc file. This is where we place pointers to all
     * the functions called when somebody tries to do something to our file. NULL
     * means we don't want to deal with something.
     */
    #ifdef HAVE_PROC_OPS
    static const struct proc_ops file_ops_4_our_proc_file = {
        .proc_read = module_output, /* "read" from the file */
        .proc_write = module_input, /* "write" to the file */
        .proc_open = module_open, /* called when the /proc file is opened */
        .proc_release = module_close, /* called when it's closed */
        .proc_lseek = noop_llseek, /* return file->f_pos */
    };
    #else
    static const struct file_operations file_ops_4_our_proc_file = {
        .read = module_output,
        .write = module_input,
        .open = module_open,
        .release = module_close,
        .llseek = noop_llseek,
    };
    #endif

    /* Initialize the module - register the proc file */
    static int __init sleep_init(void)
    {
        our_proc_file =
            proc_create(PROC_ENTRY_FILENAME, 0644, NULL, &file_ops_4_our_proc_file);
        if (our_proc_file == NULL) {
            remove_proc_entry(PROC_ENTRY_FILENAME, NULL);
            pr_debug("Error: Could not initialize /proc/%s\n", PROC_ENTRY_FILENAME);
            return -ENOMEM;
        }
        proc_set_size(our_proc_file, 80);
        proc_set_user(our_proc_file, GLOBAL_ROOT_UID, GLOBAL_ROOT_GID);

        pr_info("/proc/%s created\n", PROC_ENTRY_FILENAME);

        return 0;
    }

    /* Cleanup - unregister our file from /proc.  This could get dangerous if
     * there are still processes waiting in waitq, because they are inside our
     * open function, which will get unloaded. I'll explain how to avoid removal
     * of a kernel module in such a case in chapter 10.
     */
    static void __exit sleep_exit(void)
    {
        remove_proc_entry(PROC_ENTRY_FILENAME, NULL);
        pr_debug("/proc/%s removed\n", PROC_ENTRY_FILENAME);
    }

    module_init(sleep_init);
    module_exit(sleep_exit);

    MODULE_LICENSE("GPL");

    /*
     *  cat_nonblock.c - open a file and display its contents, but exit rather than
     *  wait for input.
     */
    #include <errno.h> /* for errno */
    #include <fcntl.h> /* for open */
    #include <stdio.h> /* standard I/O */
    #include <stdlib.h> /* for exit */
    #include <unistd.h> /* for read */

    #define MAX_BYTES 1024 * 4

    int main(int argc, char *argv[])
    {
        int fd; /* The file descriptor for the file to read */
        size_t bytes; /* The number of bytes read */
        char buffer[MAX_BYTES]; /* The buffer for the bytes */

        /* Usage */
        if (argc != 2) {
            printf("Usage: %s <filename>\n", argv[0]);
            puts("Reads the content of a file, but doesn't wait for input");
            exit(-1);
        }

        /* Open the file for reading in non blocking mode */
        fd = open(argv[1], O_RDONLY | O_NONBLOCK);

        /* If open failed */
        if (fd == -1) {
            puts(errno == EAGAIN ? "Open would block" : "Open failed");
            exit(-1);
        }

        /* Read the file and output its contents */
        do {
            /* Read characters from the file */
            bytes = read(fd, buffer, MAX_BYTES);

            /* If there's an error, report it and die */
            if (bytes == -1) {
                if (errno == EAGAIN)
                    puts("Normally I'd block, but you told me not to");
                else
                    puts("Another read error");
                exit(-1);
            }

            /* Print the characters */
            if (bytes > 0) {
                for (int i = 0; i < bytes; i++)
                    putchar(buffer[i]);
            }

            /* While there are no errors and the file isn't over */
        } while (bytes > 0);

        return 0;
    }

<a name="sec:completion"></a>

## 11.2. Completions

Sometimes one thing should happen before another within a module having multiple threads. Rather than using `/bin/sleep` commands, the kernel has another way to do this which allows timeouts or interrupts to also happen.

In the following example two threads are started, but one needs to start before another.

    /*
     * completions.c
     */
    #include <linux/completion.h>
    #include <linux/err.h> /* for IS_ERR() */
    #include <linux/init.h>
    #include <linux/kthread.h>
    #include <linux/module.h>
    #include <linux/printk.h>
    #include <linux/version.h>

    static struct {
        struct completion crank_comp;
        struct completion flywheel_comp;
    } machine;

    static int machine_crank_thread(void *arg)
    {
        pr_info("Turn the crank\n");

        complete_all(&machine.crank_comp);
    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 17, 0)
        kthread_complete_and_exit(&machine.crank_comp, 0);
    #else
        complete_and_exit(&machine.crank_comp, 0);
    #endif
    }

    static int machine_flywheel_spinup_thread(void *arg)
    {
        wait_for_completion(&machine.crank_comp);

        pr_info("Flywheel spins up\n");

        complete_all(&machine.flywheel_comp);
    #if LINUX_VERSION_CODE >= KERNEL_VERSION(5, 17, 0)
        kthread_complete_and_exit(&machine.flywheel_comp, 0);
    #else
        complete_and_exit(&machine.flywheel_comp, 0);
    #endif
    }

    static int completions_init(void)
    {
        struct task_struct *crank_thread;
        struct task_struct *flywheel_thread;

        pr_info("completions example\n");

        init_completion(&machine.crank_comp);
        init_completion(&machine.flywheel_comp);

        crank_thread = kthread_create(machine_crank_thread, NULL, "KThread Crank");
        if (IS_ERR(crank_thread))
            goto ERROR_THREAD_1;

        flywheel_thread = kthread_create(machine_flywheel_spinup_thread, NULL,
                                         "KThread Flywheel");
        if (IS_ERR(flywheel_thread))
            goto ERROR_THREAD_2;

        wake_up_process(flywheel_thread);
        wake_up_process(crank_thread);

        return 0;

    ERROR_THREAD_2:
        kthread_stop(crank_thread);
    ERROR_THREAD_1:

        return -1;
    }

    static void completions_exit(void)
    {
        wait_for_completion(&machine.crank_comp);
        wait_for_completion(&machine.flywheel_comp);

        pr_info("completions exit\n");
    }

    module_init(completions_init);
    module_exit(completions_exit);

    MODULE_DESCRIPTION("11.2. Completions example");
    MODULE_LICENSE("GPL");

The `machine` structure stores the completion states for the two threads. At the exit point of each thread the respective completion state is updated, and `wait_for_completion` is used by the flywheel thread to ensure that it does not begin prematurely.

So even though `flywheel_thread` is started first you should notice if you load this module and run `dmesg` that turning the crank always happens first because the flywheel thread waits for it to complete.

There are other variations upon the `wait_for_completion` function, which include timeouts or being interrupted, but this basic mechanism is enough for many common situations without adding a lot of complexity.
