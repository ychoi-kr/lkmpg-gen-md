12. Avoiding Collisions and Deadlocks

If processes running on different CPUs or in different threads try to access the same memory, then it is possible that strange things can happen or your system can lock up. To avoid this, various types of mutual exclusion kernel functions are available. These indicate if a section of code is "locked" or "unlocked" so that simultaneous attempts to run it can not happen.

<a name="sec:mutex"></a>
## 12.1. Mutex

You can use kernel mutexes (mutual exclusions) in much the same manner that you might deploy them in userland. This may be all that is needed to avoid collisions in most cases.

    /*
     * example_mutex.c
     */
    #include <linux/module.h>
    #include <linux/mutex.h>
    #include <linux/printk.h>

    static DEFINE_MUTEX(mymutex);

    static int example_mutex_init(void)
    {
        int ret;

        pr_info("example_mutex init\n");

        ret = mutex_trylock(&mymutex);
        if (ret != 0) {
            pr_info("mutex is locked\n");

            if (mutex_is_locked(&mymutex) == 0)
                pr_info("The mutex failed to lock!\n");

            mutex_unlock(&mymutex);
            pr_info("mutex is unlocked\n");
        } else
            pr_info("Failed to lock\n");

        return 0;
    }

    static void example_mutex_exit(void)
    {
        pr_info("example_mutex exit\n");
    }

    module_init(example_mutex_init);
    module_exit(example_mutex_exit);

    MODULE_DESCRIPTION("12.1. Mutex example");
    MODULE_LICENSE("GPL");

<a name="sec:spinlock"></a>
## 12.2. Spinlocks

As the name suggests, spinlocks lock up the CPU that the code is running on, taking 100% of its resources. Because of this you should only use the spinlock mechanism around code which is likely to take no more than a few milliseconds to run and so will not noticeably slow anything down from the user's point of view.

The example here is `"irq safe"` in that if interrupts happen during the lock then they will not be forgotten and will activate when the unlock happens, using the `flags` variable to retain their state.

    /*
     * example_spinlock.c
     */
    #include <linux/init.h>
    #include <linux/module.h>
    #include <linux/printk.h>
    #include <linux/spinlock.h>

    static DEFINE_SPINLOCK(sl_static);
    static spinlock_t sl_dynamic;

    static void example_spinlock_static(void)
    {
        unsigned long flags;

        spin_lock_irqsave(&sl_static, flags);
        pr_info("Locked static spinlock\n");

        /* Do something or other safely. Because this uses 100% CPU time, this
         * code should take no more than a few milliseconds to run.
         */

        spin_unlock_irqrestore(&sl_static, flags);
        pr_info("Unlocked static spinlock\n");
    }

    static void example_spinlock_dynamic(void)
    {
        unsigned long flags;

        spin_lock_init(&sl_dynamic);
        spin_lock_irqsave(&sl_dynamic, flags);
        pr_info("Locked dynamic spinlock\n");

        /* Do something or other safely. Because this uses 100% CPU time, this
         * code should take no more than a few milliseconds to run.
         */

        spin_unlock_irqrestore(&sl_dynamic, flags);
        pr_info("Unlocked dynamic spinlock\n");
    }

    static int example_spinlock_init(void)
    {
        pr_info("example spinlock started\n");

        example_spinlock_static();
        example_spinlock_dynamic();

        return 0;
    }

    static void example_spinlock_exit(void)
    {
        pr_info("example spinlock exit\n");
    }

    module_init(example_spinlock_init);
    module_exit(example_spinlock_exit);

    MODULE_DESCRIPTION("Spinlock example");
    MODULE_LICENSE("GPL");

<a name="sec:rwlock"></a>
## 12.3. Read and write locks

12.3. Read and write locks are specialised kinds of spinlocks so that you can exclusively read from something or write to something. Like the earlier spinlocks example, the one below shows an "irq safe" situation in which if other functions were triggered from irqs which might also read and write to whatever you are concerned with then they would not disrupt the logic. As before it is a good idea to keep anything done within the lock as short as possible so that it does not hang up the system and cause users to start revolting against the tyranny of your module.

    /*
     * example_rwlock.c
     */
    #include <linux/module.h>
    #include <linux/printk.h>
    #include <linux/rwlock.h>

    static DEFINE_RWLOCK(myrwlock);

    static void example_read_lock(void)
    {
        unsigned long flags;

        read_lock_irqsave(&myrwlock, flags);
        pr_info("Read Locked\n");

        /* Read from something */

        read_unlock_irqrestore(&myrwlock, flags);
        pr_info("Read Unlocked\n");
    }

    static void example_write_lock(void)
    {
        unsigned long flags;

        write_lock_irqsave(&myrwlock, flags);
        pr_info("Write Locked\n");

        /* Write to something */

        write_unlock_irqrestore(&myrwlock, flags);
        pr_info("Write Unlocked\n");
    }

    static int example_rwlock_init(void)
    {
        pr_info("example_rwlock started\n");

        example_read_lock();
        example_write_lock();

        return 0;
    }

    static void example_rwlock_exit(void)
    {
        pr_info("example_rwlock exit\n");
    }

    module_init(example_rwlock_init);
    module_exit(example_rwlock_exit);

    MODULE_DESCRIPTION("Read/Write locks example");
    MODULE_LICENSE("GPL");

Of course, if you know for sure that there are no functions triggered by irqs which could possibly interfere with your logic then you can use the simpler `read_lock(&myrwlock)` and `read_unlock(&myrwlock)` or the corresponding write functions.

<a name="sec:atomics"></a>
## 12.4. Atomic operations

If you are doing simple arithmetic: adding, subtracting or bitwise operations, then there is another way in the multi-CPU and multi-hyperthreaded world to stop other parts of the system from messing with your mojo. By using atomic operations you can be confident that your addition, subtraction or bit flip did actually happen and was not overwritten by some other shenanigans. An example is shown below.

    /*
     * example_atomic.c
     */
    #include <linux/atomic.h>
    #include <linux/bitops.h>
    #include <linux/module.h>
    #include <linux/printk.h>

    #define BYTE_TO_BINARY_PATTERN "%c%c%c%c%c%c%c%c"
    #define BYTE_TO_BINARY(byte)                                                   \
        ((byte & 0x80) ? '1' : '0'), ((byte & 0x40) ? '1' : '0'),                  \
            ((byte & 0x20) ? '1' : '0'), ((byte & 0x10) ? '1' : '0'),              \
            ((byte & 0x08) ? '1' : '0'), ((byte & 0x04) ? '1' : '0'),              \
            ((byte & 0x02) ? '1' : '0'), ((byte & 0x01) ? '1' : '0')

    static void atomic_add_subtract(void)
    {
        atomic_t debbie;
        atomic_t chris = ATOMIC_INIT(50);

        atomic_set(&debbie, 45);

        /* subtract one */
        atomic_dec(&debbie);

        atomic_add(7, &debbie);

        /* add one */
        atomic_inc(&debbie);

        pr_info("chris: %d, debbie: %d\n", atomic_read(&chris),
                atomic_read(&debbie));
    }

    static void atomic_bitwise(void)
    {
        unsigned long word = 0;

        pr_info("Bits 0: " BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(word));
        set_bit(3, &word);
        set_bit(5, &word);
        pr_info("Bits 1: " BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(word));
        clear_bit(5, &word);
        pr_info("Bits 2: " BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(word));
        change_bit(3, &word);

        pr_info("Bits 3: " BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(word));
        if (test_and_set_bit(3, &word))
            pr_info("wrong\n");
        pr_info("Bits 4: " BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(word));

        word = 255;
        pr_info("Bits 5: " BYTE_TO_BINARY_PATTERN, BYTE_TO_BINARY(word));
    }

    static int example_atomic_init(void)
    {
        pr_info("example_atomic started\n");

        atomic_add_subtract();
        atomic_bitwise();

        return 0;
    }

    static void example_atomic_exit(void)
    {
        pr_info("example_atomic exit\n");
    }

    module_init(example_atomic_init);
    module_exit(example_atomic_exit);

    MODULE_DESCRIPTION("12.4. Atomic operations example");
    MODULE_LICENSE("GPL");

Before the C11 standard adopts the built-in atomic types, the kernel already provided a small set of atomic types by using a bunch of tricky architecture-specific codes. Implementing the atomic types by C11 atomics may allow the kernel to throw away the architecture-specific codes and letting the kernel code be more friendly to the people who understand the standard. But there are some problems, such as the memory model of the kernel doesn't match the model formed by the C11 atomics. For further details, see:

-   [kernel documentation of atomic types](https://www.kernel.org/doc/Documentation/atomic_t.txt)

-   [Time to move to C11 atomics?](https://lwn.net/Articles/691128/)

-   [Atomic usage patterns in the kernel](https://lwn.net/Articles/698315/)
