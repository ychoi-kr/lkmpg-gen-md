19. Optimizations

<a name="sec:likely_unlikely"></a>
## 19.1. Likely and Unlikely conditions

Sometimes you might want your code to run as quickly as possible, especially if it is handling an interrupt or doing something which might cause noticeable latency. If your code contains boolean conditions and if you know that the conditions are almost always likely to evaluate as either `true` or `false`, then you can allow the compiler to optimize for this using the `likely` and `unlikely` macros. For example, when allocating memory you are almost always expecting this to succeed.

    bvl = bvec_alloc(gfp_mask, nr_iovecs, &idx);
    if (unlikely(!bvl)) {
        mempool_free(bio, bio_pool);
        bio = NULL;
        goto out;
    }

When the `unlikely` macro is used, the compiler alters its machine instruction output, so that it continues along the false branch and only jumps if the condition is true. That avoids flushing the processor pipeline. The opposite happens if you use the `likely` macro.

<a name="sec:static_keys"></a>
## 19.2. Static keys

19.2. Static keys allow us to enable or disable kernel code paths based on the runtime state of key. Its APIs have been available since 2010 (most architectures are already supported), use self-modifying code to eliminate the overhead of cache and branch prediction. The most typical use case of static keys is for performance-sensitive kernel code, such as tracepoints, context switching, networking, etc. These hot paths of the kernel often contain branches and can be optimized easily using this technique. Before we can use static keys in the kernel, we need to make sure that gcc supports `asm goto` inline assembly, and the following kernel configurations are set:

    CONFIG_JUMP_LABEL=y
    CONFIG_HAVE_ARCH_JUMP_LABEL=y
    CONFIG_HAVE_ARCH_JUMP_LABEL_RELATIVE=y

To declare a static key, we need to define a global variable using the `DEFINE_STATIC_KEY_FALSE` or `DEFINE_STATIC_KEY_TRUE` macro defined in [include/linux/jump_label.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/jump_label.h). This macro initializes the key with the given initial value, which is either false or true, respectively. For example, to declare a static key with an initial value of false, we can use the following code:

    DEFINE_STATIC_KEY_FALSE(fkey);

Once the static key has been declared, we need to add branching code to the module that uses the static key. For example, the code includes a fastpath, where a no-op instruction will be generated at compile time as the key is initialized to false and the branch is unlikely to be taken.

    pr_info("fastpath 1\n");
    if (static_branch_unlikely(&fkey))
        pr_alert("do unlikely thing\n");
    pr_info("fastpath 2\n");

If the key is enabled at runtime by calling `static_branch_enable(&fkey)`, the fastpath will be patched with an unconditional jump instruction to the slowpath code `pr_alert`, so the branch will always be taken until the key is disabled again.

The following kernel module derived from `6.5. chardev.c`, demostrates how the static key works.

    /*
     * static_key.c
     */

    #include <linux/atomic.h>
    #include <linux/device.h>
    #include <linux/fs.h>
    #include <linux/kernel.h> /* for sprintf() */
    #include <linux/module.h>
    #include <linux/printk.h>
    #include <linux/types.h>
    #include <linux/uaccess.h> /* for get_user and put_user */

    #include <asm/errno.h>

    static int device_open(struct inode *inode, struct file *file);
    static int device_release(struct inode *inode, struct file *file);
    static ssize_t device_read(struct file *file, char __user *buf, size_t count,
                               loff_t *ppos);
    static ssize_t device_write(struct file *file, const char __user *buf,
                                size_t count, loff_t *ppos);

    #define SUCCESS 0
    #define DEVICE_NAME "key_state"
    #define BUF_LEN 10

    static int major;

    enum {
        CDEV_NOT_USED = 0,
        CDEV_EXCLUSIVE_OPEN = 1,
    };

    static atomic_t already_open = ATOMIC_INIT(CDEV_NOT_USED);

    static char msg[BUF_LEN + 1];

    static struct class *cls;

    static DEFINE_STATIC_KEY_FALSE(fkey);

    static struct file_operations chardev_fops = {
        .owner = THIS_MODULE,
        .open = device_open,
        .release = device_release,
        .read = device_read,
        .write = device_write,
    };

    static int __init chardev_init(void)
    {
        major = register_chrdev(0, DEVICE_NAME, &chardev_fops);
        if (major < 0) {
            pr_alert("Registering char device failed with %d\n", major);
            return major;
        }

        pr_info("I was assigned major number %d\n", major);

        cls = class_create(THIS_MODULE, DEVICE_NAME);

        device_create(cls, NULL, MKDEV(major, 0), NULL, DEVICE_NAME);

        pr_info("Device created on /dev/%s\n", DEVICE_NAME);

        return SUCCESS;
    }

    static void __exit chardev_exit(void)
    {
        device_destroy(cls, MKDEV(major, 0));
        class_destroy(cls);

        /* Unregister the device */
        unregister_chrdev(major, DEVICE_NAME);
    }

    /* Methods */

    /**
     * Called when a process tried to open the device file, like
     * cat /dev/key_state
     */
    static int device_open(struct inode *inode, struct file *file)
    {
        if (atomic_cmpxchg(&already_open, CDEV_NOT_USED, CDEV_EXCLUSIVE_OPEN))
            return -EBUSY;

        sprintf(msg, static_key_enabled(&fkey) ? "enabled\n" : "disabled\n");

        pr_info("fastpath 1\n");
        if (static_branch_unlikely(&fkey))
            pr_alert("do unlikely thing\n");
        pr_info("fastpath 2\n");

        try_module_get(THIS_MODULE);

        return SUCCESS;
    }

    /**
     * Called when a process closes the device file
     */
    static int device_release(struct inode *inode, struct file *file)
    {
        /* We are now ready for our next caller. */
        atomic_set(&already_open, CDEV_NOT_USED);

        /**
         * Decrement the usage count, or else once you opened the file, you will
         * never get rid of the module.
         */
        module_put(THIS_MODULE);

        return SUCCESS;
    }

    /**
     * Called when a process, which already opened the dev file, attempts to
     * read from it.
     */
    static ssize_t device_read(struct file *filp, /* see include/linux/fs.h */
                               char __user *buffer, /* buffer to fill with data */
                               size_t length, /* length of the buffer */
                               loff_t *offset)
    {
        /* Number of the bytes actually written to the buffer */
        int bytes_read = 0;
        const char *msg_ptr = msg;

        if (!*(msg_ptr + *offset)) { /* We are at the end of the message */
            *offset = 0; /* reset the offset */
            return 0; /* signify end of file */
        }

        msg_ptr += *offset;

        /* Actually put the date into the buffer */
        while (length && *msg_ptr) {
            /**
             * The buffer is in the user data segment, not the kernel
             * segment so "*" assignment won't work. We have to use
             * put_user which copies data from the kernel data segment to
             * the user data segment.
             */
            put_user(*(msg_ptr++), buffer++);
            length--;
            bytes_read++;
        }

        *offset += bytes_read;

        /* Most read functions return the number of bytes put into the buffer. */
        return bytes_read;
    }

    /* Called when a process writes to dev file; echo "enable" > /dev/key_state */
    static ssize_t device_write(struct file *filp, const char __user *buffer,
                                size_t length, loff_t *offset)
    {
        char command[10];

        if (length > 10) {
            pr_err("command exceeded 10 char\n");
            return -EINVAL;
        }

        if (copy_from_user(command, buffer, length))
            return -EFAULT;

        if (strncmp(command, "enable", strlen("enable")) == 0)
            static_branch_enable(&fkey);
        else if (strncmp(command, "disable", strlen("disable")) == 0)
            static_branch_disable(&fkey);
        else {
            pr_err("Invalid command: %s\n", command);
            return -EINVAL;
        }

        /* Again, return the number of input characters used. */
        return length;
    }

    module_init(chardev_init);
    module_exit(chardev_exit);

    MODULE_LICENSE("GPL");

To check the state of the static key, we can use the `/dev/key_state` interface.

    cat /dev/key_state

This will display the current state of the key, which is disabled by default.

To change the state of the static key, we can perform a write operation on the file:

    echo enable > /dev/key_state

This will enable the static key, causing the code path to switch from the fastpath to the slowpath.

In some cases, the key is enabled or disabled at initialization and never changed, we can declare a static key as read-only, which means that it can only be toggled in the module init function. To declare a read-only static key, we can use the `DEFINE_STATIC_KEY_FALSE_RO` or `DEFINE_STATIC_KEY_TRUE_RO` macro instead. Attempts to change the key at runtime will result in a page fault. For more information, see [19.2. Static keys](https://www.kernel.org/doc/Documentation/static-keys.txt)
