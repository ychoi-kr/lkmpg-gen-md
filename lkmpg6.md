6. Character Device drivers

<a name="sec:file_operations"></a>

## 6.1. The file_operations Structure

The `file_operations` structure is defined in [include/linux/fs.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/fs.h), and holds pointers to functions defined by the driver that perform various operations on the device. Each field of the structure corresponds to the address of some function defined by the driver to handle a requested operation.

For example, every character driver needs to define a function that reads from the device. The `file_operations` structure holds the address of the module's function that performs that operation. Here is what the definition looks like for kernel 5.4:

    struct file_operations {
        struct module *owner;
        loff_t (*llseek) (struct file *, loff_t, int);
        ssize_t (*read) (struct file *, char __user *, size_t, loff_t *);
        ssize_t (*write) (struct file *, const char __user *, size_t, loff_t *);
        ssize_t (*read_iter) (struct kiocb *, struct iov_iter *);
        ssize_t (*write_iter) (struct kiocb *, struct iov_iter *);
        int (*iopoll)(struct kiocb *kiocb, bool spin);
        int (*iterate) (struct file *, struct dir_context *);
        int (*iterate_shared) (struct file *, struct dir_context *);
        __poll_t (*poll) (struct file *, struct poll_table_struct *);
        long (*unlocked_ioctl) (struct file *, unsigned int, unsigned long);
        long (*compat_ioctl) (struct file *, unsigned int, unsigned long);
        int (*mmap) (struct file *, struct vm_area_struct *);
        unsigned long mmap_supported_flags;
        int (*open) (struct inode *, struct file *);
        int (*flush) (struct file *, fl_owner_t id);
        int (*release) (struct inode *, struct file *);
        int (*fsync) (struct file *, loff_t, loff_t, int datasync);
        int (*fasync) (int, struct file *, int);
        int (*lock) (struct file *, int, struct file_lock *);
        ssize_t (*sendpage) (struct file *, struct page *, int, size_t, loff_t *, int);
        unsigned long (*get_unmapped_area)(struct file *, unsigned long, unsigned long, unsigned long, unsigned long);
        int (*check_flags)(int);
        int (*flock) (struct file *, int, struct file_lock *);
        ssize_t (*splice_write)(struct pipe_inode_info *, struct file *, loff_t *, size_t, unsigned int);
        ssize_t (*splice_read)(struct file *, loff_t *, struct pipe_inode_info *, size_t, unsigned int);
        int (*setlease)(struct file *, long, struct file_lock **, void **);
        long (*fallocate)(struct file *file, int mode, loff_t offset,
            loff_t len);
        void (*show_fdinfo)(struct seq_file *m, struct file *f);
        ssize_t (*copy_file_range)(struct file *, loff_t, struct file *,
            loff_t, size_t, unsigned int);
        loff_t (*remap_file_range)(struct file *file_in, loff_t pos_in,
                 struct file *file_out, loff_t pos_out,
                 loff_t len, unsigned int remap_flags);
        int (*fadvise)(struct file *, loff_t, loff_t, int);
    } __randomize_layout;

Some operations are not implemented by a driver. For example, a driver that handles a video card will not need to read from a directory structure. The corresponding entries in the `file_operations` structure should be set to `NULL`.

There is a gcc extension that makes assigning to this structure more convenient. You will see it in modern drivers, and may catch you by surprise. This is what the new way of assigning to the structure looks like:

    struct file_operations fops = {
        read: device_read,
        write: device_write,
        open: device_open,
        release: device_release
    };

However, there is also a C99 way of assigning to elements of a structure, [designated initializers](https://gcc.gnu.org/onlinedocs/gcc/Designated-Inits.html), and this is definitely preferred over using the GNU extension. You should use this syntax in case someone wants to port your driver. It will help with compatibility:

    struct file_operations fops = {
        .read = device_read,
        .write = device_write,
        .open = device_open,
        .release = device_release
    };

The meaning is clear, and you should be aware that any member of the structure which you do not explicitly assign will be initialized to `NULL` by gcc.

An instance of `struct file_operations` containing pointers to functions that are used to implement `read`, `write`, `open`, ... system calls is commonly named `fops`.

Since Linux v3.14, the read, write and seek operations are guaranteed for thread-safe by using the `f_pos` specific lock, which makes the file position update to become the mutual exclusion. So, we can safely implement those operations without unnecessary locking.

Additionally, since Linux v5.6, the `proc_ops` structure was introduced to replace the use of the `file_operations` structure when registering proc handlers. See more information in the [7.1](https://wikidocs.net/196798#sec:proc_ops) section.

<a name="sec:file_struct"></a>

## 6.2. The file structure

Each device is represented in the kernel by a file structure, which is defined in [include/linux/fs.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/fs.h). Be aware that a file is a kernel level structure and never appears in a user space program. It is not the same thing as a `FILE`, which is defined by glibc and would never appear in a kernel space function. Also, its name is a bit misleading; it represents an abstract open 'file', not a file on a disk, which is represented by a structure named `inode`.

An instance of struct file is commonly named `filp`. You'll also see it referred to as a struct file object. Resist the temptation.

Go ahead and look at the definition of file. Most of the entries you see, like struct dentry are not used by device drivers, and you can ignore them. This is because drivers do not fill file directly; they only use structures contained in file which are created elsewhere.

<a name="sec:register_device"></a>

## 6.3. Registering A Device

As discussed earlier, char devices are accessed through device files, usually located in `/dev`. This is by convention. When writing a driver, it is OK to put the device file in your current directory. Just make sure you place it in `/dev` for a production driver. The major number tells you which driver handles which device file. The minor number is used only by the driver itself to differentiate which device it is operating on, just in case the driver handles more than one device.

Adding a driver to your system means registering it with the kernel. This is synonymous with assigning it a major number during the module's initialization. You do this by using the `register_chrdev` function, defined by [include/linux/fs.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/fs.h).

    int register_chrdev(unsigned int major, const char *name, struct file_operations *fops);

Where unsigned int major is the major number you want to request, `const char *name` is the name of the device as it will appear in `/proc/devices` and `struct file_operations *fops` is a pointer to the `file_operations` table for your driver. A negative return value means the registration failed. Note that we didn't pass the minor number to `register_chrdev`. That is because the kernel doesn't care about the minor number; only our driver uses it.

Now the question is, how do you get a major number without hijacking one that's already in use? The easiest way would be to look through [Documentation/admin-guide/devices.txt](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/Documentation/admin-guide/devices.txt) and pick an unused one. That is a bad way of doing things because you will never be sure if the number you picked will be assigned later. The answer is that you can ask the kernel to assign you a dynamic major number.

If you pass a major number of 0 to `register_chrdev`, the return value will be the dynamically allocated major number. The downside is that you can not make a device file in advance, since you do not know what the major number will be. There are a couple of ways to do this. First, the driver itself can print the newly assigned number and we can make the device file by hand. Second, the newly registered device will have an entry in `/proc/devices`, and we can either make the device file by hand or write a shell script to read the file in and make the device file. The third method is that we can have our driver make the device file using the `device_create` function after a successful registration and `device_destroy` during the call to `cleanup_module`.

However, `register_chrdev()` would occupy a range of minor numbers associated with the given major. The recommended way to reduce waste for char device registration is using cdev interface.

The newer interface completes the char device registration in two distinct steps. First, we should register a range of device numbers, which can be completed with `register_chrdev_region` or `alloc_chrdev_region`.

    int register_chrdev_region(dev_t from, unsigned count, const char *name);
    int alloc_chrdev_region(dev_t *dev, unsigned baseminor, unsigned count, const char *name);

The choice between two different functions depends on whether you know the major numbers for your device. Using `register_chrdev_region` if you know the device major number and `alloc_chrdev_region` if you would like to allocate a dynamicly-allocated major number.

Second, we should initialize the data structure `struct cdev` for our char device and associate it with the device numbers. To initialize the `struct cdev`, we can achieve by the similar sequence of the following codes.

    struct cdev *my_dev = cdev_alloc();
    my_cdev->ops = &my_fops;

However, the common usage pattern will embed the `struct cdev` within a device-specific structure of your own. In this case, we'll need `cdev_init` for the initialization.

    void cdev_init(struct cdev *cdev, const struct file_operations *fops);

Once we finish the initialization, we can add the char device to the system by using the `cdev_add`.

    int cdev_add(struct cdev *p, dev_t dev, unsigned count);

To find a example using the interface, you can see `ioctl.c` described in section [9](https://wikidocs.net/196800).

<a name="sec:unregister_device"></a>

## 6.4. Unregistering A Device

We can not allow the kernel module to be `rmmod`'ed whenever root feels like it. If the device file is opened by a process and then we remove the kernel module, using the file would cause a call to the memory location where the appropriate function (read/write) used to be. If we are lucky, no other code was loaded there, and we'll get an ugly error message. If we are unlucky, another kernel module was loaded into the same location, which means a jump into the middle of another function within the kernel. The results of this would be impossible to predict, but they can not be very positive.

Normally, when you do not want to allow something, you return an error code (a negative number) from the function which is supposed to do it. With `cleanup_module` that's impossible because it is a void function. However, there is a counter which keeps track of how many processes are using your module. You can see what its value is by looking at the 3rd field with the command `cat /proc/modules` or `sudo lsmod`. If this number isn't zero, `rmmod` will fail. Note that you do not have to check the counter within `cleanup_module` because the check will be performed for you by the system call `sys_delete_module`, defined in [include/linux/syscalls.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/syscalls.h). You should not use this counter directly, but there are functions defined in [include/linux/module.h](https://git.kernel.org/pub/scm/linux/kernel/git/stable/linux.git/tree/include/linux/module.h) which let you increase, decrease and display this counter:

-   `try_module_get(THIS_MODULE)`: Increment the reference count of current module.

-   `module_put(THIS_MODULE)`: Decrement the reference count of current module.

-   `module_refcount(THIS_MODULE)`: Return the value of reference count of current module.

It is important to keep the counter accurate; if you ever do lose track of the correct usage count, you will never be able to unload the module; it's now reboot time, boys and girls. This is bound to happen to you sooner or later during a module's development.

<a name="sec:chardev_c"></a>

## 6.5. chardev.c

The next code sample creates a char driver named `chardev`. You can dump its device file.

    cat /proc/devices

(or open the file with a program) and the driver will put the number of times the device file has been read from into the file. We do not support writing to the file (like `echo "hi" > /dev/hello`), but catch these attempts and tell the user that the operation is not supported. Don't worry if you don't see what we do with the data we read into the buffer; we don't do much with it. We simply read in the data and print a message acknowledging that we received it.

In the multiple-threaded environment, without any protection, concurrent access to the same memory may lead to the race condition, and will not preserve the performance. In the kernel module, this problem may happen due to multiple instances accessing the shared resources. Therefore, a solution is to enforce the exclusive access. We use atomic Compare-And-Swap (CAS) to maintain the states, `CDEV_NOT_USED` and `CDEV_EXCLUSIVE_OPEN`, to determine whether the file is currently opened by someone or not. CAS compares the contents of a memory location with the expected value and, only if they are the same, modifies the contents of that memory location to the desired value. See more concurrency details in the [12](https://wikidocs.net/196804) section.

    /*
     * 6.5. chardev.c: Creates a read-only char device that says how many times
     * you have read from the dev file
     */

    #include <linux/atomic.h>
    #include <linux/cdev.h>
    #include <linux/delay.h>
    #include <linux/device.h>
    #include <linux/fs.h>
    #include <linux/init.h>
    #include <linux/kernel.h> /* for sprintf() */
    #include <linux/module.h>
    #include <linux/printk.h>
    #include <linux/types.h>
    #include <linux/uaccess.h> /* for get_user and put_user */

    #include <asm/errno.h>

    /*  Prototypes - this would normally go in a .h file */
    static int device_open(struct inode *, struct file *);
    static int device_release(struct inode *, struct file *);
    static ssize_t device_read(struct file *, char __user *, size_t, loff_t *);
    static ssize_t device_write(struct file *, const char __user *, size_t,
                                loff_t *);

    #define SUCCESS 0
    #define DEVICE_NAME "chardev" /* Dev name as it appears in /proc/devices   */
    #define BUF_LEN 80 /* Max length of the message from the device */

    /* Global variables are declared as static, so are global within the file. */

    static int major; /* major number assigned to our device driver */

    enum {
        CDEV_NOT_USED = 0,
        CDEV_EXCLUSIVE_OPEN = 1,
    };

    /* Is device open? Used to prevent multiple access to device */
    static atomic_t already_open = ATOMIC_INIT(CDEV_NOT_USED);

    static char msg[BUF_LEN + 1]; /* The msg the device will give when asked */

    static struct class *cls;

    static struct file_operations chardev_fops = {
        .read = device_read,
        .write = device_write,
        .open = device_open,
        .release = device_release,
    };

    static int __init chardev_init(void)
    {
        major = register_chrdev(0, DEVICE_NAME, &chardev_fops);

        if (major < 0) {
            pr_alert("Registering char device failed with %d\n", major);
            return major;
        }

        pr_info("I was assigned major number %d.\n", major);

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

    /* Called when a process tries to open the device file, like
     * "sudo cat /dev/chardev"
     */
    static int device_open(struct inode *inode, struct file *file)
    {
        static int counter = 0;

        if (atomic_cmpxchg(&already_open, CDEV_NOT_USED, CDEV_EXCLUSIVE_OPEN))
            return -EBUSY;

        sprintf(msg, "I already told you %d times Hello world!\n", counter++);
        try_module_get(THIS_MODULE);

        return SUCCESS;
    }

    /* Called when a process closes the device file. */
    static int device_release(struct inode *inode, struct file *file)
    {
        /* We're now ready for our next caller */
        atomic_set(&already_open, CDEV_NOT_USED);

        /* Decrement the usage count, or else once you opened the file, you will
         * never get rid of the module.
         */
        module_put(THIS_MODULE);

        return SUCCESS;
    }

    /* Called when a process, which already opened the dev file, attempts to
     * read from it.
     */
    static ssize_t device_read(struct file *filp, /* see include/linux/fs.h   */
                               char __user *buffer, /* buffer to fill with data */
                               size_t length, /* length of the buffer     */
                               loff_t *offset)
    {
        /* Number of bytes actually written to the buffer */
        int bytes_read = 0;
        const char *msg_ptr = msg;

        if (!*(msg_ptr + *offset)) { /* we are at the end of message */
            *offset = 0; /* reset the offset */
            return 0; /* signify end of file */
        }

        msg_ptr += *offset;

        /* Actually put the data into the buffer */
        while (length && *msg_ptr) {
            /* The buffer is in the user data segment, not the kernel
             * segment so "*" assignment won't work.  We have to use
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

    /* Called when a process writes to dev file: echo "hi" > /dev/hello */
    static ssize_t device_write(struct file *filp, const char __user *buff,
                                size_t len, loff_t *off)
    {
        pr_alert("Sorry, this operation is not supported.\n");
        return -EINVAL;
    }

    module_init(chardev_init);
    module_exit(chardev_exit);

    MODULE_LICENSE("GPL");

<a name="sec:modules_for_versions"></a>

## 6.6. Writing Modules for Multiple Kernel Versions

The system calls, which are the major interface the kernel shows to the processes, generally stay the same across versions. A new system call may be added, but usually the old ones will behave exactly like they used to. This is necessary for backward compatibility -- a new kernel version is not supposed to break regular processes. In most cases, the device files will also remain the same. On the other hand, the internal interfaces within the kernel can and do change between versions.

There are differences between different kernel versions, and if you want to support multiple kernel versions, you will find yourself having to code conditional compilation directives. The way to do this to compare the macro `LINUX_VERSION_CODE` to the macro `KERNEL_VERSION`. In version `a.b.c` of the kernel, the value of this macro would be $2^{16}a+2^{8}b+c$.
